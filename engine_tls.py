"""
.engine TLS helpers.

- A private certificate authority (CA) is created on first use.
- A certificate is issued for each site name on demand (SNI), so thousands of
  names do not need one giant certificate.
- A certificate placed in  tls/custom/<host>.crt  and  tls/custom/<host>.key
  is used for exactly that host name instead of a generated one.
- Browsers and customer servers must trust  tls/ca.crt  once (downloadable
  from the dashboard) to see a padlock instead of a warning.
"""
import os
import ssl
import json
import socket
import hashlib
import threading
import datetime
import ipaddress
import http.client
from urllib.parse import urlparse

try:
    from cryptography import x509
    from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    HAVE_CRYPTO = True
except Exception:  # cryptography not installed
    HAVE_CRYPTO = False


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


class TLSManager:
    def __init__(self, data_dir, log=print):
        self.log = log
        self.dir = os.path.join(data_dir, "tls")
        self.available = HAVE_CRYPTO
        self.lock = threading.Lock()
        self.ctx_cache = {}
        self.ca_key = None
        self.ca_cert = None
        if self.available:
            os.makedirs(os.path.join(self.dir, "certs"), exist_ok=True)
            os.makedirs(os.path.join(self.dir, "custom"), exist_ok=True)
            self._ensure_ca()

    # ------------------------------------------------------------ CA
    def _ensure_ca(self):
        key_path = os.path.join(self.dir, "ca.key")
        crt_path = os.path.join(self.dir, "ca.crt")
        if os.path.exists(key_path) and os.path.exists(crt_path):
            with open(key_path, "rb") as f:
                self.ca_key = serialization.load_pem_private_key(f.read(), None)
            with open(crt_path, "rb") as f:
                self.ca_cert = x509.load_pem_x509_certificate(f.read())
            return
        key = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, ".engine"),
                          x509.NameAttribute(NameOID.COMMON_NAME, ".engine Private CA")])
        cert = (x509.CertificateBuilder()
                .subject_name(name).issuer_name(name)
                .public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(_now() - datetime.timedelta(days=1))
                .not_valid_after(_now() + datetime.timedelta(days=3650))
                .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
                .add_extension(x509.KeyUsage(
                    digital_signature=True, key_cert_sign=True, crl_sign=True,
                    content_commitment=False, key_encipherment=False, data_encipherment=False,
                    key_agreement=False, encipher_only=False, decipher_only=False), critical=True)
                .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
                               critical=False)
                .sign(key, hashes.SHA256()))
        with open(key_path, "wb") as f:
            f.write(key.private_bytes(serialization.Encoding.PEM,
                                      serialization.PrivateFormat.PKCS8,
                                      serialization.NoEncryption()))
        try:
            os.chmod(key_path, 0o600)
        except OSError:
            pass
        with open(crt_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        self.ca_key, self.ca_cert = key, cert
        self.log("Created the private certificate authority (tls/ca.crt).")

    def ca_pem(self):
        if not self.available:
            return b""
        return self.ca_cert.public_bytes(serialization.Encoding.PEM)

    def ca_fingerprint(self):
        if not self.available:
            return ""
        der = self.ca_cert.public_bytes(serialization.Encoding.DER)
        return hashlib.sha256(der).hexdigest()

    # ------------------------------------------------- leaf certificates
    def _issue(self, names, ips):
        """Returns (cert_path, key_path) for these names/IPs, creating them if needed."""
        stem = hashlib.sha1("|".join(sorted(names) + sorted(ips)).encode()).hexdigest()[:20]
        crt = os.path.join(self.dir, "certs", stem + ".crt")
        key_path = os.path.join(self.dir, "certs", stem + ".key")
        if os.path.exists(crt) and os.path.exists(key_path):
            try:
                with open(crt, "rb") as f:
                    c = x509.load_pem_x509_certificate(f.read())
                if c.not_valid_after_utc > _now() + datetime.timedelta(days=14):
                    return crt, key_path
            except Exception:
                pass
        key = ec.generate_private_key(ec.SECP256R1())
        san = [x509.DNSName(n) for n in names] + [x509.IPAddress(ipaddress.ip_address(i)) for i in ips]
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, (names or ips)[0])])
        cert = (x509.CertificateBuilder()
                .subject_name(subject).issuer_name(self.ca_cert.subject)
                .public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(_now() - datetime.timedelta(days=1))
                .not_valid_after(_now() + datetime.timedelta(days=397))
                .add_extension(x509.SubjectAlternativeName(san), critical=False)
                .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                .add_extension(x509.KeyUsage(
                    digital_signature=True, key_cert_sign=False, crl_sign=False,
                    content_commitment=False, key_encipherment=False, data_encipherment=False,
                    key_agreement=False, encipher_only=False, decipher_only=False), critical=True)
                .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
                               critical=False)
                .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(
                    self.ca_key.public_key()), critical=False)
                .sign(self.ca_key, hashes.SHA256()))
        with open(key_path, "wb") as f:
            f.write(key.private_bytes(serialization.Encoding.PEM,
                                      serialization.PrivateFormat.PKCS8,
                                      serialization.NoEncryption()))
        try:
            os.chmod(key_path, 0o600)
        except OSError:
            pass
        with open(crt, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        return crt, key_path

    def _context(self, cert_path, key_path):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(cert_path, key_path)
        return ctx

    def context_for(self, names, ips=()):
        """Server context for these names; created once and cached."""
        names, ips = list(names), list(ips)
        cache_key = (tuple(sorted(names)), tuple(sorted(ips)))
        with self.lock:
            ctx = self.ctx_cache.get(cache_key)
            if ctx is None:
                custom = None
                if names:
                    c = os.path.join(self.dir, "custom", names[0] + ".crt")
                    k = os.path.join(self.dir, "custom", names[0] + ".key")
                    if os.path.exists(c) and os.path.exists(k):
                        custom = (c, k)
                crt, key = custom or self._issue(names, ips)
                ctx = self._context(crt, key)
                if len(self.ctx_cache) > 5000:
                    self.ctx_cache.clear()
                self.ctx_cache[cache_key] = ctx
            return ctx

    def server_context(self, default_names, default_ips, is_known):
        """Context for a listener: serves a default certificate and switches to a
        per-name certificate (SNI) when the visitor asks for a registered name."""
        owner = self
        listener = self._context(*self._issue(list(default_names), list(default_ips)))

        def sni(sslsock, server_name, _ctx):
            try:
                if server_name and is_known(server_name):
                    sslsock.context = owner.context_for([server_name.lower()])
            except Exception:
                pass
        listener.sni_callback = sni
        return listener


# ---------------------------------------------------------------- client
def client_context(ca_pem=None, verify=True):
    if not verify:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    if ca_pem:
        return ssl.create_default_context(cadata=ca_pem.decode() if isinstance(ca_pem, bytes) else ca_pem)
    return ssl.create_default_context()


def secure_request(url, method="GET", headers=None, body=None, ca_pem=None,
                   verify=True, timeout=8):
    """HTTP(S) request returning (status, bytes). With ca_pem the server must
    present a certificate issued by that CA; with verify=False it only encrypts."""
    u = urlparse(url)
    path = (u.path or "/") + ("?" + u.query if u.query else "")
    if u.scheme == "https":
        conn = http.client.HTTPSConnection(u.hostname, u.port or 443, timeout=timeout,
                                           context=client_context(ca_pem, verify))
    else:
        conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=timeout)
    try:
        conn.request(method, path, body=body, headers=headers or {})
        r = conn.getresponse()
        return r.status, r.read()
    finally:
        conn.close()

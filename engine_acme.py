"""
.engine automatic certificates for real domains (ACME, RFC 8555), for example
Let's Encrypt. Uses the HTTP-01 challenge: the certificate authority fetches a
token from  http://<your-domain>/.well-known/acme-challenge/<token>  on port 80,
which the engine answers by itself. Certificates renew automatically.

Needs:  the domain's DNS pointing at this machine, ports 80 and 443 reachable
from the internet, the engine started with permission to use ports 80/443,
and the 'cryptography' package.
"""
import os
import re
import json
import time
import base64
import hashlib
import threading
import http.client
from urllib.parse import urlparse

try:
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    HAVE_CRYPTO = True
except Exception:
    HAVE_CRYPTO = False

LE_PRODUCTION = "https://acme-v02.api.letsencrypt.org/directory"
LE_STAGING = "https://acme-staging-v02.api.letsencrypt.org/directory"
RENEW_BEFORE_DAYS = 30
RETRY_AFTER_ERROR = 6 * 3600
HOST_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
PRIVATE_SUFFIXES = (".engine", ".localhost", ".local", ".internal", ".lan", ".home", ".test")


class AcmeError(Exception):
    pass


def valid_public_host(host):
    host = (host or "").strip().lower()
    return bool(HOST_RE.match(host)) and not host.endswith(PRIVATE_SUFFIXES)


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class AcmeClient:
    def __init__(self, directory_url, account_key_path, email="", publish=None, unpublish=None,
                 log=print, poll_interval=1.0, timeout=90):
        if not HAVE_CRYPTO:
            raise AcmeError("Certificates need the 'cryptography' package (pip install cryptography).")
        self.directory_url = directory_url
        self.email = email
        self.publish = publish or (lambda token, keyauth: None)
        self.unpublish = unpublish or (lambda token: None)
        self.log = log
        self.poll = poll_interval
        self.timeout = timeout
        self.nonce = None
        self.kid = None
        self.directory = None
        self.key = self._load_key(account_key_path)
        n = self.key.public_key().public_numbers()
        self.jwk = {"crv": "P-256", "kty": "EC",
                    "x": _b64(n.x.to_bytes(32, "big")), "y": _b64(n.y.to_bytes(32, "big"))}
        self.thumbprint = _b64(hashlib.sha256(
            json.dumps(self.jwk, sort_keys=True, separators=(",", ":")).encode()).digest())

    @staticmethod
    def _load_key(path):
        if os.path.exists(path):
            with open(path, "rb") as f:
                return serialization.load_pem_private_key(f.read(), None)
        key = ec.generate_private_key(ec.SECP256R1())
        with open(path, "wb") as f:
            f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                      serialization.NoEncryption()))
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return key

    # ---------------------------------------------------------------- http
    def _http(self, method, url, headers=None, body=None):
        u = urlparse(url)
        path = (u.path or "/") + ("?" + u.query if u.query else "")
        if u.scheme == "https":
            conn = http.client.HTTPSConnection(u.hostname, u.port or 443, timeout=30)
        else:
            conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=30)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            r = conn.getresponse()
            return r.status, {k.lower(): v for k, v in r.getheaders()}, r.read()
        finally:
            conn.close()

    def _directory(self):
        if self.directory is None:
            status, _h, data = self._http("GET", self.directory_url)
            if status != 200:
                raise AcmeError(f"Certificate authority answered {status} for its directory.")
            self.directory = json.loads(data)
        return self.directory

    def _fresh_nonce(self):
        _s, h, _d = self._http("HEAD", self._directory()["newNonce"])
        return h["replay-nonce"]

    def _post(self, url, payload, use_kid=True):
        """Signed request (JWS, ES256). payload=None means POST-as-GET."""
        for _ in range(3):
            nonce = self.nonce or self._fresh_nonce()
            protected = {"alg": "ES256", "nonce": nonce, "url": url}
            protected["kid" if (use_kid and self.kid) else "jwk"] = self.kid if (use_kid and self.kid) else self.jwk
            p64 = _b64(json.dumps(protected).encode())
            pl64 = "" if payload is None else _b64(json.dumps(payload).encode())
            der = self.key.sign(f"{p64}.{pl64}".encode(), ec.ECDSA(hashes.SHA256()))
            r, s = decode_dss_signature(der)
            body = json.dumps({"protected": p64, "payload": pl64,
                               "signature": _b64(r.to_bytes(32, "big") + s.to_bytes(32, "big"))})
            status, h, data = self._http("POST", url, {"Content-Type": "application/jose+json"},
                                         body.encode())
            self.nonce = h.get("replay-nonce")
            if status == 400 and b"badNonce" in data:
                self.nonce = None
                continue
            ctype = h.get("content-type", "")
            parsed = json.loads(data) if data and ("json" in ctype) else data
            return status, h, parsed
        raise AcmeError("The certificate authority kept rejecting the request nonce.")

    # --------------------------------------------------------------- flow
    def _account(self):
        if self.kid:
            return
        payload = {"termsOfServiceAgreed": True}
        if self.email:
            payload["contact"] = ["mailto:" + self.email]
        status, h, body = self._post(self._directory()["newAccount"], payload, use_kid=False)
        if status not in (200, 201):
            raise AcmeError(f"Account registration failed: {body}")
        self.kid = h["location"]

    def _wait(self, url, done, what):
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            status, _h, body = self._post(url, None)
            if status != 200:
                raise AcmeError(f"Checking {what} failed: {body}")
            if body.get("status") in done:
                return body
            if body.get("status") == "invalid":
                detail = ""
                for ch in body.get("challenges", []):
                    if ch.get("error"):
                        detail = ch["error"].get("detail", "")
                raise AcmeError(f"The certificate authority rejected {what}. {detail}".strip())
            time.sleep(self.poll)
        raise AcmeError(f"Timed out waiting for {what}.")

    def issue(self, hosts):
        """Returns (certificate chain PEM, private key PEM) for these host names."""
        self._account()
        d = self._directory()
        status, h, order = self._post(d["newOrder"], {"identifiers": [{"type": "dns", "value": x} for x in hosts]})
        if status not in (200, 201):
            raise AcmeError(f"Could not start the order: {order}")
        order_url = h["location"]
        for authz_url in order["authorizations"]:
            status, _h, authz = self._post(authz_url, None)
            if authz.get("status") == "valid":
                continue
            chal = next((c for c in authz["challenges"] if c["type"] == "http-01"), None)
            if chal is None:
                raise AcmeError("The certificate authority offered no HTTP challenge.")
            keyauth = f"{chal['token']}.{self.thumbprint}"
            self.publish(chal["token"], keyauth)
            try:
                status, _h, body = self._post(chal["url"], {})
                if status not in (200, 202):
                    raise AcmeError(f"Could not start validation: {body}")
                self._wait(authz_url, ("valid",), f"the domain {authz['identifier']['value']}")
            finally:
                self.unpublish(chal["token"])
        cert_key = ec.generate_private_key(ec.SECP256R1())
        csr = (x509.CertificateSigningRequestBuilder()
               .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hosts[0])]))
               .add_extension(x509.SubjectAlternativeName([x509.DNSName(x) for x in hosts]), critical=False)
               .sign(cert_key, hashes.SHA256()))
        status, _h, body = self._post(order["finalize"], {"csr": _b64(csr.public_bytes(serialization.Encoding.DER))})
        if status not in (200, 201):
            raise AcmeError(f"Finalizing the order failed: {body}")
        order = self._wait(order_url, ("valid",), "the certificate")
        status, _h, pem = self._post(order["certificate"], None)
        if status != 200 or not isinstance(pem, bytes):
            raise AcmeError("Could not download the certificate.")
        key_pem = cert_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption())
        return pem, key_pem


class AcmeManager:
    """Issues and renews a certificate for every registered real domain."""

    def __init__(self, core):
        self.core = core
        self.challenges = {}
        self.state = {}
        self.pending = set()
        self.lock = threading.Lock()
        self.running = False
        self.poll_interval = 1.0

    # ------------------------------------------------------------- files
    def _dir(self):
        return os.path.join(self.core.data_dir(), "tls")

    def cert_paths(self, host):
        base = os.path.join(self._dir(), "custom")
        return os.path.join(base, host + ".crt"), os.path.join(base, host + ".key")

    def _state_path(self):
        return os.path.join(self._dir(), "acme_state.json")

    def _load_state(self):
        try:
            with open(self._state_path(), "r") as f:
                self.state = json.load(f)
        except Exception:
            self.state = {}

    def _save_state(self):
        try:
            os.makedirs(self._dir(), exist_ok=True)
            tmp = self._state_path() + ".tmp"
            with open(tmp, "w") as f:
                json.dump(self.state, f)
            os.replace(tmp, self._state_path())
        except OSError:
            pass

    def directory_url(self):
        return LE_STAGING if self.core.settings.get("acme_staging") else LE_PRODUCTION

    def expiry(self, host):
        """When the certificate on disk expires (unix time) or None."""
        if not HAVE_CRYPTO:
            return None
        crt, _key = self.cert_paths(host)
        try:
            with open(crt, "rb") as f:
                return x509.load_pem_x509_certificate(f.read()).not_valid_after_utc.timestamp()
        except Exception:
            return None

    def status(self, host):
        exp = self.expiry(host)
        st = dict(self.state.get(host, {}))
        if host in self.pending:
            state = "pending"
        elif exp and exp > time.time():
            state = "issued"
        else:
            state = st.get("status", "none") if st.get("status") != "issued" else "none"
        return {"host": host, "state": state, "error": st.get("error", ""), "expires": exp,
                "last_try": st.get("last_try"), "staging": bool(st.get("staging"))}

    def has_certificate(self, host):
        exp = self.expiry(host)
        return bool(exp and exp > time.time())

    # ----------------------------------------------------------- issuing
    def _publish(self, token, keyauth):
        self.challenges[token] = keyauth

    def _unpublish(self, token):
        self.challenges.pop(token, None)

    def _issue_now(self, host):
        core = self.core
        try:
            if core.proxy_port != 80:
                raise AcmeError("The engine must run with permission to use port 80 "
                                "(Administrator / root) so the certificate authority can reach it.")
            os.makedirs(os.path.join(self._dir(), "custom"), exist_ok=True)
            client = AcmeClient(self.directory_url(), os.path.join(self._dir(), "acme_account.key"),
                                core.settings.get("acme_email", ""), self._publish, self._unpublish,
                                core.log, self.poll_interval)
            cert_pem, key_pem = client.issue([host])
            crt, key = self.cert_paths(host)
            with open(key, "wb") as f:
                f.write(key_pem)
            try:
                os.chmod(key, 0o600)
            except OSError:
                pass
            with open(crt, "wb") as f:
                f.write(cert_pem)
            core.tls.invalidate()
            self.state[host] = {"status": "issued", "error": "", "last_try": time.time(),
                                "staging": bool(core.settings.get("acme_staging"))}
            core.log(f"Certificate issued for {host}")
        except Exception as e:
            self.state[host] = {"status": "error", "error": str(e)[:300], "last_try": time.time()}
            core.log(f"Certificate for {host} failed: {str(e)[:120]}")
        finally:
            with self.lock:
                self.pending.discard(host)
            self._save_state()

    def request(self, host, wait=False):
        """Starts getting a certificate for host (in the background unless wait=True)."""
        if not valid_public_host(host):
            return False, "That is not a valid public domain name."
        if not HAVE_CRYPTO:
            return False, "Certificates need the 'cryptography' package."
        with self.lock:
            if host in self.pending:
                return True, "Already in progress."
            self.pending.add(host)
        if wait:
            self._issue_now(host)
        else:
            threading.Thread(target=self._issue_now, args=(host,), daemon=True).start()
        return True, "Requesting the certificate. This takes under a minute."

    # ----------------------------------------------------------- renewal
    def check_renewals(self):
        now = time.time()
        for host in self.core.domain_hosts():
            if host in self.pending:
                continue
            exp = self.expiry(host)
            if exp and exp - now > RENEW_BEFORE_DAYS * 86400:
                continue
            last = (self.state.get(host) or {}).get("last_try") or 0
            if now - last < RETRY_AFTER_ERROR:
                continue
            self.request(host)

    def _loop(self):
        while self.running:
            try:
                self.check_renewals()
            except Exception:
                pass
            for _ in range(360):  # re-check every 6 hours
                if not self.running:
                    return
                time.sleep(60)

    def start(self):
        self._load_state()
        if self.running:
            return
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self.running = False

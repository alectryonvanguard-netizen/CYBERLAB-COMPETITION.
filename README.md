🛰# > .engine

A self-hosted hosting platform. One computer (the **mother server**) hosts
websites and apps, runs an account system for customers, and watches over
customers' own **small servers**. Everything runs over encrypted HTTPS.

You register a name such as `shop`, point it at a website or an app, and it is
served at `https://shop.engine`.

---

📷## 1. The big picture

```
                         ┌─────────────────────────────────────────┐
  Visitors ─ HTTPS ────► │  MOTHER SERVER  (your PC)               │
  (browsers)             │  • hosts up to 4,600 sites and apps     │
                         │  • customer accounts, quotas, reports   │
  You (owner) ─ HTTPS ─► │  • private messages, audit log          │
  dashboard / app        │  • private certificate authority (CA)   │
                         └───────▲───────────────▲─────────────────┘
                                 │ HTTPS         │ HTTPS
          report every minute    │               │  customer signs in
                                 │               │  (browser)
                  ┌──────────────┴───┐     ┌─────┴───────────────┐
                  │ SMALL SERVER     │     │ CUSTOMER PORTAL     │
                  │ (customer's own  │     │ reports, storage,   │
                  │ machine, same    │     │ servers, messages   │
                  │ program)         │     └─────────────────────┘
                  │ hosts their site │
                  └──────────────────┘

  Your phone ──► small companion app: status, charts, open sites
```

- The **mother server** is where you manage everything. One mother server holds up
  to **4,600** sites and apps of its own.
- A **small server** is the same program, run by a customer on their own machine. It
  hosts their site and reports to the mother server once a minute: traffic, storage,
  load, uptime. In return it receives the customer's storage limit, account status
  and private messages.
- Customers see their reports in two places: on the **mother server's customer
  portal**, and on their **own small server's dashboard** (Provider tab).
- The **phone app** is a small companion. The computer does all the real work.

---

## 2. What runs where

| | Computer (mother or small server) | Phone |
|---|---|---|
| Hosts sites and apps | Yes | No |
| Starts, stops and restarts your apps | Yes | No |
| Web dashboard (full control) | Yes | Opens it in Chrome |
| Desktop window with live charts | Yes | - |
| Customer accounts and reports | Yes (mother) | - |
| CPU / RAM / GPU / disk readings | Yes | Shows the computer's |
| Open your sites | Yes | Yes |

Tested on Linux. The Windows parts (hosts file, CPU reading, auto-start script)
follow the same logic but were not run on Windows. See section 15 for exactly what
was and was not tested.

---

## 3. Files

| File | Purpose |
|---|---|
| `engine_core.py` | The engine: name lookup (DNS), HTTP and HTTPS servers, site hosting, app forwarding, protections, link to the mother server, command line |
| `engine_admin.py` | The dashboard server and its API (owner, customer and small-server access) |
| `engine_dashboard.py` | The dashboard web page (charts, activity matrix, all tabs) |
| `engine_accounts.py` | Database: customers, small servers, daily usage, storage, uptime, messages, audit log |
| `engine_tls.py` | Private certificate authority and per-site certificates |
| `engine_infra.py` | Access-key security, CPU/RAM/GPU readings, app supervisor, phone client |
| `main.py` | The app: desktop window and phone companion |
| `buildozer.spec`, `.github/workflows/main.yml` | Builds the Android app |
| `icon.png`, `presplash.png` | App icon and launch screen |
| `deploy/` | 24/7 setup for Linux (systemd) and Windows |

Upload every `.py` file together. They depend on each other.

---

## 4. Install and first start (your PC)

1. Install Python 3.9 or newer.
2. Install the extras: `pip install -r deploy/requirements-desktop.txt`
   (`cryptography` is **required for HTTPS**; `kivy` is only for the desktop window;
   `psutil` gives better CPU/RAM readings).
3. Start it as **Administrator** (Windows) or **root / with sudo** (Linux/macOS).
   Administrator rights let it use ports 80, 443 and 53 and edit the hosts file.
   Without them it still works, on ports 8080, 8443 and 5353.
4. Pick how to run it:
   - **With a window:** `python main.py`. The first time it asks you to create your
     access key.
   - **Headless server (recommended for 24/7):**
     ```
     python engine_core.py setpassword     # create the owner access key
     python engine_core.py serve           # run the engine
     ```
5. Open the dashboard: `https://localhost:9443` (or `http://localhost:9090` on the
   same computer) and sign in as **Owner** with the access key.

The owner access key needs 8+ characters with an uppercase letter, a lowercase
letter, a number and a symbol.

---

## 5. Hosting a website

A site is plain files (HTML, CSS, JavaScript, images) served by the engine itself.

- **New site:** Dashboard → Sites → register a name, leave the target blank. You get
  a starter page. Press **Edit**, paste your HTML, **Save**, reload.
- **Existing folder:** register a name and put the folder path as the target. The
  folder needs an `index.html`. Changes appear immediately.
- **Command line:**
  ```
  python engine_core.py site shop                 # new site
  python engine_core.py site shop ./my-website    # existing folder
  ```

Links inside your pages should be relative (`css/style.css`, not `/css/style.css`)
if you also want the preview link (section 7) to work.

## 6. Hosting an app

For anything that needs code running (Flask, Node, an AI service...).

- **You start the app yourself:** register a name and its port as the target
  (`8001`). The engine forwards to it. If the app is down, visitors see a clear
  "app is not running" page (502).
- **The engine starts it for you (recommended):** add a start command, for example
  `python app.py`. The engine:
  - picks a free port and gives it to your app in the `PORT` environment variable,
  - restarts the app if it crashes (it gives up after 5 crashes within 60 seconds),
  - keeps its output in a log you can read in the dashboard.

  Your app must listen on that port:
  ```python
  import os
  app.run(host="127.0.0.1", port=int(os.environ["PORT"]))
  ```
  Command line: `python engine_core.py app api "python app.py"`

Apps receive `X-Forwarded-For` (the visitor's address) and `X-Forwarded-Proto`
(`http` or `https`).

---

## 7. Names, addresses and ports

| Where you are | Address |
|---|---|
| The engine computer | `https://shop.engine` (the engine adds the name to the hosts file for up to 200 sites) |
| Another computer or phone on your network | Set that device's DNS server to the engine computer's IP. The engine answers **every** `.engine` name, so no per-site setup is needed. Needs port 53. |
| Any device, no setup | `http://<engine-ip>/_/shop/` (preview link, shown as **Open** in the dashboard) |
| The engine's index page | `http://<engine-ip>/` lists everything registered |

**Why `:8080` or `:8443` sometimes?** Browsers use port 80 (HTTP) and 443 (HTTPS)
when none is written. Only an administrator can open those. If the engine was not
started as admin/root it uses 8080 and 8443, and the address needs the port.

**`.engine` is private.** It works only on devices that use this engine for names.
It is not a public domain and nobody else can open it. Public domain names are not
supported in this version.

| Port | Use | If it cannot be used |
|---|---|---|
| 80 | HTTP sites and apps | 8080 |
| 443 | HTTPS sites and apps | 8443 |
| 53 | Name lookups for other devices | 5353 |
| 9090 | Dashboard over HTTP (this computer only once HTTPS is on) | 9091, 9092 |
| 9443 | Dashboard over HTTPS, customers' small servers, phone | 9444, 9445 |

---

## 8. HTTPS

HTTPS is on automatically when the `cryptography` package is installed.

- **Private certificate authority (CA).** On first start the engine creates its own
  CA (`tls/ca.crt` and `tls/ca.key`). It signs a certificate for each site the first
  time someone visits it over HTTPS (about 4 ms), so thousands of sites do not need
  one huge certificate. Unregistered names receive no certificate.
- **Trust the CA once on each device** so the browser shows a padlock instead of a
  warning. Download it from Dashboard → Security → "Download the CA certificate"
  (or `http://<engine-ip>:9090/ca.crt` from the engine computer).
  - **Windows:** double-click `engine-ca.crt` → Install Certificate → Local Machine →
    "Trusted Root Certification Authorities".
  - **macOS:** open it in Keychain Access → set to "Always Trust".
  - **Linux:** copy to `/usr/local/share/ca-certificates/` and run
    `sudo update-ca-certificates`. Chrome also needs it under Settings → Privacy and
    security → Manage certificates → Authorities.
  - **Android:** Settings → Security → Install a certificate → CA certificate.
  - **iPhone:** install the profile, then Settings → General → About → Certificate
    Trust Settings → turn it on.
  Install it **only on devices you control.** Anyone holding `tls/ca.key` can
  impersonate any of your sites to devices that trust the CA, so keep that file private
  and back it up somewhere safe.
- **Force HTTPS** (Dashboard → Security) redirects every HTTP visit to HTTPS.
- **HSTS** (on by default) tells browsers to use only HTTPS for these sites.
- Technical details: TLS 1.2 and 1.3 only, EC P-256 keys, SHA-256 signatures. Site
  certificates last 397 days and are re-issued automatically when they near expiry.
  The CA lasts 10 years.

---

## 9. Customers and small servers (the mother server)

### Create a customer
Dashboard → **Customers** → New customer: username, password (same strength rules),
email, **storage quota (MB)** and **maximum number of small servers**.

### Give them a small server
Dashboard → **Servers** → choose the customer, name the server → **Create join code**.
The code is shown **once**. Send it to the customer privately. (Customers can also
create their own, up to their maximum, in their portal.)

On the customer's machine (any computer running this program):
```
python engine_core.py join <code>
python engine_core.py serve
```
or paste it in the small server's dashboard → **Provider** tab. The code contains the
mother server's address, a secret token and the mother's CA certificate, so the small
server can verify it is really talking to the right mother server.

### What the small server reports (every minute)
Version, number of sites, storage used, CPU/RAM/disk, a list of sites, and the daily
request and bandwidth counts for each site. Nothing from the sites' files or visitors
is sent.

### What the customer sees
On the **mother server portal** (`https://<mother>:9443`, sign in as **Customer**) and
on their own small server's **Provider** tab:
- **Reports for the week, month and year:** requests, bandwidth, change compared with
  the previous period, top sites, uptime %, storage history.
- An **activity matrix** (a grid of the last 20 weeks, brighter = busier).
- **Storage used versus their quota.**
- Their small servers and whether each is online.
- **Private messages** from you.

### Quotas, suspension and messages
- **Quota:** when a customer goes over their storage limit, their small server blocks
  new page saves and shows a banner. Raise the limit and it works again within a minute.
- **Suspend:** suspending a customer signs them out everywhere, blocks their login,
  and their small server stops serving their sites (visitors see 503). Activate them
  again and it resumes within a minute.
- **Private messages:** Dashboard → **Messages**. Send to one customer or to everyone
  (information, warning or billing). They appear in the portal and on the customer's
  small server.

> **Important:** a small server runs on the customer's own machine. Suspension and
> quotas are enforced by the program, but a customer who changes their own copy of the
> code could bypass them. You always see their real reported usage and can end the
> relationship. Sites hosted on **your** mother server are fully under your control.

---

## 10. The dashboard

| Tab | What it does |
|---|---|
| **Overview** | CPU, memory, disk and GPU; traffic totals; charts per week/month/year; activity matrix; top sites. Switch between this server and all customers. |
| **Sites** | Register, search (50 per page), open, edit, lock with a password, start/stop apps, unbind; logs. |
| **Customers** | Create, set limits, suspend, reset password, message, delete, view their reports. |
| **Servers** | All customers' small servers: online state, load, storage; create/reset join codes. |
| **Messages** | Send private messages; see what was sent and read. |
| **Security** | HTTPS status, CA download, force HTTPS, HSTS, rate limit, connection limit, public host name, change the owner key, audit log. |
| **Provider** | For a small server: join a mother server, see its report and messages. |

Customers get their own smaller view: Overview, My servers, Messages, Account.

---

## 11. The phone companion

Install the APK, enter the computer's address (for example `192.168.1.20`) and your
access key. The phone and computer must be on the same network. You see whether the
engine is online, CPU / RAM / GPU, traffic, and each site with an **Open** button.
**Open full dashboard** opens the complete interface in Chrome.

The phone connects over HTTPS and remembers the engine's certificate the first time
(**trust on first use**). If that certificate ever changes, the phone refuses to
connect and tells you. If you expected the change (new IP address, reinstall), tap
**Forget saved trust** and connect again. It falls back to plain HTTP only if HTTPS is
not available.

---

## 12. Security: everything in place

### Encryption of data in transit
- **HTTPS (TLS 1.2 / 1.3)** for visitors, for the dashboard (port 9443), and for the
  link between small servers and the mother server.
- Small servers **verify the mother server's certificate** against the CA stored in
  their join code, including the host name. A fake mother server is rejected.
- Once HTTPS is on, the dashboard's HTTP port answers **only requests from the same
  computer**; everyone else is told to use HTTPS. The CA certificate itself (public) is
  the only thing served over HTTP.
- The phone pins the engine's certificate (section 11).

### Passwords, keys and tokens (at rest)
| Item | Protection |
|---|---|
| Owner access key | PBKDF2-HMAC-SHA256, 150,000 rounds, random 128-bit salt. Never stored in clear. |
| Customer passwords | Same as above. |
| Small-server tokens | Stored only as SHA-256 hashes. Shown once when created; "New code" revokes the old one. |
| Visitor passwords on locked sites | PBKDF2-HMAC-SHA256, 20,000 rounds, random salt. |
| Session tokens | 192-bit random, held in memory only, expire after 12 hours, and are revoked when an account is suspended or its password changes. |
| Secret files | `engine_auth.json`, `engine_mother.json`, `engine.db`, `tls/ca.key` and all site keys are set to owner-only permission (Linux/macOS). |

Password checks use constant-time comparison, and an unknown username takes as long as
a wrong password so usernames cannot be guessed by timing.

### Access control
- Three separate roles: **owner**, **customer**, **small server**. A customer cannot
  reach any owner function (tested: every attempt returns 403).
- Customers see **only their own** servers, usage and messages (tested).
- Only the owner can register apps, start commands or folders, so customers cannot run
  code or read files on the mother server.
- Every important action goes in an **audit log** (who, what, when, from where): logins
  and failed logins, registrations, customer and server changes, messages, setting and
  key changes. The last 20,000 entries are kept.

### Protection against guessing
- Five wrong logins for a user from one address lock that user from that address for 30
  seconds. Applies to the owner, customers and the phone.
- Locked sites: after 10 wrong attempts per minute from one address, that address is
  refused for the rest of the minute, even with the right password.

### Protection for the sites you host
- **Hidden files are never served.** Anything starting with a dot (`.env`, `.git`,
  `.htaccess`) returns 403. Only `.well-known` is allowed.
- **Path traversal is blocked** (`../`, encoded forms, symbolic links are all
  confined to the site's folder).
- **Only GET and HEAD** are accepted by hosted sites; no directory listings.
- **Security headers** on every hosted page: `X-Content-Type-Options: nosniff`,
  `Referrer-Policy`, and `Strict-Transport-Security` on HTTPS.
- **Password-protect any site or app** (Sites tab → Lock). Visitors sign in with the
  username and password you set. Locked sites are **always redirected to HTTPS first**,
  so the password never travels in clear.
- **Force HTTPS** for every site (optional).
- **Per-visitor request limit** (optional, off by default) and **maximum open
  connections per address** (on, default 200). Over the limit gets 429.
- **Slow-connection defence:** a client that does not send its request within 15
  seconds is dropped; idle forwarded connections close after 2 minutes; request headers
  are capped at 8 KB.
- The engine connects to your apps on `127.0.0.1`. Make your app listen on `127.0.0.1`
  (not `0.0.0.0`) so it can only be reached through the engine and its protections.
- The dashboard itself sends `Content-Security-Policy`, `X-Frame-Options: DENY`,
  `no-store` caching and HSTS.

### Data integrity
- The list of sites is saved **atomically** (write a temp file, then swap), so a crash
  or a read at the wrong moment can never corrupt or empty it.

### What is NOT encrypted or NOT included
- **Files at rest are not encrypted:** site files, the registry, the database and logs
  are stored as ordinary files. Protect them with **full-disk encryption**
  (BitLocker on Windows, LUKS on Linux, FileVault on macOS) and keep encrypted backups.
- **No two-factor authentication.**
- **No protection against large denial-of-service attacks.** The limits above stop
  simple abuse from one address; a real attack needs a network-level service in front.
- **No web application firewall** and no malware scanning of uploaded files.
- **No public domain names or automatic certificate renewal** (Let's Encrypt). Sites
  use `.engine` names with your private CA.
- **No billing, no email notifications.**
- **Customers cannot upload files to your mother server** through a file manager yet
  (they manage their own small servers).
- Customers' small servers are **cooperative**, as explained in section 9.

### Hardening checklist
1. Install `cryptography` so HTTPS is on, then press **Force HTTPS**.
2. Choose a long, unique owner access key. Change it if it was ever shared.
3. Keep `tls/ca.key` private. Back it up offline.
4. Turn on full-disk encryption on the PC.
5. Firewall: allow ports 80, 443 and 53 where visitors need them; allow 9443 only
   from your own network, customers' servers and trusted places. Do not expose 9090.
6. Run the 24/7 server as a normal user with the provided service file, not as root.
7. Keep the operating system and Python up to date.
8. Review the audit log regularly.
9. Back up the data folder (section 14).

---

## 13. Capacity and performance

Measured on **one slow CPU core**, with a test client running on the same core (a real
PC will do better):

| Test | Result |
|---|---|
| 4,600 sites registered, limit enforced at 4,600 | works; the 4,601st is refused |
| Dashboard page of 50 sites out of 4,600 | 32 ms |
| Search across 4,600 sites | 1 ms |
| Visiting a site over HTTP | 0.2 ms each |
| HTTPS, first visit to a site (certificate created) | 4 ms |
| 100 visitors at once, random sites over HTTP | 3,265 requests/s, 0 errors |
| 50 visitors at once over HTTPS (new connection each time) | 249 requests/s, 0 errors |
| 200 idle open connections | 0.3% of one core |
| Memory with 4,600 sites | about 68 MB |

Heavy public traffic and many days of continuous running were not tested.

**GPUs.** The engine itself does not use a graphics card. Serving pages is work for
the CPU, memory and network. A GPU only helps the **apps you host** (AI, video,
rendering). The dashboard shows each NVIDIA GPU's load, VRAM and temperature when
`nvidia-smi` is present (installed with the NVIDIA driver). For hosting, spend on CPU
cores, RAM, a fast SSD and a good network connection.

With more than 200 sites the hosts file is skipped; other devices use the engine's DNS.

---

## 14. Run 24/7, back up, and where data lives

- **Linux server:** follow the steps at the top of `deploy/engine.service`.
- **Windows:** run `deploy/windows_autostart.bat` once as Administrator.
- Turn **sleep off** in the PC's power settings and give the PC a **fixed IP** (a DHCP
  reservation in your router), so addresses saved on phones and join codes keep working.
- If you started the engine from the desktop window, closing the window stops it. Use
  the headless server for 24/7.

**Data folder** (next to the program, or the folder in `ENGINE_DATA`):

| File / folder | Contents |
|---|---|
| `engine_registry.json` | Every site and app you registered |
| `engine_auth.json` | Owner key hash |
| `engine.db` | Customers, servers, usage, messages, audit log, settings |
| `engine_mother.json` | A small server's link to its mother server |
| `sites/` | Managed site files |
| `tls/` | CA and certificates (`ca.key` is the most sensitive file) |
| `logs/` | Access log and per-app logs |

Back up this whole folder regularly, encrypted.

---

## 15. Command line

```
python engine_core.py setpassword            create the owner access key
python engine_core.py serve                  run the engine and dashboard
python engine_core.py site shop              new site
python engine_core.py site shop ./folder     host a folder
python engine_core.py add api 8001           forward to an app on a port
python engine_core.py app api "python app.py"   engine runs and restarts it
python engine_core.py remove shop            remove an entry
python engine_core.py list                   show everything registered
python engine_core.py join <code>            report to a mother server
python engine_core.py leave                  stop reporting
python engine_core.py status                 link, HTTPS and CA fingerprint
```

---

## 16. What was tested, and what was not

**Tested end to end (Linux):**
- Hosting sites, folder sites and apps; app supervision (killed app restarts within
  seconds); stopped apps return 502.
- A mother server and a customer's small server over **real HTTPS with certificate
  verification**: join, heartbeat, usage reports for week, month and year, storage and
  uptime, private message delivery, quota blocking, suspension (503) and reactivation.
- Customer login, portal data, and isolation between customers; owner-only endpoints
  refused to customers and tokens.
- HTTPS: certificates per site, unregistered names rejected, HSTS, force-HTTPS redirect.
- Site protections: hidden files, path traversal, locked sites, rate limit, connection
  limit, slow-client timeout, forwarded headers.
- 4,600 sites: limit, paging, search, latency, load, memory.
- Phone link with certificate pinning, including refusing a wrong certificate.
- Saving the site list under load (a bug found and fixed during testing).

**Not tested:**
- The desktop window and the phone screens (written, checked for errors, but not run).
- The dashboard in a real browser (its code was syntax-checked and every API it calls
  was tested, but the pages and charts were not viewed).
- Windows, macOS, and real GPU hardware (GPU readings were tested with a stand-in for
  `nvidia-smi`).
- Use over the public internet.

---

## 17. Troubleshooting

- **The browser says "not secure" or shows a warning:** install the CA certificate on
  that device (section 8).
- **Chrome searches Google instead of opening the name:** type the full
  `https://shop.engine/`.
- **Name not found on the engine computer:** it was not started as admin/root, so the
  hosts file could not be updated. Use the preview link or restart as admin.
- **HTTPS is off:** `pip install cryptography`, then restart.
- **"This app is not running right now":** the target app is stopped or on another port.
  Check its status in Sites.
- **A customer's server shows offline:** it has not reported for 3 minutes. Check that
  it is running, can reach the mother server on port 9443, and that the join code is
  current (use "New code" if unsure).
- **Phone cannot connect:** same network, correct IP, firewall allows port 9443.
  "Certificate changed" means the engine's certificate is different from the one the
  phone remembered.
- **Forgot the owner key:** delete `engine_auth.json` and run `setpassword` again.
- **Customer forgot their password:** Customers tab → Password.

# > .engine

A self-hosted domain engine. You register a name such as `shop`, point it at a
website or an app, and the engine serves it at `http://shop.engine`.

**The computer runs everything. The phone is a small companion.**

| | Computer / server | Phone |
|---|---|---|
| Hosts sites and apps | Yes | No |
| Runs and restarts your apps | Yes | No |
| Web dashboard (everything) | Yes, `http://localhost:9090` | Opens it in Chrome |
| Desktop window | Yes | - |
| CPU / RAM / GPU / disk readings | Yes | Shows the computer's |
| Open your sites | Yes | Yes (preview links) |

Tested on Linux. The Windows parts (hosts file, CPU readings, autostart script)
follow the same logic but were not run on Windows.

---

## Files

| File | Purpose |
|---|---|
| `engine_core.py` | The engine: DNS, proxy, site hosting, hosts file, access log, command line |
| `engine_infra.py` | Access key, CPU/RAM/GPU readings, app supervisor, phone client |
| `engine_admin.py` | The dashboard and its API (port 9090) |
| `main.py` | The app: full desktop window, small phone companion |
| `buildozer.spec`, `.github/workflows/main.yml` | Builds the Android app |
| `icon.png`, `presplash.png` | App icon and launch screen |
| `deploy/` | 24/7 setup for Linux (systemd) and Windows |

---

## Quick start (computer)

1. Install Python 3.9 or newer. Optional: `pip install kivy psutil`.
2. Create your access key and start:
   - **With a window:** `python main.py` (it asks you to create the key).
   - **Headless server:** `python engine_core.py setpassword`, then
     `python engine_core.py serve`.
3. Run it as **Administrator / root** so it can use ports 80 and 53 and update the
   hosts file. Without that it still works, on ports 8080 and 5353.
4. Open the dashboard: `http://localhost:9090` and sign in.

The access key needs 8+ characters with an uppercase letter, a lowercase letter, a
number and a symbol. Only a salted hash is stored.

---

## Host a website

A site is plain files (HTML, CSS, JavaScript, images) that the engine serves itself.

**New site:** in the dashboard (or the window) register a name and leave the target
blank. You get a starter page. Press **Edit**, paste your HTML, **Save**, reload.

**Existing folder:** register a name and put the folder path as the target. The
folder needs an `index.html`. Changes show immediately, no restart.

**Command line:**
```
python engine_core.py site shop                 # new site
python engine_core.py site shop ./my-website    # existing folder
```
Open it at `http://shop.engine`. Links inside your pages should be relative
(`css/style.css`, not `/css/style.css`) if you also want the preview link below to work.

## Host an app

For anything that needs code running (Flask, Node, an AI service...).

**You start the app yourself:** register a name and its port as the target
(`8001`). The engine forwards to it. If the app is down visitors see a clear
"app is not running" page.

**The engine starts it for you (recommended):** add a start command, for example
`python app.py`. The engine:
- picks a free port and passes it to your app as the `PORT` environment variable,
- restarts the app if it crashes (it gives up after 5 crashes within 60 seconds),
- keeps its output in a log you can read in the dashboard.

Your app must listen on that port, for example in Python:
```python
import os
app.run(host="127.0.0.1", port=int(os.environ["PORT"]))
```
Command line: `python engine_core.py app api "python app.py"`

---

## Opening your sites

| Where | Address |
|---|---|
| The engine computer | `http://shop.engine` (the engine adds the name to the hosts file; needs admin/root) |
| Another computer or phone | Set that device's DNS server to the engine computer's IP. Needs port 53, so run as admin/root. |
| Any device, no setup | `http://<engine-ip>/_/shop/` (preview link, shown in the dashboard as **Open**) |
| The engine's own index | `http://<engine-ip>/` lists everything registered |

**Why `:8080` sometimes?** Browsers use port 80 when none is written. Only an
administrator can open port 80. If the engine was not started as admin/root it uses
8080, and the address needs it: `http://shop.engine:8080`.

**`.engine` is private.** It works only on devices that use this engine for names
(hosts file or DNS above). It is not a public domain and nobody else can open it.
Putting a site on the public internet needs a real domain from a registrar, plus
HTTPS, which this version does not include.

---

## The phone companion

Install the APK, open it and enter the computer's address (`192.168.1.20`) and your
access key. The phone and computer must be on the same Wi-Fi. You see whether the
engine is online, CPU / RAM / GPU, traffic, and each site's status with an **Open**
button. **Open full dashboard** takes you to the complete interface in Chrome.
Registering, editing and controlling apps is done on the computer.

---

## GPUs and performance

Read this before buying hardware.

- **The engine itself does not use a GPU.** Serving pages and forwarding traffic is
  work for the CPU, memory and network. A graphics card will not make hosting faster.
- **GPUs help the apps you host**: AI models, video processing, rendering. Run them as
  managed apps and the dashboard shows each NVIDIA GPU's load, VRAM and temperature
  (needs `nvidia-smi`, installed with the NVIDIA driver).
- For hosting, spend on CPU cores, RAM, a fast SSD and a good network connection.
- This version handles each visitor in its own thread, fine for small and medium
  traffic on one machine. It is not a load balancer and does not spread across servers.
- Measured on one slow CPU core with 100 simultaneous visitors: about 4,600 site pages
  per second and about 390 proxied app requests per second, no errors. 200 idle open
  connections used about 0.3% of a core. A desktop PC will do better. Heavy public
  traffic and long running days were not tested.

---

## Run 24/7

- **Linux server:** follow the steps at the top of `deploy/engine.service`.
- **Windows:** run `deploy/windows_autostart.bat` once as Administrator.
- On a computer, close the desktop window only if you use the headless server;
  closing the window stops an engine that was started from it.
- Turn off sleep in the PC's power settings, and give the PC a fixed IP (a DHCP
  reservation in your router) so the phone's saved address keeps working.

---

## Ports

| Port | Use | If it cannot be used |
|---|---|---|
| 80 | Websites and app traffic | 8080 |
| 53 | Name lookups for other devices | 5353 |
| 9090 | Dashboard and phone companion | 9091, 9092 |

Allow these through the computer's firewall if other devices must reach it. The
dashboard is protected by the access key (5 wrong tries lock that address for 30
seconds), but do not expose port 9090 to the public internet.

## Where data lives

Next to the program (or in `ENGINE_DATA` if you set it): `engine_registry.json`
(everything you registered), `engine_auth.json` (key hash), `sites/` (managed
sites), `logs/` (`access.log`, one log per app). Back these up.

## Troubleshooting

- **Chrome searches Google instead of opening the name:** type the full
  `http://shop.engine/`.
- **Name not found on the engine computer:** it was not started as admin/root, so the
  hosts file could not be updated. Use the preview link or restart as admin.
- **"This app is not running right now":** the target app is stopped or on another
  port. Check its status in the dashboard.
- **Phone cannot connect:** same Wi-Fi, correct IP, firewall allows port 9090.
- **Forgot the access key:** delete `engine_auth.json` and create a new one.

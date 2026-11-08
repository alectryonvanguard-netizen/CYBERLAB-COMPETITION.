# 🛰️ .engine — Independent Domain Hosting & Reverse Proxy Console

A 100% self-contained, independent Domain Hosting Platform built to manage localized domain routing tables without relying on third-party server infrastructure, domain registrars, or global DNS registries.

This application functions as an unkillable foreground system engine capable of intercepting web lookups and proxying up to 15 concurrent applications simultaneously on local hardware.

---

## 🏗️ Core Architecture Overview

```text
[ Connected Client Device ]
            │
            ▼ (Chrome Lookup: http://clipsy.engine)
┌──────────────────────────────────────────────────────────────┐
│                    HOST SMARTPHONE / HARDWARE                │
│                                                              │
│  1. Core Interceptor Network Socket (0.0.0.0:8080)           │
│     - Listens on all active network interfaces               │
│     - Inspects incoming raw HTTP text header arrays          │
│     - Locates the "Host:" parameter field                    │
│                                                              │
│  2. Dynamic Routing Matrix (Storage JSON Engine)              │
│     - Parses target string (e.g., 'clipsy.engine')           │
│     - Maps the lookup string against internal keys           │
│     - Identifies target processing port (e.g., Port 8001)    │
│                                                              │
│  3. Multi-Threaded Upstream Proxy Tunnel                     │
│     - Spawns isolated execution thread channels per lookup   │
│     - Forwards raw request binary chunks to loopback port   │
│     - Streams app background socket output back to Chrome   │
│                                                              │
│     ├── App Node 1 (Clipsy Core File)  ──► Loopback:8001     │
│     ├── App Node 2 (Custom App File)   ──► Loopback:8002     │
│     └── App Node 15 (Max Node Ceiling) ──► Loopback:8015     │
└──────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Local Environment Deployment Guide

### Option A: Local Execution via Terminal (Computer / Desktop Workspace)
Since the codebase relies entirely on standard Python modules, you can boot the bare-metal environment instantly from any workspace command prompt:

1. Clone or save your master infrastructure core script as `main.py`.
2. Open your terminal window and verify Python is mapped to your path:
   ```bash
   python --version
   ```
3. Boot the Domain Engine platform supervisor:
   ```bash
   python main.py
   ```
4. Access the administrative panel UI and unlock the engine gateway using your defined access key string.

### Option B: Local Android Execution via Termux (100% Independent Mobile Host)
To turn your smartphone into a 24/7 standalone hardware hosting node without compiling an APK layout, run the script inside an isolated Linux terminal partition on the device:

1. Open Termux on your Android device.
2. Update the base package dependencies and install the Python runtime:
   ```bash
   pkg update && pkg upgrade -y
   pkg install python git -y
   ```
3. Clone or copy your `main.py` application file directly into your Termux workspace directory.
4. Launch the application inside the background network engine framework:
   ```bash
   python main.py &
   ```
5. **Guarantee 24/7 Uptime:** Pull down your Android notification drawer, expand the Termux status utility marker, and select **Acquire WakeLock**. This blocks the kernel's aggressive power-saving subroutines from putting your network sockets to sleep when the device display is locked.

---

## ⛓️ Registering & Attaching Application Nodes

The platform is designed to be completely decoupled. Your background apps (like Clipsy) do not require domain configs or hosting logic inside their own source folders.

1. **Launch Your App Files:** Spin up your individual app scripts independently so they bind and listen locally to internal ports (e.g., boot your Clipsy code to listen on port `8001`).
2. **Access the Console Panel:** Authenticate into your `.engine` user interface dashboard.
3. **Bind the Domain:** In the registration input array fields, enter your custom configuration tokens:
   * **Subdomain Name:** `clipsy`
   * **Target Port:** `8001`
4. Click **Bind App**. The dashboard's internal registry persistence layer will instantly write the new mapping parameters into `engine_registry.json` and expand your routing table matrix.

---

## 🔍 Intercepting Lookups inside Google Chrome

Because `.engine` is a private, localized top-level domain creation absent from IANA's global root databases, standard mobile web browsers will default to running a Google search text query when the suffix string is inputted.

To force Google Chrome to bypass web searching and explicitly scan your local hardware node routing ports instead, structure your address lookups using explicit protocol headers and trailing slashes:

```text
http://clipsy.engine
```

* **`http://`** — Informs Chrome's address bar parser that you are executing a network handshake call rather than typing text keywords.
* **`:8080`** — Directs the browser's traffic to hit your master proxy core socket listening port.
* **`/`** — The trailing path slash explicitly tells the browser routing table engine to threat the string as a defined network resource host path.

[app]
# (str) Title of the application
title = .engine

# (str) Package name
package.name = enginecore

# (str) Package domain (for android app unique identification)
package.domain = org.cipheraegis

# (str) Source code directory where main.py resides
source.dir = .

# (list) Source files to include (letting Buildozer bundle your custom icon)
source.include_exts = py,png,jpg,json

# (str) Application version
version = 1.0.0

# (list) Application requirements
requirements = python3,kivy

# (str) Custom application icon mapping path
icon.filename = icon.png

# (str) Supported screen orientations
orientation = portrait

# (bool) Hide system status bar (0 = False, keeping system metrics visible)
fullscreen = 0

# --- MASTERPIECE INFRASTRUCTURE SETTINGS ---
android.permissions = INTERNET, FOREGROUND_SERVICE, WAKE_LOCK
android.foreground_service = true

# Pinned stable toolchain pairs to completely match the automated workflow injection paths
android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21

# Architecture targeting (Optimized for modern smartphones)
android.archs = arm64-v8a
p4a.branch = release-2024.01.21

[buildozer]
# (int) Log level (2 = Full debugging output trace)
log_level = 2

# (int) Display warning markers if compiling via root user environments
warn_on_root = 1

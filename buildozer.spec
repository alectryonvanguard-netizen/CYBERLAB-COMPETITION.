[app]
title = .engine
package.name = enginecore
package.domain = org.cipheraegis
source.dir = .
source.include_exts = py,png,jpg,json
version = 1.0.0
requirements = python3,kivy
icon.filename = icon.png
orientation = portrait
fullscreen = 0

# --- INFRASTRUCTURE SETTINGS ---
android.permissions = INTERNET, FOREGROUND_SERVICE, WAKE_LOCK
android.foreground_service = true

# Reset to let the baseline build engine manage the versions natively
android.api = 33
android.minapi = 21

android.archs = arm64-v8a
p4a.branch = master

[buildozer]
log_level = 2
warn_on_root = 1

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

# --- MASTERPIECE INFRASTRUCTURE SETTINGS ---
android.permissions = INTERNET, FOREGROUND_SERVICE, WAKE_LOCK
android.foreground_service = true

# Target modern Android 14/15 devices cleanly
android.api = 34
android.minapi = 21

# DO NOT hardcode android.ndk or android.sdk_build_tools lines here.
# Let the master branch auto-match NDK 28c cleanly.

android.archs = arm64-v8a
p4a.branch = master

[buildozer]
log_level = 2
warn_on_root = 1

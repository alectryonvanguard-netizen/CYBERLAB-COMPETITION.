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

# --- INFRASTRUCTURE LAYOUT ---
android.permissions = INTERNET, FOREGROUND_SERVICE, WAKE_LOCK
android.foreground_service = true

# Stable platform configurations matching the environment
android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21

android.archs = arm64-v8a
p4a.branch = release-2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1

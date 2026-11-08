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

# Explicitly use a stable, tested compilation toolchain pairing
android.api = 33
android.minapi = 21
android.sdk_build_tools = 33.0.2
android.ndk = 25.2.9519653
android.ndk_api = 21

android.archs = arm64-v8a

# LOCK THIS TO A STABLE PRODUCTION TAG INSTEAD OF MASTER
p4a.branch = release-2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1

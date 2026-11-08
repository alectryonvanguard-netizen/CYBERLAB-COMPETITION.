[app]
title = .engine
package.name = enginecore
package.domain = org.cipheraegis
source.dir = .
source.include_exts = py,png,jpg,json
version = 1.0.0
requirements = python3,kivy
icon.filename = %(source.dir)s/icon.png
orientation = portrait
fullscreen = 0

# --- THE FIX: TOOLCHAIN PERMISSIONS & API VERSIONS ---
android.permissions = INTERNET, FOREGROUND_SERVICE, WAKE_LOCK
android.foreground_service = true

# Explicitly target Android 14 / 15 SDK configurations (API 34)
android.api = 34
android.minapi = 21
android.ndk = 25.2.9519653
android.ndk_api = 21

# Architecture targeting
android.archs = arm64-v8a
p4a.branch = master

[buildozer]
log_level = 2
warn_on_root = 1

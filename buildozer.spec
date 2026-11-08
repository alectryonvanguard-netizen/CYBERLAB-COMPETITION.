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

# --- PRODUCTION PERMISSIONS & SERVICES ---
android.permissions = INTERNET, FOREGROUND_SERVICE, WAKE_LOCK
android.foreground_service = true

# Target parameters matching the GitHub workspace paths
android.api = 33
android.minapi = 21

# --- THE BYPASS FIX: LOCAL PACKAGING PATHS ---
# Directing buildozer to local files to avoid urllib download failures
android.sdk_path = /usr/local/lib/android/sdk
android.ndk_path = /usr/local/lib/android/sdk/ndk/25.2.9519653

android.archs = arm64-v8a
p4a.branch = release-2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1

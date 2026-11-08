[app]
title = .engine
package.name = enginecore
package.domain = org.cipheraegis
source.dir = .
source.include_exts = py,png,jpg,json,kv
version = 1.0.0
requirements = python3,kivy
icon.filename = icon.png
orientation = portrait
fullscreen = 0

android.permissions = INTERNET, FOREGROUND_SERVICE, WAKE_LOCK
android.api = 33
android.minapi = 21
android.archs = arm64-v8a
android.accept_sdk_license = True
android.build_tools_version = 33.0.2

android.sdk_path = /usr/local/lib/android/sdk
android.ndk_path = /usr/local/lib/android/sdk/ndk/25.2.9519653

p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1

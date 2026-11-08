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
icon.filename = %(source.dir)s/icon.png

# (str) Supported screen orientations
orientation = portrait

# (bool) Hide system status bar (0 = False, keeping system metrics visible)
fullscreen = 0

# (list) Low-level Android Permissions for persistent server networking
android.permissions = INTERNET, FOREGROUND_SERVICE, WAKE_LOCK

# (bool) Force the engine to execute as an unkillable foreground system process
android.foreground_service = true

# (list) Supported target hardware architectures (Optimized for modern smartphones)
android.archs = arm64-v8a

# (str) Python for Android execution branch stability
p4a.branch = master

[buildozer]
# (int) Log level (2 = Full debugging output trace)
log_level = 2

# (int) Display warning markers if compiling via root user environments
warn_on_root = 1

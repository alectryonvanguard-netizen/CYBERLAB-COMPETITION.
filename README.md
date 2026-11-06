# CYBERLAB — independent project

**Package:** `com.openai.cyberlab`  
**App label:** `CYBERLAB`  
**Build:** Android / Kotlin / Jetpack Compose  
**Minimum Android:** 7.0 (API 24)

## Current build contents

- Offline-first learning paths and knowledge checks
- Four short learning paths and six lessons
- Four fictional, contained investigation labs
- Simulated console that only reads bundled training files
- Tool reference with responsible-use notes
- Local learner profile, XP, lesson/lab completion and checklist
- GitHub Actions workflow that builds and uploads a debug APK

## Important implementation notes

This is an offline starter build. It does not yet include a cloud backend, external AI provider, sign-in service, live network scanning, or real command execution. Those are planned extensions and should be added behind a backend interface. Provider API keys must never be embedded in the APK.

The simulated lab console is deliberately restricted to the fictional files packaged with each exercise. It does not execute shell commands on the phone or connect to external systems.

## Build with GitHub Actions

1. Upload the contents of this ZIP to a repository.
2. Keep the workflow at `.github/workflows/main.yml`.
3. Push to the `main` branch or manually run **Build CYBERLAB APK** in Actions.
4. Download the artifact named `CYBERLAB-APK`.

## Project structure

```text
CYBERLAB/
├── .github/workflows/main.yml
├── app/
│   ├── build.gradle.kts
│   └── src/main/
│       ├── AndroidManifest.xml
│       ├── java/com/openai/cyberlab/
│       │   ├── MainActivity.kt
│       │   └── data/
│       │       ├── Content.kt
│       │       ├── Models.kt
│       │       ├── ProgressStore.kt
│       │       └── SimulatedTerminal.kt
│       └── res/values/themes.xml
├── build.gradle.kts
├── gradle.properties
└── settings.gradle.kts
```

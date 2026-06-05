# MyApplication

A Jetpack Compose Android application built with Kotlin. The project includes CameraX, Coil, OkHttp, NanoHTTPD, and LiteRT-based components.

## Prerequisites

Before building the project, install the following tools:

- Android Studio Ladybug or newer
- JDK 11
- Android SDK Platform 36.1
- Android SDK Build-Tools 36.1.0
- An Android device or emulator running Android 15 (API 35) or newer

## Environment setup

1. Install Android Studio.
2. Open **Settings** or **Preferences** and confirm the embedded JDK is set to JDK 11 or a compatible JDK 11 installation.
3. Open the project in Android Studio.
4. Let Gradle sync finish and download all dependencies.
5. If you plan to create a signed release build, add a `key.properties` file in the project root.

## `key.properties` configuration

Create a `key.properties` file in the repository root when you need release signing. Example:

```properties
storeFile=project-resurgence.jks
storePassword=your_store_password
keyAlias=your_key_alias
keyPassword=your_key_password
```

Place the referenced keystore file in the project root, or update `storeFile` to the correct relative path.

## Install and run

### In Android Studio

1. Select **File > Sync Project with Gradle Files**.
2. Wait until dependency download completes.
3. Choose a run configuration for the `app` module.
4. Click **Run** to install the app on a connected device or emulator.

### From the command line

```bash
./gradlew assembleDebug
./gradlew installDebug
```

On Windows PowerShell, use:

```powershell
.\gradlew.bat assembleDebug
.\gradlew.bat installDebug
```

## Build release

If `key.properties` is configured, you can generate a release build with:

```bash
./gradlew assembleRelease
```

or on Windows:

```powershell
.\gradlew.bat assembleRelease
```

## Project notes

- The app uses Compose UI.
- The Gradle configuration currently targets API 36.1 and minSdk 35.
- Some runtime features depend on camera permissions and device compatibility.

## Troubleshooting

- If Gradle sync fails, confirm that Android Studio has downloaded the correct SDK platform and build-tools versions.
- If signing fails, verify the `key.properties` values and that the keystore file exists.
- If the app cannot install, check that the connected device meets the minimum SDK requirement.

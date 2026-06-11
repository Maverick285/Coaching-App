# Buddy — Android client (Phases 1 + 2)

Kotlin + Jetpack Compose. Talks to the Phase 0/2 backend over HTTPS.

## What's in Phase 1

- **Chat screen** with message scrollback, persistent session id (resumes from server-side history on relaunch), and a sending indicator while the assistant is replying.
- **Voice input** via Android's `SpeechRecognizer` — hold the mic button on the composer to dictate; release to submit.
- **Settings screen** for backend URL + bearer token + "Test connection".
- **Dark Material 3 theme**, edge-to-edge.
- **DataStore Preferences** persists URL, token, and session id.

## What's added in Phase 2

- **Bottom navigation** — Chat / Goals / Grade / Journal.
- **Goals**: list with priority + state badges, add dialog with statement + pace target + MVP threshold, detail screen showing today's progress vs. par, sub-tasks (check to mark done), implementation intentions, "Log progress" and "+ Task" actions.
- **Grade**: today's par-1 score with system explanation, accept/adjust controls, per-goal breakdown, 28-day streak strip (gray = pause, red = zero, blue = ≥ par 1.0), weekly review section that calls the reasoning-tier `/weekly-review` and shows pattern observations + suggestions.
- **Journal**: today's entry editor with optional mood, plus the last ~20 days as cards.
- **AlarmManager** — morning check-in and end-of-day grade prompts. Times configurable in Settings; on first save the app pulls server defaults from `/health`'s `daily_rhythm` block. Reschedules on boot via a registered `BootReceiver`. Tapping the notification deep-links to Goals (morning) or Grade (end of day).
- **Notification permission** requested on Android 13+ when the user enables the alarm toggle.

## What's added in Phase 3

- **Editorial typography** — body text in `FontFamily.Serif` (Noto Serif on modern Android), labels in sans for legibility, generous line height and a restrained type scale. Warm off-white on near-black with a single muted clay accent.
- **Five-tab bottom nav** — Chat / Goals / **Focus** / Grade / Journal.
- **Capture-anywhere flow** — voice → transcript → fast-tier classification → confirmation → dispatch. Each proposed action is a tickable checkbox so the user can accept some and skip others.
- **Home-screen widget** — single-button capture launcher. Add it from your launcher's widget picker (long-press home → Widgets → Buddy → Capture).
- **Focus sessions** — set an intention + duration + optional goal, start a body-doubling session that:
    - keeps a persistent low-importance notification visible with remaining time,
    - schedules check-ins at 15 + 30 minutes and a wrap-up at duration − 3,
    - generates each check-in's text from the fast tier, calibrated to PERSONA.md,
    - posts each check-in to a separate notification channel so they're visible without disturbing the persistent presence,
    - auto-stops when the duration elapses.

The backend is Phase 0 (the `src/buddy` Python service). The Android app does not duplicate any backend logic — every message round-trip is one `POST /converse` call.

## Building

You need Android Studio Ladybug (or newer) with the Android SDK 34 platform installed.

```bash
# 1. Open the android/ directory in Android Studio.
#    First open will trigger a Gradle sync; let it generate gradle/wrapper/gradle-wrapper.jar.
# 2. Connect a device or start an emulator (API 28+).
# 3. Run the "app" configuration.
```

If you prefer the command line and have Gradle 8.10+ installed locally:

```bash
cd android
gradle wrapper          # one time only — generates gradle-wrapper.jar
./gradlew :app:installDebug
```

## Connecting to the backend

In **Settings**, set:

- **Backend URL** — the full `https://buddy.example.com` (production) or `http://10.0.2.2:8000` (Android emulator → host laptop) or `http://localhost:8000` (after `adb reverse tcp:8000 tcp:8000` on a USB-tethered device).
- **Auth token** — the value of `BUDDY_AUTH_TOKEN` from the backend's `.env`.

Tap **Test connection**. On success you'll see the resolved models (e.g. `claude-haiku-4-5-20251001, claude-opus-4-7`).

The app uses cleartext HTTP for `localhost`/`10.0.2.2` only via the default debug build's network security config; production builds should always be HTTPS.

## Layout

```
android/
├── settings.gradle.kts
├── build.gradle.kts                  (project plugins)
├── gradle.properties
├── gradle/
│   ├── libs.versions.toml            (version catalog: AGP, Kotlin, Compose, Retrofit…)
│   └── wrapper/gradle-wrapper.properties
└── app/
    ├── build.gradle.kts              (module config; namespace com.buddy.app, minSdk 28, target 34)
    ├── proguard-rules.pro
    └── src/main/
        ├── AndroidManifest.xml       (INTERNET, RECORD_AUDIO, recognition queries)
        ├── java/com/buddy/app/
        │   ├── BuddyApplication.kt
        │   ├── MainActivity.kt
        │   ├── data/
        │   │   ├── ApiClient.kt      (Retrofit + OkHttp + bearer-token interceptor)
        │   │   ├── BuddyApi.kt
        │   │   ├── ChatRepository.kt
        │   │   ├── Models.kt         (DTOs mirroring the backend Pydantic schemas)
        │   │   └── SettingsRepository.kt   (DataStore Preferences)
        │   ├── ui/
        │   │   ├── AppNav.kt
        │   │   ├── chat/             (ChatScreen + ChatViewModel)
        │   │   ├── settings/         (SettingsScreen + SettingsViewModel)
        │   │   └── theme/
        │   └── voice/
        │       └── SpeechRecognition.kt    (SpeechRecognizer wrapped as a Flow<VoiceEvent>)
        └── res/
```

## Phase 1 acceptance

Per the build spec:

> End of Phase 1: the user has a personal AI companion on their phone with persistent memory. This is already useful. Stop and use it for a week before continuing.

That means: install on a real phone, configure backend URL + token, run the persona intake from the CLI (or from the Android app once Phase 2 adds the goals/journal screens), then chat for a week before adding more features.

## Known shortcuts (intentional)

- Cleartext HTTP to `localhost`/`10.0.2.2` works in the debug build because Android's default network security config permits it for those hosts; production should always be HTTPS via Caddy.
- No streaming yet — `/converse` returns the full response. Phase 2+ may add SSE if latency feels too long for longer outputs.
- No notifications, no foreground service, no AlarmManager — those are Phase 2's morning/evening prompts.
- No accessibility service — that's Phase 5's hard-block intervention work.
- No persona-name fetching from `PERSONA.md` yet; the title bar says "Buddy" generically. Easy follow-up.

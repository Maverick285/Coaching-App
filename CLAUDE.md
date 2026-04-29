# Pre-push checklist for this repo

Run all of these before `git push` on any change. They catch the bugs
that compile cleanly but break on the user's phone.

## Backend

```
python -m pytest tests/ -q
```

Boots the FastAPI app in-process and exercises every endpoint with
mocked LLM/embedding calls. ~70s. Catches schema-validation drift,
SQL errors, and route wiring.

## Android — compile

```
cd android && ./gradlew :app:assembleDebug
```

Catches Kotlin type errors, missing imports, missing dependencies.
Always passes ⇒ APK builds.

## Android — runtime smoke (Robolectric, no emulator)

```
cd android && ./gradlew :app:testDebugUnitTest \
  --tests com.buddy.app.ui.ScreenSmokeTest
```

Mounts every top-level Compose screen on the JVM and verifies
composition completes without throwing. ~10s after first run. **This
is the test that catches "compiles but crashes on screen mount" —
e.g. NPEs in initial recompose, unresolved Compose APIs, missing
string resources, theme misconfiguration.**

If you add a new top-level screen, add a corresponding test in
`android/app/src/test/java/com/buddy/app/ui/ScreenSmokeTest.kt`. Each
test is ~5 lines. The harness deliberately does not mock the network
layer — screens hit the "configured backend, no rows yet" path with
real Retrofit calls that error out — so the test is biased toward
"the screen renders something" rather than asserting specific text.

## Limits of the smoke harness

- Does NOT catch async errors swallowed by `runCatching` in VMs.
- Does NOT catch user-interaction bugs (taps, scrolls, gestures) —
  those need a real emulator.
- Does NOT catch ART-specific quirks that don't reproduce on the JVM.

If a bug slips through that the harness should have caught, add a
specific regression test to `ScreenSmokeTest.kt` with a brief comment
linking back to the symptom.

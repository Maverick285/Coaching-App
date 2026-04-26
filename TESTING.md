# Testing Buddy on your phone

End-to-end guide: from zero to chatting with the persona on your Pixel/Samsung.

The app is two pieces:
- **Backend** — Python FastAPI service that holds memory, talks to Claude, runs the productivity loop. Has to be reachable from your phone over the network.
- **Android app** — installed APK that talks to the backend over HTTPS (or HTTP for local dev).

You'll need both running before you can test anything.

---

## 1. API keys you need first

### Required: Anthropic API key

Without this, the backend boots and the app connects, but every LLM-driven endpoint (`/converse`, `/capture`, `/goals/woop`, `/grade/...`, focus check-ins, intake, consolidation) will return 502.

1. Go to **https://console.anthropic.com/**, sign in, navigate to **API Keys**.
2. Create a key (call it `buddy-dev` or similar). Copy it once — it's only shown to you that one time.
3. Add billing — Buddy uses very little (expect **$15–40/month** at personal-use volume), but Anthropic requires a payment method before keys work.
4. Optional: set a **monthly spending cap** in the console (e.g. $50). Buddy also has its own internal cap (`BUDDY_BUDGET_HARD_USD`) that defaults to $100/month and returns 503 if hit.

### Optional: OpenAI API key

Only used for **embedding generation** (the vector half of hybrid memory search). Without it, the backend automatically falls back to BM25-only search — perfectly fine for personal use, slightly less semantically clever.

If you want to add it: same flow at **https://platform.openai.com/**. Costs are negligible (text-embedding-3-small is ~$0.02 per million tokens).

### Model availability check

The registry currently points at `claude-haiku-4-5-20251001` (fast) and `claude-opus-4-7` (reasoning). If your account doesn't have access to either, the call will fail with a clear error. To swap, set in `.env`:

```
BUDDY_FAST_MODEL_PIN=claude-sonnet-4-5
BUDDY_REASONING_MODEL_PIN=claude-opus-4-5
```

(or whatever models you do have access to). Or edit `src/buddy/llm/model_registry.json` directly.

---

## 2. Pick a backend deployment path

Three options, ordered by setup difficulty.

### Path A — Laptop + USB tether (fastest for first-try)

Best for: quick experimentation, you have the phone plugged in for the next hour.

**Pros:** zero hosting cost, no firewall/router config, no domain, works in 5 minutes.
**Cons:** phone has to be USB-connected to your laptop while you use it.

```bash
# On your laptop (one-time setup):
git clone https://github.com/Maverick285/Coaching-App.git
cd Coaching-App
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY and BUDDY_AUTH_TOKEN to a long random string.
# (Generate the token: python -c "import secrets; print(secrets.token_urlsafe(48))")

python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,cli]"
alembic upgrade head
uvicorn buddy.main:app --reload
```

Backend is now live at `http://localhost:8000` on your laptop. To make the phone reach it:

```bash
# In another terminal, with the phone plugged in via USB and ADB authorized:
adb reverse tcp:8000 tcp:8000
```

In the Android app's Settings, set:
- **Backend URL:** `http://localhost:8000`
- **Auth token:** the value of `BUDDY_AUTH_TOKEN` from your `.env`
- Tap **Test connection** — expect a green confirmation with the resolved model names.

Every time you re-plug the phone, re-run `adb reverse tcp:8000 tcp:8000`.

### Path B — Laptop on home WiFi (good middle ground)

Best for: everyday testing on your home network without a USB cable.

```bash
# Same backend setup as Path A, but bind to all interfaces:
uvicorn buddy.main:app --reload --host 0.0.0.0
```

Find your laptop's LAN IP (on macOS: `ipconfig getifaddr en0`; on Linux: `hostname -I`). Set the Android backend URL to `http://192.168.x.x:8000` (your laptop's IP).

The phone needs to be on the same WiFi as the laptop. The laptop's firewall must allow port 8000 (macOS will prompt the first time; Linux usually allows it).

**Cleartext-HTTP gotcha:** Android refuses cleartext HTTP traffic by default in release builds, but the **debug** build allows it for any host. Since you're installing the debug APK, you're fine.

### Path C — Hetzner VPS, real deployment (production-ish)

Best for: using Buddy daily, away from home, on cellular.

**Pros:** works from anywhere, real HTTPS, automatic backups.
**Cons:** ~$5/month, requires a domain, ~30 min setup the first time.

```bash
# 1. Spin up a Hetzner CX22 (€4.51/month, Ubuntu 24.04). Note the IP.
# 2. Point a subdomain at the IP (e.g. buddy.yourdomain.com).
# 3. SSH in, install Docker:
sudo apt update && sudo apt install -y docker.io docker-compose-plugin git
# 4. Clone the repo and configure:
git clone https://github.com/Maverick285/Coaching-App.git
cd Coaching-App
cp .env.example .env
nano .env   # Fill in keys + auth token + (optional) BUDDY_GIT_REMOTE
# 5. Edit the Caddyfile to point at your domain:
nano Caddyfile   # Replace `buddy.example.com` with your real subdomain.
# 6. Bring it up:
sudo docker compose up -d --build
```

Caddy will auto-fetch a Let's Encrypt cert in the first 60 seconds. Hit `https://buddy.yourdomain.com/health` from your laptop browser to confirm.

In the Android app: **Backend URL** = `https://buddy.yourdomain.com`, **Auth token** = same as in `.env`.

---

## 3. Build and install the Android app

You need **Android Studio Ladybug or newer** (or just the Android SDK + Gradle if you prefer command line).

### Option 1: Android Studio (graphical)

1. Open Android Studio → **Open** → pick the `android/` folder inside the repo.
2. Wait for Gradle sync (~3 minutes the first time).
3. Plug your phone in via USB. On the phone, enable **Developer Options** (Settings → About → tap "Build number" seven times) and **USB debugging** (Settings → Developer options → USB debugging). Authorize the laptop when the phone prompts.
4. In Android Studio, the device should appear in the device dropdown. Hit **Run** ▶ (the green triangle).
5. The IDE compiles, installs, and launches the app.

### Option 2: Command line

```bash
cd android
./gradlew :app:installDebug
```

Same prerequisites: phone plugged in, USB debugging on, laptop authorized.

The APK that ships is at `android/app/build/outputs/apk/debug/app-debug.apk` if you ever want to sideload it manually.

---

## 4. First-run configuration on the phone

1. Open the Buddy app. You'll land on the chat tab with a "Configure backend in Settings first" message and an editorial quote.
2. Tap the gear icon → **Settings**.
3. Enter **Backend URL** and **Auth token** (from your `.env`).
4. Tap **Test connection**. Expect a confirmation line that includes your resolved model names.
5. Optional: pick your morning + end-of-day prompt times. Toggle **Daily prompts** on — Android 13+ will ask for notification permission.
6. Back out of Settings.

### Run the persona intake

The persona starts as a generic "Coach". To make it yours, run the calibration intake — easiest from the CLI on your laptop, since it's a 10-question conversation:

```bash
# On your laptop, in the repo:
export BUDDY_BACKEND_URL=http://localhost:8000
export BUDDY_AUTH_TOKEN="<value from .env>"
buddy intake
```

Answer the 10 questions. The reasoning-tier model synthesizes both `PERSONA.md` (the persona's calibration) and `MEMORY.md` (your identity layer). You can re-edit either file at any time via `buddy memory edit PERSONA.md`.

You can also do this from the Android app via `/intake/start` if you don't want the CLI, but the CLI flow is more comfortable for typing longer answers.

---

## 5. Try the loop

Now exercise each surface to confirm it's all working.

### Chat
- Open the **Chat** tab.
- Type "Tell me about yourself." — you should see a response in the calibrated voice from `PERSONA.md`.
- Hold the **mic button** in the composer and dictate something — release to submit.
- Tap the **+** in the top bar to start a new session, or the **waveform icon** for the capture flow.

### Goals
- Go to the **Goals** tab. Tap the **+** FAB. Add: statement "Read 24 books this year", priority 4, daily target 18 pages, MVP "1 page".
- Tap into the goal. Hit **Log progress** → 18 → save.
- Try **+ Task** to add a task. Check it off.

### Grade
- Go to the **Grade** tab. You should see a 1.00 score (par 1.0) in the colored pill, with the explanation "On or above pace: Read 24 books this year (1.00)."
- Hit **Accept**. The grade is now finalized for today.
- Hit **Run** under "Weekly review" — this calls the reasoning tier and may take a few seconds.

### Journal
- Go to the **Journal** tab. Type a sentence about the day. Save.

### Focus session
- Go to the **Focus** tab. Set intention "30 minutes on the runsheet", duration 30. Pick the goal chip. Hit **Start session**.
- A persistent low-priority notification appears with the remaining time. Background the app — it stays.
- After 15 minutes (or whenever the first scheduled check-in fires), you'll get a notification with a persona-calibrated check-in line.
- When you're done, hit **End session** in the app or the **End** action on the notification.

### Capture from anywhere
- Long-press your home screen → **Widgets** → **Buddy** → **Capture**. Drag it onto your home screen.
- Tap it. The phone immediately starts listening.
- Say "did 30 pushups". You should see one or more proposed actions, with checkboxes.
- Tap **Confirm**. The progress logs.

### Dreams (memory consolidation)
- This runs automatically at 3 AM by default. To trigger manually for testing:
  ```bash
  python -c "
  from buddy.config import reload_settings; reload_settings()
  from buddy.memory.consolidation import run_consolidation
  import asyncio
  print(asyncio.run(run_consolidation()))
  "
  ```
- Then `buddy dreams` from the CLI to review pending memory updates.

---

## 6. Troubleshooting

### "Connection failed" in Settings
- Confirm the backend is running: `curl http://localhost:8000/health` from the laptop.
- If using Path A, confirm `adb reverse tcp:8000 tcp:8000` is active. It resets on every reconnect.
- If using Path B, confirm laptop firewall allows port 8000 and phone is on the same WiFi.
- If using Path C, confirm the cert provisioned: visit `https://buddy.yourdomain.com/health` in a desktop browser.

### "502 Bad Gateway" on /converse
- Almost always an Anthropic key issue. Check the backend log for the exact error.
- Common: model not available on your account. Pin a model you do have access to via `BUDDY_FAST_MODEL_PIN` / `BUDDY_REASONING_MODEL_PIN` in `.env`.

### Voice button does nothing
- Microphone permission denied? Settings → Apps → Buddy → Permissions → Microphone.
- Some Samsung devices ship without Google Speech Recognition. Install **Google** app from the Play Store; it brings the recognition service.

### Notifications don't fire
- Android 13+: did you grant POST_NOTIFICATIONS? Settings → Apps → Buddy → Notifications.
- Samsung specifically kills foreground services aggressively. Settings → Battery → Background usage limits → make sure Buddy is **not** in the "Sleeping apps" list. Add Buddy to **Never sleeping apps**.
- For the alarms (morning / EOD), the app uses *inexact* alarms — Doze can delay them by up to ~10 minutes. This is fine for daily prompts but won't be second-precise.

### Backend keeps restarting
- Check disk: `df -h`. SQLite will fill up if logs grow without bound (rare, but).
- Check the budget cap. If you've blown through `BUDDY_BUDGET_HARD_USD` for the month, the backend returns 503 on `/converse` until the next month or you raise the cap.

### The CLI complains "Missing CLI config"
```bash
export BUDDY_BACKEND_URL=http://localhost:8000
export BUDDY_AUTH_TOKEN="<your token>"
```
Or create `~/.config/buddy/config.toml`:
```toml
backend_url = "http://localhost:8000"
auth_token = "your-token-here"
editor = "nvim"
```

---

## 7. What you don't have to test

These are intentionally not in the app yet — they're Phase 4+ work:
- PC activity agent (drift detection while working at your computer)
- Tier 3+ interventions (friction overlays, hard app blocks)
- The wife-mediated override system (SMS → code)
- Stake-based interventions (Beeminder etc.)
- Calendar / food tracker integrations

If something feels missing that's not in this list, tell me — it's probably a bug or oversight rather than a deliberate Phase-N defer.

---

## 8. Quick reference: what the backend exposes

All require `Authorization: Bearer <token>` except `/health`.

| Method | Path | What |
|--------|------|------|
| GET    | `/health` | Liveness + resolved models + daily rhythm |
| POST   | `/converse` | Send a chat message |
| POST   | `/intake/start` + `/turn` + `/finalize` | Persona calibration |
| GET/POST/PATCH/DELETE | `/goals` | Goal CRUD |
| POST   | `/goals/woop` | WOOP synthesis |
| GET/POST/PATCH/DELETE | `/tasks` | Task CRUD |
| POST   | `/progress/log` | Direct progress entry |
| POST   | `/progress/freeform` | Free-form text → attributed progress |
| GET    | `/grade/today`, `/grade/{date}` | Par-1 day grade |
| POST   | `/grade/{date}/finalize` | Accept/adjust |
| GET    | `/streak` | No-zero-day streak with pauses |
| GET    | `/weekly-review` | Reasoning-tier rollup |
| GET/PUT | `/journal/{date}` | One entry per day |
| POST   | `/capture` + `/capture/confirm` | Capture-anywhere flow |
| POST   | `/focus/start` + `/focus/{id}/end` + `/focus/{id}/check-in` | Focus sessions |
| GET    | `/memory/files`, `/memory/file/{path}` | Inspect/edit memory |
| POST   | `/memory/search` | Hybrid memory search |
| GET/POST | `/memory/dreams` | Review proposed memory updates |
| GET    | `/usage` | API spend |

Open `http://localhost:8000/docs` in a browser for the live OpenAPI explorer.

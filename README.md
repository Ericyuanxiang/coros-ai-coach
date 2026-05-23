# coros-ai-coach — 高驰AI教练

An MCP server that lets AI assistants access your complete Coros Training Hub data, create structured workouts, and manage your training calendar — all through natural language.

No API key. No official API. Your credentials stay local, encrypted in your system keyring. The server talks directly to Coros using the same endpoints the web app and mobile app use.

## What you can do

Ask your assistant questions in plain English (or any language):

- *"How was my sleep this week? Break it down by deep, REM, and light."*
- *"What's my 4-week HRV trend? Am I above or below baseline?"*
- *"Find me a beginner 10K training plan from the Coros library and import it."*
- *"Create a 60-minute zone 2 run with a 10-minute warmup and 5-minute cooldown."*
- *"Schedule that workout for Thursday and move my existing Thursday session to Friday."*
- *"Show me my training load ratio over the last month — am I overtraining?"*
- *"Build a core strength circuit: plank, crunches, leg raises, 3 sets."*
- *"What's my lactate threshold heart rate and pace right now?"*

## How it's different

This is a fork of [cygnusb/coros-mcp](https://github.com/cygnusb/coros-mcp) that adds a significant layer of capabilities on top. The original covers basic sleep and activity retrieval. coros-ai-coach adds:

| Domain | Original | coros-ai-coach |
|--------|----------|-------------|
| Daily health | — | Steps, calories, stress levels (mobile API) |
| Training library | — | Browse 200+ official programs, import with one click |
| Running workouts | — | Full HR zone builder — 3 zone models (MaxHR, %HRR, %LTHR), pace, power, cadence |
| Strength workouts | — | Circuit builder from Coros exercise catalogue |
| Calendar | List only | View, schedule, reschedule, remove, volume summary |
| Dashboard | — | Quick "how am I today?" snapshot |
| User profile | — | HR zones, pace zones, power zones, physiological baselines |
| Workout management | Create/list | Create, list, delete workouts AND plans |
| Library browsing | — | Filter by sport, difficulty, category, region, language |

## Tools

### Health & readiness

| Tool | What it returns |
|------|----------------|
| `get_dashboard` | Current HRV, sleep quality, readiness score, recent activity summaries, fitness trend. No date params — always returns the latest ~7 days. |
| `get_daily_health` | Steps, calories, stress level (average + duration), and sleep stage breakdown for each day. From the mobile API — data not available through Training Hub. |
| `get_sleep_data` | Per-night sleep stages (deep, light, REM, awake), naps, sleep heart rate (avg/min/max), and quality score. Configurable 1–52 weeks. |
| `get_user_profile` | All physiological baselines: max HR, resting HR, lactate threshold HR, lactate threshold pace, FTP. HR zones for 3 models, pace zones, cycling power zones. |

### Training analysis

| Tool | What it returns |
|------|----------------|
| `get_training_analysis` | The full Coros "数据分析" report. 35 daily metrics: HRV (RMSSD + baseline), resting HR, training load (daily/acute/chronic), fatigue rate, VO2max, stamina, performance index. Weekly summaries with recommended load ranges. Sport-by-sport breakdown. Intensity distribution. Personal records. Configurable 1–24 weeks. |

### Activities

| Tool | What it returns |
|------|----------------|
| `list_activities` | Paginated activity list: sport type, duration, distance, HR, power, calories, training load, elevation. |
| `get_activity_detail` | Full activity detail: lap data, HR zones, power zones, all sport-specific metrics. |
| `list_sport_types` | All Coros sport type IDs and names — useful reference for creating workouts. |

### Workout builder

| Tool | What it returns |
|------|----------------|
| `create_run_workout` | Running workout with HR zone targets (zone 1–6). Three zone models: MaxHR, %HRR (heart rate reserve), %LTHR (lactate threshold). Also supports pace targets (sec/km), power (watts), cadence (spm), and equivalent pace. Supports intervals via repeat groups. |
| `create_workout` | Cycling workout with power targets (watts). Default indoor cycling, supports road bike. Interval/repeat support. |
| `create_strength_workout` | Strength circuit program. Exercises pulled from the Coros catalogue (use `list_exercises` to browse). Configurable sets, reps or timed targets, rest periods. |
| `list_exercises` | The Coros exercise catalogue for strength/conditioning. Each exercise has an `origin_id`, T-code name, and `sid_` overview key. |

### Training library

| Tool | What it returns |
|------|----------------|
| `get_training_library` | Browse the public COROS training library: 200+ programs created by COROS coaches and athletes. Each entry has a title, description, sport types, difficulty level, training targets, author, and download count. Filter by sport_type, difficulty, category. Choose region (cn/us/eu) and language (zh-CN, en-US, de, etc.). |
| `import_training_program` | Import a library program into your personal account with one click. Auto-resolves internal codes to human-readable names. Works for both single workouts and multi-week training plans. |

### Calendar

| Tool | What it returns |
|------|----------------|
| `list_planned_activities` | Everything scheduled on your training calendar for a date range. |
| `schedule_workout` | Put a workout from your library onto a specific calendar day. |
| `remove_scheduled_workout` | Remove a scheduled session from the calendar. |
| `get_training_summary` | Aggregated volume totals (duration, load, session count) over a date range. Lighter than listing all activities. |

### Workout & plan management

| Tool | What it returns |
|------|----------------|
| `list_workouts` | All saved workout programs and training plans in your account. Includes structure preview: steps, durations, intensity targets. |
| `delete_workout` | Remove a workout program. |
| `delete_plan` | Remove a training plan. |

### Auth

| Tool | What it returns |
|------|----------------|
| `authenticate_coros` | Log in with email + password. Stores both web and mobile tokens. |
| `authenticate_coros_mobile` | Mobile-only login (for sleep data access). |
| `check_coros_auth` | Token validity status, expiry time, mobile token state. |

## Architecture

### Dual API

Coros splits data across two separate API systems:

| | Training Hub (web) | Mobile API |
|---|---|---|
| **Host** | `teameuapi.coros.com` (EU) / `teamapi.coros.com` (US) | `apieu.coros.com` (EU) / `api.coros.com` (US) |
| **Auth** | MD5-hashed password → `accessToken` header | AES-128-CBC encrypted credentials (key reverse-engineered from Coros APK) |
| **Token TTL** | ~24 hours | ~1 hour |
| **Refresh** | Re-authenticate with stored credentials | Replay stored encrypted login payload |
| **Data** | HRV, training metrics, activities, workouts, calendar | Sleep stages, steps, calories, stress |

`get_training_analysis` goes further: it calls two Training Hub endpoints in parallel (`/analyse/dayDetail/query` for configurable date range + `/analyse/query` for VO2max/fitness fields) and merges them into a single result.

### Token storage

Priority chain on read: `COROS_ACCESS_TOKEN` env var → system keyring (Windows Credential Manager / macOS Keychain / Linux Secret Service) → AES-256-GCM encrypted local file.

On write, both keyring and encrypted file are updated. The entire `StoredAuth` object — web token, mobile token, and mobile login payload for replay — is serialized as JSON into a single credential.

### Auto-auth

If `COROS_EMAIL` and `COROS_PASSWORD` are set (via `.env` or environment), the server authenticates automatically on the first request and re-authenticates transparently when the token expires or is rejected. No manual auth command needed.

## Setup

### 1. Install

```bash
git clone https://github.com/Ericyuanxiang/coros-ai-coach.git
cd coros-ai-coach
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

### 2. Configure

Create `.env` in the project directory:

```env
COROS_EMAIL=you@example.com
COROS_PASSWORD=yourpassword
COROS_REGION=eu
```

That's it. The server auto-authenticates on first use.

### 3. Register with Claude Code

```bash
claude mcp add coros -- /path/to/coros-ai-coach/.venv/bin/coros-ai-coach serve
```

Or in `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "coros": {
      "command": "/path/to/coros-ai-coach/.venv/bin/coros-ai-coach",
      "args": ["serve"]
    }
  }
}
```

### Manual auth (optional)

If you prefer not to use `.env`:

```bash
coros-ai-coach auth          # Prompted login — stores web + mobile tokens
coros-ai-coach auth-status   # Check expiry and token state
coros-ai-coach auth-clear    # Remove all stored tokens
```

## Requirements

- Python >= 3.11
- A Coros account (any region: EU, US, Asia/China)

## Dependencies

- [fastmcp](https://github.com/jlowin/fastmcp) — MCP server framework
- [httpx](https://www.python-httpx.org/) — async HTTP client
- [pycryptodome](https://pycryptodome.readthedocs.io/) — AES encryption for mobile API auth
- [keyring](https://github.com/jaraco/keyring) — cross-platform credential storage
- [pydantic](https://docs.pydantic.dev/) — data validation and serialization
- [python-dotenv](https://github.com/theskumar/python-dotenv) — `.env` file support

## Structure

```
coros-ai-coach/
├── server.py           # FastMCP tool definitions (22 tools)
├── coros_api.py        # HTTP client, dual-API auth, AES encryption, response parsers
├── models.py           # Pydantic v2 data models
├── cli.py              # CLI entry point
├── auth/               # Token storage: keyring + AES-256-GCM encrypted file fallback
└── pyproject.toml
```

## Credits

Forked from [cygnusb/coros-mcp](https://github.com/cygnusb/coros-mcp) (MIT License).

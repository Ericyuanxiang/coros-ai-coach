"""
Coros AI Coach MCP Server

Usage:
    python server.py

MCP config:
    claude mcp add coros \\
      -e COROS_EMAIL=you@example.com \\
      -e COROS_PASSWORD=yourpass \\
      -e COROS_REGION=eu \\
      -- python /path/to/coros-ai-coach/server.py
"""

import os

from dotenv import load_dotenv
from fastmcp import FastMCP

import coros_api

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

mcp = FastMCP("coros-ai-coach")


async def _get_auth():
    """Return StoredAuth. Retry with fresh login if cached token fails."""
    auth = coros_api.get_stored_auth()
    if auth is None:
        auth = await coros_api.try_auto_login()
    return auth


async def _run_with_auth(fn, auth, *args, **kwargs):
    return await fn(auth, *args, **kwargs)


def _tool_error(exc: Exception, **extra) -> dict:
    return {"error": str(exc), **extra}


# ---------------------------------------------------------------------------
# Auth tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def authenticate_coros(email: str, password: str, region: str = "eu") -> dict:
    """Authenticate with Coros Training Hub."""
    try:
        auth = await coros_api.login(email, password, region)
        return {"authenticated": True, "user_id": auth.user_id, "region": auth.region}
    except Exception as exc:
        return _tool_error(exc)


@mcp.tool()
async def authenticate_coros_mobile(email: str, password: str, region: str = "eu") -> dict:
    """Authenticate with Coros mobile API (for sleep data)."""
    try:
        auth = await coros_api.login_mobile(email, password, region)
        return {"authenticated": True, "user_id": auth.user_id, "region": auth.region}
    except Exception as exc:
        return _tool_error(exc)


@mcp.tool()
async def check_coros_auth() -> dict:
    """Check authentication status."""
    auth = await _get_auth()
    if auth is None:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "user_id": auth.user_id,
        "region": auth.region,
        "has_mobile": bool(auth.mobile_access_token),
    }


# ---------------------------------------------------------------------------
# generate_plan — two-phase AI-embedded weekly plan builder
# ---------------------------------------------------------------------------

@mcp.tool()
async def generate_plan(start_day: str = "",
                         phase: str = "base",
                         ai_decision: dict | None = None) -> dict:
    """Generate a weekly training plan. Two-phase: Phase 1 returns framework,
    Phase 2 (with ai_decision) executes the plan.

    start_day: next Monday's date, e.g. "20260601" or "2026-06-01"
    phase: ONLY "base", "build", "peak", or "taper". Default "base".
    ai_decision: omit in Phase 1. Required in Phase 2.
    """
    from workflows.generate_plan import run
    if phase not in ("base", "build", "peak", "taper"):
        return {"error": f"phase 必须是 base/build/peak/taper 之一, 不是 '{phase}'"}
    if not start_day:
        from datetime import date, timedelta
        today = date.today()
        days = (7 - today.weekday()) % 7 or 7
        start_day = (today + timedelta(days=days)).strftime("%Y%m%d")
    # Normalize date format: accept "2026-06-01", "2026/06/01", etc.
    start_day = start_day.replace("-", "").replace("/", "").replace(".", "")
    if len(start_day) != 8 or not start_day.isdigit():
        return {"error": f"日期格式需要 YYYYMMDD, 例如 '20260601'. 收到: '{start_day}'"}
    # Silently fix past dates (AI doesn't know it's 2026)
    from datetime import date, timedelta
    try:
        dt = date(int(start_day[:4]), int(start_day[4:6]), int(start_day[6:8]))
        today = date.today()
        if dt < today - timedelta(days=1):
            days = (7 - today.weekday()) % 7 or 7
            start_day = (today + timedelta(days=days)).strftime("%Y%m%d")
    except ValueError:
        return {"error": f"日期不存在: '{start_day}'"}
    auth = await _get_auth()
    if auth is None:
        return {"error": "Not authenticated."}
    try:
        return await run(auth, start_day, phase, ai_decision)
    except Exception as exc:
        err = str(exc)
        if "token" in err.lower() or "access" in err.lower():
            # Token expired — force re-login and retry once
            auth = await coros_api.try_auto_login()
            if auth:
                try:
                    return await run(auth, start_day, phase, ai_decision)
                except Exception as exc2:
                    return _tool_error(exc2)
        return _tool_error(exc)




# ---------------------------------------------------------------------------
# Simple tools — AI composes itself
# ---------------------------------------------------------------------------

@mcp.tool()
async def browse_library(category: str = "workout",
                          sport_type: str = "run") -> dict:
    """Browse the COROS public training library. Returns title + linked_id for each course."""
    try:
        programs = await coros_api.fetch_training_library("cn", "zh-CN", category=category, sport_type=sport_type)
        return {"courses": [{"title": p.title, "linked_id": p.linked_id, "difficulty": p.difficulties}
                            for p in programs], "count": len(programs)}
    except Exception as exc:
        return _tool_error(exc)


@mcp.tool()
async def create_custom_workout(name: str, duration_minutes: int = 45,
                                 hr_zone_low: int = 2, hr_zone_high: int = 3) -> dict:
    """Create a custom running workout. Returns workout_id for scheduling."""
    auth = await _get_auth()
    if not auth: return {"error": "Not authenticated."}
    try:
        steps = [{"name": name, "duration_minutes": duration_minutes,
                  "hr_low": hr_zone_low, "hr_high": hr_zone_high}]
        wid = await coros_api.create_run_workout(auth, name, steps)
        return {"created": True, "workout_id": wid, "name": name}
    except Exception as exc:
        return _tool_error(exc)


@mcp.tool()
async def calculate_training_load(workout_id: str) -> dict:
    """Estimate TL (training load) for a workout before scheduling."""
    auth = await _get_auth()
    if not auth: return {"error": "Not authenticated."}
    try:
        raw = await coros_api._fetch_raw_workout(auth, workout_id)
        if raw is None: return {"error": f"Workout not found: {workout_id}"}
        est = await coros_api.fetch_program_calculate(auth, raw)
        return {"training_load": est.get("planTrainingLoad"), "duration_seconds": est.get("planDuration"),
                "distance_cm": est.get("planDistance")}
    except Exception as exc:
        return _tool_error(exc)


@mcp.tool()
async def schedule_to_calendar(workout_id: str, date: str) -> dict:
    """Schedule a workout to a specific date (YYYYMMDD or YYYY-MM-DD)."""
    auth = await _get_auth()
    if not auth: return {"error": "Not authenticated."}
    try:
        date = date.replace("-", "").replace("/", "")
        await coros_api.schedule_workout(auth, workout_id, date, 1)
        return {"scheduled": True, "workout_id": workout_id, "date": date}
    except Exception as exc:
        return _tool_error(exc)


@mcp.tool()
async def check_weekly_plan(start_day: str, end_day: str) -> dict:
    """View weekly training projection (same as Coros app)."""
    auth = await _get_auth()
    if not auth: return {"error": "Not authenticated."}
    try:
        start_day = start_day.replace("-", ""); end_day = end_day.replace("-", "")
        raw = await _run_with_auth(coros_api.fetch_schedule, auth, start_day, end_day)
        weeks = []
        if isinstance(raw, dict):
            for w in raw.get("weekStages", []):
                ws = w.get("trainSum", {})
                weeks.append({"week": w.get("firstDayInWeek"),
                              "long_term_load": ws.get("actualCti"), "short_term_load": ws.get("actualAti"),
                              "load_ratio": round((ws.get("actualTrainingLoadRatio") or 0) * 100),
                              "plan_tl": ws.get("planTrainingLoad")})
        return {"weeks": weeks}
    except Exception as exc:
        return _tool_error(exc)


@mcp.tool()
async def get_training_state() -> dict:
    """Fetch current training state (ATI, CTI, fatigue, HRV)."""
    from datetime import datetime, timedelta
    auth = await _get_auth()
    if not auth: return {"error": "Not authenticated."}
    try:
        today = datetime.now().strftime("%Y%m%d")
        ago = (datetime.now() - timedelta(days=14)).strftime("%Y%m%d")
        analysis = await coros_api.fetch_training_analysis(auth, ago, today)
        daily = sorted(analysis.get("daily_records", []), key=lambda r: r.get("date", ""), reverse=True)
        if not daily: return {"error": "No data"}
        latest = daily[0]
        ati_7d = daily[min(6, len(daily)-1)].get("ati") if len(daily) > 6 else None
        ati_14d = daily[min(13, len(daily)-1)].get("ati") if len(daily) > 13 else None
        train_days = sum(1 for r in daily[:7] if r.get("training_load", 0) or 0 > 0)
        hrv = latest.get("avg_sleep_hrv"); base = latest.get("baseline")
        return {
            "ati": latest.get("ati"), "ati_7d_ago": ati_7d, "ati_14d_ago": ati_14d,
            "cti": latest.get("cti"), "load_ratio": latest.get("training_load_ratio"),
            "fatigue": latest.get("tired_rate_state_new"), "tired_rate": latest.get("tired_rate"),
            "train_days_7d": train_days,
            "hrv": hrv, "hrv_baseline": base,
            "hrv_deviation": round((hrv - base) / base * 100, 1) if (hrv and base) else None,
        }
    except Exception as exc:
        return _tool_error(exc)


@mcp.tool()
async def get_coros_recommendation() -> dict:
    """Get Coros weekly training load recommendation."""
    from datetime import datetime, timedelta
    auth = await _get_auth()
    if not auth: return {"error": "Not authenticated."}
    try:
        today = datetime.now().strftime("%Y%m%d")
        ago = (datetime.now() - timedelta(days=14)).strftime("%Y%m%d")
        analysis = await coros_api.fetch_training_analysis(auth, ago, today)
        weeks = sorted(analysis.get("week_list", []), key=lambda w: w.get("firstDayOfWeek", 0), reverse=True)
        for w in weeks:
            if w.get("recomendTlMin") and w.get("recomendTlMax"):
                return {"min": int(w["recomendTlMin"]), "max": int(w["recomendTlMax"])}
        return {"min": 350, "max": 500}
    except Exception as exc:
        return _tool_error(exc)


def main():
    mcp.run()


if __name__ == "__main__":
    main()

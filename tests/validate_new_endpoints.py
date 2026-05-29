"""Validate new endpoints against the live Coros API."""

import asyncio
import json
import sys
import os
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coros_api import (
    _base_url, _auth_headers, get_stored_auth, try_auto_login,
    fetch_activities, fetch_workouts, fetch_team_list, _get_primary_team_id,
    fetch_plans, fetch_team_info,
)

results = []


def ok(name: str, detail: str = ""):
    results.append(("OK", name, detail))
    print(f"  [OK] {name}" + (f" - {detail}" if detail else ""))


def fail(name: str, detail: str):
    results.append(("FAIL", name, detail))
    print(f"  [FAIL] {name} - {detail}")


async def main():
    print("=== Auth ===")
    auth = get_stored_auth() or await try_auto_login()
    if not auth:
        print("FATAL: no auth")
        return
    print(f"  user_id={auth.user_id}  region={auth.region}\n")

    base = _base_url(auth.region)
    headers = {k: v for k, v in _auth_headers(auth).items() if k != "Content-Type"}
    json_headers = _auth_headers(auth)

    # ---- 1. /team/info ----
    print("--- /team/info ---")
    try:
        team_id = await _get_primary_team_id(auth)
        if not team_id:
            fail("team/info", "no team")
        else:
            info = await fetch_team_info(auth, team_id)
            if isinstance(info, dict):
                keys = list(info.keys())[:6]
                ok("team/info", f"keys={keys}")
            else:
                fail("team/info", f"unexpected type: {type(info).__name__}")
    except Exception as e:
        fail("team/info", str(e)[:100])

    # ---- 2. /training/plan/query ----
    print("--- /training/plan/query ---")
    try:
        plans = await fetch_plans(auth)
        ok("plan/query", f"{len(plans or [])} plans returned")
    except Exception as e:
        fail("plan/query", str(e)[:100])

    # ---- 3. /training/plan/detail ----
    print("--- /training/plan/detail ---")
    try:
        plans = await fetch_plans(auth)
        if plans:
            pid = plans[0].get("id") if isinstance(plans[0], dict) else getattr(plans[0], "id", None)
            if pid:
                async with httpx.AsyncClient(timeout=15) as c:
                    r = await c.get(
                        f"{base}/training/plan/detail",
                        params={"id": str(pid), "region": 1},
                        headers=headers,
                    )
                    b = r.json()
                    if b.get("result") == "0000":
                        ok("plan/detail", f"id={pid}")
                    else:
                        fail("plan/detail", f"result={b.get('result')} {b.get('message','')[:60]}")
            else:
                fail("plan/detail", "no id field")
        else:
            fail("plan/detail", "no plans to test (skip)")
    except Exception as e:
        fail("plan/detail", str(e)[:100])

    # ---- 4. /activity/team/query (KNOWN CRACKED) ----
    print("--- /activity/team/query ---")
    fail("activity/team/query", "needs parameter cracking (like filter)")

    # ---- 5. /training/plan/copy (internal, need plan detail first) ----
    print("--- /training/plan/copy ---")
    try:
        plans = await fetch_plans(auth)
        if plans:
            pid = plans[0].get("id") if isinstance(plans[0], dict) else getattr(plans[0], "id", None)
            if pid:
                # first get detail
                async with httpx.AsyncClient(timeout=15) as c:
                    r = await c.get(f"{base}/training/plan/detail", params={"id": str(pid), "region": 1}, headers=headers)
                    detail = r.json().get("data", {})
                    if detail:
                        resp = await c.post(
                            f"{base}/training/plan/copy",
                            params={"id": detail.get("id"), "region": 1},
                            json=detail,
                            headers=json_headers,
                        )
                        b = resp.json()
                        if b.get("result") == "0000":
                            ok("plan/copy", f"copied id={b.get('data',{}).get('id','?')}")
                        else:
                            fail("plan/copy", f"result={b.get('result')} {b.get('message','')[:60]}")
            else:
                fail("plan/copy", "no id field")
        else:
            fail("plan/copy", "no plans to test (skip)")
    except Exception as e:
        fail("plan/copy", str(e)[:100])

    # ---- Summary ----
    print(f"\n=== {sum(1 for r in results if r[0]=='OK')}/{len(results)} passed ===")
    for status, name, detail in results:
        print(f"  [{status}] {name}: {detail}")


if __name__ == "__main__":
    asyncio.run(main())

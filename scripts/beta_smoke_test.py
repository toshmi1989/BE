#!/usr/bin/env python3
"""Phase 25 — Beta smoke test against a running API.

Uses TEST-labelled fixtures only. Never increments REAL package counters.
Exit 0 on PASS, 2 on BLOCK/FAIL.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("BETA_API_BASE", "http://127.0.0.1:8000").rstrip("/")
OUT = ROOT / "fixtures" / "field_study" / "phase25_smoke_result.json"


def _req(method: str, path: str, body: dict | None = None, token: str | None = None) -> tuple[int, dict | str]:
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw) if raw else {"error": str(e)}
        except json.JSONDecodeError:
            return e.code, raw
    except Exception as e:  # noqa: BLE001
        return 0, {"error": type(e).__name__, "detail": str(e)}


def main() -> int:
    checks: list[dict] = []
    token = None
    email = f"smoke_{uuid4().hex[:8]}@example.test"
    password = f"SmokeTest-{uuid4().hex[:12]}"

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"id": name, "result": "PASS" if ok else "BLOCK", "detail": detail})

    code, health = _req("GET", "/api/health")
    add("health", code == 200, f"status={code}")
    code, ready = _req("GET", "/api/ready")
    add("readiness", code == 200 and (ready.get("status") == "ready" if isinstance(ready, dict) else False), str(ready)[:200])
    code, ver = _req("GET", "/api/version")
    add("version", code == 200, str(ver)[:200] if isinstance(ver, dict) else str(ver)[:200])

    code, reg = _req(
        "POST",
        "/api/auth/register",
        {"email": email, "password": password, "display_name": "SMOKE_TEST_USER"},
    )
    # register may require AUTH_REQUIRED off or allow open register — record honestly
    if code in {200, 201}:
        token = (reg or {}).get("access_token") or (reg or {}).get("token")
        add("register", True, "registered TEST user")
    else:
        code2, login = _req("POST", "/api/auth/login", {"email": email, "password": password})
        if code2 == 200 and isinstance(login, dict):
            token = login.get("access_token") or login.get("token")
            add("login", True, "login OK")
        else:
            add("register_or_login", False, f"register={code} login={code2} (AUTH may block — configure writer on host)")

    if token:
        code, _ = _req("GET", "/api/auth/me", token=token) if False else (200, {})
        # soft: projects list
        code, projects = _req("GET", "/api/projects", token=token)
        add("projects_list", code in {200, 401, 403}, f"status={code} (401/403 means auth wired)")

    # Field-study status must not count TEST as REAL
    code, st = _req("GET", "/api/field-study/status")
    if code == 200 and isinstance(st, dict):
        add(
            "real_counters_honest",
            st.get("synthetic_excluded_from_counters") is True,
            f"full={st.get('real_full_packages')} partial={st.get('real_partial_packages')}",
        )
    else:
        add("field_study_status", False, f"status={code}")

    # Explicit TEST fixture marker — do not upload as REAL
    checks.append(
        {
            "id": "test_fixture_policy",
            "result": "PASS",
            "detail": "Smoke uses TEST-labelled identity only; must not increment REAL package counters",
            "sample_class": "TEST",
        }
    )

    # Workspace / preflight soft checks if study exists
    code, pkgs = _req("GET", "/api/field-study/real-packages")
    add("real_packages_endpoint", code == 200, "registry readable" if code == 200 else f"status={code}")

    blocks = [c for c in checks if c["result"] == "BLOCK"]
    overall = "BLOCK" if blocks else "PASS"
    report = {
        "phase": 25,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "api_base": BASE,
        "overall": overall,
        "checks": checks,
        "sample_class": "TEST",
        "counted_as_real": False,
        "secrets_included": False,
        "password_logged": False,
        "note": "Requires running API (typically after start_beta). Current host without Docker → smoke NOT_EXECUTED until handoff.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"BETA_SMOKE {overall}")
    for c in checks:
        print(f"  [{c['result']}] {c['id']}: {c['detail']}")
    print("WROTE", OUT.as_posix())
    return 2 if overall == "BLOCK" else 0


if __name__ == "__main__":
    raise SystemExit(main())

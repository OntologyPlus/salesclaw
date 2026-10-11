"""确定性轨迹 schema / 契约校验。"""
from __future__ import annotations

from typing import Any


REQUIRED_CHAT_KEYS = ("session_id", "response", "intent")


def check_chat_response(result: dict, golden: dict) -> list[str]:
    """返回失败原因列表；空列表表示通过。"""
    errors: list[str] = []
    if not isinstance(result, dict):
        return ["result_not_dict"]

    for k in REQUIRED_CHAT_KEYS:
        if k not in result:
            errors.append(f"missing_key:{k}")

    expect = golden.get("expect") or {}
    if "intent" in expect and result.get("intent") != expect["intent"]:
        errors.append(
            f"intent_mismatch: got={result.get('intent')} want={expect['intent']}"
        )

    if expect.get("min_response_len"):
        resp = result.get("response") or ""
        if len(resp) < int(expect["min_response_len"]):
            errors.append(f"response_too_short:{len(resp)}")

    if expect.get("must_not_contain"):
        resp = result.get("response") or ""
        for frag in expect["must_not_contain"]:
            if frag in resp:
                errors.append(f"forbidden_fragment:{frag}")

    if expect.get("tools_allowed") is not None:
        used = result.get("actions_called") or []
        # also accept tools_used names
        for t in result.get("tools_used") or []:
            if isinstance(t, dict) and t.get("name"):
                used.append(t["name"])
        allowed = set(expect["tools_allowed"])
        for name in used:
            if name and name not in allowed:
                errors.append(f"tool_not_allowed:{name}")

    if expect.get("aborted") is True and not result.get("aborted"):
        errors.append("expected_aborted")

    return errors


def score_trajectory(result: dict, golden: dict) -> dict[str, Any]:
    errors = check_chat_response(result, golden)
    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "case_id": golden.get("id"),
        "intent": result.get("intent"),
        "run_id": result.get("run_id"),
    }

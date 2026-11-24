"""Підтвердження людини перед ризиковим інструментом."""

from __future__ import annotations

RISKY_TOOLS = {"book_stay"}


def approval_request(name: str, args: dict) -> dict:
    """Що показати людині, поки граф стоїть на interrupt."""
    return {
        "action": name,
        "args": args,
        "message": (
            "Підтвердіть ризикову дію:\n"
            f"Tool: {name}\n"
            f"Параметри: {args}"
        ),
    }


def parse_decision(approval: object, original_args: dict) -> tuple[bool, dict, str]:
    """Розбирає approve, reject і edit.

    edit — це approved=true і словник args із полями, які треба замінити.
    Будь-яка відповідь без словника approved вважається відмовою.
    """
    if not isinstance(approval, dict):
        return False, dict(original_args), "Очікувався словник із полем approved"
    approved = bool(approval.get("approved"))
    reason = str(approval.get("reason") or "").strip()
    args = dict(original_args)
    extra = approval.get("args")
    if isinstance(extra, dict):
        args.update(extra)
    return approved, args, reason

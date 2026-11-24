"""Живі сценарії: план, RAG, бюджет, відновлення, сесії та HITL."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from config import get_settings
from plan_execute import ROOT, build_app, close_app, initial_state

DB_PATH = ROOT / "agent_state.db"
PERSIST_THREAD = "session-persist"

QUERY_RAG = (
    "Дай довідку з бази знань для вихідних у Львові: "
    "типові ціни на житло, сезон поїздки і транспорт містом. "
    "Не рахуй бюджет і не бронюй житло."
)
QUERY_BUDGET = (
    "Перевір бюджет поїздки інструментом check_budget і більше нічого не роби. "
    "Ліміт 5000 грн, дорога 900 грн, житло 2000 грн, активності 300 грн, їжа 700 грн."
)
QUERY_REPLAN = (
    "Перевір бюджет вихідних і після цього забронюй житло. "
    "Ліміт 3000 грн, дорога 1400, житло 2200, активності 400, їжа 900. "
    "Готель Леополіс, заїзд 2026-12-05, 2 ночі, сума бронювання 2200 грн. "
    "Довідку з бази не шукай: спершу check_budget, потім book_stay."
)
QUERY_HITL = (
    "Забронюй житло і нічого більше не шукай. "
    "Місце: готель Леополіс. Заїзд: 2026-12-05. Ночей: 2. Сума: 4200 грн."
)


def _utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def _require_key() -> None:
    if not get_settings()["api_key"]:
        raise SystemExit("Не задано DEEPSEEK_API_KEY. Скопіюй .env.example у .env і впиши ключ.")


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": 40}


def _interrupt_values(result: object, app, config: dict) -> list:
    found: list = []
    if isinstance(result, dict):
        raw = result.get("__interrupt__")
        if raw:
            found.extend(raw if isinstance(raw, (list, tuple)) else [raw])
    state = app.get_state(config)
    for task in getattr(state, "tasks", ()) or ():
        for item in getattr(task, "interrupts", ()) or ():
            found.append(item)
    unique: list = []
    seen: set[str] = set()
    for item in found:
        key = repr(_value_of(item))
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _value_of(item: object) -> object:
    return getattr(item, "value", item)


def _print_header(title: str) -> None:
    print(f"\n===== {title} =====")


def _print_state(app, config: dict, label: str) -> None:
    state = app.get_state(config)
    values = state.values or {}
    print(f"{label} thread={config['configurable']['thread_id']}")
    print(f"goal: {values.get('goal')}")
    print(f"plan: {values.get('plan')}")
    print(f"step: {values.get('current_step')}")
    print(f"replan_count: {values.get('replan_count')}")
    print(f"completed: {values.get('completed')}")
    for message in values.get("messages") or []:
        content = getattr(message, "content", "")
        if isinstance(content, str) and content.startswith(("Ціль:", "Новий план:", "Завершено:")):
            print(f"note: {content}")
    for line in values.get("results") or []:
        print(f"result: {line}")


def run_until_end(query: str, thread_id: str, title: str) -> None:
    _require_key()
    _print_header(title)
    app = build_app(db_path=DB_PATH)
    config = _config(thread_id)
    try:
        result = app.invoke(initial_state(query), config)
        pauses = _interrupt_values(result, app, config)
        if pauses:
            for item in pauses:
                print(_value_of(item))
            _print_state(app, config, "PAUSED")
            raise SystemExit("Граф зупинився на interrupt, хоча сценарій цього не чекав.")
        _print_state(app, config, "FINAL")
    finally:
        close_app(app)


def persist_start() -> None:
    """Перший процес: пауза після executor, до рішення replanner. Файл лишається на диску."""
    _require_key()
    _print_header("persist-start")
    app = build_app(db_path=DB_PATH, interrupt_after=["executor"])
    config = _config(PERSIST_THREAD)
    try:
        app.invoke(initial_state(QUERY_BUDGET), config)
        snapshot = app.get_state(config)
        values = snapshot.values or {}
        print(f"next: {snapshot.next}")
        if values.get("completed") or int(values.get("current_step") or 0) < 1 or not snapshot.next:
            _print_state(app, config, "PAUSED")
            raise SystemExit("Не вдалося зупинитись після першого кроку.")
        _print_state(app, config, "PAUSED")
    finally:
        close_app(app)


def persist_resume() -> None:
    """Другий процес: читає той самий thread_id і доганяє план."""
    _require_key()
    _print_header("persist-resume")
    app = build_app(db_path=DB_PATH)
    config = _config(PERSIST_THREAD)
    try:
        _print_state(app, config, "RESTORED")
        restored = app.get_state(config).values or {}
        if int(restored.get("current_step") or 0) < 1:
            raise SystemExit("Стан не відновлено: current_step < 1. Спочатку запусти persist-start.")
        if restored.get("completed"):
            raise SystemExit("Перший процес уже завершив план. Пауза не спрацювала.")
        print(f"next: {app.get_state(config).next}")
        app.invoke(None, config)
        _print_state(app, config, "FINAL")
    finally:
        close_app(app)


def run_threads() -> None:
    """Дві сесії в одному файлі не бачать плани одна одної."""
    _require_key()
    _print_header("threads")
    app = build_app(db_path=DB_PATH)
    config_a = _config("session-001")
    config_b = _config("session-002")
    try:
        app.invoke(initial_state(QUERY_RAG), config_a)
        app.invoke(initial_state(QUERY_BUDGET), config_b)
        _print_state(app, config_a, "SESSION-001")
        _print_state(app, config_b, "SESSION-002")
    finally:
        close_app(app)


def run_hitl(mode: str) -> None:
    """approve виконує book_stay, reject ні, edit міняє параметри перед викликом."""
    _require_key()
    _print_header(f"hitl-{mode}")
    app = build_app(db_path=DB_PATH)
    thread_id = f"hitl-{mode}"
    config = _config(thread_id)
    try:
        result = app.invoke(initial_state(QUERY_HITL), config)
        pauses = _interrupt_values(result, app, config)
        if not pauses:
            _print_state(app, config, "FINAL")
            raise SystemExit("Граф не зупинився на ризиковій дії.")
        print("INTERRUPT:")
        for item in pauses:
            print(_value_of(item))
        if mode == "approve":
            resume = {"approved": True}
        elif mode == "reject":
            resume = {"approved": False, "reason": "Занадто дорого"}
        elif mode == "edit":
            resume = {
                "approved": True,
                "args": {"nights": 1, "total_uah": 2100},
            }
        else:
            raise SystemExit(f"Невідомий режим HITL: {mode}")
        app.invoke(Command(resume=resume), config)
        _print_state(app, config, "FINAL")
        user_messages = [
            message.content
            for message in (app.get_state(config).values or {}).get("messages", [])
            if isinstance(message, HumanMessage)
        ]
        print(f"user: {user_messages[:1]}")
    finally:
        close_app(app)


def reset_db() -> None:
    for suffix in ("", "-wal", "-shm"):
        path = Path(str(DB_PATH) + suffix)
        path.unlink(missing_ok=True)


def run_all() -> None:
    """Скидає базу і проганяє сценарії окремими процесами, щоб відновлення було справжнім."""
    _require_key()
    reset_db()
    steps = [
        ["rag"],
        ["budget"],
        ["replan"],
        ["threads"],
        ["persist-start"],
        ["persist-resume"],
        ["hitl-approve"],
        ["hitl-reject"],
        ["hitl-edit"],
    ]
    log = ROOT / "demo_output.txt"
    chunks: list[str] = []
    for args in steps:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "demo.py"), *args],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        text = (proc.stdout or "") + (proc.stderr or "")
        chunks.append(text)
        print(text, end="" if text.endswith("\n") or not text else "\n")
        if proc.returncode != 0:
            log.write_text("".join(chunks), encoding="utf-8")
            raise SystemExit(f"Сценарій {args[0]} завершився з кодом {proc.returncode}")
    log.write_text("".join(chunks), encoding="utf-8")
    print(f"\nВивід збережено в {log}")


def main() -> None:
    _utf8_stdio()
    parser = argparse.ArgumentParser(description="Демонстрація Plan-and-Execute агента")
    parser.add_argument(
        "command",
        choices=[
            "rag",
            "budget",
            "replan",
            "threads",
            "persist-start",
            "persist-resume",
            "hitl-approve",
            "hitl-reject",
            "hitl-edit",
            "all",
        ],
    )
    command = parser.parse_args().command
    if command == "rag":
        run_until_end(QUERY_RAG, "demo-rag", "rag")
    elif command == "budget":
        run_until_end(QUERY_BUDGET, "demo-budget", "budget")
    elif command == "replan":
        run_until_end(QUERY_REPLAN, "demo-replan", "replan")
    elif command == "threads":
        run_threads()
    elif command == "persist-start":
        persist_start()
    elif command == "persist-resume":
        persist_resume()
    elif command == "hitl-approve":
        run_hitl("approve")
    elif command == "hitl-reject":
        run_hitl("reject")
    elif command == "hitl-edit":
        run_hitl("edit")
    elif command == "all":
        run_all()


if __name__ == "__main__":
    main()

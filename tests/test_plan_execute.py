"""Граф на підставній моделі: план, replan, сесії та підтвердження броні."""

from __future__ import annotations

from langchain_core.messages import AIMessage
from langgraph.types import Command

from langchain_core.tools import tool as as_tool

from knowledge import SearchInput
from plan_execute import Plan, ReplanDecision, build_app, close_app, initial_state
from tools import BookStayInput, book_stay, check_budget, estimate_duration


class ScriptedLLM:
    """Віддає готові Plan, ReplanDecision і виклики інструментів без мережі."""

    def __init__(self, plans: list, decisions: list, messages: list):
        self.plans = list(plans)
        self.decisions = list(decisions)
        self.messages = list(messages)

    def with_structured_output(self, schema, **kwargs):
        parent = self

        class Bound:
            def invoke(self, messages):
                if schema.__name__ == "Plan":
                    return parent.plans.pop(0)
                if schema.__name__ == "ReplanDecision":
                    return parent.decisions.pop(0)
                raise AssertionError(f"Неочікувана схема {schema}")

        return Bound()

    def bind_tools(self, tools):
        parent = self

        class Bound:
            def invoke(self, prompt):
                return parent.messages.pop(0)

        return Bound()


def tool_message(name: str, args: dict, call_id: str = "call-1") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}],
    )


def finish(reason: str = "готово") -> ReplanDecision:
    return ReplanDecision(action="finish", updated_steps=None, reasoning=reason)


def budget_args() -> dict:
    return {
        "limit_uah": 5000,
        "transport_uah": 900,
        "stay_uah": 2000,
        "activities_uah": 300,
        "meals_uah": 700,
    }


def open_graph(tmp_path, llm, tools=None):
    app = build_app(llm, db_path=tmp_path / "agent_state.db", tools=tools)
    return app


def config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": 40}


def interrupt_values(result, app, thread_id: str) -> list:
    found = []
    if isinstance(result, dict) and result.get("__interrupt__"):
        raw = result["__interrupt__"]
        found.extend(raw if isinstance(raw, (list, tuple)) else [raw])
    state = app.get_state(config(thread_id))
    for task in getattr(state, "tasks", ()) or ():
        found.extend(getattr(task, "interrupts", ()) or ())
    return found


def test_check_budget_and_duration_validation():
    assert "fits" in check_budget.invoke(budget_args())
    deficit = check_budget.invoke(
        {
            "limit_uah": 3000,
            "transport_uah": 1400,
            "stay_uah": 2200,
            "activities_uah": 400,
            "meals_uah": 900,
        }
    )
    assert "deficit" in deficit
    assert "150" in estimate_duration.invoke({"category": "музей"})
    try:
        BookStayInput(place="A", check_in="05-12-2026", nights=0, total_uah=-1)
    except Exception as exc:  # noqa: BLE001 — тут важливий сам факт відмови схеми
        assert "ноч" in str(exc).lower() or "дату" in str(exc).lower() or "формат" in str(exc).lower()
    else:
        raise AssertionError("Схема бронювання пропустила невалідні аргументи")


def test_planner_executor_finish(tmp_path):
    llm = ScriptedLLM(
        plans=[Plan(goal="перевірити ліміт", steps=["Порахуй бюджет check_budget"])],
        decisions=[],
        messages=[tool_message("check_budget", budget_args())],
    )
    app = open_graph(tmp_path, llm)
    try:
        result = app.invoke(initial_state("Порахуй ліміт"), config("finish"))
        assert result["completed"] is True
        assert result["current_step"] == 1
        assert any("fits" in line for line in result["results"])
        assert "check_budget" in result["results"][0]
    finally:
        close_app(app)


def test_continue_runs_second_step(tmp_path):
    llm = ScriptedLLM(
        plans=[
            Plan(
                goal="оцінити день",
                steps=["Оціни тривалість музею", "Порахуй бюджет check_budget"],
            )
        ],
        decisions=[ReplanDecision(action="continue", updated_steps=None, reasoning="крок ще потрібен")],
        messages=[
            tool_message("estimate_duration", {"category": "музей"}),
            tool_message("check_budget", budget_args()),
        ],
    )
    app = open_graph(tmp_path, llm)
    try:
        result = app.invoke(initial_state("Склади день"), config("continue"))
        assert result["current_step"] == 2
        assert result["replan_count"] == 0
        assert "estimate_duration" in result["results"][0]
        assert "fits" in result["results"][1]
        assert result["completed"] is True
    finally:
        close_app(app)


def test_replan_keeps_finished_steps(tmp_path):
    llm = ScriptedLLM(
        plans=[
            Plan(
                goal="дешевший вікенд",
                steps=["Оціни тривалість музею", "Забронюй дорогий готель"],
            )
        ],
        decisions=[
            ReplanDecision(
                action="replan",
                updated_steps=["Порахуй бюджет check_budget замість броні"],
                reasoning="попереду була бронь, її прибираємо",
            )
        ],
        messages=[
            tool_message("estimate_duration", {"category": "музей"}),
            tool_message("check_budget", budget_args()),
        ],
    )
    app = open_graph(tmp_path, llm)
    try:
        result = app.invoke(initial_state("Зміни план"), config("replan"))
        assert result["plan"] == [
            "Оціни тривалість музею",
            "Порахуй бюджет check_budget замість броні",
        ]
        assert result["replan_count"] == 1
        assert result["current_step"] == 2
        assert "Заброньовано" not in " ".join(result["results"])
        assert "fits" in result["results"][1]
    finally:
        close_app(app)


def test_threads_keep_separate_state(tmp_path):
    class AwareLLM:
        def with_structured_output(self, schema, **kwargs):
            def invoke(messages):
                text = str(messages)
                if schema.__name__ == "Plan":
                    if "5000" in text:
                        return Plan(goal="бюджет сесії", steps=["check_budget для 5000"])
                    return Plan(goal="львів сесії", steps=["search_knowledge про житло"])
                return finish()

            return type("Bound", (), {"invoke": staticmethod(invoke)})()

        def bind_tools(self, tools):
            def invoke(prompt):
                step = ""
                for line in str(prompt).splitlines():
                    if line.startswith("Крок:"):
                        step = line
                if "check_budget" in step:
                    return tool_message("check_budget", budget_args())
                return tool_message("search_knowledge", {"query": "житло Львів"})

            return type("Bound", (), {"invoke": staticmethod(invoke)})()

    @as_tool("search_knowledge", args_schema=SearchInput)
    def search_fake(query: str) -> str:
        """Довідка з бази знань для тесту сесій."""
        return f"Довідка: {query}"

    app = open_graph(tmp_path, AwareLLM(), tools=[search_fake, estimate_duration, check_budget, book_stay])
    try:
        app.invoke(initial_state("Що відомо про Львів?"), config("session-001"))
        app.invoke(initial_state("Ліміт 5000 грн"), config("session-002"))
        first = app.get_state(config("session-001")).values
        second = app.get_state(config("session-002")).values
        assert first["goal"] == "львів сесії"
        assert second["goal"] == "бюджет сесії"
        assert first["results"] != second["results"]
        assert any("search_knowledge" in line for line in first["results"])
        assert any("check_budget" in line for line in second["results"])
    finally:
        close_app(app)


def test_resume_after_new_connection(tmp_path):
    db = tmp_path / "agent_state.db"
    llm = ScriptedLLM(
        plans=[Plan(goal="два кроки", steps=["Оціни музей", "Порахуй бюджет"])],
        decisions=[ReplanDecision(action="continue", updated_steps=None, reasoning="є ще крок")],
        messages=[
            tool_message("estimate_duration", {"category": "музей"}),
            tool_message("check_budget", budget_args()),
        ],
    )
    app = build_app(llm, db_path=db)
    try:
        for _chunk in app.stream(initial_state("Почни і зупинись"), config("session-persist"), stream_mode="updates"):
            values = app.get_state(config("session-persist")).values
            if int(values.get("current_step") or 0) >= 1 and not values.get("pending_call"):
                break
        paused = app.get_state(config("session-persist")).values
        assert paused["current_step"] == 1
        assert paused["completed"] is False
    finally:
        close_app(app)

    resumed = build_app(llm, db_path=db)
    try:
        restored = resumed.get_state(config("session-persist")).values
        assert restored["plan"][0] == "Оціни музей"
        assert restored["current_step"] == 1
        result = resumed.invoke(None, config("session-persist"))
        assert result["completed"] is True
        assert result["current_step"] == 2
        assert "fits" in result["results"][1]
    finally:
        close_app(resumed)


def test_pause_after_executor_survives_new_connection(tmp_path):
    db = tmp_path / "pause.db"
    llm = ScriptedLLM(
        plans=[Plan(goal="пауза", steps=["Порахуй бюджет check_budget"])],
        decisions=[],
        messages=[tool_message("check_budget", budget_args())],
    )
    app = build_app(llm, db_path=db, interrupt_after=["executor"])
    try:
        app.invoke(initial_state("Зупинись після кроку"), config("pause"))
        paused = app.get_state(config("pause"))
        assert paused.values["current_step"] == 1
        assert paused.values["completed"] is False
        assert "fits" in paused.values["results"][0]
        assert paused.next
    finally:
        close_app(app)

    resumed = build_app(llm, db_path=db)
    try:
        restored = resumed.get_state(config("pause"))
        assert restored.values["current_step"] == 1
        assert restored.values["completed"] is False
        result = resumed.invoke(None, config("pause"))
        assert result["completed"] is True
        assert result["goal"] == "пауза"
    finally:
        close_app(resumed)


def test_hitl_approve_reject_and_edit(tmp_path):
    calls: list[dict] = []

    def book_spy(place: str, check_in: str, nights: int, total_uah: float) -> str:
        """Ризикове бронювання для тесту."""
        calls.append(
            {
                "place": place,
                "check_in": check_in,
                "nights": nights,
                "total_uah": total_uah,
            }
        )
        return book_stay.invoke(
            {
                "place": place,
                "check_in": check_in,
                "nights": nights,
                "total_uah": total_uah,
            }
        )

    spy = as_tool("book_stay", args_schema=BookStayInput)(book_spy)
    booking = {
        "place": "готель Леополіс",
        "check_in": "2026-12-05",
        "nights": 2,
        "total_uah": 4200,
    }

    def run(mode: str, thread_id: str):
        llm = ScriptedLLM(
            plans=[Plan(goal="бронь", steps=["Забронюй готель Леополіс"])],
            decisions=[],
            messages=[tool_message("book_stay", booking)],
        )
        app = build_app(llm, db_path=tmp_path / f"{thread_id}.db", tools=[check_budget, spy])
        try:
            result = app.invoke(initial_state("Забронюй"), config(thread_id))
            pauses = interrupt_values(result, app, thread_id)
            assert pauses, "очікувався interrupt перед book_stay"
            if mode == "approve":
                resume = {"approved": True}
            elif mode == "reject":
                resume = {"approved": False, "reason": "Занадто дорого"}
            else:
                resume = {"approved": True, "args": {"nights": 1, "total_uah": 2100}}
            done = app.invoke(Command(resume=resume), config(thread_id))
            return done
        finally:
            close_app(app)

    approved = run("approve", "hitl-approve")
    assert calls[-1]["nights"] == 2
    assert any("Заброньовано" in line for line in approved["results"])

    before = len(calls)
    rejected = run("reject", "hitl-reject")
    assert len(calls) == before
    assert any("Відхилено оператором" in line and "Занадто дорого" in line for line in rejected["results"])
    assert not any("Заброньовано" in line for line in rejected["results"])

    edited = run("edit", "hitl-edit")
    assert calls[-1]["nights"] == 1
    assert calls[-1]["total_uah"] == 2100
    assert any("2100.00" in line for line in edited["results"])


def test_invalid_booking_does_not_interrupt(tmp_path):
    llm = ScriptedLLM(
        plans=[Plan(goal="зламана бронь", steps=["Забронюй з нулем ночей"])],
        decisions=[],
        messages=[
            tool_message(
                "book_stay",
                {
                    "place": "готель",
                    "check_in": "2026-12-05",
                    "nights": 0,
                    "total_uah": 100,
                },
            )
        ],
    )
    app = open_graph(tmp_path, llm)
    try:
        result = app.invoke(initial_state("Забронюй невалідно"), config("bad-book"))
        assert not interrupt_values(result, app, "bad-book")
        assert result["completed"] is True
        assert any("Помилка валідації" in line for line in result["results"])
        assert not any("Заброньовано" in line for line in result["results"])
    finally:
        close_app(app)

"""Граф Plan-and-Execute: planner, executor і replanner зі збереженням стану."""

from __future__ import annotations

import json
import operator
import sqlite3
from pathlib import Path
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel, Field, ValidationError

from config import build_llm, invoke_structured
from hitl import RISKY_TOOLS, approval_request, parse_decision
from knowledge import search_knowledge
from tools import book_stay, check_budget, estimate_duration

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "agent_state.db"
MAX_STEPS = 8
MAX_REPLANS = 2

PLANNER_PROMPT = """Склади план для задачі користувача.
Доступні інструменти виконавця, кожен крок викликає рівно один:
- search_knowledge: довідка з бази знань (ціни-орієнтири, сезон, транспорт, музеї, дефіцит). Не додає суми і не бронює.
- estimate_duration: типова тривалість категорії в хвилинах.
- check_budget: сума вже відомих витрат у грн проти ліміту. Потрібні ліміт, дорога, житло, активності, їжа.
- book_stay: незворотне бронювання житла. Додавай лише якщо користувач прямо просить забронювати.

Правила:
- Від 1 до 5 коротких кроків українською.
- У кроці назви інструмент і підстав аргументи, які вже є в задачі.
- Не планую пошук в інтернеті.
- Якщо просять лише порахувати ліміт, залиш один крок check_budget.
- Якщо просять лише довідку, залиш кроки search_knowledge і за потреби estimate_duration.
- book_stay не став перед check_budget, якщо ліміт ще не перевірений.
- Не ховай умову «якщо deficit» всередині одного кроку. Перевірка ліміту і бронювання — два окремі кроки.
"""

EXECUTOR_PROMPT = """Виконай рівно поточний крок і виклич один інструмент.
Не вигадуй ціни. Довідку бери з search_knowledge, суму рахуй через check_budget.
book_stay викликай лише якщо крок прямо вимагає бронювання.
Аргументи бери з тексту кроку і попередніх результатів, нічого не підставляй від себе.
"""

REPLANNER_PROMPT = """Оціни прогрес і поверни одне рішення.
- continue: наступний крок плану ще потрібен без зміни формулювання.
- replan: заміни лише НЕВИКОНАНІ кроки. updated_steps не містить уже зробленого. Якщо в результатах є «Вердикт: deficit», а в залишку є book_stay або бронювання, action обов'язково replan, без жодного кроку бронювання. Замість броні постав один крок estimate_duration для прогулянки.
- finish: ціль досягнута, бронювання відхилено або корисної дії більше немає.

Не повторюй виконані кроки. Якщо залишок плану порожній, обирай finish.
"""


class Plan(BaseModel):
    """План виконання задачі."""

    goal: str = Field(description="Головна ціль задачі")
    steps: list[str] = Field(description="Список кроків для досягнення цілі")


class ReplanDecision(BaseModel):
    """Рішення replanner: продовжити, перепланувати або завершити."""

    action: Literal["continue", "replan", "finish"] = Field(
        description="continue=виконати наступний крок, replan=змінити план, finish=завершити"
    )
    updated_steps: list[str] | None = Field(
        default=None,
        description="Лише ще не виконані кроки, якщо action=replan",
    )
    reasoning: str = Field(description="Пояснення рішення")


class PlanExecuteState(TypedDict):
    messages: Annotated[list, operator.add]
    goal: str
    plan: list[str]
    current_step: int
    results: list[str]
    completed: bool
    replan_count: int
    pending_call: dict | None


def default_tools() -> list:
    """Чотири інструменти виконавця: довідка, тривалість, бюджет, бронь."""
    return [search_knowledge, estimate_duration, check_budget, book_stay]


def initial_state(query: str) -> PlanExecuteState:
    return {
        "messages": [HumanMessage(content=query)],
        "goal": "",
        "plan": [],
        "current_step": 0,
        "results": [],
        "completed": False,
        "replan_count": 0,
        "pending_call": None,
    }


def message_text(message: object) -> str:
    content = getattr(message, "content", "") or getattr(message, "text", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text") or item))
        return "\n".join(parts)
    return str(content or "")


def user_text(state: PlanExecuteState) -> str:
    """Останнє повідомлення людини. Повторний запуск тієї самої сесії не чіпляється за старий запит."""
    last = ""
    for message in state["messages"]:
        if isinstance(message, HumanMessage):
            last = message_text(message)
    return last


def tool_calls_of(message: object) -> list:
    calls = getattr(message, "tool_calls", None) or []
    return list(calls)


def call_args(tool_call: dict) -> dict:
    args = tool_call.get("args") or {}
    if isinstance(args, str):
        args = json.loads(args)
    return dict(args)


def open_checkpointer(db_path: str | Path):
    """Файл SQLite, не :memory:. З'єднання треба закрити через close_app."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    from langgraph.checkpoint.sqlite import SqliteSaver

    conn = sqlite3.connect(str(path), check_same_thread=False)
    saver = SqliteSaver(conn)
    if hasattr(saver, "setup"):
        saver.setup()
    return saver, conn


def close_app(app) -> None:
    conn = getattr(app, "checkpointer_conn", None)
    if conn is not None:
        conn.close()
        app.checkpointer_conn = None


def build_app(
    llm=None,
    *,
    db_path: str | Path = DEFAULT_DB,
    tools: list | None = None,
    interrupt_after: list[str] | None = None,
):
    """Збирає граф із файловим SqliteSaver. Без checkpointer HITL не відновлюється."""
    llm = llm or build_llm()
    tool_list = list(tools or default_tools())
    tool_map = {item.name: item for item in tool_list}
    saver, conn = open_checkpointer(db_path)

    def run_tool(name: str, args: dict) -> str:
        tool = tool_map.get(name)
        if tool is None:
            return f"Невідомий інструмент: {name}"
        try:
            result = tool.invoke(args)
        except Exception as exc:  # noqa: BLE001 — валідація повертається в результати кроку
            return f"Помилка валідації: {exc}"
        return f"{name}: {result}"

    def advance(state: PlanExecuteState, step_idx: int, text: str, *, clear_pending: bool) -> dict:
        payload = {
            "current_step": step_idx + 1,
            "results": [*state["results"], f"Крок {step_idx + 1}: {text}"],
            "messages": [AIMessage(content=f"Виконано крок {step_idx + 1}: {text}")],
        }
        if clear_pending:
            payload["pending_call"] = None
        return payload

    def resolve_pending(state: PlanExecuteState) -> dict:
        """Другий захід у вузол: interrupt уже має збережений виклик, модель не кличемо знову."""
        pending = state["pending_call"] or {}
        approval = interrupt(approval_request(str(pending.get("name")), dict(pending.get("args") or {})))
        approved, args, reason = parse_decision(approval, dict(pending.get("args") or {}))
        step_idx = int(pending.get("step_idx", state["current_step"]))
        name = str(pending.get("name"))
        if not approved:
            text = f"Відхилено оператором: {reason}".rstrip()
            return advance(state, step_idx, text, clear_pending=True)
        tool = tool_map.get(name)
        schema = getattr(tool, "args_schema", None)
        if schema is not None:
            try:
                schema.model_validate(args)
            except ValidationError as exc:
                return advance(state, step_idx, f"Помилка валідації: {exc}", clear_pending=True)
        return advance(state, step_idx, run_tool(name, args), clear_pending=True)

    def planner_node(state: PlanExecuteState) -> dict:
        """Генерує Plan через structured output."""
        task = user_text(state)
        prompt = f"{PLANNER_PROMPT}\nЗадача: {task}"
        raw = invoke_structured(llm, Plan, [HumanMessage(content=prompt)])
        plan = raw if isinstance(raw, Plan) else Plan.model_validate(raw)
        if not plan.steps:
            return {
                "goal": plan.goal,
                "plan": [],
                "current_step": 0,
                "results": [],
                "completed": True,
                "pending_call": None,
                "messages": [AIMessage(content=f"Ціль: {plan.goal}. План порожній.")],
            }
        return {
            "goal": plan.goal,
            "plan": list(plan.steps),
            "current_step": 0,
            "results": [],
            "completed": False,
            "replan_count": 0,
            "pending_call": None,
            "messages": [AIMessage(content=f"Ціль: {plan.goal}. План: {list(plan.steps)}")],
        }

    def executor_node(state: PlanExecuteState) -> dict:
        """Виконує один крок. Перед book_stay лише запам'ятовує виклик."""
        if state.get("pending_call"):
            return resolve_pending(state)

        step_idx = state["current_step"]
        plan = state["plan"]
        if state.get("completed") or step_idx >= len(plan) or step_idx >= MAX_STEPS:
            return {"completed": True, "pending_call": None}

        current_step = plan[step_idx]
        prompt = (
            f"{EXECUTOR_PROMPT}\n"
            f"Крок: {current_step}\n"
            f"Попередні результати: {state['results']}"
        )
        response = llm.bind_tools(tool_list).invoke(prompt)
        calls = tool_calls_of(response)
        if not calls:
            text = message_text(response).strip() or "Інструмент не викликано"
            return advance(state, step_idx, text, clear_pending=False)

        call = calls[0]
        name = str(call.get("name", ""))
        args = call_args(call)
        if name in RISKY_TOOLS:
            tool = tool_map.get(name)
            schema = getattr(tool, "args_schema", None)
            if schema is not None:
                try:
                    clean = schema.model_validate(args).model_dump()
                except ValidationError as exc:
                    return advance(state, step_idx, f"Помилка валідації: {exc}", clear_pending=False)
            else:
                clean = args
            return {
                "pending_call": {"name": name, "args": clean, "step_idx": step_idx},
                "messages": [AIMessage(content=f"Очікує підтвердження {name}: {clean}")],
            }
        return advance(state, step_idx, run_tool(name, args), clear_pending=False)

    def replanner_node(state: PlanExecuteState) -> dict:
        """Вирішує continue, replan або finish. Нові кроки не затирають зроблені."""
        if state.get("completed"):
            return {}
        plan = list(state["plan"])
        step_idx = state["current_step"]
        if step_idx >= len(plan):
            return {
                "completed": True,
                "messages": [AIMessage(content="Завершено: кроки плану виконано")],
            }
        if state.get("replan_count", 0) >= MAX_REPLANS:
            return {
                "completed": True,
                "messages": [AIMessage(content="Завершено: досягнуто ліміт перепланувань")],
            }

        remaining = plan[step_idx:]
        prompt = (
            f"{REPLANNER_PROMPT}\n"
            f"Ціль: {state['goal']}\n"
            f"План: {plan}\n"
            f"Виконано кроків: {step_idx}/{len(plan)}\n"
            f"Результати: {state['results']}\n"
            f"Залишилось: {remaining}"
        )
        raw = invoke_structured(llm, ReplanDecision, [HumanMessage(content=prompt)])
        decision = raw if isinstance(raw, ReplanDecision) else ReplanDecision.model_validate(raw)
        if decision.action == "finish":
            return {
                "completed": True,
                "messages": [AIMessage(content=f"Завершено: {decision.reasoning}")],
            }
        if decision.action == "replan" and decision.updated_steps:
            new_plan = [*plan[:step_idx], *decision.updated_steps]
            return {
                "plan": new_plan,
                "current_step": step_idx,
                "replan_count": state.get("replan_count", 0) + 1,
                "messages": [AIMessage(content=f"Новий план: {new_plan}. {decision.reasoning}")],
            }
        return {"messages": [AIMessage(content=f"Продовжуємо: {decision.reasoning}")]}

    def after_executor(state: PlanExecuteState) -> Literal["executor", "replanner", "__end__"]:
        if state.get("pending_call"):
            return "executor"
        if state.get("completed"):
            return "__end__"
        return "replanner"

    def should_end(state: PlanExecuteState) -> Literal["executor", "__end__"]:
        if state.get("completed"):
            return "__end__"
        return "executor"

    graph = StateGraph(PlanExecuteState)
    graph.add_node("planner", planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("replanner", replanner_node)
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "executor")
    graph.add_conditional_edges(
        "executor",
        after_executor,
        {"executor": "executor", "replanner": "replanner", "__end__": END},
    )
    graph.add_conditional_edges("replanner", should_end, {"executor": "executor", "__end__": END})
    app = graph.compile(checkpointer=saver, interrupt_after=interrupt_after or [])
    app.checkpointer_conn = conn
    return app

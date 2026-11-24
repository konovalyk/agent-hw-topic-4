Домашнє завдання №2

Plan-and-Execute з memory та HITL



Вступ



⚠️Максимальна кількість балів за домашнє завдання — 100 балів. Вага ДЗ №2 у підсумковій оцінці — 35%. Орієнтовна трудомісткість: 7 годин.


У цьому домашньому завданні ви побудуєте агента з архітектурою Plan-and-Execute — розширення ReAct з попереднього ДЗ, де агент СПОЧАТКУ складає план (список кроків), а ПОТІМ виконує його крок за кроком. Це підвищує якість для складних задач, де потрібна послідовність із 3+ дій.



Ключова відмінність від ДЗ1 (ReAct): у ReAct агент вирішує наступний крок «на льоту» — бачить результат tool і думає, що далі. У Plan-and-Execute агент складає ПОВНИЙ план заздалегідь, виконує його послідовно, і після кожного кроку вирішує: чи план ще актуальний, чи потрібно перепланувати (replanning). Це три вузли LangGraph: planner → executor → replanner.



Додатково, ви реалізуєте три production-критичних можливості:

1) Persistence — збереження стану агента між сесіями через SqliteSaver (якщо процес впав — можна продовжити з того місця, де зупинились);

2) Agentic RAG — агент самостійно вирішує, коли звернутися до бази знань (ChromaDB) замість tool;

3) Human-in-the-Loop (HITL) — для ризикових дій агент зупиняється і запитує підтвердження людини через interrupt()/approval.



Робота базується на матеріалах Теми 3 (планування, пам'ять, RAG) та Теми 4 (LangGraph advanced, HITL, checkpointers). Агент працює з обраним вами LLM-провайдером: OpenAI (GPT-5.2), Gemini (gemini-3.8-flash), Mistral або Ollama.





Що саме потрібно зробити



Зібрати planner — executor — replanner у LangGraph. Planner генерує план (список кроків) через structured outputs. Executor виконує один крок плану за ітерацію. Replanner вирішує: продовжити план, змінити або завершити.
Налаштувати checkpointer (SqliteSaver) та продемонструвати відновлення стану: зупинити виконання посередині плану, перезапустити процес, продовжити з того самого місця через thread_id.
Реалізувати agentic RAG з vector store (ChromaDB): створити базу знань із ≥8 документів для вашої доменної області, реалізувати RAG-інструмент (search_knowledge), продемонструвати, що агент самостійно вирішує, коли звернутися до бази знань.
Додати interrupt()/approval для ризикового tool: агент зупиняється перед виконанням ризикової дії, показує деталі, отримує approve/reject від людини, та продовжує або зупиняється відповідно.




Вимоги до роботи



Рішення оформлюється як Python-репозиторій (GitHub) або Jupyter Notebook.
Plan-and-Execute граф з трьома вузлами (planner, executor, replanner) працює.
Structured outputs: Plan та ReplanDecision як Pydantic-моделі.
SqliteSaver з persistence (файл, не :memory:) + демонстрація відновлення.
Agentic RAG: ChromaDB з ≥8 документів + search_knowledge tool.
HITL: interrupt()/resume для ризикового tool + approve/reject сценарії.
Код структурований, з коментарями українською мовою.
README з описом архітектури, інструкцією запуску та аналізом.




Критерії оцінювання (100 балів)



Завдання 1. Plan-and-Execute (30 балів):

10 балів — planner генерує Plan через with_structured_output (goal + steps).
10 балів — executor виконує кроки послідовно, використовуючи tools.
5 балів — replanner приймає ReplanDecision (continue/replan/finish).
5 балів — 3-4 tools з Pydantic-схемами та валідацією.
Завдання 2. Checkpointer та persistence (20 балів):

10 балів — SqliteSaver підключений, стан зберігається у файлі.
5 балів — продемонстровано відновлення стану після "перезапуску".
5 балів — продемонстровано незалежність thread_id (різні сесії).
Завдання 3. Agentic RAG (25 балів):

10 балів — ChromaDB з ≥8 змістовних документів для доменної області.
8 балів — search_knowledge tool працює та повертає релевантні результати.
7 балів — агент САМОСТІЙНО вирішує, коли використовувати RAG vs інший tool.
Завдання 4. HITL (25 балів):

10 балів — interrupt() зупиняє граф перед ризиковою дією з деталями.
8 балів — approve сценарій: tool виконується після підтвердження.
7 балів — reject сценарій: tool НЕ виконується, агент обробляє відмову.




Формат здачі



Артефакти, які потрібно здати:

Python-репозиторій (GitHub) або Jupyter Notebook з повним кодом.
agent_state.db — файл SQLite з збереженим станом (результат SqliteSaver).
README.md з: описом архітектури (planner/executor/replanner), інструкцією запуску, описом бази знань, описом ризикового tool та HITL flow, аналізом результатів.
Файли завантажити у систему до встановленого дедлайну.

Назва: HW2_Прізвище.zip (або посилання на GitHub/Colab)





Підказки для легшого виконання



Перевикористання з ДЗ1
Ваші tools з ДЗ1 можна перевикористати! Якщо ви створили weather, calculator та інші — вони підходять для executor. Не потрібно починати з нуля.

Structured outputs
Якщо with_structured_output не працює з вашим провайдером — альтернатива: звичайний LLM invoke з промптом "Поверни JSON з полями..." та json.loads() для парсингу. Або використайте instructor бібліотеку.

ChromaDB embedding model
ChromaDB за замовчуванням використовує all-MiniLM-L6-v2 (завантажується при першому запуску, ~80MB). Для збереження embedding-кешу між запусками використовуйте chromadb.PersistentClient(path="./chroma_db") замість chromadb.Client() (in-memory).

HITL debugging
Для тестування HITL:

Запустіть граф;
Він зупиниться на interrupt();
Отримайте стан через app.get_state(config);
Відновіть через app.invoke(Command(resume=...), config).
Якщо граф не зупиняється — переконайтеся, що checkpointer підключений і LLM дійсно викликає ризиковий tool.

Типові помилки:

"interrupt() не працює" — забули checkpointer при compile().
"Стан не відновлюється" — використовуєте :memory: замість файлу.
"Агент не використовує RAG" — покращіть docstring search_knowledge.
"Replanner завжди каже finish" — додайте більше контексту у промпт.
"with_structured_output помилка" — перевірте, що Pydantic-модель має Field(description=...) для кожного поля.


Рекомендована структура проєкту
# hw2_plan_execute/
# ├── tools.py              # Tools з Pydantic-схемами
# ├── knowledge.py          # ChromaDB + search_knowledge tool
# ├── plan_execute.py       # LangGraph: planner + executor + replanner
# ├── hitl.py               # Human-in-the-Loop з interrupt()
# ├── agent_state.db        # SQLite з збереженим станом (генерується)
# ├── requirements.txt
# └── README.md





Підготовка до виконання завдання



Створити Python-проєкт (рекомендовано: окрема директорія з venv або Google Colab).

Встановити залежності:

pip install langgraph langchain langchain-core "pydantic>=2.0"
pip install langgraph-checkpoint-sqlite    # SqliteSaver
pip install chromadb                       # Vector store для RAG
# Один з LLM-провайдерів (на вибір):
pip install langchain-google-genai         # Gemini
pip install langchain-openai               # OpenAI
pip install langchain-mistralai            # Mistral
pip install langchain-ollama               # Ollama

Перевірити, що SqliteSaver та ChromaDB працюють:

# Перевірка SqliteSaver:
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
 
conn = sqlite3.connect(':memory:')
saver = SqliteSaver(conn)
print(f'SqliteSaver: OK')
 
# Перевірка ChromaDB:
import chromadb
 
client = chromadb.Client()
collection = client.create_collection('test_collection')
collection.add(
    documents=['LangGraph - це фреймворк для агентів', 'ChromaDB - vector database'],
    ids=['doc1', 'doc2'],
)
results = collection.query(query_texts=['агентний фреймворк'], n_results=1)
print(f'ChromaDB query: {results["documents"][0]}')
 
# Перевірка interrupt:
from langgraph.types import interrupt, Command
print(f'interrupt: OK')





Завдання



Завдання 1. Plan-and-Execute у LangGraph (30 балів)

Мета: 
Побудувати LangGraph з трьома вузлами: planner (генерує план), executor (виконує крок), replanner (вирішує, чи продовжувати). Planner використовує structured outputs для генерації списку кроків.


Архітектура Plan-and-Execute:

Planner приймає запит користувача та генерує Plan — список кроків через with_structured_output. Кожен крок має опис та очікуваний tool.
Executor бере перший невиконаний крок з плану та виконує його через tools.
Replanner аналізує результати попереднього кроку та вирішує:
продовжити план як є;
змінити залишкові кроки;
завершити, якщо ціль досягнута.


Інструкція:

Визначте State з полями: messages, plan (список кроків), current_step (номер кроку), results (результати виконаних кроків), completed (чи завершено).
Створіть Pydantic-модель Plan з полями: steps (list[str]) та goal (str). Використовуйте її у planner через with_structured_output.
Створіть Pydantic-модель ReplanDecision з полями: action ("continue", "replan", "finish") та updated_steps (optional list[str]).
Реалізуйте 3-4 tools з Pydantic-схемами (можна перевикористати з ДЗ1 або створити нові для іншого домену).
Побудуйте граф: START → planner → executor → replanner → (executor або END).


Приклад коду (planner з structured outputs):

from pydantic import BaseModel, Field
from typing import Annotated, TypedDict, Literal
import operator
from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
 
# ── Structured Output Models ─────────────────────────────────────
class Plan(BaseModel):
    """План виконання задачі."""
    goal: str = Field(description='Головна ціль задачі')
    steps: list[str] = Field(description='Список кроків для досягнення цілі')
 
class ReplanDecision(BaseModel):
    """Рішення replanner: продовжити, перепланувати або завершити."""
    action: Literal['continue', 'replan', 'finish'] = Field(
        description='continue=виконати наступний крок, replan=змінити план, finish=завершити'
    )
    updated_steps: list[str] | None = Field(
        default=None,
        description='Оновлені кроки (тільки якщо action=replan)',
    )
    reasoning: str = Field(description='Пояснення рішення')
 
# ── State ────────────────────────────────────────────────────────
class PlanExecuteState(TypedDict):
    messages: Annotated[list, operator.add]
    plan: list[str]           # список кроків
    current_step: int         # поточний крок (0-indexed)
    results: list[str]        # результати виконаних кроків
    completed: bool
 
# ── LLM ──────────────────────────────────────────────────────────
llm = ChatGoogleGenerativeAI(model='gemini-3.8-flash') # для Gemini 3 temperature залишаємо за замовчуванням (1.0)
planner_llm = llm.with_structured_output(Plan)
replanner_llm = llm.with_structured_output(ReplanDecision)

Пояснення: with_structured_output(Plan) змушує LLM повертати відповідь у форматі Plan (goal + steps), а не вільний текст. Це гарантує, що planner завжди поверне структурований план, який можна програмно обробити. Аналогічно replanner_llm повертає ReplanDecision з action та reasoning.



Приклад коду (planner, executor, replanner вузли):

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
 
# ── Ваші tools (з ДЗ1 або нові) ─────────────────────────────────
@tool
def search_info(query: str) -> str:
    """Пошук інформації за запитом."""
    return f'Результати для: {query}'
 
@tool
def calculate(expression: str) -> str:
    """Обчислити математичний вираз."""
    try:
        return str(eval(expression))
    except Exception as e:
        return f'Помилка: {e}'
 
tools = [search_info, calculate]
tools_by_name = {t.name: t for t in tools}
 
# ── Planner Node ─────────────────────────────────────────────────
def planner_node(state: PlanExecuteState) -> dict:
    """Генерує план виконання задачі."""
    user_msg = state['messages'][0] if state['messages'] else ''
    prompt = (
        f'Створи план для виконання задачі: {user_msg}\n'
        f'Розбий на 2-5 конкретних кроків. Кожен крок має бути виконуваним.'
    )
    plan = planner_llm.invoke(prompt)
    return {
        'plan': plan.steps,
        'current_step': 0,
        'results': [],
        'messages': [AIMessage(content=f'План: {plan.steps}')],
    }
 
# ── Executor Node ────────────────────────────────────────────────
def executor_node(state: PlanExecuteState) -> dict:
    """Виконує поточний крок плану."""
    step_idx = state['current_step']
    plan = state['plan']
 
    if step_idx >= len(plan):
        return {'completed': True}
 
    current_step = plan[step_idx]
 
    # Виконати крок через LLM з tools
    llm_with_tools = llm.bind_tools(tools)
    response = llm_with_tools.invoke(
        f'Виконай цей крок: {current_step}\n'
        f'Попередні результати: {state["results"]}'
    )
 
    # Якщо LLM викликав tool — виконати
    result = response.text
    if hasattr(response, 'tool_calls') and response.tool_calls:
        for tc in response.tool_calls:
            tool_fn = tools_by_name.get(tc['name'])
            if tool_fn:
                tool_result = tool_fn.invoke(tc['args'])
                result = f'{tc["name"]}: {tool_result}'
 
    return {
        'current_step': step_idx + 1,
        'results': [*state['results'], f'Крок {step_idx+1}: {result}'],
        'messages': [AIMessage(content=f'Виконано крок {step_idx+1}: {result}')],
    }
 
# ── Replanner Node ───────────────────────────────────────────────
def replanner_node(state: PlanExecuteState) -> dict:
    """Вирішує: продовжити, перепланувати або завершити."""
    plan = state['plan']
    step_idx = state['current_step']
    results = state['results']
 
    if step_idx >= len(plan):
        return {'completed': True}
 
    remaining = plan[step_idx:]
    prompt = (
        f'Оціни прогрес виконання:\n'
        f'План: {plan}\n'
        f'Виконано кроків: {step_idx}/{len(plan)}\n'
        f'Результати: {results}\n'
        f'Залишилось: {remaining}\n'
        f'Рішення: continue (наступний крок), replan (змінити план), finish (завершити)?'
    )
    decision = replanner_llm.invoke(prompt)
 
    if decision.action == 'finish':
        return {'completed': True, 'messages': [AIMessage(content=f'Завершено: {decision.reasoning}')]}
    elif decision.action == 'replan' and decision.updated_steps:
        return {'plan': decision.updated_steps, 'current_step': 0}
 
    return {}  # continue — нічого не змінювати
 
# ── Router ───────────────────────────────────────────────────────
def should_end(state: PlanExecuteState) -> Literal['executor', '__end__']:
    if state.get('completed'):
        return '__end__'
    return 'executor'
 
# ── Граф ─────────────────────────────────────────────────────────
graph = StateGraph(PlanExecuteState)
graph.add_node('planner', planner_node)
graph.add_node('executor', executor_node)
graph.add_node('replanner', replanner_node)
 
graph.add_edge(START, 'planner')
graph.add_edge('planner', 'executor')
graph.add_edge('executor', 'replanner')
graph.add_conditional_edges('replanner', should_end)
 
# Компілюємо БЕЗ checkpointer (додамо в Завданні 2)
app = graph.compile()

Зверніть увагу на потік: planner генерує план → executor виконує один крок → replanner вирішує що далі → якщо не завершено → назад до executor. Replanner — це ключова відмінність від простого sequential execution: агент адаптує план на основі проміжних результатів.



Очікуваний формат: працюючий LangGraph з трьома вузлами, демонстрація на 2-3 прикладах різної складності, де видно генерацію плану, виконання кроків та (опціонально) replanning.





Завдання 2. Checkpointer та відновлення стану (20 балів)

Мета: 
Налаштувати SqliteSaver як checkpointer для LangGraph графа та продемонструвати persistence — збереження стану між запусками програми.
Чому persistence важливий? У production агент може працювати години або дні над складною задачею. Якщо процес впав (crash, restart, deployment) — без checkpointer весь прогрес втрачається. SqliteSaver зберігає стан після кожного вузла, і при наступному запуску можна продовжити з того самого місця. Це також необхідно для HITL: агент зупиняється на interrupt(), людина відповідає пізніше, і агент продовжує з збереженого стану.


Інструкція:

Підключіть SqliteSaver до вашого графа через compile(checkpointer=saver).
Запустіть агента з thread_id (config={"configurable": {"thread_id": "1"}}).
Зупиніть виконання посередині (наприклад, через max_steps або вручну).
Перезапустіть програму та продовжіть з того самого thread_id — покажіть, що стан відновлено.
Продемонструйте, що різні thread_id мають незалежний стан.


Приклад коду:

import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
 
# ── Підключення SqliteSaver ──────────────────────────────────────
# Використовуємо файл (не :memory:) для persistence між запусками!
conn = sqlite3.connect('agent_state.db', check_same_thread=False)
saver = SqliteSaver(conn)
 
# Компілюємо граф з checkpointer
app_with_memory = graph.compile(checkpointer=saver)
 
# ── Запуск з thread_id ───────────────────────────────────────────
config = {'configurable': {'thread_id': 'session-001'}}
 
# Перший запуск
result = app_with_memory.invoke(
    {
        'messages': [HumanMessage(content='Сплануй подорож до Парижа')],
        'plan': [],
        'current_step': 0,
        'results': [],
        'completed': False,
    },
    config=config,
)
print(f'Steps completed: {result["current_step"]}')
 
# ── Відновлення стану (після перезапуску програми) ────────────────
# Той самий thread_id → продовжить з останнього checkpoint
state = app_with_memory.get_state(config)
print(f'Restored state: step={state.values.get("current_step")}')
print(f'Plan: {state.values.get("plan")}')
print(f'Results so far: {state.values.get("results")}')
 
# ── Незалежні сесії ──────────────────────────────────────────────
config2 = {'configurable': {'thread_id': 'session-002'}}
# Новий thread_id = чистий стан (незалежний від session-001)

Ключове: sqlite3.connect з ФАЙЛОМ — це забезпечує persistence між запусками процесу. check_same_thread=False потрібно для LangGraph, який може використовувати кілька потоків. thread_id ідентифікує сесію: різні thread_id — незалежні ланцюжки виконання.



Очікуваний формат: демонстрація збереження стану (перший запуск → зупинка → відновлення), демонстрація незалежності thread_id, скріншот або вивід, що показує відновлений стан.





Завдання 3. Agentic RAG з ChromaDB (25 балів)

Мета: 
Додати до агента базу знань (ChromaDB) та RAG-інструмент, щоб агент самостійно вирішував, коли звернутися до бази знань замість tool.
Agentic RAG відрізняється від звичайного RAG: у звичайному RAG кожен запит автоматично шукає в базі знань. У agentic RAG АГЕНТ вирішує, чи потрібна база знань. Наприклад, для запиту "Порахуй 2+2" — не потрібна база, потрібен calculator tool. Для запиту "Які правила візового режиму?" — потрібна база знань. Це реалізується через tool search_knowledge, який LLM викликає як звичайний tool.
Інструкція:

Створіть базу знань із ≥8 документів для вашої доменної області. Документи мають бути змістовними (2-5 речень кожен).
Завантажте документи у ChromaDB collection.
Створіть tool search_knowledge(query: str), який шукає у ChromaDB і повертає топ-3 релевантних документи.
Додайте search_knowledge до списку tools агента.
Продемонструйте, що агент САМОСТІЙНО вирішує, коли використовувати search_knowledge vs інші tools.


Приклад коду:

import chromadb
from langchain_core.tools import tool
 
# ── Створення бази знань ─────────────────────────────────────────
chroma_client = chromadb.Client()
knowledge_base = chroma_client.create_collection('domain_knowledge')
 
# Документи для вашої доменної області (≥8 штук)
# Приклад: туристична база знань
documents = [
    "Для в'їзду до країн ЄС громадянам України потрібна біометрична віза або безвіз на 90 днів.",
    'Париж — столиця Франції, відомий Ейфелевою вежею, Лувром та собором Нотр-Дам.',
    'Середня вартість проживання у Парижі: хостел 30-50 EUR, готель 3* 80-150 EUR за ніч.',
    'Метро Парижа має 16 ліній і покриває все місто. Денний квиток коштує близько 16 EUR.',
    'Найкращий час для відвідування Парижа: квітень-червень та вересень-жовтень.',
    'Ейфелева вежа відкрита щодня. Квиток: 17-26 EUR залежно від рівня. Бронюйте заздалегідь.',
    'Лувр — найбільший музей світу. Закритий по вівторках. Квиток 22 EUR, безкоштовно до 18 років.',
    'Французька кухня: круасани, багети, сири, вино. Обід у кафе: 15-25 EUR на особу.',
    'Сезон розпродажів у Парижі: січень та липень. Знижки до 70% у бутиках.',
    'Безпека: уникайте кишенькових злодіїв у метро та біля туристичних місць.',
]
doc_ids = [f'doc_{i}' for i in range(len(documents))]
 
knowledge_base.add(documents=documents, ids=doc_ids)
print(f'Knowledge base: {knowledge_base.count()} documents loaded')
 
# ── RAG Tool ─────────────────────────────────────────────────────
@tool
def search_knowledge(query: str) -> str:
    """Пошук інформації у базі знань.
 
    Використовуйте цей інструмент, коли потрібна довідкова
    інформація, факти, правила або рекомендації з бази знань.
    НЕ використовуйте для обчислень або дій.
 
    Args:
        query: Пошуковий запит.
 
    Returns:
        Топ-3 релевантних документи з бази знань.
    """
    results = knowledge_base.query(query_texts=[query], n_results=3)
    docs = results['documents'][0]
    return '\n---\n'.join(docs)
 
# Тест:
result = search_knowledge.invoke({'query': 'візовий режим ЄС'})
print(f'RAG result:\n{result}')

Пояснення: search_knowledge — це звичайний LangChain tool. LLM вирішує, коли його викликати, на основі docstring. Тому docstring критично важливий: «Використовуйте для довідкової інформації» допомагає LLM зрозуміти, що цей tool для знань, а не для дій. ChromaDB автоматично використовує embedding model (за замовчуванням all-MiniLM-L6-v2) для семантичного пошуку.



Очікуваний формат: ChromaDB з ≥ 8 документів, search_knowledge tool, демонстрація, де агент використовує RAG (довідкове питання) vs де використовує інший tool (дія/обчислення).





Завдання 4. Human-in-the-Loop: interrupt/approval (25 балів)

Мета: 
Додати HITL для ризикового інструмента — агент зупиняється перед виконанням ризикової дії, показує деталі, і чекає на підтвердження людини.
Чому HITL потрібен? Деякі дії незворотні: переказ коштів, видалення даних, відправка email масовій аудиторії, бронювання квитків. Агент може помилитися (галюцинувати параметри, неправильно зрозуміти запит), тому критичні дії повинні проходити через підтвердження людини. LangGraph реалізує це через interrupt() — функцію, що зупиняє граф та зберігає стан.
Інструкція:

Визначте ризиковий tool у вашій доменній області (бронювання, переказ, видалення, відправка — будь-яка незворотна дія).
Додайте interrupt() перед виконанням ризикового tool: граф зупиняється, показує деталі дії (що саме буде зроблено), чекає на відповідь.
Реалізуйте три сценарії: approve (підтвердити та виконати), reject (відхилити), edit (змінити параметри та виконати).
Для HITL ОБОВ'ЯЗКОВО потрібен checkpointer (SqliteSaver з Завдання 2) — без нього стан не зберігається між interrupt та resume.


Приклад коду:

from typing import TypedDict, Annotated
import operator
from langgraph.types import interrupt, Command
from langchain_core.tools import tool
from langchain_core.messages import AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
 
llm = ChatGoogleGenerativeAI(model='gemini-3.8-flash') # для Gemini 3 temperature залишаємо за замовчуванням (1.0)
 
# State (з Завдання 1 — повторюємо для зручності)
class PlanExecuteState(TypedDict):
    messages: Annotated[list, operator.add]
    plan: list[str]
    current_step: int
    results: list[str]
    completed: bool
 
# Tools (з Завдання 1)
@tool
def search_info(query: str) -> str:
    """Пошук інформації."""
    return f'Результати для: {query}'
 
tools = [search_info]
tools_by_name = {t.name: t for t in tools}
 
# ── Ризиковий tool ───────────────────────────────────────────────
@tool
def book_hotel(hotel_name: str, check_in: str, nights: int, total_cost: float) -> str:
    """Забронювати готель (РИЗИКОВА ДІЯ — потребує підтвердження).
 
    Args:
        hotel_name: Назва готелю.
        check_in: Дата заїзду (YYYY-MM-DD).
        nights: Кількість ночей.
        total_cost: Загальна вартість (EUR).
    """
    return f'Заброньовано: {hotel_name}, {check_in}, {nights} ночей, {total_cost} EUR'
 
# ── Executor з HITL ──────────────────────────────────────────────
RISKY_TOOLS = {'book_hotel'}  # Набір ризикових tools
 
def executor_with_hitl(state: PlanExecuteState) -> dict:
    """Executor з interrupt для ризикових tools."""
    step_idx = state['current_step']
    plan = state['plan']
 
    if step_idx >= len(plan):
        return {'completed': True}
 
    current_step = plan[step_idx]
    llm_with_tools = llm.bind_tools(tools + [book_hotel])
    response = llm_with_tools.invoke(
        f'Виконай крок: {current_step}\nРезультати: {state["results"]}'
    )
 
    # Перевірити, чи tool ризиковий
    if hasattr(response, 'tool_calls') and response.tool_calls:
        for tc in response.tool_calls:
            if tc['name'] in RISKY_TOOLS:
                # ── INTERRUPT: зупинити для підтвердження ────────
                approval = interrupt({
                    'action': tc['name'],
                    'args': tc['args'],
                    'message': (
                        f'Підтвердіть ризикову дію:\n'
                        f'Tool: {tc["name"]}\n'
                        f'Параметри: {tc["args"]}'
                    ),
                })
 
                if isinstance(approval, dict) and approval.get('approved'):
                    # Виконати tool після підтвердження
                    tool_fn = tools_by_name.get(tc['name'], book_hotel)
                    result = tool_fn.invoke(tc['args'])
                    # Повертаємо результат tool, НЕ перезаписуємо response.content
                    return {
                        'current_step': step_idx + 1,
                        'results': [*state['results'], f'Крок {step_idx+1}: {tc["name"]}: {result}'],
                        'messages': [AIMessage(content=f'Крок {step_idx+1}: {result}')],
                    }
                else:
                    result = f'Відхилено оператором: {approval.get("reason", "") if isinstance(approval, dict) else ""}'
                    return {
                        'current_step': step_idx + 1,
                        'results': [*state['results'], f'Крок {step_idx+1}: {result}'],
                        'messages': [AIMessage(content=result)],
                    }
 
    result = response.text
    return {
        'current_step': step_idx + 1,
        'results': [*state['results'], f'Крок {step_idx+1}: {result}'],
        'messages': [AIMessage(content=f'Крок {step_idx+1}: {result}')],
    }



Приклад коду (resume після interrupt):

from langgraph.types import Command
 
# ── Запуск агента (зупиниться на interrupt) ──────────────────────
config = {'configurable': {'thread_id': 'hitl-demo'}}
 
# Компілюємо з checkpointer (обов'язково для HITL!)
app_hitl = graph.compile(checkpointer=saver)
 
# Запуск — агент зупиниться при виклику ризикового tool
# result = app_hitl.invoke(initial_state, config=config)
 
# ── Людина вирішує ───────────────────────────────────────────────
# Показати деталі: result['__interrupt__']  (або app_hitl.get_state(config).tasks)
# Людина натискає "Approve" або "Reject"
 
# Approve:
# app_hitl.invoke(Command(resume={'approved': True}), config=config)
 
# Reject:
# app_hitl.invoke(
#     Command(resume={'approved': False, 'reason': 'Занадто дорого'}),
#     config=config,
# )

Очікуваний формат: ризиковий tool визначено, interrupt() зупиняє граф, демонстрація approve (tool виконується) та reject (tool не виконується), стан зберігається через checkpointer між interrupt та resume.


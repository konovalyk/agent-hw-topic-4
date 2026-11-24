"""Інструменти плану вихідних: тривалість, бюджет і бронювання житла."""

from __future__ import annotations

from datetime import datetime

from langchain_core.tools import tool
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Відомі категорії. Усе, чого немає в таблиці, отримує 90 хвилин.
DURATION_MINUTES = {
    "museum": 150,
    "gallery": 150,
    "park": 60,
    "viewpoint": 60,
    "lunch": 60,
    "dinner": 90,
    "cafe": 45,
    "transfer": 20,
}
DURATION_ALIASES = {
    "museum": "museum",
    "музей": "museum",
    "gallery": "gallery",
    "галерея": "gallery",
    "park": "park",
    "парк": "park",
    "viewpoint": "viewpoint",
    "оглядовий майданчик": "viewpoint",
    "lunch": "lunch",
    "обід": "lunch",
    "dinner": "dinner",
    "вечеря": "dinner",
    "cafe": "cafe",
    "кафе": "cafe",
    "transfer": "transfer",
    "дорога": "transfer",
    "дорога до центру": "transfer",
}


class DurationInput(BaseModel):
    """Категорія місця, для якого потрібна типова тривалість."""

    model_config = ConfigDict(str_strip_whitespace=True)

    category: str = Field(description="Категорія: музей, галерея, парк, оглядовий майданчик, обід, вечеря, кафе або дорога")

    @field_validator("category")
    @classmethod
    def category_present(cls, value: str) -> str:
        if len(value) < 2:
            raise ValueError("Категорія має містити щонайменше 2 символи")
        return value


class BudgetInput(BaseModel):
    """Суми в гривнях для перевірки ліміту поїздки."""

    model_config = ConfigDict(str_strip_whitespace=True)

    limit_uah: float = Field(description="Верхня межа бюджету в грн, більша за нуль")
    transport_uah: float = Field(description="Вартість дороги туди й назад у грн")
    stay_uah: float = Field(description="Вартість житла за всі ночі у грн")
    activities_uah: float = Field(description="Квитки на місця у грн")
    meals_uah: float = Field(description="Орієнтовна вартість їжі у грн")

    @field_validator("limit_uah")
    @classmethod
    def limit_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("Ліміт має бути більшим за нуль")
        return value

    @field_validator("transport_uah", "stay_uah", "activities_uah", "meals_uah")
    @classmethod
    def amount_non_negative(cls, value: float) -> float:
        if value < 0:
            raise ValueError("Сума не може бути від'ємною")
        return value


class BookStayInput(BaseModel):
    """Параметри незворотного бронювання житла."""

    model_config = ConfigDict(str_strip_whitespace=True)

    place: str = Field(description="Назва готелю або квартири")
    check_in: str = Field(description="Дата заїзду у форматі YYYY-MM-DD")
    nights: int = Field(description="Кількість ночей, більше нуля")
    total_uah: float = Field(description="Загальна сума бронювання в грн, більша за нуль")

    @field_validator("place")
    @classmethod
    def place_present(cls, value: str) -> str:
        if len(value) < 2:
            raise ValueError("Назва житла має містити щонайменше 2 символи")
        return value

    @field_validator("check_in")
    @classmethod
    def check_in_date(cls, value: str) -> str:
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("Дата заїзду має бути у форматі YYYY-MM-DD") from exc
        return value

    @field_validator("nights")
    @classmethod
    def nights_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Кількість ночей має бути більшою за нуль")
        return value

    @field_validator("total_uah")
    @classmethod
    def total_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("Сума бронювання має бути більшою за нуль")
        return value


@tool(args_schema=DurationInput)
def estimate_duration(category: str) -> str:
    """Оцінити тривалість візиту, якщо в довідці немає точних хвилин.

    Викликай, коли потрібна типова тривалість категорії, а не ціна і не бронь.
    Музей і галерея — 150 хв, парк і оглядовий майданчик — 60, обід — 60,
    вечеря — 90, кафе — 45, дорога до центру — 20. Невідома категорія — 90 хв.
    Джерело оцінки завжди default.

    Args:
        category: Тип місця або прийому їжі українською чи англійською.

    Returns:
        Рядок із хвилинами і позначкою duration_source: default.
    """
    key = DURATION_ALIASES.get(category.casefold())
    minutes = DURATION_MINUTES.get(key or "", 90)
    label = key or category.casefold()
    return f"{label}: {minutes} хв (duration_source: default)"


@tool(args_schema=BudgetInput)
def check_budget(
    limit_uah: float,
    transport_uah: float,
    stay_uah: float,
    activities_uah: float,
    meals_uah: float,
) -> str:
    """Перевірити, чи вміщається поїздка в ліміт.

    Викликай, коли ліміт і всі чотири суми вже відомі в гривнях.
    Інструмент не шукає ціни, не читає базу знань і не бронює житло.
    До 85% ліміту включно — fits, вище і до 100% — tight, понад ліміт — deficit.

    Args:
        limit_uah: Стеля бюджету в грн.
        transport_uah: Дорога в грн.
        stay_uah: Житло в грн.
        activities_uah: Вхідні квитки в грн.
        meals_uah: Їжа в грн.

    Returns:
        Сума, частка ліміту і вердикт fits, tight або deficit.
    """
    total = transport_uah + stay_uah + activities_uah + meals_uah
    if total <= limit_uah * 0.85:
        verdict = "fits"
    elif total <= limit_uah:
        verdict = "tight"
    else:
        verdict = "deficit"
    share = total / limit_uah
    return (
        f"Разом {total:.2f} грн із ліміту {limit_uah:.2f} грн ({share:.0%}). "
        f"Вердикт: {verdict}."
    )


@tool(args_schema=BookStayInput)
def book_stay(place: str, check_in: str, nights: int, total_uah: float) -> str:
    """Забронювати житло. Це незворотна ризикова дія.

    Викликай лише коли користувач прямо просить бронювання і вже відомі
    назва, дата заїзду, кількість ночей і сума в грн. Не викликай для
    довідки, розрахунку бюджету чи оцінки тривалості. Граф зупиниться
    і запитає людину перед виконанням.

    Args:
        place: Назва готелю або квартири.
        check_in: Дата заїзду YYYY-MM-DD.
        nights: Кількість ночей.
        total_uah: Сума в грн.

    Returns:
        Підтвердження бронювання. Без згоди людини граф цей рядок не повертає.
    """
    return (
        f"Заброньовано: {place}, заїзд {check_in}, {nights} ночей, {total_uah:.2f} грн. "
        "Операцію виконано після підтвердження."
    )

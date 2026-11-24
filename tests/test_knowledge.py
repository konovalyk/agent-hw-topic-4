"""Пошук у постійній базі знань, без моделі."""

from __future__ import annotations

from knowledge import DOCUMENTS, search_knowledge


def test_knowledge_base_has_enough_documents_and_finds_lviv_stay():
    assert len(DOCUMENTS) >= 8

    def sentences(text: str) -> int:
        parts = [part.strip() for part in text.replace("!", ".").replace("?", ".").split(".")]
        return len([part for part in parts if part])

    assert all(2 <= sentences(item) <= 5 for item in DOCUMENTS)
    found = search_knowledge.invoke({"query": "ціни на житло у Львові хостел"})
    first = found.split("\n---\n", maxsplit=1)[0]
    assert "хостелі" in first
    season = search_knowledge.invoke({"query": "сезон поїздки до Львова"})
    assert season.split("\n---\n", maxsplit=1)[0].startswith("Сезон поїздки")
    transport = search_knowledge.invoke({"query": "транспорт містом у Львові"})
    assert transport.split("\n---\n", maxsplit=1)[0].startswith("Транспорт містом")
    try:
        search_knowledge.invoke({"query": "x"})
    except Exception as exc:  # noqa: BLE001 — коротенький запит має відсікти схема
        assert "2" in str(exc)
    else:
        raise AssertionError("Короткий запит не відхилено")

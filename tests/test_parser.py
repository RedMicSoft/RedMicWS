import json
import os

import pytest

from app.series.parser import ASSParser

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "subs_by_name_normal")
INPUT_FILE = os.path.join(DATA_DIR, "input", "test.ass")
DESC_FILE = os.path.join(DATA_DIR, "input", "description.json")
OUTPUT_DIR = os.path.join(DATA_DIR, "output")

with open(DESC_FILE, encoding="utf-8") as _f:
    _desc = json.load(_f)
PROJECT_DESCRIPTION: str = _desc["project"]
SERIES_DESCRIPTION: str = _desc["series"]

EXPECTED_ROLES = {
    "Ales",
    "Fiery",
    "l_Luna",
    "Мираша",
    "Надпись",
    "Rian",
    "Sebner_TV",
    "Староста",
}

# Явное сопоставление имени роли → файл с ожидаемым результатом.
# Файл test_I_Luna.srt соответствует роли "l_Luna" (строчная L, не заглавная I).
ROLE_TO_FILE: dict[str, str] = {
    "Ales": "test_Ales.srt",
    "Fiery": "test_Fiery.srt",
    "l_Luna": "test_I_Luna.srt",
    "Мираша": "test_Мираша.srt",
    "Надпись": "test_Надпись.srt",
    "Rian": "test_Rian.srt",
    "Sebner_TV": "test_Sebner_TV.srt",
    "Староста": "test_Староста.srt",
}


def _read_expected(filename: str) -> str:
    """Читает файл, убирает BOM и нормализует переносы строк."""
    with open(os.path.join(OUTPUT_DIR, filename), encoding="utf-8-sig") as f:
        return f.read().replace("\r\n", "\n")


def _normalize(content: str) -> str:
    """Убирает BOM и нормализует переносы строк."""
    return content.lstrip("\ufeff").replace("\r\n", "\n")


def test_extract_roles_by_name() -> None:
    """Парсер правильно извлекает все роли из поля Name."""
    parser = ASSParser(INPUT_FILE)
    parser.load()
    assert parser.roles == EXPECTED_ROLES


@pytest.mark.parametrize("role", sorted(ROLE_TO_FILE))
def test_role_content_matches_expected(role: str) -> None:
    """Контент, сгенерированный для роли, совпадает с эталонным файлом."""
    expected = _read_expected(ROLE_TO_FILE[role])

    parser = ASSParser(INPUT_FILE)
    parser.load()
    content = _normalize(
        parser.get_role_content(
            role,
            project_description=PROJECT_DESCRIPTION,
            series_description=SERIES_DESCRIPTION,
            output_format="srt",
        )
    )

    assert content == expected

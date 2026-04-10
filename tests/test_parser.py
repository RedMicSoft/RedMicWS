import json
import os

import pytest

from app.series.parser import ASSParser


def _load_desc(data_dir: str) -> tuple[str, str]:
    with open(os.path.join(data_dir, "input", "description.json"), encoding="utf-8") as f:
        d = json.load(f)
    return d["project"], d["series"]


def _read_expected(output_dir: str, filename: str) -> str:
    """Читает эталонный файл, убирает BOM и нормализует переносы строк."""
    with open(os.path.join(output_dir, filename), encoding="utf-8-sig") as f:
        return f.read().replace("\r\n", "\n")


def _normalize(content: str) -> str:
    """Убирает BOM и нормализует переносы строк."""
    return content.lstrip("\ufeff").replace("\r\n", "\n")


# ---------------------------------------------------------------------------
# subs_by_name_normal — роли берутся из поля Name
# ---------------------------------------------------------------------------

_NAME_DIR = os.path.join(os.path.dirname(__file__), "data", "subs_by_name_normal")
_NAME_PROJECT, _NAME_SERIES = _load_desc(_NAME_DIR)

_NAME_EXPECTED_ROLES = {
    "Ales",
    "Fiery",
    "l_Luna",
    "Мираша",
    "Надпись",
    "Rian",
    "Sebner_TV",
    "Староста",
}

# Файл test_I_Luna.srt соответствует роли "l_Luna" (строчная L, не заглавная I).
_NAME_ROLE_TO_FILE: dict[str, str] = {
    "Ales": "test_Ales.srt",
    "Fiery": "test_Fiery.srt",
    "l_Luna": "test_I_Luna.srt",
    "Мираша": "test_Мираша.srt",
    "Надпись": "test_Надпись.srt",
    "Rian": "test_Rian.srt",
    "Sebner_TV": "test_Sebner_TV.srt",
    "Староста": "test_Староста.srt",
}


def test_by_name_extract_roles() -> None:
    """Парсер правильно извлекает все роли из поля Name."""
    parser = ASSParser(os.path.join(_NAME_DIR, "input", "test.ass"))
    parser.load()
    assert parser.roles == _NAME_EXPECTED_ROLES


@pytest.mark.parametrize("role", sorted(_NAME_ROLE_TO_FILE))
def test_by_name_role_content(role: str) -> None:
    """Контент для роли (use_name=True) совпадает с эталонным файлом."""
    expected = _read_expected(os.path.join(_NAME_DIR, "output"), _NAME_ROLE_TO_FILE[role])

    parser = ASSParser(os.path.join(_NAME_DIR, "input", "test.ass"))
    parser.load()
    content = _normalize(
        parser.get_role_content(
            role,
            project_description=_NAME_PROJECT,
            series_description=_NAME_SERIES,
            output_format="srt",
        )
    )

    assert content == expected


# ---------------------------------------------------------------------------
# subs_by_style_normal — роли берутся из поля Style
# ---------------------------------------------------------------------------

_STYLE_DIR = os.path.join(os.path.dirname(__file__), "data", "subs_by_style_normal")
_STYLE_PROJECT, _STYLE_SERIES = _load_desc(_STYLE_DIR)

_STYLE_EXPECTED_ROLES = {
    "Twilight",
    "Spike",
    "ms Cake",
    "Mayor",
    "SB",
    "Фон_ж_1",
}

_STYLE_ROLE_TO_FILE: dict[str, str] = {
    "Twilight": "test_Twilight.srt",
    "Spike": "test_Spike.srt",
    "ms Cake": "test_ms Cake.srt",
    "Mayor": "test_Mayor.srt",
    "SB": "test_SB.srt",
    "Фон_ж_1": "test_Фон_ж_1.srt",
}


def test_by_style_extract_roles() -> None:
    """Парсер правильно извлекает все роли из поля Style."""
    parser = ASSParser(
        os.path.join(_STYLE_DIR, "input", "test.ass"), use_name=False
    )
    parser.load()
    assert parser.roles == _STYLE_EXPECTED_ROLES


@pytest.mark.parametrize("role", sorted(_STYLE_ROLE_TO_FILE))
def test_by_style_role_content(role: str) -> None:
    """Контент для роли (use_name=False) совпадает с эталонным файлом."""
    expected = _read_expected(os.path.join(_STYLE_DIR, "output"), _STYLE_ROLE_TO_FILE[role])

    parser = ASSParser(
        os.path.join(_STYLE_DIR, "input", "test.ass"), use_name=False
    )
    parser.load()
    content = _normalize(
        parser.get_role_content(
            role,
            project_description=_STYLE_PROJECT,
            series_description=_STYLE_SERIES,
            output_format="srt",
        )
    )

    assert content == expected


# ---------------------------------------------------------------------------
# subs_by_name_with_beginning — поле Name, «Начало» уже есть в исходнике
# ---------------------------------------------------------------------------

_NAME_BEG_DIR = os.path.join(os.path.dirname(__file__), "data", "subs_by_name_with_beginning")
_NAME_BEG_PROJECT, _NAME_BEG_SERIES = _load_desc(_NAME_BEG_DIR)

_NAME_BEG_ROLE_TO_FILE: dict[str, str] = {
    "Ales": "test_Ales.srt",
    "Fiery": "test_Fiery.srt",
    "l_Luna": "test_I_Luna.srt",
    "Мираша": "test_Мираша.srt",
    "Надпись": "test_Надпись.srt",
    "Rian": "test_Rian.srt",
    "Sebner_TV": "test_Sebner_TV.srt",
    "Староста": "test_Староста.srt",
}


@pytest.mark.parametrize("role", sorted(_NAME_BEG_ROLE_TO_FILE))
def test_by_name_with_beginning_no_duplicate(role: str) -> None:
    """При наличии «Начало» в исходнике запись не дублируется (use_name=True)."""
    expected = _read_expected(
        os.path.join(_NAME_BEG_DIR, "output"), _NAME_BEG_ROLE_TO_FILE[role]
    )

    parser = ASSParser(os.path.join(_NAME_BEG_DIR, "input", "test.ass"))
    parser.load()
    content = _normalize(
        parser.get_role_content(
            role,
            project_description=_NAME_BEG_PROJECT,
            series_description=_NAME_BEG_SERIES,
            output_format="srt",
        )
    )

    assert content.count("Начало") == 1
    assert content == expected


# ---------------------------------------------------------------------------
# subs_by_style_with_beginning — поле Style, «Начало» уже есть в исходнике
# ---------------------------------------------------------------------------

_STYLE_BEG_DIR = os.path.join(os.path.dirname(__file__), "data", "subs_by_style_with_beginning")
_STYLE_BEG_PROJECT, _STYLE_BEG_SERIES = _load_desc(_STYLE_BEG_DIR)

_STYLE_BEG_ROLE_TO_FILE: dict[str, str] = {
    "Twilight": "test_Twilight.srt",
    "Spike": "test_Spike.srt",
    "ms Cake": "test_ms Cake.srt",
    "Mayor": "test_Mayor.srt",
    "SB": "test_SB.srt",
    "Фон_ж_1": "test_Фон_ж_1.srt",
}


@pytest.mark.parametrize("role", sorted(_STYLE_BEG_ROLE_TO_FILE))
def test_by_style_with_beginning_no_duplicate(role: str) -> None:
    """При наличии «Начало» в исходнике запись не дублируется (use_name=False)."""
    expected = _read_expected(
        os.path.join(_STYLE_BEG_DIR, "output"), _STYLE_BEG_ROLE_TO_FILE[role]
    )

    parser = ASSParser(
        os.path.join(_STYLE_BEG_DIR, "input", "test.ass"), use_name=False
    )
    parser.load()
    content = _normalize(
        parser.get_role_content(
            role,
            project_description=_STYLE_BEG_PROJECT,
            series_description=_STYLE_BEG_SERIES,
            output_format="srt",
        )
    )

    assert content.count("Начало") == 1
    assert content == expected

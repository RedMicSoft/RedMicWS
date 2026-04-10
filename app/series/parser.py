import os
import re
from typing import Literal

import pysubs2

BEGINNING_DURATION_MS = 100  # 0.1 секунды
TECH_MARKER = "!t"
TECH_INFO_PREFIX = "!ТЕХ ИНФ"

# HTML-теги, которые pysubs2 добавляет при конвертации italic/bold-стилей в SRT,
# и ASS override-блоки вида {…}, которые не нужны в SRT-выводе.
_SRT_CLEANUP_RE = re.compile(r"</?(?:i|b|u|s)>|\{[^}]*\}", re.IGNORECASE)


class ASSParser:
    """
    Парсер субтитров в формате ASS.

    Умеет:
    - Извлекать роли из поля Name или Style (по флагу use_name).
      В поле Name несколько ролей могут быть разделены символом «;».
    - Создавать отдельный файл (ASS или SRT) для каждой роли с репликами только этой роли.
    - Вставлять реплику «Начало» длительностью 0,1 с в самое начало каждого файла.
    - Если в исходнике есть строка с текстом «!t», заменять её на
      «!ТЕХ ИНФ {project_description} {series_description}» во всех сохраняемых файлах.
    """

    def __init__(self, filename: str, use_name: bool = True) -> None:
        """
        Args:
            filename:  путь к исходному .ass файлу.
            use_name:  True  → роли берутся из поля Name (может быть несколько через «;»).
                       False → роли берутся из поля Style.
        """
        self.filename = os.path.abspath(filename)
        self.use_name = use_name
        self.subs: pysubs2.SSAFile | None = None
        self.roles: set[str] = set()

    # ------------------------------------------------------------------
    # Загрузка и разбор
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Читает .ass файл и извлекает список ролей."""
        self.subs = pysubs2.load(self.filename, encoding="utf-8")
        self._extract_roles()

    def _extract_roles(self) -> None:
        """Заполняет self.roles уникальными именами ролей из загруженного файла."""
        if self.subs is None:
            raise RuntimeError("Файл не загружен. Вызовите load() сначала.")

        self.roles = set()
        for event in self.subs:
            if event.type != "Dialogue":
                continue
            if self.use_name:
                for name in event.name.split(";"):
                    name = name.strip()
                    if name:
                        self.roles.add(name)
            else:
                style = event.style.strip()
                if style:
                    self.roles.add(style)

    # ------------------------------------------------------------------
    # Сохранение
    # ------------------------------------------------------------------

    def _build_role_ssa_file(
        self,
        role: str,
        project_description: str = "",
        series_description: str = "",
    ) -> "pysubs2.SSAFile":
        """Строит SSAFile с репликами указанной роли (внутренний метод)."""
        if self.subs is None:
            raise RuntimeError("Файл не загружен. Вызовите load() сначала.")

        output = pysubs2.SSAFile()
        output.info.update(self.subs.info)
        output.styles.update(self.subs.styles)
        output.aegisub_project.update(self.subs.aegisub_project)

        beginning_record = pysubs2.SSAEvent(
            start=0,
            end=BEGINNING_DURATION_MS,
            text="Начало",
        )
        output.append(beginning_record)

        for event in self.subs:
            if event.type != "Dialogue":
                continue

            # Пропускаем исходную запись «Начало», если она уже есть в файле,
            # чтобы не создавать дубль с той, что вставили выше.
            if event.start == 0 and event.text.strip() == "Начало":
                continue

            if event.text.strip() == TECH_MARKER:
                tech_event = event.copy()
                tech_event.text = (
                    f"{TECH_INFO_PREFIX} {project_description} {series_description}"
                )
                output.append(tech_event)
                continue

            if self.use_name:
                names = {n.strip() for n in event.name.split(";")}
                if role not in names:
                    continue
                filtered = event.copy()
                filtered.name = role
            else:
                if event.style.strip() != role:
                    continue
                filtered = event.copy()

            output.append(filtered)

        return output

    def get_role_content(
        self,
        role: str,
        project_description: str = "",
        series_description: str = "",
        output_format: Literal["ass", "srt"] = "srt",
    ) -> str:
        """
        Возвращает содержимое файла для указанной роли в виде строки,
        не сохраняя на диск.
        """
        output = self._build_role_ssa_file(role, project_description, series_description)
        content = output.to_string(output_format)
        if output_format == "srt":
            content = _SRT_CLEANUP_RE.sub("", content)
        return content

    def save_role(
        self,
        role: str,
        output_path: str,
        project_description: str = "",
        series_description: str = "",
        output_format: Literal["ass", "srt"] = "ass",
    ) -> None:
        """
        Сохраняет копию субтитров только с репликами указанной роли.

        В начало файла вставляется реплика «Начало» (0,1 с).
        Если в исходнике есть строка-маркер «!t», она добавляется
        с текстом «!ТЕХ ИНФ {project_description} {series_description}»,
        сохраняя оригинальные тайминги.

        Args:
            role:                 имя роли (должно быть в self.roles).
            output_path:          путь для сохранения выходного файла.
            project_description:  описание проекта для строки !ТЕХ ИНФ.
            series_description:   описание серии для строки !ТЕХ ИНФ.
            output_format:        формат выходного файла — «ass» или «srt».
        """
        output = self._build_role_ssa_file(role, project_description, series_description)
        if output_format == "srt":
            content = _HTML_TAG_RE.sub("", output.to_string("srt"))
            with open(output_path, "w", encoding="utf-8-sig") as f:
                f.write(content)
        else:
            output.save(output_path, format_=output_format, encoding="utf-8")

    def save_all_roles(
        self,
        output_dir: str,
        base_name: str | None = None,
        project_description: str = "",
        series_description: str = "",
        output_format: Literal["ass", "srt"] = "ass",
    ) -> None:
        """
        Сохраняет отдельный файл для каждой найденной роли.

        Args:
            output_dir:           директория для сохранения файлов.
            base_name:            базовое имя файлов (без расширения).
                                  По умолчанию — имя исходного файла без расширения.
            project_description:  описание проекта для строки !ТЕХ ИНФ.
            series_description:   описание серии для строки !ТЕХ ИНФ.
            output_format:        формат выходных файлов — «ass» или «srt».
        """
        if self.subs is None:
            raise RuntimeError("Файл не загружен. Вызовите load() сначала.")

        if base_name is None:
            base_name = os.path.splitext(os.path.basename(self.filename))[0]

        os.makedirs(output_dir, exist_ok=True)

        for role in sorted(self.roles):
            output_path = os.path.join(output_dir, f"{base_name} {role}.{output_format}")
            self.save_role(
                role,
                output_path,
                project_description=project_description,
                series_description=series_description,
                output_format=output_format,
            )

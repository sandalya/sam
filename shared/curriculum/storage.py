"""
shared/curriculum/storage.py — читання/запис CurriculumState у JSON.

Ключові принципи:
- Атомарний запис через tmp+rename (не залишає пошкоджений файл при збої)
- Граційна обробка відсутніх файлів — повертає порожній CurriculumState
- Валідація на завантаженні — warnings логуються, не кидають
- Бекапи з timestamp перед небезпечними операціями

Референс: workspace/sam/docs/DATA_MODEL.md
"""
from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import CurriculumState, SCHEMA_VERSION, validate

log = logging.getLogger("shared.curriculum.storage")


class CurriculumStorageError(Exception):
    """Помилка читання/запису курікулома."""


# ─── Load ─────────────────────────────────────────────────────────────────────

def load(path: Path | str) -> CurriculumState:
    """
    Завантажує CurriculumState з JSON.

    Якщо файлу немає — повертає порожній стан (новий користувач).
    Якщо JSON битий — кидає CurriculumStorageError.
    Warnings валідації — логуються, не кидають.

    Для міграцій зі старих версій схеми див. migrate_if_needed().
    """
    p = Path(path)

    if not p.exists():
        log.info(f"No curriculum file at {p}, returning empty state")
        return CurriculumState()

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CurriculumStorageError(f"Corrupted JSON at {p}: {e}") from e

    # Підтримуємо тільки поточну версію. Для міграцій — окрема функція.
    file_version = data.get("schema_version", 0)
    if file_version != SCHEMA_VERSION:
        raise CurriculumStorageError(
            f"Schema version mismatch in {p}: file={file_version}, "
            f"code={SCHEMA_VERSION}. Run migrate_if_needed() first."
        )

    try:
        state = CurriculumState.from_dict(data)
    except (KeyError, TypeError) as e:
        raise CurriculumStorageError(f"Cannot deserialize {p}: {e}") from e

    warnings = validate(state)
    if warnings:
        log.warning(
            f"Curriculum loaded from {p} with {len(warnings)} validation issues:"
        )
        for w in warnings:
            log.warning(f"  - {w}")

    return state


# ─── Save (atomic) ────────────────────────────────────────────────────────────

def save(state: CurriculumState, path: Path | str) -> None:
    """
    Атомарно зберігає CurriculumState в JSON.

    Процес: пише в tmp-файл поруч, викликає rename (atomic на posix),
    що гарантує або повністю новий файл, або повністю старий —
    ніколи не буде напівзаписаного.

    Валідація — попередженням (не блокує запис).
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    warnings = validate(state)
    if warnings:
        log.warning(
            f"Saving curriculum with {len(warnings)} validation issues to {p}"
        )
        for w in warnings:
            log.warning(f"  - {w}")

    data = state.to_dict()
    # Гарантуємо що schema_version свіжий — навіть якщо в state він застарілий
    data["schema_version"] = SCHEMA_VERSION

    tmp = p.with_suffix(p.suffix + ".tmp")
    try:
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(p)  # atomic на всіх posix-системах
    except OSError as e:
        tmp.unlink(missing_ok=True)
        raise CurriculumStorageError(f"Cannot save curriculum to {p}: {e}") from e

    log.debug(f"Saved curriculum to {p} (schema v{SCHEMA_VERSION})")


# ─── Backup ───────────────────────────────────────────────────────────────────

def backup(path: Path | str, suffix: Optional[str] = None) -> Optional[Path]:
    """
    Робить копію файлу з timestamp перед небезпечними операціями.

    Повертає шлях до бекапу, або None якщо оригіналу немає.

    suffix — довільна мітка в імені, напр. "before_migration".
    """
    p = Path(path)
    if not p.exists():
        log.info(f"No file to backup at {p}")
        return None

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    label = f"_{suffix}" if suffix else ""
    backup_path = p.with_name(f"{p.stem}.backup{label}_{ts}{p.suffix}")

    try:
        shutil.copy2(p, backup_path)
    except OSError as e:
        raise CurriculumStorageError(f"Cannot backup {p}: {e}") from e

    log.info(f"Backed up {p} -> {backup_path}")
    return backup_path


# ─── Load-or-create helper ────────────────────────────────────────────────────

def load_or_create(path: Path | str, learning_vector: str = "") -> CurriculumState:
    """
    Завантажує стан, або створює новий порожній якщо файлу немає.

    Зручно для startup-коду який не хоче розрізняти "перший запуск"
    і "наступний запуск".
    """
    p = Path(path)
    if p.exists():
        return load(p)

    state = CurriculumState(learning_vector=learning_vector)
    save(state, p)
    log.info(f"Created new empty curriculum at {p}")
    return state


# ─── Schema migration stub ────────────────────────────────────────────────────

def migrate_if_needed(path: Path | str) -> bool:
    """
    Перевіряє чи файл потребує міграції на нову версію схеми.

    Наразі маємо тільки v1 — нічого не мігруємо.
    Коли з'явиться v2 — тут будуть виклики migrate_v1_to_v2 і т.д.

    Повертає True якщо міграція виконана, False якщо не потрібна.
    """
    p = Path(path)
    if not p.exists():
        return False

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise CurriculumStorageError(f"Cannot read {p} for migration check")

    file_version = data.get("schema_version", 0)
    if file_version == SCHEMA_VERSION:
        return False

    if file_version > SCHEMA_VERSION:
        raise CurriculumStorageError(
            f"File at {p} has newer schema v{file_version} than code v{SCHEMA_VERSION}. "
            f"Update the code or downgrade the file."
        )

    # Тут будуть майбутні міграції v1->v2 тощо
    raise CurriculumStorageError(
        f"Migration from schema v{file_version} to v{SCHEMA_VERSION} "
        f"is not implemented yet."
    )

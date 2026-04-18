"""
shared/curriculum/migration.py — міграція legacy курікулома на нову модель.

ДИЗАЙН: two-pass з чорновиком.

Pass 1 — plan_migration():
  - Читає legacy-теми (CURRICULUM hardcoded + curriculum_dynamic.json)
  - Читає legacy-стан (learning_state.json — completed/started)
  - Читає legacy-NBLM прив'язки (notebooklm_notebooks.json)
  - Викликає LLM-кластеризацію (islands.cluster_topics_for_migration)
  - Викликає LLM для content_style (islands.determine_content_style)
  - Генерує нові ID в форматі {island_slug}-{n}
  - Зберігає ЧОРНОВИК у data/migration_draft.json
  - Саша може редагувати чорновик руками (це чистий JSON)

Pass 2 — apply_migration():
  - Читає чорновик
  - Бекапить legacy файли (з префіксом _legacy_ + timestamp)
  - Створює curriculum.json за чорновиком
  - Перемаповує ключі в notebooklm_notebooks.json на нові ID
  - Валідує результат

Після apply: Sam використовує новий курікулом. Старі файли залишаються
як бекапи. Можна повторити міграцію якщо чорновик змінили.

Референс: sam/docs/DATA_MODEL.md розділ 3, BOOTSTRAP_DIALOG.md
"""
from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import (
    Island, Topic, TopicFormat, CurriculumState,
    SCHEMA_VERSION, validate,
)
from .storage import save, backup
from .islands import (
    ClusteringProposal, cluster_topics_for_migration, determine_content_style,
)

log = logging.getLogger("shared.curriculum.migration")


# ─── Маппінг форматів legacy → new ────────────────────────────────────────────

# Старі NBLM-ключі з notebooklm_notebooks.json[id].generated
# на нові формати в TopicFormat
LEGACY_FORMAT_MAP: dict[str, Optional[str]] = {
    "video":       "video",
    "podcast":     "podcast_nblm",   # перейменовано
    "audio":       "podcast_nblm",   # був дубль podcast
    "study":       None,             # викидаємо
    "briefing":    None,             # викидаємо
    "mindmap":     None,             # викидаємо
    "flashcards":  "flashcards",
    "slides":      "slides",
    "infographic": "infographic",
}


# ─── Чорновик міграції (Pass 1 output) ────────────────────────────────────────

@dataclass
class TopicDraft:
    """Планований стан однієї теми в чорновику міграції."""
    legacy_id: int
    new_id: str                # {island-slug}-{n}
    island_id: str
    title: str
    why: str = ""
    read: str = ""
    do: str = ""
    estimate: str = ""
    state: str = "active"
    content_style: str = "audio"
    formats: dict[str, dict] = field(default_factory=dict)  # fmt_key -> {status, url, consumed...}

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TopicDraft":
        return cls(
            legacy_id=int(data["legacy_id"]),
            new_id=str(data["new_id"]),
            island_id=str(data["island_id"]),
            title=str(data["title"]),
            why=str(data.get("why", "")),
            read=str(data.get("read", "")),
            do=str(data.get("do", "")),
            estimate=str(data.get("estimate", "")),
            state=str(data.get("state", "active")),
            content_style=str(data.get("content_style", "audio")),
            formats=dict(data.get("formats", {})),
        )


@dataclass
class IslandDraft:
    """Планований стан одного острова в чорновику міграції."""
    id: str
    title: str
    description: str
    is_gap: bool = False
    order: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "IslandDraft":
        return cls(
            id=str(data["id"]),
            title=str(data["title"]),
            description=str(data.get("description", "")),
            is_gap=bool(data.get("is_gap", False)),
            order=int(data.get("order", 0)),
        )


@dataclass
class MigrationDraft:
    """Чорновик — результат plan_migration(), вхід для apply_migration()."""
    created_at: str
    learning_vector: str
    islands: list[IslandDraft]
    topics: list[TopicDraft]
    reasoning: str = ""                    # пояснення LLM чому саме так
    legacy_to_new_id: dict[str, str] = field(default_factory=dict)  # "1" -> "agents-1"
    unmapped_nblm_keys: list[str] = field(default_factory=list)     # ключі в notebooklm_notebooks.json без теми

    def to_dict(self) -> dict:
        return {
            "created_at": self.created_at,
            "learning_vector": self.learning_vector,
            "reasoning": self.reasoning,
            "islands": [i.to_dict() for i in self.islands],
            "topics": [t.to_dict() for t in self.topics],
            "legacy_to_new_id": dict(self.legacy_to_new_id),
            "unmapped_nblm_keys": list(self.unmapped_nblm_keys),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MigrationDraft":
        return cls(
            created_at=str(data.get("created_at", "")),
            learning_vector=str(data.get("learning_vector", "")),
            reasoning=str(data.get("reasoning", "")),
            islands=[IslandDraft.from_dict(i) for i in data.get("islands", [])],
            topics=[TopicDraft.from_dict(t) for t in data.get("topics", [])],
            legacy_to_new_id={str(k): str(v) for k, v in data.get("legacy_to_new_id", {}).items()},
            unmapped_nblm_keys=[str(k) for k in data.get("unmapped_nblm_keys", [])],
        )

    def summary(self) -> str:
        """Людський короткий підсумок (для чату)."""
        populated = [i for i in self.islands if not i.is_gap]
        gaps = [i for i in self.islands if i.is_gap]

        lines = [
            f"📋 Чорновик міграції (від {self.created_at})",
            f"",
            f"Learning vector: {self.learning_vector}",
            f"",
            f"🏝 Острови ({len(populated)} заповнених, {len(gaps)} прогалин):",
        ]
        for island in populated:
            topics = [t for t in self.topics if t.island_id == island.id]
            lines.append(f"  • {island.title} — {len(topics)} тем")
            for t in topics:
                lines.append(f"      - {t.new_id}: {t.title}")
        if gaps:
            lines.append("")
            lines.append(f"⚠️ Прогалини:")
            for g in gaps:
                lines.append(f"  • {g.title} — {g.description}")

        if self.unmapped_nblm_keys:
            lines.append("")
            lines.append(f"🔸 NBLM notebooks без відповідної теми: {len(self.unmapped_nblm_keys)}")
            lines.append(f"  (ключі: {', '.join(self.unmapped_nblm_keys[:5])}{'...' if len(self.unmapped_nblm_keys) > 5 else ''})")

        lines.append("")
        lines.append(f"Всього тем: {len(self.topics)}")
        if self.reasoning:
            lines.append(f"Логіка: {self.reasoning}")
        return "\n".join(lines)


# ─── Pass 1: Планування ───────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_legacy_topics(
    seed_topics: list[dict],
    dynamic_path: Path,
) -> list[dict]:
    """Об'єднує seed CURRICULUM + dynamic JSON у єдиний список."""
    topics: list[dict] = []

    # seed — беремо весь список як є
    for t in seed_topics:
        topics.append({
            "id": int(t["id"]),
            "title": str(t.get("title", "")),
            "why": str(t.get("why", "")),
            "read": str(t.get("read", "")),
            "do": str(t.get("do", "")),
            "estimate": str(t.get("estimate", "")),
            "category": str(t.get("category", "")),
        })

    # dynamic — з файлу
    if dynamic_path.exists():
        try:
            raw = json.loads(dynamic_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            log.error(f"Cannot parse {dynamic_path}: {e}")
            raise
        for t in raw:
            topics.append({
                "id": int(t["id"]),
                "title": str(t.get("title", "")),
                "why": str(t.get("why", "")),
                "read": str(t.get("read", "")),
                "do": str(t.get("do", "")),
                "estimate": str(t.get("estimate", "")),
                "category": str(t.get("category", "")),
            })

    # Перевірка на duplicate ID
    ids = [t["id"] for t in topics]
    if len(ids) != len(set(ids)):
        dupes = [i for i in ids if ids.count(i) > 1]
        raise ValueError(f"Duplicate legacy IDs between seed and dynamic: {sorted(set(dupes))}")

    log.info(f"Loaded {len(topics)} legacy topics ({len(seed_topics)} seed + {len(topics) - len(seed_topics)} dynamic)")
    return topics


def _load_nblm_state(nblm_path: Path) -> dict:
    if not nblm_path.exists():
        log.warning(f"No NBLM state at {nblm_path}")
        return {}
    try:
        return json.loads(nblm_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        log.error(f"Cannot parse {nblm_path}: {e}")
        return {}


def _generate_new_ids(
    proposal: ClusteringProposal,
    topics: list[dict],
) -> tuple[dict[int, str], list[TopicDraft]]:
    """
    Генерує нові ID для тем у форматі {island_slug}-{n}.
    Повертає (mapping legacy_id → new_id, список TopicDraft).
    """
    topics_by_id: dict[int, dict] = {int(t["id"]): t for t in topics}
    assignment = proposal.assignment_map()  # int -> island_slug

    legacy_to_new: dict[int, str] = {}
    drafts: list[TopicDraft] = []

    # Групуємо теми по островах (щоб номерувати коректно)
    by_island: dict[str, list[int]] = {}
    for lid, island_id in assignment.items():
        by_island.setdefault(island_id, []).append(lid)

    for island_id, lids in by_island.items():
        # Стабільний порядок: за зростанням legacy_id (детермінована нумерація)
        lids_sorted = sorted(lids)
        for n, lid in enumerate(lids_sorted, start=1):
            new_id = f"{island_id}-{n}"
            legacy_to_new[lid] = new_id
            t = topics_by_id[lid]
            drafts.append(TopicDraft(
                legacy_id=lid,
                new_id=new_id,
                island_id=island_id,
                title=t["title"],
                why=t.get("why", ""),
                read=t.get("read", ""),
                do=t.get("do", ""),
                estimate=t.get("estimate", ""),
                state="active",             # дефолт, користувач перепроставить
                content_style="audio",      # заповнимо далі через determine_content_style
                formats={},                 # заповнимо далі з NBLM state
            ))

    return legacy_to_new, drafts


def _apply_content_styles(drafts: list[TopicDraft]) -> None:
    """Визначає content_style для всіх тем одним LLM-викликом, оновлює drafts in-place."""
    topics_for_llm = [
        {"id": str(d.legacy_id), "title": d.title, "why": d.why}
        for d in drafts
    ]
    styles = determine_content_style(topics_for_llm)
    for d in drafts:
        d.content_style = styles.get(str(d.legacy_id), "audio")


def _apply_legacy_formats(
    drafts: list[TopicDraft],
    nblm_state: dict,
) -> list[str]:
    """
    Для кожного TopicDraft переносить дані з NBLM state у формат TopicFormat (dict).
    Повертає список ключів в NBLM state які не знайшли відповідної теми.
    """
    drafts_by_lid: dict[int, TopicDraft] = {d.legacy_id: d for d in drafts}
    unmapped: list[str] = []

    for key, entry in nblm_state.items():
        try:
            lid = int(key)
        except (ValueError, TypeError):
            unmapped.append(key)
            continue

        draft = drafts_by_lid.get(lid)
        if not draft:
            unmapped.append(key)
            continue

        # entry може бути dict {notebook_id, generated, pending, status}, або плоский str
        if isinstance(entry, dict):
            notebook_id = entry.get("notebook_id")
            generated = entry.get("generated", [])
        elif isinstance(entry, str):
            notebook_id = entry
            generated = []
        else:
            continue

        nb_url = (
            f"https://notebooklm.google.com/notebook/{notebook_id}"
            if notebook_id else None
        )

        for legacy_fmt in generated:
            new_fmt = LEGACY_FORMAT_MAP.get(legacy_fmt)
            if new_fmt is None:
                continue  # викидаємо old formats (study, briefing, mindmap)
            # Якщо вже додано через дубль (podcast + audio → podcast_nblm) — не переписуємо
            if new_fmt in draft.formats:
                continue
            draft.formats[new_fmt] = {
                "status": "ready",
                "consumed": False,
                "generated_at": None,
                "consumed_at": None,
                "url": nb_url,
                "error": None,
            }

    return unmapped


def plan_migration(
    *,
    seed_topics: list[dict],
    data_dir: Path | str,
    learning_vector: str,
    draft_path: Optional[Path | str] = None,
) -> MigrationDraft:
    """
    Pass 1: створює чорновик міграції, зберігає в draft_path.

    Args:
        seed_topics: список CURRICULUM з modules/curriculum.py (5 seed-тем)
        data_dir: директорія де лежать curriculum_dynamic.json, notebooklm_notebooks.json
        learning_vector: текст про напрямок Саші
        draft_path: куди зберегти чорновик. Default: {data_dir}/migration_draft.json

    Returns:
        MigrationDraft — також збережений на диск.
    """
    data_dir = Path(data_dir)
    dynamic_path = data_dir / "curriculum_dynamic.json"
    nblm_path = data_dir / "notebooklm_notebooks.json"
    if draft_path is None:
        draft_path = data_dir / "migration_draft.json"
    draft_path = Path(draft_path)

    log.info(f"Starting migration planning: data_dir={data_dir}")

    # 1. Зберемо всі legacy теми
    legacy_topics = _load_legacy_topics(seed_topics, dynamic_path)
    nblm_state = _load_nblm_state(nblm_path)

    # 2. LLM кластеризація на острови
    topics_for_llm = [
        {"id": t["id"], "title": t["title"], "why": t["why"], "category": t["category"]}
        for t in legacy_topics
    ]
    log.info(f"Clustering {len(topics_for_llm)} topics into islands...")
    proposal = cluster_topics_for_migration(topics_for_llm, learning_vector)
    log.info(
        f"LLM proposed {len(proposal.populated_islands())} populated islands "
        f"+ {len(proposal.gap_islands())} gaps"
    )

    # 3. Генерація нових ID
    legacy_to_new_int, drafts = _generate_new_ids(proposal, legacy_topics)

    # 4. Content style (ще один LLM виклик)
    log.info(f"Determining content_style for {len(drafts)} topics...")
    _apply_content_styles(drafts)

    # 5. Перенесення NBLM форматів у стан тем
    unmapped = _apply_legacy_formats(drafts, nblm_state)

    # 6. Збираємо islands drafts (populated + gap)
    island_drafts: list[IslandDraft] = []
    for order, island in enumerate(proposal.islands):
        island_drafts.append(IslandDraft(
            id=island.id,
            title=island.title,
            description=island.description,
            is_gap=island.is_gap,
            order=order,
        ))

    # 7. Чорновик
    draft = MigrationDraft(
        created_at=_now(),
        learning_vector=learning_vector,
        islands=island_drafts,
        topics=drafts,
        reasoning=proposal.reasoning,
        legacy_to_new_id={str(k): v for k, v in legacy_to_new_int.items()},
        unmapped_nblm_keys=unmapped,
    )

    # 8. Зберегти чорновик
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text(
        json.dumps(draft.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info(f"Migration draft saved to {draft_path}")

    return draft


def load_draft(draft_path: Path | str) -> MigrationDraft:
    """Читає чорновик з диска."""
    p = Path(draft_path)
    if not p.exists():
        raise FileNotFoundError(f"No migration draft at {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    return MigrationDraft.from_dict(data)


# ─── Pass 2: Застосування ─────────────────────────────────────────────────────

@dataclass
class MigrationResult:
    """Повертається з apply_migration() — що саме зроблено."""
    curriculum_path: Path
    backups: list[Path] = field(default_factory=list)   # створені бекапи
    remapped_nblm_keys: int = 0                         # скільки ключів перепозначено
    dropped_nblm_keys: list[str] = field(default_factory=list)  # які ключі викинули

    def summary(self) -> str:
        lines = [
            f"✅ Міграцію застосовано",
            f"  curriculum.json → {self.curriculum_path}",
            f"  бекапів створено: {len(self.backups)}",
            f"  NBLM ключів перепозначено: {self.remapped_nblm_keys}",
        ]
        if self.dropped_nblm_keys:
            lines.append(f"  NBLM ключів викинуто (без теми): {len(self.dropped_nblm_keys)}")
        return "\n".join(lines)


def _backup_legacy_files(data_dir: Path, suffix: str) -> list[Path]:
    """
    Робить копії legacy файлів з префіксом _legacy_ перед зміною.
    Повертає список шляхів до бекапів.
    """
    legacy_files = [
        "curriculum_dynamic.json",
        "learning_state.json",
        "notebooklm_notebooks.json",
    ]
    backups: list[Path] = []
    for fname in legacy_files:
        src = data_dir / fname
        if not src.exists():
            continue
        dst = data_dir / f"_legacy_{src.stem}_{suffix}{src.suffix}"
        shutil.copy2(src, dst)
        backups.append(dst)
        log.info(f"Backup: {src.name} → {dst.name}")
    return backups


def _remap_nblm_state(
    data_dir: Path,
    legacy_to_new_id: dict[str, str],
) -> tuple[int, list[str]]:
    """
    Переписує ключі в notebooklm_notebooks.json зі старих (int як string)
    на нові ({island}-{n}).

    Ключі що не знайдені в mapping — видаляються (з логуванням).
    Повертає (скільки remapped, список dropped keys).
    """
    nblm_path = data_dir / "notebooklm_notebooks.json"
    if not nblm_path.exists():
        return 0, []

    try:
        data = json.loads(nblm_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Cannot parse {nblm_path}: {e}") from e

    new_data: dict = {}
    remapped = 0
    dropped: list[str] = []
    for old_key, entry in data.items():
        new_key = legacy_to_new_id.get(old_key)
        if new_key is None:
            dropped.append(old_key)
            continue
        new_data[new_key] = entry
        remapped += 1

    # Атомарний запис
    tmp = nblm_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(new_data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(nblm_path)

    log.info(f"NBLM state remapped: {remapped} kept, {len(dropped)} dropped")
    if dropped:
        log.warning(f"Dropped NBLM keys (no matching topic): {dropped}")
    return remapped, dropped


def _draft_to_curriculum_state(draft: MigrationDraft) -> CurriculumState:
    """Конвертує чорновик у повноцінний CurriculumState."""
    islands = [
        Island(
            id=i.id,
            title=i.title,
            description=i.description,
            order=i.order,
        )
        for i in draft.islands
    ]

    topics: list[Topic] = []
    for td in draft.topics:
        fmts: dict[str, TopicFormat] = {}
        for fmt_key, fmt_data in td.formats.items():
            fmts[fmt_key] = TopicFormat(
                status=fmt_data.get("status", "pending"),
                consumed=fmt_data.get("consumed", False),
                generated_at=fmt_data.get("generated_at"),
                consumed_at=fmt_data.get("consumed_at"),
                url=fmt_data.get("url"),
                error=fmt_data.get("error"),
            )
        topics.append(Topic(
            id=td.new_id,
            island_id=td.island_id,
            title=td.title,
            why=td.why,
            read=td.read,
            do=td.do,
            estimate=td.estimate,
            state=td.state,  # type: ignore[arg-type]
            content_style=td.content_style,  # type: ignore[arg-type]
            legacy_id=td.legacy_id,
            formats=fmts,
        ))

    state = CurriculumState(
        schema_version=SCHEMA_VERSION,
        learning_vector=draft.learning_vector,
        islands=islands,
        topics=topics,
        migrated_from=draft.created_at,
    )
    return state


def apply_migration(
    draft: MigrationDraft,
    data_dir: Path | str,
    *,
    curriculum_path: Optional[Path | str] = None,
) -> MigrationResult:
    """
    Pass 2: застосовує чорновик. Створює curriculum.json, перемаповує NBLM keys,
    робить бекапи legacy файлів.

    Args:
        draft: результат plan_migration() або відредагований вручну
        data_dir: директорія зі старими файлами
        curriculum_path: куди писати новий курікулом. Default: {data_dir}/curriculum.json

    Returns:
        MigrationResult з деталями.
    """
    data_dir = Path(data_dir)
    if curriculum_path is None:
        curriculum_path = data_dir / "curriculum.json"
    curriculum_path = Path(curriculum_path)

    # Якщо вже є curriculum.json — це повторна міграція, зробимо його бекап
    if curriculum_path.exists():
        bp = backup(curriculum_path, suffix="before_reapply")
        log.warning(f"curriculum.json already exists, backed up to {bp}")

    suffix = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # 1. Бекапи legacy
    backups = _backup_legacy_files(data_dir, suffix)

    # 2. Конвертуємо draft → CurriculumState
    state = _draft_to_curriculum_state(draft)

    # 3. Валідація
    warnings = validate(state)
    if warnings:
        log.warning(f"Curriculum state has {len(warnings)} validation warnings:")
        for w in warnings:
            log.warning(f"  - {w}")

    # 4. Пишемо curriculum.json
    save(state, curriculum_path)
    log.info(f"Wrote curriculum.json to {curriculum_path}")

    # 5. Перемапимо NBLM ключі
    remapped_count, dropped = _remap_nblm_state(data_dir, draft.legacy_to_new_id)

    return MigrationResult(
        curriculum_path=curriculum_path,
        backups=backups,
        remapped_nblm_keys=remapped_count,
        dropped_nblm_keys=dropped,
    )

"""
shared/curriculum/models.py — модель даних нового курікулома Sam.

Сутності:
- Island       — смислова група тем (RAG, Agents, Evals...)
- Topic        — одиниця вивчення з власним пайплайном контенту
- TopicFormat  — стан одного формату в темі (slides, podcast_nblm, etc.)
- CurriculumState — верхній рівень (острови + теми + метадані)

Серіалізація — to_dict / from_dict руками, без зовнішніх залежностей.
Формат файлу — JSON зі schema_version для майбутніх міграцій.

Референс: workspace/sam/docs/DATA_MODEL.md
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Literal, Optional


# ─── Типи-літерали для type-safety і валідації ────────────────────────────────

TopicState = Literal["pending", "active", "mastered"]
ContentStyle = Literal["audio", "visual"]
FormatStatus = Literal["pending", "generating", "ready", "failed", "skipped"]
FormatKey = Literal[
    "slides",
    "podcast_nblm",
    "podcast_tts",
    "video",
    "infographic",
    "flashcards",
    "exam",
]

ALLOWED_FORMATS: tuple[FormatKey, ...] = (
    "slides",
    "podcast_nblm",
    "podcast_tts",
    "video",
    "infographic",
    "flashcards",
    "exam",
)

ALLOWED_TOPIC_STATES: tuple[TopicState, ...] = ("pending", "active", "mastered")
ALLOWED_CONTENT_STYLES: tuple[ContentStyle, ...] = ("audio", "visual")
ALLOWED_FORMAT_STATUSES: tuple[FormatStatus, ...] = (
    "pending",
    "generating",
    "ready",
    "failed",
    "skipped",
)

SCHEMA_VERSION = 1


def _now_iso() -> str:
    """UTC timestamp в ISO 8601 форматі."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ─── TopicFormat ──────────────────────────────────────────────────────────────

@dataclass
class TopicFormat:
    """Стан одного формату в темі."""
    status: FormatStatus = "pending"
    consumed: bool = False
    generated_at: Optional[str] = None
    consumed_at: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TopicFormat":
        return cls(
            status=data.get("status", "pending"),
            consumed=data.get("consumed", False),
            generated_at=data.get("generated_at"),
            consumed_at=data.get("consumed_at"),
            url=data.get("url"),
            error=data.get("error"),
        )


# ─── Island ───────────────────────────────────────────────────────────────────

@dataclass
class Island:
    """Смислова група тем. Теми живуть всередині островів."""
    id: str                # slug, напр. "rag", "agents"
    title: str             # людське ім'я, напр. "RAG & Retrieval"
    description: str       # 1-2 речення опису
    order: int = 0         # порядок у UI (0-based)
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Island":
        return cls(
            id=data["id"],
            title=data["title"],
            description=data.get("description", ""),
            order=data.get("order", 0),
            created_at=data.get("created_at") or _now_iso(),
        )


# ─── Topic ────────────────────────────────────────────────────────────────────

@dataclass
class Topic:
    """Одиниця вивчення з власним пайплайном контенту."""
    id: str                                           # "{island-slug}-{n}", напр. "rag-1"
    island_id: str                                    # посилання на Island
    title: str
    why: str = ""
    read: str = ""                                    # URL основного ресурсу
    do: str = ""                                      # практична задача
    estimate: str = ""                                # "1-2 дні"
    state: TopicState = "pending"
    content_style: ContentStyle = "audio"
    parent_topic_id: Optional[str] = None             # для підтем (Фаза 6)
    crosslinks: list[str] = field(default_factory=list)  # ID пов'язаних тем
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    mastered_at: Optional[str] = None
    legacy_id: Optional[int] = None                   # старий числовий ID (для NBLM маппінга)
    formats: dict[str, TopicFormat] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        # formats — окремо, бо asdict розгортає dataclass → dict, але ми хочемо явно
        d["formats"] = {k: v.to_dict() if isinstance(v, TopicFormat) else v
                        for k, v in self.formats.items()}
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Topic":
        formats_raw = data.get("formats", {})
        formats = {
            k: TopicFormat.from_dict(v) for k, v in formats_raw.items()
        }
        return cls(
            id=data["id"],
            island_id=data["island_id"],
            title=data["title"],
            why=data.get("why", ""),
            read=data.get("read", ""),
            do=data.get("do", ""),
            estimate=data.get("estimate", ""),
            state=data.get("state", "pending"),
            content_style=data.get("content_style", "audio"),
            parent_topic_id=data.get("parent_topic_id"),
            crosslinks=list(data.get("crosslinks", [])),
            created_at=data.get("created_at") or _now_iso(),
            updated_at=data.get("updated_at") or _now_iso(),
            mastered_at=data.get("mastered_at"),
            legacy_id=data.get("legacy_id"),
            formats=formats,
        )

    # ── Зручні хелпери (read-only, без зміни стану) ──────────────────────────

    def format(self, key: FormatKey) -> TopicFormat:
        """Повертає TopicFormat для ключа, створюючи pending якщо немає."""
        if key not in self.formats:
            self.formats[key] = TopicFormat()
        return self.formats[key]

    def formats_ready_count(self) -> int:
        """Скільки форматів в стані ready."""
        return sum(1 for f in self.formats.values() if f.status == "ready")

    def formats_consumed_count(self) -> int:
        """Скільки форматів позначено spожитими."""
        return sum(1 for f in self.formats.values() if f.consumed)

    def is_mastered(self) -> bool:
        return self.state == "mastered"

    def is_pending(self) -> bool:
        return self.state == "pending"

    def is_active(self) -> bool:
        return self.state == "active"


# ─── CurriculumState (верхній рівень) ─────────────────────────────────────────

@dataclass
class CurriculumState:
    """Кореневий обʼєкт курікулома. Одна штука на користувача."""
    schema_version: int = SCHEMA_VERSION
    learning_vector: str = ""
    islands: list[Island] = field(default_factory=list)
    topics: list[Topic] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)
    migrated_from: Optional[str] = None

    # ── Серіалізація ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "learning_vector": self.learning_vector,
            "created_at": self.created_at,
            "migrated_from": self.migrated_from,
            "islands": [i.to_dict() for i in self.islands],
            "topics": [t.to_dict() for t in self.topics],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CurriculumState":
        return cls(
            schema_version=data.get("schema_version", 1),
            learning_vector=data.get("learning_vector", ""),
            islands=[Island.from_dict(i) for i in data.get("islands", [])],
            topics=[Topic.from_dict(t) for t in data.get("topics", [])],
            created_at=data.get("created_at") or _now_iso(),
            migrated_from=data.get("migrated_from"),
        )

    # ── Пошук та навігація ───────────────────────────────────────────────────

    def get_island(self, island_id: str) -> Optional[Island]:
        return next((i for i in self.islands if i.id == island_id), None)

    def get_topic(self, topic_id: str) -> Optional[Topic]:
        return next((t for t in self.topics if t.id == topic_id), None)

    def topics_in_island(self, island_id: str) -> list[Topic]:
        return [t for t in self.topics if t.island_id == island_id]

    def topics_by_state(self, state: TopicState) -> list[Topic]:
        return [t for t in self.topics if t.state == state]

    def child_topics(self, parent_id: str) -> list[Topic]:
        return [t for t in self.topics if t.parent_topic_id == parent_id]

    # ── Підрахунки для UI ────────────────────────────────────────────────────

    def counts(self) -> dict[str, int]:
        return {
            "total": len(self.topics),
            "pending": sum(1 for t in self.topics if t.state == "pending"),
            "active": sum(1 for t in self.topics if t.state == "active"),
            "mastered": sum(1 for t in self.topics if t.state == "mastered"),
            "islands": len(self.islands),
        }


# ─── Валідація ────────────────────────────────────────────────────────────────

class CurriculumValidationError(ValueError):
    """Помилка валідації моделі курікулома."""


def validate(state: CurriculumState) -> list[str]:
    """
    Перевіряє цілісність стану. Повертає список warning-повідомлень.
    Не кидає — дає змогу завантажити підозрілий стан і залогувати проблеми.
    Для суворої перевірки — викликати validate_strict.
    """
    warnings: list[str] = []

    island_ids = {i.id for i in state.islands}
    topic_ids = {t.id for t in state.topics}

    # Перевірки на рівні islands
    seen_island_ids: set[str] = set()
    for island in state.islands:
        if island.id in seen_island_ids:
            warnings.append(f"Duplicate island id: {island.id}")
        seen_island_ids.add(island.id)
        if not island.id or " " in island.id:
            warnings.append(f"Invalid island id (empty or has spaces): {island.id!r}")

    # Перевірки на рівні topics
    seen_topic_ids: set[str] = set()
    for topic in state.topics:
        if topic.id in seen_topic_ids:
            warnings.append(f"Duplicate topic id: {topic.id}")
        seen_topic_ids.add(topic.id)

        if topic.island_id not in island_ids:
            warnings.append(
                f"Topic {topic.id!r} references non-existent island {topic.island_id!r}"
            )

        if topic.state not in ALLOWED_TOPIC_STATES:
            warnings.append(f"Topic {topic.id!r} has invalid state: {topic.state!r}")

        if topic.content_style not in ALLOWED_CONTENT_STYLES:
            warnings.append(
                f"Topic {topic.id!r} has invalid content_style: {topic.content_style!r}"
            )

        if topic.state == "mastered" and not topic.mastered_at:
            warnings.append(f"Topic {topic.id!r} is mastered but mastered_at is empty")

        for cl in topic.crosslinks:
            if cl not in topic_ids:
                warnings.append(
                    f"Topic {topic.id!r} has crosslink to non-existent topic {cl!r}"
                )

        if topic.parent_topic_id:
            if topic.parent_topic_id == topic.id:
                warnings.append(f"Topic {topic.id!r} has itself as parent")
            elif topic.parent_topic_id not in topic_ids:
                warnings.append(
                    f"Topic {topic.id!r} has non-existent parent {topic.parent_topic_id!r}"
                )

        for fmt_key, fmt in topic.formats.items():
            if fmt_key not in ALLOWED_FORMATS:
                warnings.append(
                    f"Topic {topic.id!r} has unknown format key: {fmt_key!r}"
                )
            if fmt.status not in ALLOWED_FORMAT_STATUSES:
                warnings.append(
                    f"Topic {topic.id!r} format {fmt_key!r} has invalid status: {fmt.status!r}"
                )

    return warnings


def validate_strict(state: CurriculumState) -> None:
    """Кидає CurriculumValidationError якщо є будь-які проблеми."""
    warnings = validate(state)
    if warnings:
        raise CurriculumValidationError(
            f"Curriculum validation failed ({len(warnings)} issues):\n"
            + "\n".join(f"  - {w}" for w in warnings)
        )

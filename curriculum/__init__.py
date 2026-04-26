"""
shared/curriculum/ — модель даних і управління курікуломом Sam.

Публічне API:

    from curriculum import (
        # models
        CurriculumState, Island, Topic, TopicFormat,
        SCHEMA_VERSION, ALLOWED_FORMATS,

        # storage
        load, save, backup, load_or_create,

        # mutations
        add_island, add_topic, set_topic_state, update_topic_fields,
        remove_topic, set_format_status, set_format_url, mark_format_consumed,

        # validation
        validate, validate_strict, CurriculumValidationError,
    )

Для міграції з legacy — див. curriculum.migration.
Для LLM-кластеризації островів — curriculum.islands.
Для рендеру pinned панелі — curriculum.renderer.
"""
from .models import (
    Article,
    # Main entities
    CurriculumState,
    Island,
    Topic,
    TopicFormat,
    # Constants
    SCHEMA_VERSION,
    ALLOWED_FORMATS,
    ALLOWED_TOPIC_STATES,
    ALLOWED_CONTENT_STYLES,
    ALLOWED_FORMAT_STATUSES,
    # Types
    TopicState,
    ContentStyle,
    FormatStatus,
    FormatKey,
    # Validation
    validate,
    validate_strict,
    CurriculumValidationError,
)

from .storage import (
    load,
    save,
    backup,
    load_or_create,
    migrate_if_needed,
    CurriculumStorageError,
)

from .mutations import (
    add_island,
    add_topic,
    set_topic_state,
    update_topic_fields,
    remove_topic,
    set_format_status,
    set_format_url,
    mark_format_consumed,
    set_nblm_notebook_id,
    add_article, remove_article,
    set_article_nblm_notebook_id, set_article_format_status,
)

__all__ = [
    # models
    "CurriculumState", "Island", "Topic", "TopicFormat",
    "SCHEMA_VERSION", "ALLOWED_FORMATS", "ALLOWED_TOPIC_STATES",
    "ALLOWED_CONTENT_STYLES", "ALLOWED_FORMAT_STATUSES",
    "TopicState", "ContentStyle", "FormatStatus", "FormatKey",
    "validate", "validate_strict", "CurriculumValidationError",
    # storage
    "load", "save", "backup", "load_or_create",
    "migrate_if_needed", "CurriculumStorageError",
    # mutations
    "add_island", "add_topic", "set_topic_state", "update_topic_fields",
    "remove_topic", "set_format_status", "set_format_url", "mark_format_consumed",
    "set_nblm_notebook_id",
    "Article",
    "add_article", "remove_article",
    "set_article_nblm_notebook_id", "set_article_format_status",
]

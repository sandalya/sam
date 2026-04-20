"""
sam/modules/pinned.py — pinned /cur2 з новою моделлю курікулома.

Читає curriculum_v2.json через curriculum.storage і рендерить
через curriculum.renderer.render(). Стан закріпленого повідомлення
зберігається у pinned_state_v2.json (окремо від старого pinned_state.json),
щоб старий /cur і новий /cur2 могли жити у чаті паралельно.
"""
import json
import logging
import sys
from pathlib import Path

from telegram.error import BadRequest

# Додаємо workspace root у path щоб імпорти shared працювали при прямому запуску.
# У проді Sam так само імпортує shared, шлях вже у sys.path.
_WORKSPACE = Path(__file__).resolve().parents[2]
if str(_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE))

from curriculum.storage import load as load_curriculum
from curriculum.renderer import render_pinned

log = logging.getLogger("sam.pinned")

BOT_USERNAME = "sashoks_assistant1_sam_bot"


def _state_path(data_dir: Path) -> Path:
    return data_dir / "pinned_state.json"


def _curriculum_path(data_dir: Path) -> Path:
    return data_dir / "curriculum.json"


def load_state(data_dir: Path) -> dict:
    p = _state_path(data_dir)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(data_dir: Path, state: dict) -> None:
    p = _state_path(data_dir)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.rename(p)

# ── Expanded state (pinned_expanded.json) ────────────────────────────────────

def _expanded_path(data_dir: Path) -> Path:
    return data_dir / "pinned_expanded.json"


def load_expanded(data_dir: Path) -> dict:
    """Повертає {"topics": [...], "mastered": bool}."""
    p = _expanded_path(data_dir)
    if not p.exists():
        return {"topics": [], "mastered": False}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return {
            "topics": data.get("topics", []),
            "mastered": data.get("mastered", False),
        }
    except Exception:
        return {"topics": [], "mastered": False}


def save_expanded(data_dir: Path, expanded: dict) -> None:
    p = _expanded_path(data_dir)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(expanded, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.rename(p)


def toggle_topic_expanded(data_dir: Path, topic_id: str) -> bool:
    """Toggle topic у expanded list. Повертає новий стан (True=expanded)."""
    exp = load_expanded(data_dir)
    topics = exp["topics"]
    if topic_id in topics:
        topics.remove(topic_id)
        result = False
    else:
        topics.append(topic_id)
        result = True
    exp["topics"] = topics
    save_expanded(data_dir, exp)
    return result


def toggle_mastered_expanded(data_dir: Path) -> bool:
    """Toggle mastered section. Повертає новий стан."""
    exp = load_expanded(data_dir)
    exp["mastered"] = not exp["mastered"]
    save_expanded(data_dir, exp)
    return exp["mastered"]




def _render_current(data_dir: Path) -> str:
    cur_state = load_curriculum(_curriculum_path(data_dir))
    exp = load_expanded(data_dir)
    return render_pinned(
        cur_state,
        bot_username=BOT_USERNAME,
        expanded_mastered=exp["mastered"],
        expanded_topic_ids=set(exp["topics"]),
    )


async def refresh_pinned(bot, chat_id: int, data_dir: Path) -> int | None:
    """
    Оновлює закріплене /cur2 повідомлення або створює нове.
    Returns: message_id або None якщо не вдалося.
    """
    state = load_state(data_dir)
    msg_id = state.get("message_id")
    text = _render_current(data_dir)

    if msg_id:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            log.info(f"Pinned refreshed (edit) msg_id={msg_id}")
            return msg_id
        except BadRequest as e:
            if "not modified" in str(e).lower():
                log.info(f"Pinned unchanged msg_id={msg_id}")
                return msg_id
            log.warning(f"Pinned edit failed ({e}), creating new")
            save_state(data_dir, {})
            msg_id = None

    sent = await bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    try:
        await bot.pin_chat_message(
            chat_id=chat_id,
            message_id=sent.message_id,
            disable_notification=True,
        )
        save_state(data_dir, {"message_id": sent.message_id})
        log.info(f"Pinned created msg_id={sent.message_id}")
        return sent.message_id
    except Exception as e:
        log.error(f"pin_chat_message failed: {e}")
        return None


async def unpin(bot, chat_id: int, data_dir: Path) -> bool:
    state = load_state(data_dir)
    msg_id = state.get("message_id")
    save_state(data_dir, {})
    if not msg_id:
        return False
    try:
        await bot.unpin_chat_message(chat_id=chat_id, message_id=msg_id)
        log.info(f"Pinned unpinned msg_id={msg_id}")
        return True
    except Exception as e:
        log.warning(f"unpin failed: {e}")
        return False

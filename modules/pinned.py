"""
sam/modules/pinned.py — управління закріпленим /hub повідомленням.

Pinned = той самий рендер що і /hub, але закріплений у чаті і автооновлюється.
State зберігається у data/pinned_state.json як {"message_id": N} або {}.
"""
import json
import logging
from pathlib import Path
from telegram.error import BadRequest

from shared.hub_renderer import hub_page

log = logging.getLogger("sam.pinned")


def _state_path(data_dir: Path) -> Path:
    return data_dir / "pinned_state.json"


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


async def _render_current_hub(data_dir: Path) -> tuple:
    """Рендерить поточний стан /hub через існуючий hub_page()."""
    from modules.curriculum import _get as _get_cur, load_state as _load_cur_state
    inst = _get_cur()
    cur_state = _load_cur_state()
    profile = inst.load_profile()
    all_topics = inst.get_full_curriculum(cur_state, profile)
    text, kb = hub_page(all_topics, page=0, data_dir=data_dir)
    return text, kb


async def refresh_pinned(bot, chat_id: int, data_dir: Path) -> int | None:
    """
    Оновлює закріплене повідомлення або створює нове якщо його ще нема.

    Returns: message_id закріпленого повідомлення, або None якщо не вдалося.
    """
    state = load_state(data_dir)
    msg_id = state.get("message_id")
    text, kb = await _render_current_hub(data_dir)

    # Гілка 1: є msg_id — пробуємо edit
    if msg_id:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=text,
                reply_markup=kb,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            log.info(f"Pinned refreshed (edit) msg_id={msg_id}")
            return msg_id
        except BadRequest as e:
            # "Message is not modified" — контент не змінився, це ок
            if "not modified" in str(e).lower():
                log.info(f"Pinned unchanged msg_id={msg_id}")
                return msg_id
            # Будь-яка інша помилка (видалено, rate limit) — fallback до створення
            log.warning(f"Pinned edit failed ({e}), creating new")
            save_state(data_dir, {})
            msg_id = None

    # Гілка 2: немає msg_id або edit провалився — створюємо нове + пінимо
    sent = await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=kb,
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
    """Знімає закріплення і чистить state. Повертає True якщо вдалося."""
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

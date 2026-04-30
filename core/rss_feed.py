import json
import logging
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
import xml.etree.ElementTree as ET

from core.audio_downloader import download_podcast_audio

log = logging.getLogger("core.rss_feed")

DEFAULT_FEED_META = {
    "base_url": "http://100.86.239.46:8765",
    "title": "Sam AI Podcast",
    "description": "Навчальні подкасти від Sam — AI, агенти, архітектура",
    "author": "Sam",
    "language": "uk-ua",
}

CURRICULUM_PATH = Path(__file__).parent.parent / "data" / "curriculum.json"
AUDIO_DIR = Path(__file__).parent.parent / "data" / "audio"
FEED_XML = Path(__file__).parent.parent / "data" / "feed.xml"


def generate_feed(
    curriculum_path: Path | None = None,
    audio_dir: Path | None = None,
    output_xml: Path | None = None,
    feed_meta: dict | None = None,
) -> Path:
    """
    Сканує curriculum, для кожного ready podcast_nblm викликає downloader,
    генерує RSS 2.0 з podcast extensions (iTunes namespace).
    Returns: Path до feed.xml.
    """
    curriculum_path = curriculum_path or CURRICULUM_PATH
    audio_dir = audio_dir or AUDIO_DIR
    output_xml = output_xml or FEED_XML
    meta = {**DEFAULT_FEED_META, **(feed_meta or {})}
    base_url = meta["base_url"].rstrip("/")

    try:
        state = json.loads(curriculum_path.read_text(encoding="utf-8"))
    except Exception as e:
        log.error(f"rss_feed: failed to read curriculum: {e}")
        raise

    items = []

    for topic in state.get("topics", []):
        fmt = topic.get("formats", {}).get("podcast_nblm", {})
        if fmt.get("status") != "ready":
            continue
        nid = topic.get("nblm_notebook_id", "")
        if not nid:
            continue
        item_id = topic["id"]
        mp3 = download_podcast_audio(nid, audio_dir, item_id)
        if mp3 is None:
            log.warning(f"rss_feed: skip topic {item_id} — download failed")
            continue
        items.append({
            "id": item_id,
            "title": topic.get("title", item_id),
            "description": topic.get("title", item_id),
            "mp3": mp3,
            "generated_at": fmt.get("generated_at"),
        })

    for article in state.get("articles", []):
        fmt = article.get("formats", {}).get("podcast_nblm", {})
        if fmt.get("status") != "ready":
            continue
        nid = article.get("nblm_notebook_id", "")
        if not nid:
            continue
        item_id = article["id"]
        mp3 = download_podcast_audio(nid, audio_dir, item_id)
        if mp3 is None:
            log.warning(f"rss_feed: skip article {item_id} — download failed")
            continue
        summary = article.get("summary", article.get("title", item_id))
        items.append({
            "id": item_id,
            "title": article.get("title", item_id),
            "description": summary,
            "mp3": mp3,
            "generated_at": fmt.get("generated_at"),
        })

    # Сортуємо: найновіше зверху
    def _sort_key(item):
        gen = item.get("generated_at")
        if gen:
            try:
                return datetime.fromisoformat(gen.replace("Z", "+00:00")).timestamp()
            except Exception:
                pass
        return item["mp3"].stat().st_mtime

    items.sort(key=_sort_key, reverse=True)

    # Bonus: orphan notebooks (після curriculum)
    for orphan in _collect_orphan_items(audio_dir):
        items.append(orphan)

    xml_bytes = _build_rss_xml(items, meta, base_url)
    output_xml.parent.mkdir(parents=True, exist_ok=True)
    output_xml.write_bytes(xml_bytes)
    log.info(f"rss_feed: wrote {len(items)} items to {output_xml}")
    return output_xml


ORPHAN_META = AUDIO_DIR / "orphan_meta.json"


def _collect_orphan_items(audio_dir: Path) -> list:
    """Читає orphan_meta.json і повертає feed items з [Bonus] prefix."""
    meta_path = audio_dir / "orphan_meta.json"
    if not meta_path.exists():
        return []
    try:
        entries = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning(f"rss_feed: orphan_meta read failed: {e}")
        return []

    result = []
    for entry in entries:
        mp3 = Path(entry.get("mp3_path", ""))
        if not mp3.exists() or mp3.stat().st_size <= 100_000:
            continue
        result.append({
            "id":           f"orphan_{entry['notebook_id'][:8]}",
            "title":        f"[Bonus] {entry['title']}",
            "description":  entry["title"],
            "mp3":          mp3,
            "generated_at": entry.get("audio_artifact_created_at"),
        })
    return result


def _build_rss_xml(items: list, meta: dict, base_url: str) -> bytes:
    ITUNES = "http://www.itunes.com/dtds/podcast-1.0.dtd"
    # Реєструємо prefix до створення елементів — ET додасть xmlns:itunes автоматично
    ET.register_namespace("itunes", ITUNES)

    root = Element("rss", {"version": "2.0"})
    channel = SubElement(root, "channel")

    SubElement(channel, "title").text = meta["title"]
    SubElement(channel, "link").text = base_url
    SubElement(channel, "description").text = meta["description"]
    SubElement(channel, "language").text = meta.get("language", "uk-ua")
    SubElement(channel, f"{{{ITUNES}}}author").text = meta.get("author", "Sam")
    SubElement(channel, f"{{{ITUNES}}}image", {"href": f"{base_url}/cover.jpg"})

    for item in items:
        entry = SubElement(channel, "item")
        SubElement(entry, "title").text = item["title"]
        SubElement(entry, "description").text = item["description"]
        SubElement(entry, "guid", {"isPermaLink": "false"}).text = item["id"]

        mp3: Path = item["mp3"]
        filename = mp3.name
        file_size = mp3.stat().st_size
        audio_url = f"{base_url}/audio/{filename}"
        SubElement(entry, "enclosure", {
            "url": audio_url,
            "length": str(file_size),
            "type": "audio/mpeg",
        })

        # pubDate: RFC 2822
        gen = item.get("generated_at")
        if gen:
            try:
                dt = datetime.fromisoformat(gen.replace("Z", "+00:00"))
            except Exception:
                dt = datetime.fromtimestamp(mp3.stat().st_mtime, tz=timezone.utc)
        else:
            dt = datetime.fromtimestamp(mp3.stat().st_mtime, tz=timezone.utc)
        SubElement(entry, "pubDate").text = format_datetime(dt)

        # itunes:duration (seconds) via mutagen if available
        duration = _get_duration(mp3)
        if duration:
            SubElement(entry, f"{{{ITUNES}}}duration").text = str(duration)

    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(root, encoding="unicode").encode("utf-8")


def _get_duration(mp3: Path) -> int | None:
    try:
        from mutagen.mp3 import MP3
        audio = MP3(str(mp3))
        return int(audio.info.length)
    except Exception:
        return None


async def regenerate_feed_async() -> None:
    """Async wrapper — викликається з asyncio.create_task() після генерації podcast_nblm."""
    import asyncio
    try:
        await asyncio.to_thread(generate_feed)
        log.info("rss_feed: async regeneration done")
    except Exception as e:
        log.warning(f"rss_feed: async regeneration failed: {e}")

import json
import logging
import subprocess
from pathlib import Path

from core.audio_downloader import download_podcast_audio, NBLM_BIN

log = logging.getLogger("core.nblm_orphan_sync")

BASE_DIR       = Path(__file__).parent.parent
CURRICULUM_PATH = BASE_DIR / "data" / "curriculum.json"
AUDIO_DIR      = BASE_DIR / "data" / "audio"
ORPHAN_META    = AUDIO_DIR / "orphan_meta.json"


def _run_json(cmd: list) -> "dict | None":
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            log.warning(f"orphan_sync: CLI rc={r.returncode} cmd={cmd[:3]}")
            return None
        return json.loads(r.stdout)
    except Exception as e:
        log.warning(f"orphan_sync: CLI exception cmd={cmd[:3]}: {e}")
        return None


def _curriculum_notebook_ids() -> set:
    try:
        state = json.loads(CURRICULUM_PATH.read_text(encoding="utf-8"))
        ids = set()
        for t in state.get("topics", []):
            nid = t.get("nblm_notebook_id") or ""
            if nid:
                ids.add(nid)
        for a in state.get("articles", []):
            nid = a.get("nblm_notebook_id") or ""
            if nid:
                ids.add(nid)
        return ids
    except Exception as e:
        log.warning(f"orphan_sync: can't read curriculum: {e}")
        return set()


def sync_orphan_audio() -> dict:
    """
    Знаходить NotebookLM notebooks не в curriculum, скачує їхній latest completed audio.
    Зберігає metadata у data/audio/orphan_meta.json.
    Returns: {"orphan_items": [...], "skipped": N}
    """
    data = _run_json([str(NBLM_BIN), "list", "--json"])
    if not data:
        return {"orphan_items": [], "error": "notebooklm list failed"}

    notebooks = data.get("notebooks", [])

    # Дедуплікація по title (case-insensitive) — залишаємо найновіший
    title_map: dict = {}
    for nb in notebooks:
        key = nb.get("title", "").strip().lower()
        existing = title_map.get(key)
        if not existing or (nb.get("created_at", "") > existing.get("created_at", "")):
            title_map[key] = nb

    unique = list(title_map.values())
    log.info(f"orphan_sync: {len(notebooks)} notebooks → {len(unique)} unique by title")

    # Фільтруємо curriculum notebooks
    cur_ids = _curriculum_notebook_ids()
    orphans = [nb for nb in unique if nb["id"] not in cur_ids]
    skipped_cur = len(unique) - len(orphans)
    log.info(f"orphan_sync: {len(orphans)} orphans ({skipped_cur} skipped — in curriculum)")

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    # Завантажуємо audio для кожного orphan
    items = []
    skipped_no_audio = 0
    for nb in orphans:
        nbid  = nb["id"]
        title = nb.get("title", nbid)

        art_data = _run_json([str(NBLM_BIN), "artifact", "list", "-n", nbid, "--json"])
        if not art_data:
            skipped_no_audio += 1
            continue

        audio = [
            a for a in art_data.get("artifacts", [])
            if a.get("type_id") == "audio" and a.get("status") == "completed"
        ]
        if not audio:
            skipped_no_audio += 1
            continue

        # Найновіший audio artifact
        audio.sort(key=lambda a: a.get("created_at", ""), reverse=True)
        latest = audio[0]

        output_name = f"nbid_{nbid[:8]}"
        mp3 = download_podcast_audio(nbid, AUDIO_DIR, output_name)
        if mp3 is None:
            log.warning(f"orphan_sync: download failed '{title[:50]}'")
            skipped_no_audio += 1
            continue

        items.append({
            "notebook_id": nbid,
            "title":       title,
            "mp3_path":    str(mp3),
            "size":        mp3.stat().st_size,
            "audio_artifact_created_at": latest.get("created_at", ""),
        })
        log.info(f"orphan_sync: +'{title[:60]}' {mp3.stat().st_size:,}b")

    ORPHAN_META.write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info(f"orphan_sync: done — {len(items)} items, {skipped_no_audio} no-audio")

    return {
        "orphan_items": items,
        "skipped_curriculum": skipped_cur,
        "skipped_no_audio": skipped_no_audio,
    }

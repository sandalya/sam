import logging
import subprocess
from pathlib import Path

log = logging.getLogger("core.audio_downloader")

NBLM_BIN = Path("/home/sashok/.openclaw/workspace/sam/venv/bin/notebooklm")
MIN_FILE_SIZE = 100_000


def download_podcast_audio(
    notebook_id: str,
    output_dir: Path,
    output_name: str,
    force: bool = False,
) -> "Path | None":
    """
    Качає latest audio artifact з notebook'а на Pi5.
    Returns: Path до mp3 файла, або None при помилці.
    Idempotent: якщо файл існує і force=False — повертає шлях без перекачування.
    """
    output_path = output_dir / f"{output_name}.mp3"

    if output_path.exists() and not force:
        log.info(f"audio_downloader: skip {output_path.name} (exists, no-clobber)")
        return output_path

    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(NBLM_BIN), "download", "audio",
        "-n", notebook_id,
        "--latest",
        "--force" if force else "--no-clobber",
        str(output_path),
    ]

    log.info(f"audio_downloader: downloading notebook={notebook_id} -> {output_path.name}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        log.warning(f"audio_downloader: timeout for notebook={notebook_id}")
        return None
    except Exception as e:
        log.warning(f"audio_downloader: subprocess error for notebook={notebook_id}: {e}")
        return None

    if result.returncode != 0:
        log.warning(
            f"audio_downloader: CLI error notebook={notebook_id} "
            f"rc={result.returncode} stderr={result.stderr[:200]}"
        )
        return None

    if not output_path.exists() or output_path.stat().st_size <= MIN_FILE_SIZE:
        log.warning(f"audio_downloader: file missing or too small: {output_path}")
        return None

    log.info(f"audio_downloader: done {output_path.name} ({output_path.stat().st_size:,} bytes)")
    return output_path

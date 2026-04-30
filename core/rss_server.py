import asyncio
import logging
from pathlib import Path

from aiohttp import web

log = logging.getLogger("core.rss_server")

BASE_DIR = Path(__file__).parent.parent
AUDIO_DIR = BASE_DIR / "data" / "audio"
FEED_XML  = BASE_DIR / "data" / "feed.xml"

HOST = "100.86.239.46"
PORT = 8765


async def handle_healthz(request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def handle_feed(request: web.Request) -> web.Response:
    if not FEED_XML.exists():
        return web.Response(status=404, text="feed not generated yet")
    return web.FileResponse(
        FEED_XML,
        headers={"Content-Type": "application/rss+xml; charset=utf-8"},
    )


async def handle_audio(request: web.Request) -> web.Response:
    filename = request.match_info["filename"]
    if "/" in filename or ".." in filename or not filename.endswith(".mp3"):
        return web.Response(status=400, text="invalid filename")
    path = AUDIO_DIR / filename
    if not path.exists():
        return web.Response(status=404, text="not found")
    # FileResponse handles Accept-Ranges and Range requests natively
    return web.FileResponse(path, headers={"Content-Type": "audio/mpeg"})


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/healthz",          handle_healthz)
    app.router.add_get("/feed.xml",         handle_feed)
    app.router.add_get("/audio/{filename}", handle_audio)
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    log.info(f"Starting RSS server on {HOST}:{PORT}")
    web.run_app(create_app(), host=HOST, port=PORT, access_log=log)

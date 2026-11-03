"""Uploaded media on the `media` volume (docker-compose.yml). The API writes it here; the web
container mounts the same volume read-only and serves it at /media/ (web/nginx.conf).

MEDIA_DIR is the volume's mount point in the API container (/media). For a run without Docker,
point it at any folder, e.g. MEDIA_DIR=./media.
"""

import os
import secrets
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

MEDIA_URL = "/media/"
SUBDIR = "videos"


@dataclass(frozen=True)
class Kind:
    content_type: str
    suffix: str
    max_bytes: int


# Cloudflare (in front of staging and production) refuses request bodies over 100 MB, so a
# video must stay under that: about 10 minutes of 720p screen recording at a sensible bitrate.
KINDS = {
    "video": Kind("video/mp4", ".mp4", 95 * 1024 * 1024),
    "captions": Kind("text/vtt", ".vtt", 1024 * 1024),
}


class MediaError(ValueError):
    """The upload is refused; the message says why, in words for the uploader."""


def media_dir() -> Path:
    return Path(os.environ.get("MEDIA_DIR", "/media"))


def file_for(url_path: str) -> Path:
    """The file a /media/videos/… path refers to. Paths are validated by the schemas first
    (`MEDIA_PATH`), so no `..` or other folders can get here."""
    return media_dir() / url_path.removeprefix(MEDIA_URL)


def _looks_right(kind: str, head: bytes) -> bool:
    if kind == "video":
        return len(head) >= 8 and head[4:8] == b"ftyp"  # every MP4 starts with an ftyp box
    return head.removeprefix(b"\xef\xbb\xbf").startswith(b"WEBVTT")


async def save_upload(kind: str, chunks: AsyncIterator[bytes]) -> tuple[str, int]:
    """Write an upload under a new random name and return its /media/ path and size. Written to
    a temporary name first, so a half-finished upload is never served."""
    spec = KINDS[kind]
    folder = media_dir() / SUBDIR
    folder.mkdir(parents=True, exist_ok=True)
    name = secrets.token_urlsafe(12).replace("-", "_") + spec.suffix
    final = folder / name
    partial = folder / f".{name}.part"
    size = 0
    head = b""
    try:
        with partial.open("wb") as out:
            async for chunk in chunks:
                size += len(chunk)
                if size > spec.max_bytes:
                    raise MediaError(
                        f"The file is over {spec.max_bytes // (1024 * 1024)} MB. Compress it first."
                    )
                if len(head) < 16:
                    head += chunk[: 16 - len(head)]
                out.write(chunk)
        if size == 0:
            raise MediaError("The file is empty.")
        if not _looks_right(kind, head):
            raise MediaError(
                "This is not an MP4 video." if kind == "video" else "This is not a WebVTT file."
            )
        partial.chmod(0o644)  # nginx, a different user, reads it
        partial.rename(final)
    finally:
        partial.unlink(missing_ok=True)
    return f"{MEDIA_URL}{SUBDIR}/{name}", size

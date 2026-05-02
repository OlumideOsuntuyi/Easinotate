"""Image loading utilities - filesystem + URL."""
from __future__ import annotations
import os
import shutil
import uuid
from pathlib import Path
from typing import Tuple
from urllib.parse import urlparse
import urllib.request

from PIL import Image

VALID_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}


class ImageLoadError(Exception):
    pass


def import_from_path(src_path: str, target_dir: str) -> Tuple[str, int, int]:
    """Copy an image from src_path into target_dir under a unique name.

    Returns (stored_name, width, height).
    """
    src_path = os.path.abspath(src_path)
    if not os.path.exists(src_path):
        raise ImageLoadError(f"File not found: {src_path}")

    ext = Path(src_path).suffix.lower()
    if ext not in VALID_EXT:
        raise ImageLoadError(f"Unsupported image extension: {ext}")

    os.makedirs(target_dir, exist_ok=True)
    stored_name = _unique_name(target_dir, Path(src_path).name)
    dst = os.path.join(target_dir, stored_name)
    shutil.copy2(src_path, dst)

    try:
        with Image.open(dst) as im:
            w, h = im.size
    except Exception as e:
        # cleanup partial
        try: os.remove(dst)
        except OSError: pass
        raise ImageLoadError(f"Could not read image: {e}") from e

    return stored_name, w, h


def import_from_url(url: str, target_dir: str, timeout: float = 20.0) -> Tuple[str, int, int]:
    """Download an image from URL into target_dir.

    Returns (stored_name, width, height).
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ImageLoadError("Only http(s) URLs are supported.")

    name_from_url = os.path.basename(parsed.path) or f"image_{uuid.uuid4().hex[:8]}.jpg"
    ext = Path(name_from_url).suffix.lower()
    if ext not in VALID_EXT:
        # Default to .jpg if extension unknown
        name_from_url = f"{Path(name_from_url).stem or 'image'}_{uuid.uuid4().hex[:6]}.jpg"

    os.makedirs(target_dir, exist_ok=True)
    stored_name = _unique_name(target_dir, name_from_url)
    dst = os.path.join(target_dir, stored_name)

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Easinotate/1.0 (image importer)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(dst, "wb") as f:
            shutil.copyfileobj(resp, f)
    except Exception as e:
        raise ImageLoadError(f"Download failed: {e}") from e

    try:
        with Image.open(dst) as im:
            w, h = im.size
            fmt = (im.format or "").lower()
        # If we ended up with a mismatched extension, normalize it
        if fmt and not stored_name.lower().endswith(fmt[:3]):
            pass  # leave it; PIL recognizes by content
    except Exception as e:
        try: os.remove(dst)
        except OSError: pass
        raise ImageLoadError(f"Downloaded file is not a valid image: {e}") from e

    return stored_name, w, h


def _unique_name(target_dir: str, name: str) -> str:
    """Return a name unique within target_dir, appending a short hash if needed."""
    base = os.path.basename(name)
    if not os.path.exists(os.path.join(target_dir, base)):
        return base
    stem, ext = os.path.splitext(base)
    return f"{stem}_{uuid.uuid4().hex[:6]}{ext}"


def scan_folder(root: str, recursive: bool = True) -> list[str]:
    """Return a sorted list of absolute paths to image files under ``root``.

    Filters by VALID_EXT. Skips hidden files and any path component starting
    with '.'. When ``recursive`` is False, only direct children of ``root``
    are returned.
    """
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        return []

    found: list[str] = []
    if recursive:
        for dirpath, dirnames, filenames in os.walk(root):
            # prune hidden directories in-place so os.walk doesn't descend into them
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for fname in filenames:
                if fname.startswith("."):
                    continue
                if Path(fname).suffix.lower() in VALID_EXT:
                    found.append(os.path.join(dirpath, fname))
    else:
        for fname in os.listdir(root):
            if fname.startswith("."):
                continue
            full = os.path.join(root, fname)
            if os.path.isfile(full) and Path(fname).suffix.lower() in VALID_EXT:
                found.append(full)

    found.sort()
    return found


def derive_primary_label(file_path: str, root: str) -> str:
    """Derive a primary_label from a file's path relative to a root folder.

    e.g. root=/data/appliances, file=/data/appliances/fans/ceiling/img.jpg
        -> "fans/ceiling"

    Returns "" if the file is directly under root or outside it.
    """
    try:
        rel = os.path.relpath(file_path, root)
    except ValueError:
        return ""
    parts = rel.replace("\\", "/").split("/")
    if len(parts) <= 1:
        return ""
    # drop the filename, keep the directory components
    return "/".join(parts[:-1])
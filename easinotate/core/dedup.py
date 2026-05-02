"""Perceptual-hash based duplicate detection for Easinotate.

Uses two hashes per image:
  - SHA-256 of file bytes  → catches *exact* duplicates regardless of content
  - dHash (8x8 difference) → catches *near* duplicates: re-encodes,
    light crops, brightness shifts, etc.

No external deps beyond Pillow (already required).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from PIL import Image


# ---------------------------------------------------------------------------
# Hashes
# ---------------------------------------------------------------------------

def dhash(path: str, hash_size: int = 8) -> int:
    """Difference-hash an image. Returns an int with `hash_size*hash_size` bits.

    The classic dHash trick: resize to (N+1, N) grayscale, then for each row
    compare adjacent pixels — bit is 1 if left > right. Tiny, fast, robust.
    """
    with Image.open(path) as im:
        im = im.convert("L").resize(
            (hash_size + 1, hash_size), Image.Resampling.LANCZOS
        )
        pixels = list(im.getdata())
    w = hash_size + 1
    bits = 0
    for row in range(hash_size):
        base = row * w
        for col in range(hash_size):
            bits = (bits << 1) | (1 if pixels[base + col] > pixels[base + col + 1] else 0)
    return bits


def file_sha256(path: str, chunk: int = 1 << 16) -> str:
    """SHA-256 of the raw file bytes (exact-duplicate detector)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def hamming(a: int, b: int) -> int:
    """Hamming distance between two integer bit-hashes."""
    x = a ^ b
    # int.bit_count is 3.10+; fall back for older interpreters just in case.
    try:
        return x.bit_count()
    except AttributeError:  # pragma: no cover
        return bin(x).count("1")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@dataclass
class ImageHash:
    image_id: str
    path: str
    dhash: int
    sha: str


@dataclass
class DupGroup:
    """A group of duplicate or near-duplicate images.

    ``members`` is a list of image_ids; the first element is the suggested
    "keep" candidate (currently just the first encountered).
    ``is_exact`` is True when all members had identical SHA-256.
    """
    members: List[str]
    is_exact: bool = False
    sample_distance: int = 0


# ---------------------------------------------------------------------------
# Pipelines
# ---------------------------------------------------------------------------

ProgressCb = Optional[Callable[[int, int], None]]


def hash_images(
    items: Iterable[Tuple[str, str]],
    progress: ProgressCb = None,
) -> Dict[str, ImageHash]:
    """Hash an iterable of ``(image_id, file_path)`` tuples.

    Skips files that don't exist or fail to open. Calls ``progress(done, total)``
    after each image when provided.
    """
    items = list(items)
    out: Dict[str, ImageHash] = {}
    total = len(items)
    for i, (iid, p) in enumerate(items, start=1):
        try:
            if Path(p).exists():
                out[iid] = ImageHash(
                    image_id=iid,
                    path=p,
                    dhash=dhash(p),
                    sha=file_sha256(p),
                )
        except Exception:
            # bad image / unreadable file — just skip; not fatal
            pass
        if progress is not None:
            progress(i, total)
    return out


def find_duplicate_groups(
    hashes: Dict[str, ImageHash],
    threshold: int = 6,
) -> List[DupGroup]:
    """Group exact + near-duplicate images.

    ``threshold`` is the maximum dHash Hamming distance (0..64) to count two
    images as "similar". Typical values:
        3   = strict (almost identical)
        6   = balanced (default)
        10  = loose (likely-similar)

    Exact-byte duplicates are always grouped, regardless of threshold.
    """
    if not hashes:
        return []

    # 1) exact-match groups by SHA-256
    by_sha: Dict[str, List[str]] = {}
    for iid, h in hashes.items():
        by_sha.setdefault(h.sha, []).append(iid)
    exact_groups = [
        DupGroup(members=ids, is_exact=True)
        for ids in by_sha.values() if len(ids) > 1
    ]
    # ids that are already locked into an exact group (skip them in similarity step)
    swallowed = {iid for g in exact_groups for iid in g.members}

    # 2) near-duplicate groups by dHash hamming distance — union-find
    candidates = [iid for iid in hashes if iid not in swallowed]
    parent = {iid: iid for iid in candidates}
    rank = {iid: 0 for iid in candidates}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if rank[ra] < rank[rb]:
            ra, rb = rb, ra
        parent[rb] = ra
        if rank[ra] == rank[rb]:
            rank[ra] += 1

    # O(n^2) — fine for typical dataset sizes (hundreds, low thousands).
    # If you need to scale further, swap for BK-tree or LSH.
    n = len(candidates)
    sample_dist: Dict[Tuple[str, str], int] = {}
    for i in range(n):
        a = hashes[candidates[i]]
        for j in range(i + 1, n):
            b = hashes[candidates[j]]
            d = hamming(a.dhash, b.dhash)
            if d <= threshold:
                union(candidates[i], candidates[j])
                key = tuple(sorted([candidates[i], candidates[j]]))
                sample_dist[key] = d

    sim_groups: Dict[str, List[str]] = {}
    for iid in candidates:
        sim_groups.setdefault(find(iid), []).append(iid)

    similar = []
    for ids in sim_groups.values():
        if len(ids) <= 1:
            continue
        # pick a representative pairwise distance for display
        d_sample = 0
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                key = tuple(sorted([ids[i], ids[j]]))
                if key in sample_dist:
                    d_sample = max(d_sample, sample_dist[key])
        similar.append(DupGroup(members=ids, is_exact=False, sample_distance=d_sample))

    return exact_groups + similar
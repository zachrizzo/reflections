"""Deterministic local copies for re-creatable normalized TripoSR inputs."""

import hashlib
from pathlib import Path
import re

from triposr_market_geometry import MAX_BYTES, TARGET_LONGEST_CM


def digest(data):
    return hashlib.sha256(data).hexdigest()


def non_reparse(path):
    status = path.lstat()
    if path.is_symlink() or getattr(status, "st_file_attributes", 0) & 0x400:
        raise ValueError(f"Refusing a linked normalized-source path: {path}")


def preserve_normalized(source_dir, kind, raw_sha, normalized):
    """Create/reuse an exact digest-named Saved copy without overwriting."""
    if (kind not in TARGET_LONGEST_CM or not re.fullmatch(r"[0-9a-f]{64}", raw_sha or "") or
            not isinstance(normalized, bytes) or not 28 <= len(normalized) <= MAX_BYTES):
        raise ValueError("Invalid normalized-source identity or size")
    source_dir = Path(source_dir)
    non_reparse(source_dir)
    folder = source_dir / "Normalized"
    folder.mkdir(exist_ok=True)
    non_reparse(folder)
    path = folder / f"{kind}_{raw_sha[:16]}.glb"
    expected = digest(normalized)
    try:
        with path.open("xb") as target:
            if target.write(normalized) != len(normalized):
                raise OSError("Incomplete normalized-source write")
    except FileExistsError:
        non_reparse(path)
        if not path.is_file() or path.stat().st_size != len(normalized):
            raise ValueError("Existing normalized source differs; it was not overwritten")
        if digest(path.read_bytes()) != expected:
            raise ValueError("Existing normalized source differs; it was not overwritten")
    non_reparse(path)
    if not path.is_file() or path.stat().st_size != len(normalized) or digest(path.read_bytes()) != expected:
        raise ValueError("Normalized source changed while being preserved")
    return path

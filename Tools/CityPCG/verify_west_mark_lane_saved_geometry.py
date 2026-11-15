"""Compare the pinned saved replacement mesh with its named pilot GLB.

Runs offline only in an unreserved, loaded-editor window with no PIE lease and
ample memory. The verified payload is retained in a fresh Saved file.
Matching geometry does not authorize activation or prove UVs or runtime state.
"""

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import time

import decompress_west_mark_lane_source as decoder
from build_grouped_tile_derivatives import TRAIN_HEADER, memory_headroom
from fetch_triposr_weights import window_open
from extract_tile_frontages import read_glb
from verify_unreal_source_groups_offline import match_groups
from verify_west_mark_lane_road_retention import materials
from verify_west_mark_lane_section_mapping import MAX_GLB_BYTES, MAX_TRIANGLES, read_accessor, triangle_key
from verify_west_mark_lane_saved_sections import PROJECT, SPECS, SLOTS, verify_bytes


ASSET = PROJECT / SPECS["replacement"]["path"]
GLB = PROJECT / "Saved/CityPCG/MedievalSurvey/SM_GLMedieval_WestBlockTile.glb"
EXTRACTOR = PROJECT / "Tools/CityPCG/extract_unreal_source_groups.mjs"
PARSER = PROJECT / "Saved/CityPCG/UAssetResearch/raw-unreal-0.1.13/package/dist/index.js"
ASSET_SHA = SPECS["replacement"]["sha256"]
GLB_SHA = "dcbd8f89b2975cea4db92771d0126e7f1867ecf912ee301183f9ff4f8443581e"
EXTRACTOR_SHA = "9ca5cc6aae257003dff65624544f1afa7b4c8247023050ee8502ded7660d675c"
PARSER_SHA = "bff54c6adf1958211246cbd571ad55d70628c14bfaf74deb572d31fc4eec0d70"
RAW_BLAKE3 = bytes.fromhex("91f4a3fdc4fefcd85fb355701e3bf2afe6968a89f025e16f47e4f33b9a327134")
PAYLOAD_DIR = PROJECT / "Saved/CityPCG/MedievalSurvey"


def train_window():
    with (PROJECT / "Saved/PIE_QUEUE.md").open(encoding="utf-8-sig") as stream:
        for line in stream:
            match = TRAIN_HEADER.match(line)
            if not match:
                continue
            status = re.match(r"\s*:?\s*([A-Za-z_]+)\b", match.group(2))
            if not status or status.group(1).upper() != "LOADED":
                raise RuntimeError("Leading editor train is not LOADED")
            if re.search(r"\b(others?\s+wait|reserv\w*|proof\s+round|npc-unify|restart\w*)\b", line, re.I):
                raise RuntimeError("The leading queue entry reserves the editor window")
            return match.group(1)
    raise RuntimeError("The leading editor train cannot be determined")


class Guard:
    def __init__(self):
        window_open()  # no lease (even expired), editor running, 4/10 GiB floors
        self.train = train_window()
        self.physical, self.commit = memory_headroom()
        self.last = 0.0
        self.check(force=True)

    def check(self, force=False):
        if os.path.lexists(PROJECT / "Saved/PIE_LOCK.json"):
            raise RuntimeError("An editor lease appeared; stopping")
        now = time.monotonic()
        if not force and now - self.last < 0.5:
            return
        window_open()
        if train_window() != self.train:
            raise RuntimeError("The editor train changed; stopping")
        physical, commit = memory_headroom()
        if (physical < max(4 * 1024**3, self.physical - 1024**3) or
                commit < max(10 * 1024**3, self.commit - 2 * 1024**3)):
            raise RuntimeError("Available memory fell; stopping")
        self.last = now


def sha(path, check):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(256 * 1024)
            if not chunk:
                break
            check()
            result.update(chunk)
    return result.hexdigest()


def decode_replacement(data, check, decode, blake3):
    if hashlib.sha256(data).hexdigest() != ASSET_SHA:
        raise ValueError("Saved replacement asset hash differs")
    header = decoder.find_buffer(data)  # verifies magic, table, sizes and header CRC
    actual = tuple(header[k] for k in ("offset", "codec", "level", "exponent", "count", "raw_size", "total_size", "raw_hash"))
    if actual != (39026, 3, 3, 18, 45, 11598179, 1059575, RAW_BLAKE3):
        raise ValueError("Replacement compressed-buffer layout differs")
    output = bytearray()
    pos = header["payload_offset"]
    for i, size in enumerate(header["table"]):
        check()
        expected = min(1 << header["exponent"], header["raw_size"] - len(output))
        chunk = data[pos:pos+size]
        if len(chunk) != size:
            raise ValueError("Truncated compressed block")
        raw = chunk if size == expected else decode(chunk, expected)
        if len(raw) != expected:
            raise ValueError(f"Oodle block {i} returned the wrong size")
        output.extend(raw)
        pos += size
    if (len(output) != header["raw_size"] or pos != header["offset"] + header["total_size"] or
            blake3(output).digest() != RAW_BLAKE3):
        raise ValueError("Replacement decompressed payload failed full BLAKE3 or size verification")
    return output


def payload_path(value, *, existing=False):
    """Require a direct child of the intended Saved folder, without overwrite."""
    saved = (PROJECT / "Saved").resolve(strict=True)
    intended = PAYLOAD_DIR.absolute()
    root = PAYLOAD_DIR.resolve(strict=True)
    if (PAYLOAD_DIR.is_symlink() or getattr(PAYLOAD_DIR, "is_junction", lambda: False)() or
            root != intended):
        raise ValueError("Intended payload directory is redirected")
    if not root.is_relative_to(saved) or root == saved:
        raise ValueError("Payload directory is outside the intended Saved root")
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = PROJECT / candidate
    if not re.fullmatch(r"WestBlockTile_mesh_payload_[A-Za-z0-9_-]+\.bin", candidate.name):
        raise ValueError("Unexpected payload filename")
    if not existing and os.path.lexists(candidate):
        raise FileExistsError("Payload output already exists")
    if candidate.is_symlink():
        raise ValueError("Payload output must not be a symlink")
    resolved = candidate.resolve(strict=existing)
    if resolved.parent != root:
        raise ValueError("Payload output must be directly inside the intended Saved folder")
    if existing and (not resolved.is_file() or not os.path.lexists(candidate)):
        raise ValueError("Retained payload is missing or is not a regular file")
    return resolved


def save_verified_payload(destination, payload, expected_sha, check, blake3):
    """Exclusively create and read back guarded chunks; retain partials on abort."""
    output = payload_path(destination)
    check()
    if payload_path(destination) != output:
        raise ValueError("Payload target changed before creation")
    with output.open("xb") as stream:
        for offset in range(0, len(payload), 256 * 1024):
            check()
            chunk = payload[offset:offset + 256 * 1024]
            if stream.write(chunk) != len(chunk):
                raise IOError("Short write to retained payload")
    check()
    if payload_path(output, existing=True) != output:
        raise ValueError("Retained payload path changed")
    sha256, raw_hash, total = hashlib.sha256(), blake3(), 0
    with output.open("rb") as stream:
        while True:
            check()
            chunk = stream.read(256 * 1024)
            if not chunk:
                break
            sha256.update(chunk)
            raw_hash.update(chunk)
            total += len(chunk)
    if total != len(payload) or sha256.hexdigest() != expected_sha or raw_hash.digest() != RAW_BLAKE3:
        raise ValueError("Retained payload failed readback verification")
    check()
    return output


def extractor_for_payload(source, payload_sha):
    if not re.fullmatch(r"[0-9a-f]{64}", payload_sha):
        raise ValueError("Invalid decompressed payload SHA-256")
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != EXTRACTOR_SHA:
        raise ValueError("Source group extractor differs")
    changes = [
        ("fad42a2a33c47b14298e5206fbbd3f3e60b3124ea8316f4f35077539824673f1", ASSET_SHA),
        ("147621d39e17a2288a7559e8fa846ed07e3090e384d4855b266891d29953f83c", payload_sha),
        ("process.argv.slice(2)", "process.argv.slice(1)"),
        ("process.argv.length !== 5", "process.argv.length !== 4"),
    ]
    for before, after in changes:
        if source.count(before) != 1:
            raise ValueError("Pinned source extractor adapter anchor differs")
        source = source.replace(before, after, 1)
    return source


def extract_groups(payload_file, payload_size, payload_sha, source, guard):
    script = extractor_for_payload(source, payload_sha)
    guard.check(force=True)
    payload_file = payload_path(payload_file, existing=True)
    child = subprocess.Popen(["node", "--max-old-space-size=256", "--input-type=module", "-e", script,
                              str(PARSER), str(ASSET), str(payload_file)], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    started = time.monotonic()
    try:
        while True:
            guard.check()
            if time.monotonic() - started > 45:
                raise RuntimeError("Replacement parser timed out")
            try:
                out, error = child.communicate(timeout=0.25)
                break
            except subprocess.TimeoutExpired:
                continue
        guard.check(force=True)
        if child.returncode or len(out) > 24 * 1024**2:
            raise RuntimeError("Replacement MeshDescription parser failed: " + error.decode("utf-8", "replace")[:2000])
        result = json.loads(out)
        if (result["asset_sha256"] != ASSET_SHA or result["payload_sha256"] != payload_sha or
                result["parser_sha256"] != PARSER_SHA or result["consumed"] != payload_size or result["trailing"] != 0):
            raise ValueError("Replacement parser identities or payload consumption differ")
        return result["sections"]
    except BaseException:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=5)
        raise


def glb_counters(path, check):
    check()
    if path.stat().st_size > MAX_GLB_BYTES:
        raise ValueError("GLB exceeds comparison size limit")
    doc, blob = read_glb(path)
    with path.open("rb") as stream:
        stream.seek(12)
        json_size, json_kind = struct.unpack("<I4s", stream.read(8))
        stream.seek(20 + json_size)
        bin_size, bin_kind = struct.unpack("<I4s", stream.read(8))
    if (json_kind != b"JSON" or bin_kind != b"BIN\x00" or json_size % 4 or bin_size % 4 or
            28 + json_size + bin_size != path.stat().st_size or len(blob) != bin_size or
            len(doc.get("buffers", [])) != 1 or "uri" in doc["buffers"][0] or
            doc["buffers"][0].get("byteLength", len(blob)) > len(blob)):
        raise ValueError("Unexpected GLB chunk or buffer structure")
    result, count = [], 0
    for primitive in doc["meshes"][0]["primitives"]:
        check()
        if primitive.get("mode", 4) != 4 or primitive.get("extensions"):
            raise ValueError("Expected uncompressed indexed triangles")
        positions = read_accessor(doc, blob, primitive["attributes"]["POSITION"], {("VEC3", 5126)})
        indexes = read_accessor(doc, blob, primitive["indices"], {("SCALAR", 5121), ("SCALAR", 5123), ("SCALAR", 5125)})
        if not indexes or len(indexes) % 3:
            raise ValueError("Incomplete GLB triangles")
        count += len(indexes) // 3
        if count > MAX_TRIANGLES:
            raise ValueError("Too many GLB triangles")
        counter = Counter()
        for start in range(0, len(indexes), 3):
            if start % 1536 == 0:
                check()
            corners = [item[0] for item in indexes[start:start+3]]
            if any(i >= len(positions) for i in corners):
                raise ValueError("Invalid GLB triangle position")
            counter[b"".join(triangle_key([positions[i] for i in corners])).hex()] += 1
        result.append(counter)
    if not result:
        raise ValueError("GLB has no primitives")
    return result


def compare_groups(groups, primitives, named):
    """Require unique, complete geometry matches and corresponding slot names."""
    if (len(groups) != 6 or [row["section"] for row in groups] != list(range(6)) or
            len(named) != 6 or len(set(named)) != 6 or set(named) != set(SLOTS)):
        raise ValueError("Saved replacement groups or GLB slot names are ambiguous")
    counters = [Counter(row["triangles"]) for row in groups]
    forward, _, bijection = match_groups(counters, primitives)
    if (not bijection or any(row["slot"] != named[forward[i][0]] for i, row in enumerate(groups))):
        raise ValueError("Saved replacement geometry or corresponding slot names differ")
    return [{"saved_polygon_group": row["section"], "saved_imported_slot": row["slot"],
             "glb_primitive": forward[i][0], "signed_triangles": sum(counters[i].values())}
            for i, row in enumerate(groups)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload-output", required=True, type=Path,
                        help="Fresh WestBlockTile_mesh_payload_<name>.bin directly inside Saved/CityPCG/MedievalSurvey")
    args = parser.parse_args()
    guard = Guard()
    output = payload_path(args.payload_output)
    paths = {"asset": (ASSET, ASSET_SHA), "glb": (GLB, GLB_SHA),
             "extractor": (EXTRACTOR, EXTRACTOR_SHA), "parser": (PARSER, PARSER_SHA)}
    for name, (path, expected) in paths.items():
        if sha(path, guard.check) != expected:
            raise ValueError(f"Pinned {name} differs")
    data = ASSET.read_bytes()
    saved_metadata = verify_bytes(data, SPECS["replacement"])
    source = EXTRACTOR.read_text(encoding="utf-8")
    sys.path.insert(0, str(decoder.DEPENDENCIES))
    from blake3 import blake3
    payload = decode_replacement(data, guard.check, decoder.oodle_decoder(), blake3)
    payload_sha = hashlib.sha256(payload).hexdigest()
    output = save_verified_payload(output, payload, payload_sha, guard.check, blake3)
    payload_size = len(payload)
    del payload
    groups = extract_groups(output, payload_size, payload_sha, source, guard)
    primitives = glb_counters(GLB, guard.check)
    named = materials(GLB)
    mapping = compare_groups(groups, primitives, named)
    for name, (path, expected) in paths.items():
        if sha(path, guard.check) != expected:
            raise ValueError(f"Pinned {name} changed during comparison")
    if payload_path(output, existing=True) != output or sha(output, guard.check) != payload_sha:
        raise ValueError("Retained payload changed during comparison")
    guard.check(force=True)
    result = {"status": "saved_replacement_geometry_matches_named_glb_live_checks_required",
              "asset_sha256": ASSET_SHA, "named_glb_sha256": GLB_SHA,
              "payload_file": str(output), "payload_sha256": payload_sha, "payload_blake3": RAW_BLAKE3.hex(),
              "source_extractor_sha256": EXTRACTOR_SHA, "parser_sha256": PARSER_SHA,
              "mapping": mapping,
              "saved_sections": saved_metadata["sections"],
              "limits": ["Position and winding geometry only: UVs, normals, materials and render data are not compared.",
                         "Saved file only: live section binding, asset, actor, transform and collision are unverified.",
                         "No visual, navigation, streaming or gameplay verification; pilot activation remains disabled."]}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

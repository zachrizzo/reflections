"""Create a deterministic, review-only worklist from existing tile surveys.

No GLB is parsed or Unreal/Blender accessed. The reports and prior mask are
hash-bound; their original source/overlay pins are carried forward without
claiming that the binary exports or historic screening inputs were rechecked.
"""

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
SURVEY = ROOT / "Saved/CityPCG/MedievalSurvey"
SNAPSHOT = ROOT / "ArtDirection/CityPCG/MedievalOpening/ScreenedSurveySnapshot20261115"
SNAPSHOT_MANIFEST = SNAPSHOT / "snapshot_manifest.json"
PREVIOUS = SNAPSHOT / "rollout_18_buildings_20261115.json"
TILES = ("Tile_p03_p00", "Tile_p03_p01", "Tile_p04_p00")
REPORTS = {tile: SNAPSHOT / f"{tile}_next_building_blocks.json" for tile in TILES}
OUTPUT = SURVEY / "screened_worklist_from_snapshot_20261115_codex_v2.json"
MAX_MODELS_PER_BATCH = 4
PRIVATE_PATH = re.compile(r"(^[A-Za-z]:[\\/]|^\\\\|^file:/*|^/(?!Game(?:/|$)|Script(?:/|$)))", re.IGNORECASE)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_input(path):
    data = path.read_bytes()
    return json.loads(data.decode("utf-8-sig")), {"path": path.relative_to(ROOT).as_posix(),
                                                   "sha256": sha(data),
                                                   "sha256_lf": sha(data.replace(b"\r\n", b"\n"))}


def has_private_absolute_path(value):
    if isinstance(value, dict):
        return any(has_private_absolute_path(key) or has_private_absolute_path(item) for key, item in value.items())
    if isinstance(value, list):
        return any(has_private_absolute_path(item) for item in value)
    return isinstance(value, str) and bool(PRIVATE_PATH.search(value))


def checked_snapshot():
    """Pin canonical review inputs and retain their original local hashes."""
    index, index_info = read_input(SNAPSHOT_MANIFEST)
    if (index.get("schema") != 1 or index.get("status") != "historical_review_snapshot_only" or
            index.get("source_binaries_included") is not False or
            index.get("historical_settings_hashes_available") is not False):
        raise ValueError("Expected a historical review-only snapshot without source binaries")
    records = index.get("files", [])
    by_name = {row["file"]: row for row in records}
    expected = {PREVIOUS.name, *(path.name for path in REPORTS.values())}
    if len(records) != len(expected) or set(by_name) != expected or has_private_absolute_path(index):
        raise ValueError("Snapshot must identify exactly the baseline and three screened reports")
    for name, record in by_name.items():
        data = (SNAPSHOT / name).read_bytes()
        canonical = data.replace(b"\r\n", b"\n")
        possible_originals = (canonical, canonical.replace(b"\n", b"\r\n"))
        if (record.get("original_project_relative_path") != f"Saved/CityPCG/MedievalSurvey/{name}" or
                sha(canonical) != record.get("canonical_lf_sha256") or
                len(canonical) != record.get("canonical_lf_bytes") or
                not any(sha(original) == record.get("original_sha256") and len(original) == record.get("original_bytes")
                        for original in possible_originals) or has_private_absolute_path(json.loads(canonical.decode("utf-8-sig")))):
            raise ValueError(f"Snapshot input differs from its recorded identity: {name}")
    return index_info


def output_from_basename(name):
    """Only allow an ordinary JSON filename in the fixed Saved directory."""
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,139}\.json", name) or
            name.split(".", 1)[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                                               *(f"LPT{i}" for i in range(1, 10))}):
        raise ValueError("Output must be a simple non-reserved .json basename")
    return SURVEY / name


def checked_output_parent(output=None):
    """Create only the intended Saved subdirectories on a fresh checkout."""
    output = OUTPUT if output is None else Path(output)
    parent = ROOT
    for name in ("Saved", "CityPCG", "MedievalSurvey"):
        directory = parent / name
        if not directory.exists():
            directory.mkdir()
        if directory.is_symlink() or directory.resolve(strict=True) != directory:
            raise RuntimeError("The intended Saved output directory was redirected")
        parent = directory
    if output.parent != parent:
        raise RuntimeError("The worklist output is not in the intended Saved directory")
    return parent


def evidence(building):
    """Keep face addresses and geometry signatures separate for overlap tests."""
    wall = building["source_wall_faces_by_edge"]
    wall_sig = building["wall_triangle_signature_by_edge"]
    roof, roof_sig = building["source_roof_faces"], building["roof_triangle_signatures"]
    if (not wall or len(wall) != len(wall_sig) or not roof or len(roof) != len(roof_sig) or
            any(len(a) != 2 or len(b) != 2 for a, b in zip(wall, wall_sig))):
        raise ValueError(f'{building["id"]}: incomplete source triangle evidence')
    addresses = {("wall", item) for pair in wall for item in pair} | {("roof", item) for item in roof}
    signatures = {("wall", item) for pair in wall_sig for item in pair} | {("roof", item) for item in roof_sig}
    total = sum(map(len, wall)) + len(roof)
    if (len(addresses) != total or len(signatures) != total or
            any(type(value) is not int or value < 0 for _, value in addresses) or
            any(not isinstance(value, str) or len(value) != 20 for _, value in signatures)):
        raise ValueError(f'{building["id"]}: invalid or repeated source triangle evidence')
    payload = json.dumps({"addresses": sorted(addresses), "signatures": sorted(signatures)},
                         separators=(",", ":"), sort_keys=True).encode("ascii")
    return addresses, signatures, sha(payload)


def components(nodes, links):
    """Find connected components of only the still-unused group members."""
    adjacency = defaultdict(set)
    for link in links:
        members = link["members"]
        if len(members) != 2 or members[0] == members[1]:
            raise ValueError("Each recorded street link must name two distinct buildings")
        first, second = members
        if first in nodes and second in nodes:
            adjacency[first].add(second)
            adjacency[second].add(first)
    pending = set(nodes)
    result = []
    while pending:
        stack = [min(pending)]
        group = set()
        while stack:
            current = stack.pop()
            if current not in pending:
                continue
            pending.remove(current)
            group.add(current)
            stack.extend(sorted(adjacency[current] & pending, reverse=True))
        result.append(sorted(group))
    return sorted(result)


def make_worklist(previous, reports, inputs):
    if (previous.get("status") != "offline_only" or previous.get("requested_mask_failures") or
            previous.get("requested_pin_failures") or set(previous["cumulative_masks"]) != set(TILES) or
            set(reports) != set(TILES) or set(inputs) != {"baseline", *TILES}):
        raise ValueError("Expected the complete previously audited three-tile baseline and surveys")
    baseline_ids = set()
    blocks, singletons, conflicts, summaries = [], [], [], {}
    for tile in TILES:
        report, baseline = reports[tile], previous["cumulative_masks"][tile]
        if (report["tile"] != tile or baseline["source_tile"] != tile or
                report["source_export_sha256"] != baseline["source_export_sha256"] or
                report["source_origin_m"] != baseline["source_origin_m"] or
                report["ordinary_wall_primitive"] != baseline["ordinary_wall_primitive"] or
                report["roof_primitive"] != baseline["roof_primitive"]):
            raise ValueError(f"{tile}: baseline and survey source pins disagree")
        used_addresses, used_signatures, used_by_id = set(), set(), {}
        for row in baseline["buildings"]:
            if row["id"] in baseline_ids:
                raise ValueError("Baseline contains a repeated building ID")
            baseline_ids.add(row["id"])
            addresses, signatures, _ = evidence(row)
            if used_addresses & addresses or used_signatures & signatures:
                raise ValueError(f"{tile}: baseline contains duplicate source face evidence")
            used_addresses.update(addresses)
            used_signatures.update(signatures)
            used_by_id[row["id"]] = (addresses, signatures)
        candidates = {}
        candidate_evidence = {}
        state = {}
        for row in report["screened_candidates"]:
            identifier = row["id"]
            if not identifier.startswith(tile + "_") or identifier in candidates:
                raise ValueError(f"{tile}: malformed or duplicate screened ID")
            footprint = row["footprint"]
            if (len(footprint) < 3 or not all(len(point) == 2 and all(math.isfinite(x) for x in point)
                                               for point in footprint) or not row.get("entries")):
                raise ValueError(f"{identifier}: missing surveyed footprint or entry evidence")
            addresses, signatures, fingerprint = evidence(row)
            if identifier in used_by_id:
                if (addresses, signatures) != used_by_id[identifier]:
                    raise ValueError(f"{identifier}: baseline source face evidence changed")
                state[identifier] = "already_in_baseline"
            elif addresses & used_addresses or signatures & used_signatures:
                state[identifier] = "conflicts_with_baseline_faces"
                conflicts.append({"tile": tile, "building_id": identifier,
                                  "reason": "ID differs but one or more source face addresses or signatures overlap the baseline"})
            else:
                state[identifier] = "new_candidate"
            candidates[identifier] = {"id": identifier, "face_evidence_sha256": fingerprint,
                                      "area_m2": row["area_m2"], "origin_m": row["origin_m"]}
            candidate_evidence[identifier] = (addresses, signatures)
        # Different candidate IDs must not cause the same source face to be
        # scheduled twice, even if neither is in the current baseline.
        owner_by_face, overlaps = {}, defaultdict(set)
        for identifier, (addresses, signatures) in candidate_evidence.items():
            for face in (("address", *item) for item in addresses):
                if face in owner_by_face:
                    overlaps[identifier].add(owner_by_face[face])
                    overlaps[owner_by_face[face]].add(identifier)
                else:
                    owner_by_face[face] = identifier
            for face in (("signature", *item) for item in signatures):
                if face in owner_by_face:
                    overlaps[identifier].add(owner_by_face[face])
                    overlaps[owner_by_face[face]].add(identifier)
                else:
                    owner_by_face[face] = identifier
        for identifier, other_ids in sorted(overlaps.items()):
            if state[identifier] == "new_candidate":
                state[identifier] = "conflicts_with_screened_candidate"
                conflicts.append({"tile": tile, "building_id": identifier,
                                  "reason": "source face evidence overlaps another screened candidate",
                                  "overlapping_candidate_ids": sorted(other_ids)})
        grouped = set()
        for group in report["connected_groups"]:
            members = group["members"]
            if (not members or len(members) != len(set(members)) or not set(members) <= candidates.keys() or
                    grouped & set(members) or group["id"] != "block_" + sha("|".join(sorted(members)).encode("ascii"))[:12]):
                raise ValueError(f'{tile}: invalid, overlapping or changed screened group {group["id"]}')
            grouped.update(members)
            links = group["street_links"]
            if any(not set(link["members"]) <= set(members) for link in links) or len(components(set(members), links)) != 1:
                raise ValueError(f'{tile}: recorded street-link group {group["id"]} is not connected')
            new = {member for member in members if state[member] == "new_candidate"}
            if not new:
                continue
            parts = []
            for part in components(new, links):
                part_ids = set(part)
                part_links = [link for link in links if set(link["members"]) <= part_ids]
                parts.append({"building_ids": part, "retained_street_links": part_links,
                              "requires_new_connectivity_evidence": (len(part) == 1 or len(new) != len(members) or
                                                                      len(part) > MAX_MODELS_PER_BATCH),
                              "requires_current_road_revalidation": True,
                              "exceeds_four_model_batch": len(part) > MAX_MODELS_PER_BATCH})
            blocks.append({"tile": tile, "source_group_id": group["id"],
                           "status": "offline_screened_needs_revalidation",
                           "group_has_baseline_or_conflicting_members": len(new) != len(members),
                           "original_members": sorted(members),
                           "baseline_members": sorted(member for member in members if state[member] == "already_in_baseline"),
                           "conflicting_members": sorted(member for member in members if state[member].startswith("conflicts_")),
                           "new_buildings": [candidates[member] for member in sorted(new)],
                           "new_connected_components": parts})
        for identifier in sorted(set(candidates) - grouped):
            if state[identifier] == "new_candidate":
                singletons.append({"tile": tile, "status": "offline_screened_singleton_needs_route_review",
                                   "building": candidates[identifier]})
        summaries[tile] = {"source_export_sha256": report["source_export_sha256"],
                           "overlay_export_sha256": report["overlay_export_sha256"],
                           "reviewed_neighbor_tiles": report["reviewed_neighbor_tiles"],
                           "baseline_buildings": len(baseline["buildings"]),
                           "screened_candidates": len(candidates),
                           "additional_candidates": sum(item == "new_candidate" for item in state.values()),
                           "overlapping_or_conflicting_candidates": sum(item.startswith("conflicts_") for item in state.values())}
    return {"status": "offline_review_worklist_only", "runtime_activation_eligible": False,
            "source_ue_section_mapping": "unverified", "source_binary_hashes_rechecked": False,
            "reported_total_tile_assets_at_baseline": previous["source_tile_count"],
            "reported_locally_exported_tiles_at_baseline": previous["locally_exported_tile_count"],
            "baseline_building_count": len(baseline_ids),
            "additional_screened_candidates": sum(row["additional_candidates"] for row in summaries.values()),
            "inputs": inputs, "tiles": summaries, "connected_groups": blocks,
            "singletons": singletons, "source_face_conflicts": conflicts,
            "required_before_generation": [
                "Recheck exact source and overlay hashes, available neighbors, live actor descriptors and current protections.",
                "Recompute links for mixed or split groups; singletons need their own evidenced access review.",
                "Reject or explicitly re-review any source-face overlap, and carry the latest complete cumulative tile mask forward.",
                "Keep groups over four models bounded and connectivity-checked; do not invent additional placements."],
            "required_before_runtime": [
                "Independently verify GLB primitive-to-live-Unreal section identity, materials, transform and collision.",
                "Require every matching grouped cell and cumulative filtered tile to be ready together; restore original on failure.",
                "Check navigation, story routes, roof access, streaming, LAN and the refreshed playable build."],
            "limitations": ["Prior screening settings and live actor evidence were not freshly reconstructed.",
                            "Reports and masks are pinned, but original tile and overlay files were not rehashed in this run.",
                            "Unexported tiles, unrecorded actors and missing neighboring exports are not surveyed."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=OUTPUT.name, metavar="BASENAME",
                        help="Fresh .json filename under Saved/CityPCG/MedievalSurvey")
    args = parser.parse_args()
    try:
        output_path = output_from_basename(args.output)
    except ValueError as error:
        parser.error(str(error))
    snapshot_manifest = checked_snapshot()
    previous, baseline_input = read_input(PREVIOUS)
    report_pairs = {tile: read_input(path) for tile, path in REPORTS.items()}
    reports = {tile: value[0] for tile, value in report_pairs.items()}
    inputs = {"baseline": baseline_input, **{tile: value[1] for tile, value in report_pairs.items()}}
    result = make_worklist(previous, reports, inputs)
    result["review_snapshot_manifest"] = snapshot_manifest
    for record in inputs.values():
        path = ROOT / record["path"]
        if sha(path.read_bytes()) != record["sha256"]:
            raise RuntimeError("An input report changed during worklist generation")
    if sha(SNAPSHOT_MANIFEST.read_bytes()) != snapshot_manifest["sha256"]:
        raise RuntimeError("The snapshot manifest changed during worklist generation")
    checked_output_parent(output_path)
    with output_path.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(result, output, indent=2)
        output.write("\n")
    print(f"Recorded {result['additional_screened_candidates']} additional screened candidates "
          f"in {len(result['connected_groups'])} groups and {len(result['singletons'])} singletons: {output_path}")


if __name__ == "__main__":
    main()

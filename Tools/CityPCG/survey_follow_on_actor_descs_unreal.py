"""Read saved Gray London actor descriptors around the three follow-on blocks."""

import json
import math
from pathlib import Path

from extract_tile_frontages import clip
from plan_whole_building_replacements import distance_to_building, ring_edges
from preview_west_mark_lane_unreal import editor_available


CANDIDATES = {
    "west_connector": "west_connector_whole_buildings_candidate.json",
    "leadenhall_northwest": "leadenhall_northwest_whole_buildings_candidate.json",
    "east_of_royal_mint": "east_tower_whole_buildings_candidate.json",
}


def xy_box_cm(points, margin_m, bottom_m, top_m):
    x, y = zip(*points)
    return [
        [(min(x) - margin_m) * 100, (min(y) - margin_m) * 100, bottom_m * 100],
        [(max(x) + margin_m) * 100, (max(y) + margin_m) * 100, top_m * 100],
    ]


def survey_regions(candidate, footprint_margin_m):
    for building in candidate["buildings"]:
        ring = building["footprint"]
        base, roof = building["base_m"], building["source_roof_m"]
        yield {
            "kind": "footprint",
            "id": building["id"],
            "footprint_m": ring,
            "query_bounds_cm": xy_box_cm(ring, footprint_margin_m, base - 3, roof + 8),
        }
    for index, link in enumerate(candidate["validated_road_links"], start=1):
        yield {
            "kind": "road_link",
            "id": f"road_{index}",
            "members": link["members"],
            "guide_m": link["guide_m"],
            "query_bounds_cm": xy_box_cm(link["guide_m"], 2., -3., 6.),
        }


def footprint_intersects_bounds(ring, bounds_cm):
    (xmin, ymin, _), (xmax, ymax, _) = bounds_cm
    limits = (xmin / 100, ymin / 100, xmax / 100, ymax / 100)
    if any(clip(a, b, limits) is not None for a, b in ring_edges(ring)):
        return True
    return any(distance_to_building((x, y), ring) <= .00001
               for x in limits[::2] for y in limits[1::2])


def box_for(unreal, bounds):
    result = unreal.Box()
    result.set_editor_properties({
        "min": unreal.Vector(*bounds[0]),
        "max": unreal.Vector(*bounds[1]),
        "is_valid": True,
    })
    return result


def xyz(vector):
    return [float(getattr(vector, axis)) for axis in "xyz"]


def descriptor_snapshot(unreal, descriptor):
    prop = descriptor.get_editor_property
    box = prop("bounds")
    native = prop("native_class")
    path = str(prop("actor_path"))
    package = str(prop("actor_package"))
    if not package.startswith("/") or not path.startswith("/"):
        raise RuntimeError(f"Cannot resolve the saved package and object path for {prop('label')}.")
    guid = prop("guid").to_string()
    instance_guid = prop("instance_guid").to_string()
    return {
        "label": str(prop("label")),
        "internal_name": str(prop("name")),
        "actor_package": package,
        "actor_path": path,
        "guid": guid,
        "instance_guid": instance_guid,
        "native_class": native.get_path_name() if native else None,
        "folder_path": str(prop("folder_path")),
        "streaming_bounds_cm": [xyz(box.min), xyz(box.max)],
        "runtime_grid": str(prop("runtime_grid")),
        "is_spatially_loaded": bool(prop("is_spatially_loaded")),
        "actor_is_editor_only": bool(prop("actor_is_editor_only")),
        "descriptor_data_layer_assets": sorted(
            unreal.SystemLibrary.break_soft_object_path(asset)
            for asset in prop("data_layer_assets")
        ),
    }


def layer_catalog(library, world):
    manager = library.get_data_layer_manager_for_object(world)
    if manager is None:
        return None
    rows = []
    for layer in manager.get_data_layer_instances():
        asset = layer.get_asset()
        parent = layer.get_parent()
        rows.append({
            "short_name": layer.get_data_layer_short_name(),
            "full_name": layer.get_data_layer_full_name(),
            "instance_path": layer.get_path_name(),
            "instance_package": layer.get_package().get_name(),
            "asset_path": asset.get_path_name() if asset else None,
            "asset_package": asset.get_package().get_name() if asset else None,
            "parent_instance_path": parent.get_path_name() if parent else None,
            "type": str(layer.get_type()),
        })
    return sorted(rows, key=lambda row: row["instance_path"])


def intersecting_descriptors(library, box):
    result = library.get_intersecting_actor_descs(box)
    if result is None:
        raise RuntimeError("The World Partition descriptor query did not return a result.")
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], bool):
        if not result[0]:
            raise RuntimeError("The World Partition descriptor query failed.")
        return result[1]
    return result


def survey(lease_owner, *, footprint_margin_m=4., report_name=None):
    """Inspect the already-open map under its current lease and return JSON-ready evidence."""
    import unreal

    if not math.isfinite(footprint_margin_m) or footprint_margin_m < 0:
        raise ValueError("Provide a finite, non-negative footprint margin in metres.")
    if report_name is not None and (
        Path(report_name).name != report_name or Path(report_name).suffix.lower() != ".json"
    ):
        raise ValueError("Provide a JSON basename for a report under Saved/CityPCG/MedievalSurvey.")
    _, world, lease = editor_available(unreal, lease_owner, require_lease=True)
    project = Path(unreal.Paths.project_dir()).resolve()
    candidates = project / "ArtDirection/CityPCG/MedievalOpening"
    library = unreal.WorldPartitionBlueprintLibrary
    layers = layer_catalog(library, world)
    layer_instances = {}
    for layer in layers or []:
        if layer["asset_path"]:
            layer_instances.setdefault(layer["asset_path"], []).append(layer["instance_path"])

    actors, blocks = {}, {}
    for name, filename in CANDIDATES.items():
        candidate = json.loads((candidates / filename).read_text(encoding="utf-8-sig"))
        if candidate.get("status") != "offline_candidate" or candidate.get("coordinate_system") != "ue_local_m":
            raise ValueError(f"Unexpected candidate status or frame in {filename}.")
        regions = list(survey_regions(candidate, footprint_margin_m))
        for region in regions:
            hits = {}
            box = box_for(unreal, region["query_bounds_cm"])
            for descriptor in intersecting_descriptors(library, box):
                row = descriptor_snapshot(unreal, descriptor)
                key = f'{row["instance_guid"]}|{row["actor_package"]}|{row["actor_path"]}'
                row["data_layer_instance_matches"] = {
                    asset: layer_instances.get(asset, []) for asset in row["descriptor_data_layer_assets"]
                }
                if key in actors and actors[key] != row:
                    raise RuntimeError(f"Descriptor changed during the survey for {row['actor_path']}.")
                actors[key] = row
                hit = {"actor_key": key, "label": row["label"], "actor_package": row["actor_package"]}
                if region["kind"] == "footprint":
                    hit["footprint_touches_actor_bounds_xy"] = footprint_intersects_bounds(
                        region["footprint_m"], row["streaming_bounds_cm"]
                    )
                hits[key] = hit
            region["hits"] = sorted(hits.values(), key=lambda hit: (hit["label"], hit["actor_key"]))
        blocks[name] = {
            "candidate": filename,
            "source_tile": candidate["source_tile"],
            "source_asset": candidate["source_tile_asset"],
            "source_export_sha256": candidate["source_export_sha256"],
            "regions": regions,
        }

    editor_available(unreal, lease_owner, require_lease=True, expected_lease=lease)
    report = {
        "status": "descriptor_review_only",
        "world": world.get_path_name(),
        "footprint_margin_m": footprint_margin_m,
        "blocks": blocks,
        "actors": dict(sorted(actors.items())),
        "data_layer_instances": layers,
    }
    if report_name is None:
        return report
    directory = Path(unreal.Paths.project_saved_dir()) / "CityPCG/MedievalSurvey"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / report_name
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return {"report": str(output.resolve()), "actors": len(actors), "blocks": len(blocks)}

"""Draft owned PCG market dressing for MedievalLondon; never runs on import.

Placement requires a later live survey of actual generated stall instances,
support surfaces and story markers. No example coordinates are treated as
reviewed placements. Call only from an explicitly leased editor session.
"""

import asyncio
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import time

import apply_facade_pcg as pcg_helpers
import build_medieval_london_map as town
import import_triposr_market_unreal as importer
from triposr_market_geometry import ASSET_ROOT, LEVEL, TARGET_LONGEST_CM, normalize_z_up_glb, placement, vector


GRAPH_ROOT = ASSET_ROOT + "/Graphs"
TOWN_ACTOR = "Medieval London | Market Street"
ID = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,39}\Z")


def close(a, b, tolerance):
    return abs(float(a) - float(b)) <= tolerance


def angle_close(a, b, tolerance=.05):
    return abs((float(a) - float(b) + 180.) % 360. - 180.) <= tolerance


def transform_values(transform):
    if transform is None:
        raise RuntimeError("A generated instance has no readable transform")
    pos = transform.get_editor_property("translation")
    scale = transform.get_editor_property("scale3d")
    rot = transform.get_editor_property("rotation").rotator()
    return (vector((pos.x, pos.y, pos.z)), vector((rot.roll, rot.pitch, rot.yaw)),
            vector((scale.x, scale.y, scale.z)))


def matches_transform(actual, expected):
    loc, rot, scale = actual
    eloc, erot, escale = expected
    return (all(close(a, b, .05) for a, b in zip(loc, eloc)) and
            all(angle_close(a, b) for a, b in zip(rot, erot)) and
            all(close(a, b, .0001) for a, b in zip(scale, escale)))


def checked_plan(plan):
    if (not isinstance(plan, dict) or plan.get("schema") != 1 or plan.get("level") != LEVEL or
            not ID.fullmatch(plan.get("id", "")) or plan.get("status") != "live_survey_requires_visual_review"):
        raise ValueError("Expected a current live survey for the MedievalLondon map")
    source = importer.PROJECT / "Tools/CityPCG/build_medieval_london_map.py"
    markers = importer.PROJECT / "ArtDirection/WorldJump/graylondon_markers.json"
    populate = importer.PROJECT / "Tools/CityPCG/populate_medieval_london_gameplay.py"
    for key, file in (("town_layout_sha256", source), ("markers_sha256", markers),
                      ("marker_layout_sha256", populate)):
        if plan.get(key) != importer.sha256(file):
            raise ValueError(f"The reviewed {key} no longer matches")
    rows = plan.get("placements")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 24:
        raise ValueError("Choose between one and 24 reviewed props")
    for row in rows:
        if (row.get("kind") not in TARGET_LONGEST_CM or
                not re.fullmatch(r"[0-9a-f]{64}", row.get("source_sha256", "")) or
                row.get("axis_conversion") != "z_up_to_gltf_y_up"):
            raise ValueError("Each prop needs a known kind and exact reviewed source digest")
        vector(row.get("support_cm"))
        vector(row.get("anchor", {}).get("location_cm"))
        vector(row.get("anchor", {}).get("rotation_deg"))
        vector(row.get("anchor", {}).get("scale"))
        anchor, surface = row["anchor"], row.get("surface", {})
        if (not isinstance(anchor.get("actor_path"), str) or not isinstance(anchor.get("component_path"), str) or
                not isinstance(anchor.get("mesh_path"), str) or type(anchor.get("instance_index")) is not int or
                anchor["instance_index"] < 0 or not isinstance(surface.get("actor_path"), str) or
                not isinstance(surface.get("component_path"), str)):
            raise ValueError("A live stall instance and traced support identity are required")
    return rows


def xy_clear(placed, story):
    """Conservatively cover the real curved main-street reserve and markers."""
    for row in placed:
        x, y = row["support_cm"][:2]
        radius = row["radius_cm"]
        low, high = town.curve_bounds(x - radius, x + radius)
        reserve = town.WALK_HALF_WIDTH_CM + radius + 20.
        if low - reserve <= y <= high + reserve:
            raise ValueError("A prop envelope overlaps the curved main-street walking reserve")
        if any(math.hypot(x - sx, y - sy) < radius + town.MARKER_CLEARANCE_CM for sx, sy, _ in story):
            raise ValueError("A prop envelope is too close to a story marker")
    for i, left in enumerate(placed):
        for right in placed[i + 1:]:
            if math.dist(left["support_cm"][:2], right["support_cm"][:2]) < left["radius_cm"] + right["radius_cm"]:
                raise ValueError("Two prop envelopes overlap")


def transformed_box(bounds, transform):
    """A conservative world AABB for yaw-only positive-scale town meshes."""
    lo, hi = (vector(row) for row in bounds)
    location, rotation, scale = transform
    if (any(b <= a for a, b in zip(lo, hi)) or min(scale) <= 0 or
            not angle_close(rotation[0], 0) or not angle_close(rotation[1], 0)):
        raise ValueError("Unsupported scene mesh bounds or non-yaw transform")
    angle = math.radians(rotation[2])
    c, s = math.cos(angle), math.sin(angle)
    cx, cy, cz = tuple((a + b) * .5 * k for a, b, k in zip(lo, hi, scale))
    hx, hy, hz = tuple((b - a) * .5 * k for a, b, k in zip(lo, hi, scale))
    wx, wy, wz = location[0] + c * cx - s * cy, location[1] + s * cx + c * cy, location[2] + cz
    ex, ey = abs(c) * hx + abs(s) * hy, abs(s) * hx + abs(c) * hy
    return ((wx - ex, wy - ey, wz - hz), (wx + ex, wy + ey, wz + hz))


def box_overlaps_prop(box, prop):
    lo, hi = box
    x, y, z = prop["support_cm"]
    height = prop["size_cm"][2]
    # Small vertical contact tolerance allows a supported object to touch a floor.
    if hi[2] <= z + 1. or lo[2] >= z + height - 1.:
        return False
    dx = max(lo[0] - x, 0., x - hi[0])
    dy = max(lo[1] - y, 0., y - hi[1])
    return math.hypot(dx, dy) < prop["radius_cm"] + 2.


def is_cosmetic_paving(mesh_path, world_box, solid_floor_z_cm):
    paving = town.PAVING + "." + town.PAVING.rsplit("/", 1)[-1]
    return mesh_path == paving and world_box[1][2] <= solid_floor_z_cm + 12.


def verify_scene_clearance(unreal, actors, placed):
    """Check loaded static-mesh geometry envelopes, including the stall itself.

    This is conservative AABB evidence, not an Unreal collision or gameplay
    acceptance test. It intentionally rejects non-yaw meshes until surveyed.
    """
    examined = 0
    for actor in actors:
        for component in actor.get_components_by_class(unreal.StaticMeshComponent):
            mesh = component.get_editor_property("static_mesh")
            if not mesh:
                continue
            bound = mesh.get_bounds()
            origin, extent = bound.origin, bound.box_extent
            box = ((origin.x - extent.x, origin.y - extent.y, origin.z - extent.z),
                   (origin.x + extent.x, origin.y + extent.y, origin.z + extent.z))
            if isinstance(component, unreal.InstancedStaticMeshComponent):
                count = component.get_instance_count()
                if count < 0 or count > 100_000:
                    raise RuntimeError("Unexpected scene instance count")
                transforms = (component.get_instance_transform(i, world_space=True) for i in range(count))
            else:
                transforms = (component.get_world_transform(),)
            for transform in transforms:
                examined += 1
                values = transform_values(transform)
                origin_xyz, _, scale = values
                # A sphere around the transform origin encloses the entire
                # local box even when the local pivot is off-centre or the
                # mesh is rotated. Avoid rejecting distant rotated objects.
                local_radius = math.sqrt(sum(max(abs(lo), abs(hi)) ** 2 for lo, hi in zip(*box)))
                max_scale = max(abs(value) for value in scale)
                if all(math.dist(origin_xyz, prop["support_cm"]) >
                       local_radius * max_scale + prop["radius_cm"] + prop["size_cm"][2] + 3.
                       for prop in placed):
                    continue
                world_box = transformed_box(box, values)
                for prop in placed:
                    cosmetic_floor = is_cosmetic_paving(mesh.get_path_name(), world_box, prop["solid_floor_z_cm"])
                    if not cosmetic_floor and box_overlaps_prop(world_box, prop):
                        raise RuntimeError(f"A proposed prop overlaps an existing static mesh: {component.get_path_name()}")
    return examined


def verified_stories(actors):
    expected = town.town_story_points()
    labels = defaultdict(list)
    for actor in actors:
        labels[actor.get_actor_label()].append(actor)
    for x, y, label in expected:
        if len(labels[label]) != 1:
            raise RuntimeError(f"Cannot uniquely find loaded story marker {label}")
        location = labels[label][0].get_actor_location()
        if not close(location.x, x, 2.) or not close(location.y, y, 2.):
            raise RuntimeError(f"Story marker {label} differs from the reviewed layout")
    return expected


def verify_anchor(unreal, actors, anchor, support):
    candidates = [a for a in actors if a.get_actor_label() == TOWN_ACTOR]
    if len(candidates) != 1 or candidates[0].get_path_name() != anchor["actor_path"]:
        raise RuntimeError("The surveyed market PCG volume is no longer the same actor")
    components = [c for c in candidates[0].get_components_by_class(unreal.InstancedStaticMeshComponent)
                  if c.get_path_name() == anchor["component_path"]]
    if len(components) != 1:
        raise RuntimeError("The surveyed stall instance component is unavailable")
    component = components[0]
    mesh = component.get_editor_property("static_mesh")
    expected_stall = town.PROPS["stall"]
    expected_stall += "." + expected_stall.rsplit("/", 1)[-1]
    if not mesh or mesh.get_path_name() != anchor["mesh_path"] or anchor["mesh_path"] != expected_stall:
        raise RuntimeError("The surveyed anchor is no longer an existing town stall")
    index = anchor["instance_index"]
    if index >= component.get_instance_count():
        raise RuntimeError("The surveyed stall index changed")
    expected = (vector(anchor["location_cm"]), vector(anchor["rotation_deg"]), vector(anchor["scale"]))
    actual = transform_values(component.get_instance_transform(index, world_space=True))
    if not matches_transform(actual, expected) or math.dist(actual[0][:2], support[:2]) > 350.:
        raise RuntimeError("Stall transform changed, or prop is too far from its anchor")


def verify_support(unreal, world, row):
    x, y, z = vector(row["support_cm"])
    offset = row["surface"].get("cosmetic_offset_cm", 0.)
    if type(offset) not in (int, float) or not math.isfinite(offset) or not 0. <= offset <= 12.:
        raise ValueError("Cosmetic floor offset must be between 0 and 12 cm")
    hit = unreal.SystemLibrary.line_trace_single(
        world, unreal.Vector(x, y, z + 150.), unreal.Vector(x, y, z - 150.),
        unreal.TraceTypeQuery.ECC_VISIBILITY, True, [], unreal.DrawDebugTrace.NONE, False)
    if not hit:
        raise RuntimeError("No collision-trace support; cosmetic paving alone is not proof of ground")
    result = hit.to_tuple()
    impact, normal, actor, component = result[5], result[7], result[9], result[10]
    surface = row["surface"]
    if (not actor or not component or actor.get_path_name() != surface["actor_path"] or
            component.get_path_name() != surface["component_path"] or result[1] or
            not all(math.isfinite(float(v)) for v in (impact.z, normal.x, normal.y, normal.z)) or
            not close(impact.z + offset, z, 3.) or normal.z < .95):
        raise RuntimeError("The supporting surface changed or is not level at the reviewed height")
    return float(impact.z)


def verify_material(unreal, mesh, kind):
    mat_package = importer.material_package(kind)
    material = unreal.EditorAssetLibrary.load_asset(mat_package)
    if not isinstance(material, unreal.Material) or material.get_package().get_name() != mat_package:
        raise RuntimeError("Missing owned vertex-color material")
    edit = unreal.MaterialEditingLibrary
    base = edit.get_material_property_input_node(material, unreal.MaterialProperty.MP_BASE_COLOR)
    rough = edit.get_material_property_input_node(material, unreal.MaterialProperty.MP_ROUGHNESS)
    metal = edit.get_material_property_input_node(material, unreal.MaterialProperty.MP_METALLIC)
    if (not isinstance(base, unreal.MaterialExpressionVertexColor) or
            str(edit.get_material_property_input_node_output_name(material, unreal.MaterialProperty.MP_BASE_COLOR)) != "" or
            not isinstance(rough, unreal.MaterialExpressionConstant) or
            not isinstance(metal, unreal.MaterialExpressionConstant) or
            not close(rough.get_editor_property("r"), .8, 1e-5) or
            not close(metal.get_editor_property("r"), 0., 1e-5) or
            not material.get_editor_property("used_with_instanced_static_meshes")):
        raise RuntimeError("Owned material graph differs from the vertex-color contract")
    slots = mesh.get_editor_property("static_materials")
    if not slots or any(mesh.get_material(i) != material for i in range(len(slots))):
        raise RuntimeError("Not all mesh sections use the owned material")


def verify_output(unreal, actor, groups, meshes):
    expected = defaultdict(list)
    for kind, rows in groups.items():
        for loc, yaw, scale, _ in rows:
            expected[meshes[kind].get_path_name()].append((tuple(loc), (0., 0., yaw), tuple(scale)))
    counts = Counter()
    for component in actor.get_components_by_class(unreal.InstancedStaticMeshComponent):
        mesh = component.get_editor_property("static_mesh")
        path = mesh.get_path_name() if mesh else None
        if (path not in expected or str(component.get_collision_profile_name()) != "NoCollision" or
                component.get_collision_enabled() != unreal.CollisionEnabled.NO_COLLISION or
                component.get_editor_property("can_ever_affect_navigation")):
            raise RuntimeError("Unexpected generated mesh, collision or navigation")
        for index in range(component.get_instance_count()):
            actual = transform_values(component.get_instance_transform(index, world_space=True))
            matches = [i for i, candidate in enumerate(expected[path]) if matches_transform(actual, candidate)]
            if len(matches) != 1:
                raise RuntimeError("Generated transform differs from the reviewed placement")
            expected[path].pop(matches[0])
            counts[path] += 1
    if any(rows for rows in expected.values()):
        raise RuntimeError("One or more planned instances are missing")
    return dict(counts)


def survey_one(kind, source_sha256, stall_index, offset_cm, *, identifier, yaw_deg=0., cosmetic_offset_cm=8.):
    """Read the actual stall/floor and return one reviewed-candidate plan.

    The caller chooses an offset and reviews the resulting location; this does
    not create a graph, actor or package. An unsafe choice raises instead.
    """
    import unreal

    lease = importer.lease_check(unreal)
    if (kind not in TARGET_LONGEST_CM or not ID.fullmatch(identifier or "") or
            type(stall_index) is not int or stall_index < 0):
        raise ValueError("Expected a known prop, new identifier and stall index")
    offset = vector(offset_cm, 2)
    if math.hypot(*offset) > 350.:
        raise ValueError("The candidate must be near its surveyed stall")
    if type(cosmetic_offset_cm) not in (int, float) or not 0 <= cosmetic_offset_cm <= 12:
        raise ValueError("Invalid cosmetic floor offset")
    yaw = float(yaw_deg)
    if not math.isfinite(yaw):
        raise ValueError("Invalid candidate yaw")
    path = importer.source_path(kind, source_sha256)
    if importer.sha256(path) != source_sha256:
        raise RuntimeError("The candidate source changed")
    mesh_package = importer.asset_package(kind)
    mesh = unreal.EditorAssetLibrary.load_asset(mesh_package)
    if not isinstance(mesh, unreal.StaticMesh) or mesh.get_package().get_name() != mesh_package:
        raise RuntimeError("Import and check this prop first")
    verify_material(unreal, mesh, kind)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    volume, = (actor for actor in actors if actor.get_actor_label() == TOWN_ACTOR)
    stall = town.PROPS["stall"]
    stall += "." + stall.rsplit("/", 1)[-1]
    candidates = [component for component in volume.get_components_by_class(unreal.InstancedStaticMeshComponent)
                  if component.get_editor_property("static_mesh") and
                  component.get_editor_property("static_mesh").get_path_name() == stall]
    if len(candidates) != 1 or stall_index >= candidates[0].get_instance_count():
        raise RuntimeError("The exact generated stall instance is not available")
    component = candidates[0]
    loc, rot, scale = transform_values(component.get_instance_transform(stall_index, world_space=True))
    x, y = loc[0] + offset[0], loc[1] + offset[1]
    hit = unreal.SystemLibrary.line_trace_single(
        world, unreal.Vector(x, y, loc[2] + 250.), unreal.Vector(x, y, loc[2] - 250.),
        unreal.TraceTypeQuery.ECC_VISIBILITY, True, [], unreal.DrawDebugTrace.NONE, False)
    if not hit:
        raise RuntimeError("The candidate has no traceable solid floor")
    traced = hit.to_tuple()
    if not traced[9] or not traced[10] or traced[1] or not math.isfinite(traced[5].z):
        raise RuntimeError("The candidate floor trace lacks a stable surface")
    support = [x, y, traced[5].z + cosmetic_offset_cm]
    row = {"kind": kind, "source_sha256": source_sha256, "axis_conversion": "z_up_to_gltf_y_up",
           "support_cm": support, "yaw_deg": yaw,
           "anchor": {"actor_path": volume.get_path_name(), "component_path": component.get_path_name(),
                      "mesh_path": stall, "instance_index": stall_index, "location_cm": loc,
                      "rotation_deg": rot, "scale": scale},
           "surface": {"actor_path": traced[9].get_path_name(), "component_path": traced[10].get_path_name(),
                       "cosmetic_offset_cm": cosmetic_offset_cm}}
    box = mesh.get_bounds()
    origin, extent = box.origin, box.box_extent
    bounds = ((origin.x - extent.x, origin.y - extent.y, origin.z - extent.z),
              (origin.x + extent.x, origin.y + extent.y, origin.z + extent.z))
    prop = placement(kind, bounds, support, yaw)
    verify_anchor(unreal, actors, row["anchor"], prop["support_cm"])
    prop["solid_floor_z_cm"] = verify_support(unreal, world, row)
    xy_clear([prop], verified_stories(actors))
    count = verify_scene_clearance(unreal, actors, [prop])
    result = {"schema": 1, "status": "live_survey_requires_visual_review", "id": identifier, "level": LEVEL,
              "town_layout_sha256": importer.sha256(importer.PROJECT / "Tools/CityPCG/build_medieval_london_map.py"),
              "markers_sha256": importer.sha256(importer.PROJECT / "ArtDirection/WorldJump/graylondon_markers.json"),
              "marker_layout_sha256": importer.sha256(importer.PROJECT / "Tools/CityPCG/populate_medieval_london_gameplay.py"),
              "placements": [row]}
    checked_plan(result)
    importer.lease_check(unreal, lease)
    return {"plan": result, "proposed": prop, "checked_scene_instances": count, "saved_packages": []}


async def run(plan_path, *, placement_visually_reviewed=False):
    """Generate/save the exact graph and owned non-World-Partition map only.

    This is an untested editor draft. It cannot run without a live-reviewed
    survey and explicit lease. Async failure can leave new unsaved state.
    """
    import unreal

    if placement_visually_reviewed is not True:
        raise ValueError("Visually review and explicitly acknowledge the surveyed placement first")
    lease = importer.lease_check(unreal)
    plan = plan_path if isinstance(plan_path, dict) else json.loads(Path(plan_path).read_text(encoding="utf-8-sig"))
    rows = checked_plan(plan)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    world_actors = list(actors.get_all_level_actors())
    story = verified_stories(world_actors)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    kinds = {row["kind"] for row in rows}
    meshes, sources = {}, {}
    for kind in sorted(kinds):
        shas = {row["source_sha256"] for row in rows if row["kind"] == kind}
        if len(shas) != 1:
            raise ValueError("A prop kind must have exactly one reviewed source")
        source_sha = next(iter(shas))
        path = importer.source_path(kind, source_sha)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != source_sha:
            raise RuntimeError("Source changed after its digest was checked")
        package = importer.asset_package(kind)
        mesh = unreal.EditorAssetLibrary.load_asset(package)
        if not isinstance(mesh, unreal.StaticMesh) or mesh.get_package().get_name() != package:
            raise RuntimeError("The reviewed owned mesh is not imported")
        verify_material(unreal, mesh, kind)
        normalized, _ = normalize_z_up_glb(raw)
        importer.compare_unreal(unreal, mesh, normalized)
        meshes[kind], sources[kind] = mesh, path
    groups, placed = defaultdict(list), []
    for index, row in enumerate(rows):
        importer.lease_check(unreal, lease)
        kind, mesh = row["kind"], meshes[row["kind"]]
        bounds = mesh.get_bounds()
        origin, extent = bounds.origin, bounds.box_extent
        box = ((origin.x - extent.x, origin.y - extent.y, origin.z - extent.z),
               (origin.x + extent.x, origin.y + extent.y, origin.z + extent.z))
        prop = placement(kind, box, row["support_cm"], row["yaw_deg"], row.get("longest_cm"))
        verify_anchor(unreal, world_actors, row["anchor"], prop["support_cm"])
        prop["solid_floor_z_cm"] = verify_support(unreal, world, row)
        placed.append(prop)
        groups[kind].append((prop["location_cm"], prop["yaw_deg"], prop["scale"], index + 1))
    xy_clear(placed, story)
    checked_scene_instances = verify_scene_clearance(unreal, world_actors, placed)
    graph_name = "PCG_GLMarketTripo_" + plan["id"]
    graph_path = GRAPH_ROOT + "/" + graph_name
    importer.assert_absent(unreal, graph_path)
    if any(actor.get_actor_label() == graph_name for actor in world_actors):
        raise RuntimeError("A market graph actor already uses this label")
    importer.lease_check(unreal, lease)
    pcg = unreal.get_editor_subsystem(unreal.PCGEditorSubsystem)
    graph = pcg.create_graph(graph_name, GRAPH_ROOT)
    if not graph or graph.get_package().get_name() != graph_path:
        raise RuntimeError("Could not create the exact owned graph")
    pcg_helpers.populate_point_mesh_graph(unreal, pcg, graph, groups, meshes)
    info = pcg.spawn_graph_instance(graph, graph_name, pcg_helpers.cell_transform(unreal, groups))
    actor = info.get_editor_property("actor")
    if not actor or actor.get_actor_label() != graph_name or actor.get_package().get_name() != LEVEL:
        raise RuntimeError("The new PCG actor is not in the owned non-World-Partition map")
    actor.set_actor_enable_collision(False)
    if actor.get_actor_enable_collision():
        raise RuntimeError("The market PCG actor still has collision enabled")
    actor.set_folder_path("CityPCG/MarketDressing")
    component = actor.get_component_by_class(unreal.PCGComponent)
    component.set_editor_properties({"generation_trigger": unreal.PCGComponentGenerationTrigger.GENERATE_ON_DEMAND,
                                     "generate_on_drop_when_trigger_on_demand": False,
                                     "regenerate_in_editor": False, "is_component_partitioned": False})
    pending = (pcg.wait_for_graph_instance(component) if component.get_editor_property("generation_in_progress")
               else pcg.execute_graph_instance(component))
    deadline = time.monotonic() + 25.
    while not pending.get_editor_property("is_complete"):
        importer.lease_check(unreal, lease)
        if time.monotonic() >= deadline:
            raise RuntimeError("PCG is still pending; no packages saved. Coordinate cleanup before retrying.")
        await asyncio.sleep(.1)
    if pending.get_editor_property("error"):
        raise RuntimeError("PCG generation failed; no packages were saved")
    for message in pending.get_editor_property("value"):
        if str(message.get_editor_property("severity")).lower() in ("fatal", "error", "warning"):
            raise RuntimeError("PCG reported a warning or error; no packages were saved")
    counts = verify_output(unreal, actor, groups, meshes)
    importer.lease_check(unreal, lease)
    packages = [graph.get_package(), world.get_package()]
    if [p.get_name() for p in packages] != [graph_path, LEVEL]:
        raise RuntimeError("Unexpected save packages")
    if not unreal.EditorLoadingAndSavingUtils.save_packages(packages, only_dirty=False):
        raise RuntimeError("Explicit graph/map save failed; inspect both packages for partial writes")
    return {"status": "editor_generated_requires_play_and_visual_validation", "instances": counts,
            "checked_scene_instances": checked_scene_instances,
            "saved_packages": [graph_path, LEVEL], "placements": placed}

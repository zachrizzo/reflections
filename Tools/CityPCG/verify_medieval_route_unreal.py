"""Verify a route spanning multiple Gray London tiles and produce one PCG plan."""

from collections import defaultdict
import json
import math
from pathlib import Path

from apply_facade_pcg import MEDIEVAL_DESTINATION, graph_name, read_plan
from import_medieval_kit import opening_world
from plan_medieval_district import plan
from verify_tile_frontages_unreal import verify_document


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def verify_route(sources, previous_plans=(), cell_budget=125, narrow_kit=False):
    """Use already loaded OSM actors and leave the editor state unchanged."""
    import unreal

    opening_world(unreal)
    documents = [read_json(path) for path in sources]
    previous = [read_json(path) for path in previous_plans]
    if not documents:
        raise ValueError("Supply at least one protected street corridor.")
    if cell_budget < 1:
        raise ValueError("The cell budget must be positive.")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    loaded = {actor.get_actor_label() for actor in actors.get_all_level_actors()}
    missing = sorted({f"OSM {document['source']}" for document in documents} - loaded)
    if missing:
        raise RuntimeError(f"Load the exact published source tile actors first: {missing}")

    cells = defaultdict(list)
    evidence = []
    claimed = set()
    for document in documents:
        frontages = document["frontages"]
        window = 50
        runs = []
        for index in range(0, len(frontages), window):
            result = verify_document({**document, "frontages": frontages[index:index + window]})
            runs.append(result)
        if not runs:
            continue
        verification = {"expected_actor": runs[0]["expected_actor"],
                        "samples": [hit for run in runs for hit in run["samples"]]}
        verified = plan(document, verification, previous, cell_budget=cell_budget, narrow_kit=narrow_kit)
        evidence.append({
            "source": document["source"],
            "scope": document.get("review_scope"),
            "rays": sum(run["rays"] for run in runs),
            "passed": sum(run["passed"] for run in runs),
            "wall_runs": len(frontages),
            "skipped_frontages": verified["skipped_frontages"],
            "previously_dressed_frontages": verified["previously_dressed_frontages"],
            "unfit_frontages": verified["unfit_frontages"],
            "samples": verification["samples"],
        })
        for cell in verified["cells"]:
            added = cells[cell["id"]]
            for point in cell["points"]:
                if point["id"] in claimed:
                    raise ValueError(f"The reviewed corridors share instance {point['id']}.")
                claimed.add(point["id"])
                added.append(point)
            if len(added) > cell_budget:
                raise ValueError(f"Combined cell {cell['id']} exceeds {cell_budget} bays.")

    return {
        "coordinate_system": "ue_cm",
        "kit": f"{MEDIEVAL_DESTINATION}/Kit",
        "verified": True,
        "cells": [{"id": key, "points": points} for key, points in sorted(cells.items())],
        "verification": evidence,
    }


def audit_cells(plan_path, cell_ids, use_game_world=False):
    """Read the generated transforms and visual state from the chosen loaded world."""
    import unreal

    planned = read_plan(plan_path)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_game_world() if use_game_world else opening_world(unreal)
    if not world or not world.get_path_name().endswith("GrayLondon_Geodata.GrayLondon_Geodata"):
        raise RuntimeError("The requested Gray London world is unavailable.")
    actors = {actor.get_actor_label(): actor
              for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.PCGVolume)}
    reports = {}
    for cell_id in cell_ids:
        label = graph_name(cell_id)
        actor = actors.get(label)
        if not actor:
            raise RuntimeError(f"Load the generated PCG actor {label} before checking its instances.")
        pcg = actor.get_component_by_class(unreal.PCGComponent)
        graph = pcg.get_graph() if pcg else None
        expected_graph = f"{MEDIEVAL_DESTINATION}/Graphs/{label}"
        if not graph or graph.get_package().get_name() != expected_graph or not pcg.get_editor_property("generated"):
            raise RuntimeError(f"{label} is not the generated graph for this medieval plan.")
        actual = defaultdict(list)
        rendered = []
        for component in actor.get_components_by_class(unreal.InstancedStaticMeshComponent):
            mesh = component.get_editor_property("static_mesh")
            if (not mesh or not component.is_visible() or component.get_editor_property("hidden_in_game") or
                    str(component.get_collision_profile_name()) != "NoCollision" or
                    component.get_editor_property("can_ever_affect_navigation")):
                raise RuntimeError(f"Unexpected visual or collision state on {label}/{component.get_name()}.")
            name = mesh.get_name()
            if mesh.get_package().get_name() != f"{MEDIEVAL_DESTINATION}/Kit/{name}":
                raise RuntimeError(f"{label} uses unexpected mesh {mesh.get_path_name()}.")
            if component.was_recently_rendered(1.0):
                rendered.append(name)
            for index in range(component.get_instance_count()):
                transform = component.get_instance_transform(index, True)
                location = tuple(getattr(transform.translation, axis) for axis in "xyz")
                scale = tuple(getattr(transform.scale3d, axis) for axis in "xyz")
                actual[name].append((location, transform.rotation.rotator().yaw, scale))
        groups = planned[cell_id]
        if {name: len(rows) for name, rows in actual.items()} != {name: len(rows) for name, rows in groups.items()}:
            raise RuntimeError(f"{label} does not have the accepted mesh instance counts.")
        maxima = [0.0, 0.0, 0.0]
        for name, expected in groups.items():
            remaining = actual[name]
            for location, yaw, scale, _ in expected:
                errors = [(math.dist(location, other_location), abs((yaw - other_yaw + 180) % 360 - 180),
                           max(abs(a - b) for a, b in zip(scale, other_scale)))
                          for other_location, other_yaw, other_scale in remaining]
                nearest = min(range(len(errors)), key=errors.__getitem__)
                if any(error > tolerance for error, tolerance in zip(errors[nearest], (.04, .001, .00001))):
                    raise RuntimeError(f"Instance transform differs from plan in {label}/{name} at {location}.")
                maxima = [max(previous, current) for previous, current in zip(maxima, errors[nearest])]
                remaining.pop(nearest)
        reports[cell_id] = {"actor": actor.get_path_name(), "graph": expected_graph,
                            "instances": sum(len(rows) for rows in groups.values()),
                            "maximum_position_cm_yaw_deg_scale_error": maxima,
                            "recently_rendered_meshes": sorted(rendered)}
    return reports

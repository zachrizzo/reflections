"""Verify a route spanning multiple Gray London tiles and produce one PCG plan."""

from collections import defaultdict
import json
from pathlib import Path

from apply_facade_pcg import MEDIEVAL_DESTINATION
from import_medieval_kit import opening_world
from plan_medieval_district import plan
from verify_tile_frontages_unreal import verify_document


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def verify_route(sources, previous_plans=(), cell_budget=125):
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
        verified = plan(document, verification, previous, cell_budget=cell_budget)
        evidence.append({
            "source": document["source"],
            "scope": document.get("review_scope"),
            "rays": sum(run["rays"] for run in runs),
            "passed": sum(run["passed"] for run in runs),
            "wall_runs": len(frontages),
            "skipped_frontages": verified["skipped_frontages"],
            "previously_dressed_frontages": verified["previously_dressed_frontages"],
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

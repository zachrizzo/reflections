"""Measure motion-matched feet, route travel, applied clothing and a real hit in PIE."""
import json
import math
import time
import traceback
from pathlib import Path

import unreal


OUT = Path(unreal.Paths.project_intermediate_dir()).resolve() / "NpcMovement" / "pie.json"
BONES = ("upperarm_l", "upperarm_r", "lowerarm_l", "lowerarm_r", "head")


def vector(value):
    return list(value.to_tuple())


def sample(world):
    records = {}
    actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
    for actor in actors:
        brain = actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent)
        if not brain:
            continue
        driver = brain.get_locomotion_driver()
        source_mesh = driver.get_editor_property("mesh") if driver else None
        body = next(c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name() == "Body")
        components = actor.get_components_by_class(unreal.SkeletalMeshComponent)
        records[actor.get_actor_label()] = {
            "position": vector(actor.get_actor_location()),
            "speed": driver.get_velocity().length() if driver else 0,
            "driver_penetrating_world": driver_penetrating_world(world, actor, driver),
            "source": source_mesh.get_anim_instance().get_class().get_name() if source_mesh and source_mesh.get_anim_instance() else None,
            "source_visible": source_mesh.is_visible() if source_mesh else None,
            "visible": body.get_anim_instance().get_class().get_name() if body.get_anim_instance() else None,
            "foot_l": vector(body.get_world_transform().inverse_transform_location(body.get_socket_location("foot_l"))),
            "foot_r": vector(body.get_world_transform().inverse_transform_location(body.get_socket_location("foot_r"))),
            "reaction": str(brain.get_editor_property("reaction")),
            "visible_meshes": {
                c.get_name(): c.get_skeletal_mesh_asset().get_name()
                for c in components
                if c.is_visible() and c.get_skeletal_mesh_asset() and not c.get_editor_property("hidden_in_game")
            },
            "cloth": [
                c.get_skeletal_mesh_asset().get_name()
                for c in components
                if c.is_visible() and c.get_skeletal_mesh_asset() and c.get_skeletal_mesh_asset().get_name().endswith(("Refit", "SimpleRed"))
            ],
            "owner": actor,
            "driver": driver,
            "body": body,
        }
    return records


def driver_penetrating_world(world, actor, driver):
    if not driver:
        return False
    capsule = driver.get_component_by_class(unreal.CapsuleComponent)
    center = capsule.get_world_location()
    hits = unreal.SystemLibrary.capsule_trace_multi_for_objects(
        world, center, center + unreal.Vector(0, 0, 0.1),
        capsule.get_scaled_capsule_radius() - 0.5, capsule.get_scaled_capsule_half_height() - 0.5,
        [unreal.ObjectTypeQuery.ECC_WORLD_STATIC], False, [actor, driver], unreal.DrawDebugTrace.NONE, False,
    ) or []
    return any(hit.to_tuple()[1] for hit in hits)


def run():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if editor.get_game_world():
        raise RuntimeError("End existing Play before starting the crowd test")
    state = {"start": time.monotonic(), "elapsed": 0.0, "first": None, "samples": [], "impact": None, "physics": []}

    def observe(delta):
        try:
            if time.monotonic() - state["start"] > 90:
                raise TimeoutError("Crowd PIE test did not complete")
            world = editor.get_game_world()
            player = unreal.GameplayStatics.get_player_pawn(world, 0) if world else None
            if not player:
                return
            state["elapsed"] += delta
            elapsed = state["elapsed"]
            if elapsed < 0.30:
                return
            if state["first"] is None:
                state["first"] = sample(world)
                child = next(c for c in player.get_components_by_class(unreal.ChildActorComponent) if c.get_name() == "HeroVisual")
                hero_visual = child.get_editor_property("child_actor")
                state["hero_clothing"] = {
                    c.get_name(): c.get_skeletal_mesh_asset().get_name()
                    for c in hero_visual.get_components_by_class(unreal.SkeletalMeshComponent)
                    if c.get_name().startswith("Travel") and c.is_visible() and c.get_skeletal_mesh_asset()
                }
            if len(state["samples"]) < 20 and elapsed >= 0.45 + len(state["samples"]) * 0.25:
                state["samples"].append(sample(world))
            if elapsed >= 5.5 and state["impact"] is None:
                row = sample(world)["Crowd Preview - White 01"]
                target = row["owner"]
                proxy = next(c for c in target.get_components_by_class(unreal.CapsuleComponent) if c.get_name() == "RuntimeNpcHitProxy")
                center = proxy.get_world_location()
                health = target.get_component_by_class(unreal.ReflectionsHealthComponent)
                state["impact"] = {"health": health, "before": health.get_editor_property("health"), "body": row["body"]}
                combat = player.get_component_by_class(unreal.ReflectionsSpellCombatComponent)
                start = center - unreal.Vector(115, 0, 0)
                combat.release_spell(unreal.HeroSpell.FIRE, unreal.Transform(location=start, rotation=unreal.Rotator(), scale=unreal.Vector(1, 1, 1)))
            if state["impact"]:
                body = state["impact"]["body"]
                if any(body.is_simulating_physics(bone) for bone in BONES):
                    state["physics"].append(elapsed)
            if elapsed < 7.2:
                return
            motion = {}
            for label, row in state["first"].items():
                rows = [snap[label] for snap in state["samples"]]
                motion[label] = {
                    "source": row["source"],
                    "source_visible": row["source_visible"],
                    "retarget": row["visible"],
                    "distance_from_start_cm": round(max(math.dist(row["position"], s["position"]) for s in rows), 1),
                    "max_speed_cm_s": round(max(s["speed"] for s in rows), 1),
                    "world_penetration_samples": sum(s["driver_penetrating_world"] for s in rows),
                    "foot_l_local_range_cm": round(max(math.dist(a["foot_l"], b["foot_l"]) for a in rows for b in rows), 2),
                    "foot_r_local_range_cm": round(max(math.dist(a["foot_r"], b["foot_r"]) for a in rows for b in rows), 2),
                    "clothes": row["cloth"],
                    "visible_meshes": row["visible_meshes"],
                }
            body = state["impact"]["body"]
            report = {"map": world.get_path_name(), "hero_clothing": state["hero_clothing"], "motion": motion, "impact": {
                "health_before": state["impact"]["before"],
                "health_after": state["impact"]["health"].get_editor_property("health"),
                "visible_body_simulated": bool(state["physics"]),
                "recovered": not any(body.is_simulating_physics(bone) for bone in BONES),
            }}
            OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
            unreal.unregister_slate_post_tick_callback(observe.handle)
            levels.editor_request_end_play()
        except BaseException:
            OUT.write_text(traceback.format_exc(), encoding="utf-8")
            unreal.unregister_slate_post_tick_callback(observe.handle)
            if editor.get_game_world():
                levels.editor_request_end_play()

    observe.handle = unreal.register_slate_post_tick_callback(observe)
    levels.editor_request_begin_play()

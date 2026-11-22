"""Capture the Test Town preview lineup using Unreal's editor Python console.

Execute this file in the editor with the characters standing in their neutral pose.
Run audit_posed_surfaces.py in Blender on the resulting surfaces directory.
"""
import json
from pathlib import Path

import unreal


PREVIEW_FOLDERS = {"Preview/MetaHuman Lineup", "Preview/Fantasy MetaHumans", "Preview/Wardrobe Holdout"}
JOINTS = ("pelvis", "spine_03", "spine_05", "upperarm_l", "upperarm_r", "hand_l", "hand_r", "foot_l", "foot_r")
MOTIONS = {
    "walk": "/MetaHumanCharacter/Optional/Animation/UEFNAnimPreset/Locomotion/AS_MH_Neutral_Walk_Loop_F",
    "crouch": "/Game/Characters/Hero/Animation/Locomotion/AS_Hero_CrouchWalk",
    "cast": "/Game/Characters/Hero/Animation/CombatCasts/AS_Hero_CombatHealRaise",
}


def capture_actor(actor, clips, directory, library):
    pieces = actor.get_components_by_class(unreal.SkeletalMeshComponent)
    body = next(comp for comp in pieces if comp.get_name() == "Body")
    face = next(comp for comp in pieces if comp.get_name() == "Face")
    tunics = [comp for comp in actor.get_components_by_class(unreal.ChaosClothComponent)
              if comp.get_material(0) and comp.get_material(0).get_name() == "M_WayfarersLinen"]
    if len(tunics) != 1 or body.animation_mode != unreal.AnimationMode.ANIMATION_BLUEPRINT:
        raise ValueError(f"Expected the neutral preview actor wearing one tunic: {actor.get_actor_label()}")

    mode = body.animation_mode
    ticking = body.get_editor_property("update_animation_in_editor")
    original_leader = face.leader_pose_component
    directory.mkdir(parents=True, exist_ok=True)
    manifest = directory / "frames.json"
    manifest.unlink(missing_ok=True)
    frames = {}
    to_actor = actor.get_actor_transform().inverse_transform_location

    def record(label, clip=None):
        frame = {
            "time": round(body.get_position(), 5) if clip else 0.0,
            "animation": clip.get_path_name() if clip else "rest",
            "bones_cm": {j: list(to_actor(body.get_socket_location(j)).to_tuple()) for j in JOINTS},
        }
        for part, component in (("body", body), ("face", face), ("tunic", tunics[0])):
            if not library.write_posed_surface(component, str(directory / f"{label}_{part}.bin")):
                raise ValueError(f"Cannot read {actor.get_actor_label()} {label} {part}")
        frames[label] = frame

    try:
        library.refresh_sample_pose(body)
        library.refresh_sample_pose(face)
        record("rest")
        # The manual editor actor has no facial performance. Follow the same neck
        # for this body-only pose sample and restore the original face driver below.
        face.set_leader_pose_component(body, True)
        body.set_update_animation_in_editor(True)
        for name, clip in clips.items():
            body.play_animation(clip, False)
            body.stop()
            for percent in (22, 50, 78):
                body.set_position(clip.get_play_length() * percent / 100, fire_notifies=False)
                library.refresh_sample_pose(body)
                label = f"{name}_{percent}"
                record(label, clip)
                moved = max((unreal.Vector(*xyz) - unreal.Vector(*frames["rest"]["bones_cm"][joint])).length()
                            for joint, xyz in frames[label]["bones_cm"].items())
                if moved < 3:
                    raise ValueError(f"Animation failed to advance: {directory.name} {label}")
    finally:
        body.stop()
        body.set_animation(None)
        body.set_animation_mode(mode)
        body.set_update_animation_in_editor(ticking)
        library.refresh_sample_pose(body)
        face.set_leader_pose_component(original_leader, True)
        library.refresh_sample_pose(face)
    manifest.write_text(json.dumps(frames, indent=2), encoding="utf-8")


def main():
    unreal.load_module("ClothingFitEditor")
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if not world or not world.get_path_name().startswith("/Game/Maps/TestTown/L_TestTown."):
        raise ValueError("Open Test Town in editor mode")
    project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
    output = project / "Intermediate/WayfarerReview/surfaces"
    clips = {name: unreal.load_asset(path) for name, path in MOTIONS.items()}
    if not all(isinstance(clip, unreal.AnimSequence) for clip in clips.values()):
        raise ValueError("Missing motion review clip")
    lineup = [actor for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
              if str(actor.get_folder_path()) in PREVIEW_FOLDERS]
    if not lineup:
        raise ValueError("No preview characters in Test Town")
    names = [actor.get_actor_label().split(" ", 1)[-1] for actor in lineup]
    if len(set(names)) != len(lineup):
        raise ValueError("Each lineup character needs a unique name")
    output.mkdir(parents=True, exist_ok=True)
    manifest = output / "capture.json"
    manifest.write_text(json.dumps({"complete": False, "characters": names}))
    for actor, name in zip(lineup, names):
        capture_actor(actor, clips, output / name, unreal.ClothingFitLibrary)
    manifest.write_text(json.dumps({"complete": True, "characters": names}))
    unreal.log(f"Captured {len(lineup)} MetaHumans in {output}")


if __name__ == "__main__":
    main()

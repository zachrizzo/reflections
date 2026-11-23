"""Compare sampled Unreal garment geometry against skin and another garment.

Run in Blender. Input positions are actor-local centimeters. Report contact
area as the sum of touched obstacle triangles, not projected visible area.
"""
import argparse
import json
from pathlib import Path
import sys

from mathutils import Vector
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_posed_surfaces import surface, tree


def skin_orientation(points, faces):
    a, b, c = points[faces].transpose((1, 0, 2))
    return 1 if np.einsum("ij,ij->", a, np.cross(b, c)) > 0 else -1


def contacts(obstacle, obstacle_faces, cloth, cloth_faces, cloth_tree, orientation=None):
    obstacle_tree = tree(obstacle, obstacle_faces)
    pairs = obstacle_tree.overlap(cloth_tree)
    if not pairs:
        return {"obstacle_triangles": 0, "garment_triangles": 0, "obstacle_area_cm2": 0.,
                "worst_sample_inward_mm": 0. if orientation is not None else None}

    skin_indices, garment_indices = [np.unique(indices) for indices in zip(*pairs, strict=True)]
    a, b, c = obstacle[obstacle_faces[skin_indices]].transpose((1, 0, 2))
    area = .5 * np.linalg.norm(np.cross(b - a, c - a), axis=1).sum()
    inward_mm = None
    if orientation is not None:
        contact_verts = cloth[np.unique(cloth_faces[garment_indices])]
        centers = cloth[cloth_faces[garment_indices]].mean(axis=1)
        peak = 0.
        for pos in np.vstack((contact_verts, centers)):
            point = Vector(pos)
            hit, normal, _, distance = obstacle_tree.find_nearest(point)
            if (point - hit).dot(normal) * orientation < 0:
                peak = max(peak, distance)
        inward_mm = round(10 * peak, 2)
    return {
        "obstacle_triangles": len(skin_indices),
        "garment_triangles": len(garment_indices),
        "obstacle_area_cm2": round(float(area), 3),
        "worst_sample_inward_mm": inward_mm,
    }


def measure_frame(folder, label, neutral):
    body, body_faces = surface(folder / f"{label}_body.bin")
    head, head_faces = surface(folder / f"{label}_face.bin")
    bottom, bottom_faces = surface(folder / f"{label}_bottom.bin")
    cloth, cloth_faces = surface(folder / f"{label}_jerkin.bin")
    if label == "standing":
        edges = np.unique(np.sort(cloth_faces[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2), axis=1), axis=0)
        lengths = np.linalg.norm(cloth[edges[:, 0]] - cloth[edges[:, 1]], axis=1)
        eligible = lengths >= .050
        neutral.update(position=cloth, topology=cloth_faces, edges=edges[eligible], lengths=lengths[eligible])
    elif not np.array_equal(cloth_faces, neutral["topology"]):
        raise ValueError(f"Topology varied during motion in {folder}")

    cloth_tree = tree(cloth, cloth_faces)
    bounds = np.array((cloth.min(axis=0) - 2, cloth.max(axis=0) + 2))
    skin = np.concatenate((body, head))
    joined_faces = np.concatenate((body_faces, head_faces + len(body)))
    active = np.all((skin >= bounds[0]) & (skin <= bounds[1]), axis=1)
    # Keep full torso triangles consistently for both overlap and depth queries.
    skin_contacts = contacts(skin, joined_faces[active[joined_faces].any(axis=1)], cloth, cloth_faces,
                             cloth_tree, skin_orientation(skin, joined_faces))
    bottoms = np.all((bottom >= bounds[0]) & (bottom <= bounds[1]), axis=1)
    trousers_contacts = contacts(bottom, bottom_faces[bottoms[bottom_faces].any(axis=1)], cloth, cloth_faces, cloth_tree)
    edges = neutral["edges"]
    elongation = np.linalg.norm(cloth[edges[:, 0]] - cloth[edges[:, 1]], axis=1) / neutral["lengths"] - 1
    return {"jerkin_triangles": len(cloth_faces), "skin": skin_contacts, "trousers": trousers_contacts,
            "edge_elongation_p95_pct": round(float(np.percentile(elongation, 95) * 100), 2),
            "jerkin_vertex_travel_p95_cm": round(float(np.percentile(np.linalg.norm(cloth - neutral["position"], axis=1), 95)), 2)}


def summarize(frames):
    summary = {"poses": len(frames)}
    for name in ("skin", "trousers"):
        areas = [frame[name]["obstacle_area_cm2"] for frame in frames]
        peak = max(frames, key=lambda frame: frame[name]["obstacle_area_cm2"])
        summary[name] = {
            "poses_with_contact": sum(frame[name]["garment_triangles"] > 0 for frame in frames),
            "max_garment_triangles": max(frame[name]["garment_triangles"] for frame in frames),
            "median_obstacle_area_cm2": round(float(np.median(areas)), 3),
            "peak_obstacle_area_cm2": peak[name]["obstacle_area_cm2"],
            "max_sample_inward_mm": max((frame[name]["worst_sample_inward_mm"] for frame in frames), default=None) if name == "skin" else None,
            "peak_area_pose": peak["label"],
        }
    summary["worst_edge_elongation_p95_pct"] = max(frame["edge_elongation_p95_pct"] for frame in frames)
    summary["max_vertex_travel_p95_cm"] = max(frame["jerkin_vertex_travel_p95_cm"] for frame in frames)
    return summary


def audit(folder):
    manifest = json.loads((folder / "Manifest.json").read_text())
    neutral = {}
    standing = dict(label="standing", **measure_frame(folder, "standing", neutral))
    summaries = {"standing": summarize([standing])}
    all_frames = {"standing": [standing]}
    for name, clip in manifest["clips"].items():
        frames = [
            dict(label=frame["label"], **measure_frame(folder, frame["label"], neutral))
            for frame in clip["frames"]
        ]
        all_frames[name] = frames
        summaries[name] = summarize(frames)
    return {"wardrobe": manifest["source"], "particles": manifest["particles"], "summary": summaries, "frames": all_frames}


def audit_roster(folder):
    manifest = json.loads((folder / "RosterManifest.json").read_text())
    wearers = {name: audit(folder / name) for name in manifest["characters"]}
    passes = {}
    for section in ("standing", "walk", "reach"):
        passes[section] = {
            obstacle: sum(data["summary"][section][obstacle]["poses_with_contact"] == 0
                          for data in wearers.values())
            for obstacle in ("skin", "trousers")
        }
        passes[section]["both"] = sum(
            data["summary"][section]["skin"]["poses_with_contact"] == 0
            and data["summary"][section]["trousers"]["poses_with_contact"] == 0
            for data in wearers.values()
        )
    passes["characters_sampled"] = len(wearers)
    passes["total_poses"] = sum(section["poses"] for data in wearers.values()
                                for section in data["summary"].values())
    passes["all_poses_clear"] = sum(
        all(clip[collider]["poses_with_contact"] == 0 for clip in data["summary"].values()
            for collider in ("skin", "trousers"))
        for data in wearers.values()
    )
    return {"summary": passes, "capture": manifest, "wearers": wearers}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    is_roster = (args.folder / "RosterManifest.json").is_file()
    results = audit_roster(args.folder) if is_roster else audit(args.folder)
    args.output.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results["summary"], separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()

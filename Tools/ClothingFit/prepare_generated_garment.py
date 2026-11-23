"""Automatic fit preparation for an image-generated garment (step between registration and Unreal import).

  python prepare_generated_garment.py <garment.npz> <source body capture folder> <output folder>
         [--under bottom] [--joints joints.json] [--set key=value ...] [--arms auto|on|off]

garment.npz        registered garment in source-body space, written by garmentprep/blender_io.py dump
                   (P welded positions in cm, F triangles, UV per corner; Unreal capture convention)
capture folder     standing_body.bin, standing_face.bin and standing_<under>.bin of the SOURCE body
                   wearing the layer underneath, plus Manifest.json with its joints (or --joints)
output folder      Prepared.npz, P.npy / F.npy / UV.npy (for blender_io.py build) and PrepareReport.json

What it does, with no garment-specific numbers:
  1. splits triangle edges that are too long to bend (original vertices, UVs and texture mapping kept);
  2. finds cloth buried in the body. A patch the spine or neck bone runs through is brought out on
     the side the bone leaves it by (lifted onto the shoulder if that is short, otherwise out
     sideways), never through the far wall. This is what opens a flat neck hole and wraps it behind
     the neck. All other buried cloth leaves by the nearest wall;
  3. for a sleeveless top (detected: cloth at the shoulders, none around the upper arms) keeps the
     cloth off the resting upper arm on its trunk-facing side, and close to the trunk in the space
     the hanging, swinging arm passes through (form-fitting sides);
     sleeves and trouser legs (detected: cloth all the way round a limb) are pulled in to hug the limb,
     and if they run on past the wrist or ankle they are shortened below the elbow or knee so the hands
     and feet stay free;
  4. relaxes the displacement over the mesh (both walls of the shell together) with sliding contact,
     stacks the two walls, keeps surface relief, and repeats until no triangle crosses skin or layer.
Needs numpy and scipy. Takes about a minute for a 70k-triangle garment.
"""
import argparse
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "garmentprep"))
import contact
import corridor
import field
import meshops
import prep

TRUNK = ("pelvis", "spine_01", "spine_02", "spine_03", "spine_04", "spine_05", "neck_01")
PARENTS = {"spine_01": "pelvis", "spine_02": "spine_01", "spine_03": "spine_02", "spine_04": "spine_03", "spine_05": "spine_04",
           "neck_01": "spine_05", "neck_02": "neck_01", "head": "neck_02",
           "clavicle_l": "spine_05", "upperarm_l": "clavicle_l", "lowerarm_l": "upperarm_l", "hand_l": "lowerarm_l",
           "clavicle_r": "spine_05", "upperarm_r": "clavicle_r", "lowerarm_r": "upperarm_r", "hand_r": "lowerarm_r",
           "thigh_l": "pelvis", "calf_l": "thigh_l", "foot_l": "calf_l", "thigh_r": "pelvis", "calf_r": "thigh_r", "foot_r": "calf_r"}


def load_joints(capture, override=None):
    for path in (override, capture / "joints_local.json"):
        if path and Path(path).exists():
            data = json.loads(Path(path).read_text())
            return {k: np.asarray(v, float) for k, v in data.get("joints", data).items()}
    rest = json.loads((capture / "Manifest.json").read_text())["rest"]
    assert "lowerarm_l" in rest, "the capture has no arm joints; pass --joints"
    return {k: np.asarray(v, float) for k, v in rest.items()}


def body_fields(capture, under, lo, hi, cache=True):
    """Signed distance field of the source body's skin, with the layer underneath folded in."""
    body, bf = meshops.read_surface(capture / "standing_body.bin")
    face, ff = meshops.read_surface(capture / "standing_face.bin")
    skin = np.vstack((body, face)); sf = np.vstack((bf, ff + len(body)))
    layers = []
    for tag in under:
        path = capture / f"standing_{tag}.bin"
        if path.exists():
            layers.append(meshops.read_surface(path))
    key = f"{len(skin)}_{len(sf)}_{float(skin.sum()):.3f}_{'-'.join(under)}_{np.round(lo, 1).tolist()}_{np.round(hi, 1).tolist()}"
    store = capture / "BodyField.pkl"
    if cache and store.exists():
        saved = pickle.load(open(store, "rb"))
        if saved.get("key") == key:
            return skin, sf, layers, saved["field"]
    plain = field.SignedField(skin, sf, lo, hi)
    full = plain
    for P, F in layers:
        full = prep.add_layer(full, P, F, .15)
    if cache:
        pickle.dump(dict(key=key, field=full), open(store, "wb"))
    return skin, sf, layers, full


def wraps_limb(P, a, b, lo=.35, hi=.65, radius=12.):
    """True if cloth goes all the way round the bone a->b half way along it (a sleeve or a trouser leg)."""
    bone = b - a
    length = np.linalg.norm(bone)
    bone = bone / length
    rel = P - a
    along = rel @ bone
    off = rel - along[:, None] * bone
    ring = (along > lo * length) & (along < hi * length) & (np.linalg.norm(off, axis=1) < radius)
    if ring.sum() < 60:
        return False
    u = np.cross(bone, [0., 1., 0.]); u /= np.linalg.norm(u)
    v = np.cross(u, bone)
    angle = np.degrees(np.arctan2(off[ring] @ v, off[ring] @ u))
    return len(np.unique(((angle + 180) // 30).astype(int))) >= 11


END_PAST = {"hand": 1.5, "foot": -3.}    # cm past the wrist / ankle joint where a sleeve / trouser leg ends


def end_limbs_at_joints(P, F, joints, trunk, log=print):
    """A sleeve may not cover the hand and a trouser leg may not cover the foot. Where cloth that wraps a limb
    runs on past the wrist (ankle), the part below the elbow (knee) is shortened along the forearm (shin) so the
    cuff lands END_PAST cm past the wrist (ankle) joint. Shorter sleeves and legs are left alone."""
    P = P.copy()
    report = {}
    d_trunk = prep.distance_to_segments(P, np.asarray(trunk))[0] if len(trunk) else np.full(len(P), np.inf)
    for upper, lower, end in (("upperarm", "lowerarm", "hand"), ("thigh", "calf", "foot")):
        chains = {}
        for side in "lr":
            a, b, c = (joints.get(f"{n}_{side}") for n in (upper, lower, end))
            if a is not None and b is not None and c is not None and wraps_limb(P, b, c, radius=16.):
                chains[side] = (a, b, c)            # cloth all round the forearm / shin: a sleeve or leg that reaches it
        if not chains:
            continue
        dist = {}
        for side, (a, b, c) in chains.items():
            u = (c - b) / np.linalg.norm(c - b)
            seg = np.asarray([[a, b], [b, c], [c, c + 40. * u]])
            dist[side] = prep.distance_to_segments(P, seg)[0]
        for side, (a, b, c) in chains.items():
            others = [dist[o] for o in dist if o != side] + [d_trunk]
            mine = (dist[side] < np.minimum.reduce(others)) & (dist[side] < 16.)
            u = (c - b) / np.linalg.norm(c - b)
            length = float(np.linalg.norm(c - b))
            along = (P - b) @ u
            perp = np.linalg.norm((P - b) - along[:, None] * u, axis=1)
            ring = mine & (np.abs(along - .5 * length) < 4.)
            if ring.sum() < 30:
                continue
            # the sleeve (trouser leg) below the elbow (knee): inside a tube round the forearm (shin) line. Generated
            # meshes come in many separate panels (a cuff band can be its own piece), so this is geometric, not by
            # connectivity; the tube is sized from the sleeve itself half way down the forearm.
            tube = min(14., 1.6 * float(np.median(perp[ring])) + 2.)
            limb = mine & (perp < tube) & (along > 0)
            if not limb.any():
                continue
            reach = float(along[limb].max())
            target = length + END_PAST[end]
            name = f"{lower}_{side}"
            if reach <= target + .5:
                report[name] = dict(ends_past_joint_cm=round(reach - length, 1), shortened_cm=0.)
                continue
            move = limb
            P[move] += ((along[move] * target / reach) - along[move])[:, None] * u
            report[name] = dict(ends_past_joint_cm=round(reach - length, 1), shortened_cm=round(reach - target, 1), vertices=int(move.sum()), tube_cm=round(tube, 1))
            log(f"{name}: cloth ran {reach - length:.1f} cm past the {end} joint; shortened by {reach - target:.1f} cm below the {lower} joint")
    return P, report


def needs_arm_room(P, joints):
    """A sleeveless top: cloth at the shoulders, none around the upper arms."""
    if not all(k in joints for k in ("upperarm_l", "upperarm_r", "lowerarm_l", "lowerarm_r")):
        return False
    at_shoulder = any((np.linalg.norm(P - joints[f"upperarm_{s}"], axis=1) < 14.).sum() > 50 for s in "lr")
    sleeved = any(wraps_limb(P, joints[f"upperarm_{s}"], joints[f"lowerarm_{s}"]) for s in "lr")
    return at_shoulder and not sleeved


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("garment", type=Path)
    parser.add_argument("capture", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--under", action="append", default=None, help="tag of a layer worn underneath (default: bottom)")
    parser.add_argument("--joints", type=Path)
    parser.add_argument("--set", action="append", default=[], metavar="key=value", help="override a preparation setting")
    parser.add_argument("--arms", choices=("auto", "on", "off"), default="auto",
                        help="room for the hanging arm at the armhole and side: auto = only for a sleeveless top")
    parser.add_argument("--no-arms", action="store_true", help="same as --arms off")
    args = parser.parse_args()
    under = args.under or ["bottom"]
    params = {}
    for item in args.set:
        key, value = item.split("=", 1)
        params[key] = json.loads(value)
    started = time.time()
    data = np.load(args.garment)
    P, F, UV = data["P"], data["F"], data["UV"]
    joints = load_joints(args.capture, args.joints)
    bones = prep.bone_segments(joints, PARENTS)
    # sleeves end at the wrist, trouser legs at the ankle (the hands and feet stay free)
    trunk_segments = prep.bone_segments({k: joints[k] for k in TRUNK if k in joints}, PARENTS)
    P, limb_ends = end_limbs_at_joints(P, F, joints, trunk_segments)
    grow = np.array([8., 8., 14.])
    skin, sf, layers, full = body_fields(args.capture, under, P.min(0) - 8, P.max(0) + grow)
    arms = trunk = None
    arm_room = False if args.no_arms or args.arms == "off" else True if args.arms == "on" else needs_arm_room(P, joints)
    print(f"arm room at armhole and side: {'on' if arm_room else 'off'} ({'set' if args.no_arms or args.arms != 'auto' else 'detected'})")
    if arm_room and "lowerarm_l" in joints:
        arms = corridor.ArmCorridor(skin, joints)
        trunk = prep.bone_segments({k: joints[k] for k in TRUNK if k in joints}, PARENTS)
    spine = prep.bone_segments({k: joints[k] for k in TRUNK + ("neck_02", "head") if k in joints}, PARENTS)
    # sleeves and trouser legs (cloth all the way round a limb) are made to hug that limb
    limbs = []
    for chain in (("upperarm", "lowerarm", "hand"), ("thigh", "calf", "foot")):
        for side in "lr":
            a, b, c = (joints.get(f"{name}_{side}") for name in chain)
            if a is not None and b is not None and c is not None and (wraps_limb(P, a, b, radius=16.) or wraps_limb(P, b, c, radius=16.)):
                limbs.append([[a, b], [b, c]])
    print(f"limbs wrapped by the garment: {len(limbs)}")
    # the rule that brings pierced cloth out on the side the bone leaves by is for a neck hole made flat by a
    # front-view image; a garment that does not reach the neck (trousers, a skirt) has no such cloth, and a waistband
    # that sits a little inside the belly simply leaves by the nearest wall
    reaches_neck = "neck_01" in joints and int((np.linalg.norm(P - joints["neck_01"], axis=1) < 15.).sum()) > 50
    print(f"neck-hole rule (pierced cloth leaves on the bone's side): {'on' if reaches_neck else 'off, the garment does not reach the neck'}")
    result = prep.prepare(P, F, UV, full, bones, (skin, sf), layers, params, arms=arms, trunk_bones=trunk, spine=spine, limbs=limbs, pierce=reaches_neck)
    P0, F1, UV1, P1 = result["P0"], result["F"], result["UV"], result["P"]
    # torn facing: an inner wall (a turned-in hem or waistband facing) that started deep in the body can only come out
    # by stretching into a long thin fin across the opening. Such a triangle is not cloth any more; it is dropped
    # (it sits inside the opening, out of sight).
    def longest(Q):
        T = Q[F1]
        return np.max([np.linalg.norm(T[:, i] - T[:, (i + 1) % 3], axis=1) for i in range(3)], axis=0)
    torn = (longest(P1) > 6.) & (longest(P1) > 3. * longest(P0))
    if torn.any():
        print(f"torn facing: {int(torn.sum())} triangles stretched into fins, dropped")
        F1, UV1 = F1[~torn], UV1[~torn]
    args.output.mkdir(parents=True, exist_ok=True)
    np.savez(args.output / "Prepared.npz", P0=P0, P=P1, F=F1, UV=UV1, parent=result["parent"])
    for name, array in (("P", P1), ("F", F1), ("UV", UV1)):
        np.save(args.output / f"{name}.npy", array)
    meshops.write_surface(args.output / "standing_garment.bin", P1, F1)

    # ---- acceptance numbers for the standing shape (exact triangle tests)
    W0, Fw, inv = meshops.weld(P0, F1)
    W1 = np.zeros_like(W0); W1[inv] = P1
    crossing, skin_hit = contact.crossing_triangles(skin, sf, P1, F1)
    layer_cross = sum(len(contact.crossing_triangles(Pl, Fl, P1, F1)[0]) for Pl, Fl in layers)
    cp, dist, _ = contact.closest_on_tris(P1, skin, sf[np.all((skin[sf] >= P1.min(0) - 6) & (skin[sf] <= P1.max(0) + 6), axis=(1, 2))], k=10)
    edges = meshops.edges_of(F1)
    l0 = np.linalg.norm(P0[edges[:, 0]] - P0[edges[:, 1]], axis=1)
    l1 = np.linalg.norm(P1[edges[:, 0]] - P1[edges[:, 1]], axis=1)
    ok = l0 > .05
    change = (l1[ok] / l0[ok] - 1) * 100
    spread = float(np.abs(P1 - W1[inv]).max())
    report = dict(result["report"])
    report.pop("history", None)
    report.update(
        seconds=round(time.time() - started, 1), arm_room=bool(arm_room), limb_ends=limb_ends, neck_hole_rule=bool(reaches_neck), torn_triangles_dropped=int(torn.sum()),
        settings={k: v for k, v in dict(prep.DEFAULTS, **params).items()},
        triangles=int(len(F1)), vertices=int(len(P1)),
        standing=dict(triangles_crossing_skin=int(len(crossing)), triangles_crossing_layer_underneath=int(layer_cross),
                      skin_clearance_cm_min_p1_p5_p50=np.percentile(dist, [0, 1, 5, 50]).round(2).tolist(),
                      hem_lowest_z_cm_before_after=[round(float(P0[:, 2].min()), 2), round(float(P1[:, 2].min()), 2)]),
        seam_duplicates_max_spread_cm=spread,
        edge_length_change_pct_p1_p5_p50_p95_p99=np.percentile(change, [1, 5, 50, 95, 99]).round(1).tolist(),
        displacement_cm_p50_p95_max=np.percentile(np.linalg.norm(P1 - P0, axis=1), [50, 95, 100]).round(2).tolist(),
        self_crossing_pairs_before_after=[contact.self_crossing_pairs(W0, Fw), contact.self_crossing_pairs(W1, Fw)])
    # where the cloth was brought out of the body: report the cost there (stretch of the moved edge, squeeze of the patch)
    planned = result["planned"][result["garment"].inv]
    if planned.any():
        on_patch = planned[edges[:, 0]] & planned[edges[:, 1]] & ok
        report["moved_patch_edge_change_pct_p5_p50_p95"] = np.percentile((l1[on_patch] / l0[on_patch] - 1) * 100, [5, 50, 95]).round(1).tolist()
    (args.output / "PrepareReport.json").write_text(json.dumps(report, indent=1, default=float))
    print(json.dumps({k: report[k] for k in ("standing", "edge_length_change_pct_p1_p5_p50_p95_p99", "self_crossing_pairs_before_after", "refinement", "seconds")}, indent=1, default=float))


if __name__ == "__main__":
    main()

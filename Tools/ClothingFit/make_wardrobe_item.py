"""One command: garment description (or picture) -> fitted MetaHuman Wardrobe Item, tested on every body.

  python make_wardrobe_item.py <Name> <top|bottom> --describe "<what the garment looks like>"
  python make_wardrobe_item.py <Name> <top|bottom> --image <reference.png>
  python make_wardrobe_item.py <Name> <top|bottom> --mesh <textured.obj> --texture <colour.png>

  options  --over <Name>      a top that is worn over a bottom made with this command (default: the travel trousers)
           --until image|mesh|fit|unreal|test|mask   stop after that stage (default: mask, i.e. all)
           --redo  image|mesh|fit|unreal|test|mask   run that stage and the ones after it again
           --bodies Name ...   test only these bodies of the roster (default: all)
           --wear-with <WI path>   the other garment worn during the test (default: travel trousers for a top)

Stages (each is skipped when its result is already in Saved/ClothingFit/Generated/<Name>/):
  image   Codex (ChatGPT) draws the catalog reference image          garmentprep/reference_image.py
  mesh    local TRELLIS.2 (MIT) makes the textured mesh from that    generate_garment_mesh_trellis2.py
          image (GPU; needs ~21 GB of free memory: run it while the Unreal editor is closed)
  fit     the mesh is read, registered on the source body and
          fit-prepared (no crossing triangle on the source body)     register_garment.py, prepare_generated_garment.py
  unreal  static mesh -> cloth asset -> outfit -> Wardrobe Item       garmentprep/editor/import_garment.py
  test    the item is put on every MetaHuman of the roster, 51 poses
          each are captured and measured                             garmentprep/run_lineup.py, lineup_report.py
  mask    body hidden-face map from the source body's 51 captured poses,
          imported and set on the Wardrobe Item (the body under the
          garment is removed when a character is built)              garmentprep/hidden_face_map.py, editor/import_garment.py
No step edits a mesh by hand and nothing is tuned per garment or per character.
Run with a Python that has numpy, scipy, trimesh and Pillow. Blender is used without a window.
The Unreal stages need the shared editor (MCP on port 8019) and take the editor lease themselves.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PREP = HERE / "garmentprep"
PY = sys.executable
SOURCE = ROOT / "Saved/ClothingFit/SourceBody/Barnaby"           # standing capture of the source body (see README)
SOURCE_BODY_ASSET = "/Game/Characters/Clothing/VillageWardrobe/SwiftTailorPilot/Source/MHC_GiltBarnaby_FullBody"
PACKAGE = "/Game/Characters/Clothing/VillageWardrobe/Generated"
TROUSERS = "/Game/Characters/Clothing/VillageWardrobe/TravelTrousers/WI_TravelTrousers"
STAGES = ["image", "mesh", "fit", "unreal", "test", "mask"]
MASK_SHRINK = 1.0      # cm: skin next to the hidden area is pushed in this far (MaxShrinkDistance), the hidden area itself is removed
SOURCE_LABEL = "GiltBarnaby"                                       # roster label of the source body
SLOT = {"top": "Top Garment", "bottom": "Bottom Garment", "cloak": "Outfits"}
TRIANGLES = 60000


def blender():
    found = os.environ.get("BLENDER") or shutil.which("blender")
    if not found:
        local = Path(os.environ.get("TEMP", "")) / "codex-blender-4.5.5/blender-4.5.5-windows-x64/blender.exe"
        found = str(local) if local.exists() else None
    assert found, "Blender not found: set BLENDER to blender.exe"
    return found


def run(cmd, log):
    print("  >", " ".join(f'"{c}"' if " " in str(c) else str(c) for c in cmd[:6]), "..." if len(cmd) > 6 else "")
    with open(log, "a", encoding="utf-8") as stream:
        stream.write(f"\n=== {time.strftime('%H:%M:%S')} {' '.join(map(str, cmd))}\n")
        stream.flush()
        code = subprocess.call([str(c) for c in cmd], stdout=stream, stderr=subprocess.STDOUT)
    assert code == 0, f"step failed (exit {code}); see {log}"


def editor_python(script, params, purpose):
    sys.path.insert(0, str(PREP))
    import ue
    ok, data = ue.wait_claim(purpose, 240, 1800)
    assert ok, f"could not get the editor lease: {data}"
    try:
        code = "import json\nPARAMS = json.loads(" + repr(json.dumps(params)) + ")\n" + Path(script).read_text(encoding="utf-8")
        client = ue.Client()
        for _ in range(24):
            failed, value = client.python(code)
            if not (isinstance(value, str) and "running a slow task" in value):
                break
            time.sleep(5)
        assert not failed, f"editor script failed: {str(value)[:1500]}"
        return value
    finally:
        ue.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name")
    parser.add_argument("kind", choices=("top", "bottom", "cloak"))
    parser.add_argument("--describe")
    parser.add_argument("--image", type=Path)
    parser.add_argument("--mesh", type=Path)
    parser.add_argument("--texture", type=Path)
    parser.add_argument("--over")
    parser.add_argument("--until", choices=STAGES, default="mask")
    parser.add_argument("--redo", choices=STAGES)
    parser.add_argument("--bodies", nargs="*")
    parser.add_argument("--wear-with")
    parser.add_argument("--allow-defects", action="store_true", help="debug only: continue even if the automatic fit defect check flags folds/tears/stretch")
    args = parser.parse_args()
    name, kind = args.name, args.kind
    out = ROOT / "Saved/ClothingFit/Generated" / name
    out.mkdir(parents=True, exist_ok=True)
    log = out / "make_wardrobe_item.log"
    last = STAGES.index(args.until)
    redo = STAGES.index(args.redo) if args.redo else len(STAGES)

    def wanted(stage, result):
        index = STAGES.index(stage)
        return index <= last and (index >= redo or not Path(result).exists())

    assert (SOURCE / "standing_body.bin").exists(), f"source body capture missing: {SOURCE} (see the README)"
    report = {"name": name, "kind": kind}

    # ---- image
    image = args.image or out / f"{name}_Reference.png"
    legacy = out / f"{name}-Textured.obj"            # garments made before 2026-11-23 with Hunyuan3D-2 (retired)
    mesh = args.mesh or (legacy if legacy.exists() and redo > STAGES.index("mesh") else out / f"{name}-T2-solid.obj")
    texture = args.texture or (args.mesh.parent / "material_0.png" if args.mesh else out / "material_0.png")
    image, mesh, texture = Path(image).resolve(), Path(mesh).resolve(), Path(texture).resolve()     # the editor has another working folder
    if not args.mesh and wanted("image", image) and not args.image:
        assert args.describe, "give --describe, --image or --mesh"
        print("image: asking Codex for the reference image")
        run([PY, PREP / "reference_image.py", kind, args.describe, image], log)
    # ---- mesh
    if not args.mesh and wanted("mesh", mesh):
        print("mesh: local TRELLIS.2 image-to-3D with baked texture (GPU, editor closed)")
        run([PY, HERE / "generate_garment_mesh_trellis2.py", name, image, out], log)
    if last < STAGES.index("fit"):
        return
    # ---- fit
    source = SOURCE
    under = []
    if kind == "top":
        if args.over:
            # worn over another generated garment: its fitted standing shape is the layer underneath
            source = out / "SourceWithUnder"
            source.mkdir(exist_ok=True)
            for item in ("standing_body.bin", "standing_face.bin", "joints_local.json"):
                shutil.copyfile(SOURCE / item, source / item)
            below = ROOT / "Saved/ClothingFit/Generated" / args.over / "Prepared/standing_garment.bin"
            assert below.exists(), f"make {args.over} first"
            shutil.copyfile(below, source / "standing_under.bin")
            under = ["under"]
        else:
            under = ["bottom"]
    elif kind == "cloak":
        # worn over trousers and (optionally) a generated top (--over <TopName>)
        source = out / "SourceWithUnder"
        source.mkdir(exist_ok=True)
        for item in ("standing_body.bin", "standing_face.bin", "standing_bottom.bin", "joints_local.json"):
            if (SOURCE / item).exists():
                shutil.copyfile(SOURCE / item, source / item)
        under = ["bottom"] if (source / "standing_bottom.bin").exists() else []
        if args.over:
            below = ROOT / "Saved/ClothingFit/Generated" / args.over / "Prepared/standing_garment.bin"
            assert below.exists(), f"make {args.over} first"
            shutil.copyfile(below, source / "standing_under.bin")
            under.append("under")
    prepared = out / "Prepared"
    fbx = out / f"{name}_Fit.fbx"
    if wanted("fit", fbx):
        print("fit: reading the mesh")
        run([blender(), "-b", "--python", PREP / "blender_io.py", "--", "dump", mesh, "", out / "Raw.npz", TRIANGLES], log)
        print("fit: registering on the source body")
        run([PY, HERE / "register_garment.py", out / "Raw.npz", source, kind, out / "Registered.npz"], log)
        print("fit: fit preparation")
        cmd = [PY, HERE / "prepare_generated_garment.py", out / "Registered.npz", source, prepared]
        for tag in under or ["none"]:
            cmd += ["--under", tag]
        if kind == "cloak":
            cmd += ["--arms", "off"]
        run(cmd, log)
        run([PY, PREP / "preview.py", prepared / "Prepared.npz", source, out / "Prepared_preview.png", f"{name} prepared"]
            + ([] if under == ["bottom"] else ["--no-under"]), log)
        run([blender(), "-b", "--python", PREP / "blender_io.py", "--", "build", prepared, fbx, out / f"{name}_Fit.blend", name], log)
    fit = json.loads((prepared / "PrepareReport.json").read_text())
    report["fit"] = {k: fit[k] for k in ("standing", "self_crossing_pairs_before_after", "edge_length_change_pct_p1_p5_p50_p95_p99",
                                         "torn_triangles_dropped", "quality", "triangles", "arm_room") if k in fit}
    print("fit:", json.dumps(report["fit"]))
    assert fit["standing"]["triangles_crossing_skin"] == 0 and fit["standing"]["triangles_crossing_layer_underneath"] == 0, \
        "the prepared garment still crosses the source body; not importing it"
    if not args.allow_defects and "quality" in fit and not fit["quality"]["passed"]:
        raise SystemExit("fit defect check failed; not importing it: " + "; ".join(fit["quality"]["defects"]))
    if last < STAGES.index("unreal"):
        return
    # ---- unreal
    package = f"{PACKAGE}/{name}"
    item = f"{package}/WI_{name}"
    done = out / "import_progress.json"
    if wanted("unreal", done):
        print("unreal: importing and building the Wardrobe Item")
        if done.exists():
            done.unlink()
        params = {"fbx": str(fbx).replace("\\", "/"), "package": package, "name": name, "material": f"{package}/M_{name}",
                  "texture": str(texture).replace("\\", "/"), "source_body": SOURCE_BODY_ASSET, "size_name": "Barnaby",
                  "roughness": 0.85, "progress": str(done).replace("\\", "/")}
        # Wire TRELLIS.2's baked roughness map when it has genuine non-degenerate cloth variation (never metallic)
        rough_candidates = sorted(texture.parent.glob(f"T_{name}_T2_*_Roughness.png"))
        if rough_candidates:
            from PIL import Image
            import numpy as np
            ra = np.asarray(Image.open(rough_candidates[0]), float) / 255.0
            p1, p50, p99 = np.percentile(ra, [1, 50, 99])
            if 0.55 <= p50 <= 0.95 and (p99 - p1) > 0.02:
                params["roughness_texture"] = str(rough_candidates[0].resolve()).replace("\\", "/")
        if (out / "BodyHiddenFaceMap.png").exists():
            params["hidden_face_map"] = str((out / "BodyHiddenFaceMap.png").resolve()).replace("\\", "/")
        (out / "import_params.json").write_text(json.dumps(params, indent=1))
        value = editor_python(PREP / "editor/import_garment.py", params, f"garment-fit: import of generated garment {name} (new assets under {package} only)")
        print("unreal:", str(value)[:400])
    report["wardrobe_item"] = item
    if last < STAGES.index("test"):
        return
    # ---- test
    lineup = out / "Lineup"
    roster = json.loads((PREP / "roster.json").read_text())
    wear = {SLOT[kind]: item}
    surfaces = {name.lower(): f"/{name}/"}
    below = "none"
    clear_slots = [] if kind == "cloak" else ["Outfits"]
    if kind == "top":
        if args.over:
            wear[SLOT["bottom"]] = f"{PACKAGE}/{args.over}/WI_{args.over}"
            surfaces["under"] = f"/{args.over}/"
        else:
            wear[SLOT["bottom"]] = args.wear_with or TROUSERS
            surfaces["under"] = "OA_TravelTrousers" if not args.wear_with else args.wear_with.rsplit("/", 1)[0].rsplit("/", 1)[1]
        below = "under"
    elif kind == "cloak":
        wear[SLOT["bottom"]] = args.wear_with or TROUSERS
        if args.over:
            wear[SLOT["top"]] = f"{PACKAGE}/{args.over}/WI_{args.over}"
            surfaces["under"] = f"/{args.over}/"
            below = "under"
        else:
            surfaces["under"] = "OA_TravelTrousers" if not args.wear_with else args.wear_with.rsplit("/", 1)[0].rsplit("/", 1)[1]
            below = "under"
    elif args.wear_with:
        wear[SLOT["top"]] = args.wear_with
    config = {"out": str(lineup).replace("\\", "/"), "roster": roster, "wear": wear, "clear_slots": clear_slots, "surfaces": surfaces,
              "audit": [[name.lower(), below]] + ([["under", "none"]] if args.over and kind != "cloak" else []), "standing_views": ["front", "back", "left", "right"], "pose_views": ["back", "left"],
              "photo_frames": {"walk": [12], "reach": [12]}}
    if kind in ("bottom", "cloak") or args.over:
        config.update(camera_distance=220 if kind == "cloak" else 215, aim_height=96 if kind == "cloak" else 92)        # whole figure in the pictures
    (out / "lineup.json").write_text(json.dumps(config, indent=1))
    print(f"test: {len(roster) if not args.bodies else len(args.bodies)} bodies, 51 poses each")
    cmd = [PY, PREP / "run_lineup.py", out / "lineup.json"] + (["--only"] + args.bodies if args.bodies else [])
    run(cmd, log)
    run([PY, PREP / "lineup_report.py", lineup, name.lower()], log)
    if args.over:
        run([PY, PREP / "lineup_report.py", lineup, "under"], log)       # the bottom worn underneath, from the same captures
    table = lineup / f"Lineup_{name.lower()}.md"
    report["table"] = str(table)
    (out / "Report.json").write_text(json.dumps(report, indent=1))
    print(table.read_text(encoding="utf-8"))
    if last < STAGES.index("mask"):
        return
    # ---- mask: which body triangles the garment hides in every captured pose of the source body
    mask_done = out / "mask_progress.json"
    if wanted("mask", mask_done):
        tag = name.lower()
        source_poses = lineup / SOURCE_LABEL
        if not (source_poses / f"reach_24_{tag}.bin").exists():
            print(f"mask: capturing the source body {SOURCE_LABEL}")
            run([PY, PREP / "run_lineup.py", out / "lineup.json", "--only", SOURCE_LABEL], log)
        print("mask: body hidden-face map")
        run([PY, PREP / "hidden_face_map.py", source_poses, tag, out, "--name", name, "--shrink", str(MASK_SHRINK)], log)
        run([PY, PREP / "emulate_hidden_faces.py", source_poses, tag, out / "BodyHiddenFaceMap.png"], log)
        if mask_done.exists():
            mask_done.unlink()
        params = {"package": package, "name": name, "mask_only": True, "progress": str(mask_done).replace("\\", "/"), "max_shrink": MASK_SHRINK,
                  "hidden_face_map": str((out / "BodyHiddenFaceMap.png").resolve()).replace("\\", "/")}
        value = editor_python(PREP / "editor/import_garment.py", params, f"garment-fit: body hidden-face map for {name} (saves T_{name}_BodyHiddenFaces and WI_{name} only)")
        print("mask:", str(value)[:400])
    mask = json.loads((out / "BodyHiddenFaceMap.json").read_text())
    emulated = json.loads((lineup / SOURCE_LABEL / f"HiddenFaceEmulation_{name.lower()}.json").read_text())
    report["body_hidden_face_map"] = {"png": str(out / "BodyHiddenFaceMap.png"), "removed_body_triangles": mask["engine_removed_triangles"],
                                      "emulated_non_arm_crossings_before_after": [emulated["non_arm_total_before"], emulated["non_arm_total_after"]]}
    (out / "Report.json").write_text(json.dumps(report, indent=1))
    print("mask:", json.dumps(report["body_hidden_face_map"]))


if __name__ == "__main__":
    main()

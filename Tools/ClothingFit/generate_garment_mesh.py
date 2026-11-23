"""Reference image -> textured 3D garment mesh, with the local generator the Market Jerkin was made with.

  python generate_garment_mesh.py <Name> <reference.png> <output folder> [--vram-share 0] [--steps 100] [--resolution 512]

Same steps Codex ran for the Market Jerkin (local Hunyuan3D-2 + Hunyuan3D-Paint 2.0, no cloud, no credits):
  1. geometry from the image                       -> <Name>-HQ.glb (+ <Name>-HQ_input.png, background removed)
  2. reduce to 125,000 triangles for texturing     -> <Name>-PaintInput.ply
  3. texture from the same image                   -> <Name>-Textured.glb + T_<Name>_BaseColor.png
  4. convert                                       -> <Name>-Textured.obj + material_0.png
Every step is skipped when its output exists. The GPU steps are capped to a share of the video
memory so they fail on their own instead of starving the Unreal editor (it crashed that way once).
Post a NOTICE in Saved/PIE_QUEUE.md before running this next to the shared editor.
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import time
from pathlib import Path

LOCAL3D = Path(os.environ.get("LOCAL3D_HOME", r"C:\Users\zachc\tools\Local3D"))
HERE = Path(__file__).resolve().parent

CAPPED = """import os, sys, runpy
import torch
torch.cuda.set_per_process_memory_fraction(float(sys.argv[1]))
sys.argv = sys.argv[2:]
sys.path.insert(0, os.path.dirname(os.path.abspath(sys.argv[0])))
runpy.run_path(sys.argv[0], run_name="__main__")
"""

TO_OBJ = """import sys
from pathlib import Path
import trimesh
from trimesh.exchange.obj import export_obj
src, dst = Path(sys.argv[1]), Path(sys.argv[2])
model = trimesh.load(src, force="mesh", process=False)
assert model.visual.kind == "texture"
data, files = export_obj(model, include_normals=True, include_texture=True, return_texture=True, mtl_name=dst.stem + ".mtl")
dst.write_text(data, encoding="utf-8")
for name, content in files.items():
    (dst.parent / Path(name).name).write_bytes(content.encode() if isinstance(content, str) else content)
print(len(model.vertices), len(model.faces), list(files))
"""


def blender():
    found = os.environ.get("BLENDER_EXE")
    if found and Path(found).exists():
        return found
    hits = glob.glob(os.path.expandvars(r"%TEMP%\codex-blender-*\blender-*\blender.exe")) + glob.glob(r"C:\Program Files\Blender Foundation\*\blender.exe")
    if not hits:
        raise SystemExit("Blender not found; set BLENDER_EXE")
    return sorted(hits)[-1]


def vram_share(requested):
    """Share of the video memory a GPU step may use: what is free now minus a reserve for the editor."""
    stop = Path(__file__).resolve().parents[2] / "Saved/ClothingFit/STOP_GPU"
    if stop.exists():
        raise SystemExit(f"GPU work stopped by {stop}")
    if requested > 0:
        return requested
    out = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"], text=True)
    used, total = (float(v) for v in out.strip().splitlines()[0].split(","))
    return round(max(.2, (total - used - 1800) / total), 3)


def run(cmd, log, env=None):
    started = time.time()
    with open(log, "a", encoding="utf-8", errors="replace") as stream:
        stream.write(f"\n== {time.strftime('%H:%M:%S')} {' '.join(str(c) for c in cmd)}\n")
        stream.flush()
        code = subprocess.call([str(c) for c in cmd], stdout=stream, stderr=subprocess.STDOUT, env=env)
    if code:
        raise SystemExit(f"step failed (exit {code}); see {log}")
    return round(time.time() - started, 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name"); parser.add_argument("image", type=Path); parser.add_argument("output", type=Path)
    parser.add_argument("--vram-share", type=float, default=0., help="0 = what is free now minus a reserve for the editor")
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--resolution", type=int, default=512)
    parser.add_argument("--seed", type=int, default=1234)
    args = parser.parse_args()
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    py = LOCAL3D / ".venv/Scripts/python.exe"
    assert py.exists(), f"local generator not found at {LOCAL3D}"
    env = dict(os.environ, HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", TOKENIZERS_PARALLELISM="false", PYTHONUTF8="1")
    capped = out / "_capped_run.py"; capped.write_text(CAPPED)
    to_obj = out / "_to_obj.py"; to_obj.write_text(TO_OBJ)
    log = out / "Generation.log"
    name = args.name
    hq, paint_in = out / f"{name}-HQ.glb", out / f"{name}-PaintInput.ply"
    textured, obj = out / f"{name}-Textured.glb", out / f"{name}-Textured.obj"
    times = {}
    if not hq.exists():
        times["geometry_s"] = run([py, "-u", capped, vram_share(args.vram_share), LOCAL3D / "generate_mesh.py", "--image", args.image.resolve(), "--output", hq,
                                   "--steps", args.steps, "--resolution", args.resolution, "--seed", args.seed], log, env)
    if not paint_in.exists():
        ply = out / f"{name}-HQ.ply"
        if not ply.exists():
            run([py, "-u", "-c", "import trimesh,sys; m=trimesh.load(sys.argv[1],force='mesh',process=False); print(len(m.faces)); m.export(sys.argv[2])", hq, ply], log, env)
        times["reduce_s"] = run([blender(), "-b", "--python-exit-code", "2", "--python", HERE / "garmentprep/blender_reduce.py", "--", ply, paint_in, 125000], log)
    if not textured.exists():
        times["texture_s"] = run([py, "-u", capped, vram_share(args.vram_share), LOCAL3D / "texture_mesh.py", "--mesh", paint_in, "--image", out / f"{name}-HQ_input.png",
                                  "--output", textured, "--name", name], log, env)
    if not obj.exists():
        run([py, "-u", to_obj, textured, obj], log, env)
    report = dict(name=name, image=str(args.image), mesh=str(obj), texture=str(out / "material_0.png"), seconds=times,
                  generator="local Hunyuan3D-2 (geometry) + Hunyuan3D-Paint 2.0 (texture)", steps=args.steps, resolution=args.resolution, seed=args.seed)
    (out / "GenerationReport.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()

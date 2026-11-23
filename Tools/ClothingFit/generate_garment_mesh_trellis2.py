"""Reference image -> textured 3D garment mesh with Microsoft TRELLIS.2 (MIT), run headless through ComfyUI's
built-in TRELLIS.2 nodes (no CUDA toolkit, no nvdiffrast, no flash-attn).

  python generate_garment_mesh_trellis2.py <Name> <reference.png> <output folder>
         [--resolution 1536] [--faces 125000] [--texture 4096] [--remesh solid|udf|sdf|none ...] [--reserve-vram 2]

Writes to <output folder>:
  <Name>-T2-Raw.glb                     shape as decoded (no texture), for inspection
  <Name>-T2-<remesh>.glb                remeshed, decimated, unwrapped, base colour + metallic + roughness baked
  <Name>-T2-<remesh>.obj + material_0.png   the same as OBJ + base colour PNG for the fit stage (first --remesh only)
  T_<Name>_T2_<remesh>_{BaseColor,Metallic,Roughness}.png
  GenerationReport.json
Model files (Comfy-Org/TRELLIS.2 bf16, DINOv3 ViT-L, BiRefNet) live in C:\\Users\\zachc\\tools\\ComfyUI\\models.
The ComfyUI server is started for the run and stopped afterwards. Post a NOTICE in Saved/PIE_QUEUE.md first:
this is an outside-editor GPU job. Settings follow ComfyUI's TRELLIS.2 template (CFG override and rescale match
the original pipeline); background removal is BiRefNet (MIT), never RMBG-2.0 (non-commercial).

Memory: on this PC every GB of video memory is also charged to Windows' commit limit. A 1536 run with the bf16
model used 17-19 GB of commit (measured 2026-11-23), which does not fit next to the open Unreal editor (~20 GB
commit, 8 GB VRAM). The script refuses to start under --min-free-commit (default 21 GB) and stops the ComfyUI
server by itself if free commit falls under 2 GB during the run. Run it while the editor is closed.
"""
import argparse
import ctypes
import json
import threading
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

COMFY = Path(os.environ.get("COMFYUI_HOME", r"C:\Users\zachc\tools\ComfyUI"))
PORT = 8190
URL = f"http://127.0.0.1:{PORT}"
STOP = Path(__file__).resolve().parents[2] / "Saved/ClothingFit/STOP_GPU"
CHANNELS = {"basecolor": "BaseColor", "metallic": "Metallic", "roughness": "Roughness"}
UNETS = {"bf16": "trellis_2_bf16.safetensors", "int8": "trellis_2_int8_convrot.safetensors"}


class _Mem(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def free_commit_gb():
    m = _Mem(); m.dwLength = ctypes.sizeof(_Mem)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPageFile / 2 ** 30


def guard(proc, floor, state):
    """Stop the server when free commit falls under `floor` GB (the editor and other programs need it)."""
    while proc.poll() is None and not state.get("stop"):
        free = free_commit_gb()
        state["lowest"] = min(state.get("lowest", 1e9), free)
        if free < floor:
            proc.kill()
            state["killed"] = round(free, 2)
            return
        time.sleep(.25)


def api(path, payload=None, timeout=30):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(URL + path, data=data, headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


def up():
    try:
        api("/system_stats", timeout=3)
        return True
    except Exception:
        return False


def start_server(log, reserve, extra=()):
    env = dict(os.environ, PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True", PYTHONUTF8="1", HF_HUB_OFFLINE="1")
    out = COMFY / "output"
    stream = open(log, "a", encoding="utf-8", errors="replace")
    proc = subprocess.Popen([str(COMFY / ".venv/Scripts/python.exe"), "main.py", "--listen", "127.0.0.1", "--port", str(PORT),
                             "--disable-auto-launch", "--dont-print-server", "--reserve-vram", str(reserve), "--disable-pinned-memory",
                             "--output-directory", str(out), *extra], cwd=COMFY, stdout=stream, stderr=subprocess.STDOUT, env=env)
    for _ in range(240):
        if proc.poll() is not None:
            raise SystemExit(f"ComfyUI exited (code {proc.returncode}); see {log}")
        if up():
            return proc
        time.sleep(1)
    proc.kill()
    raise SystemExit(f"ComfyUI did not come up; see {log}")


def remesh_inputs(mode):
    if mode == "solid":
        return {"sign_mode": "solid", "sign_mode.fill": 20.0, "sign_mode.qef": False}
    if mode == "sdf":
        return {"sign_mode": "sdf", "sign_mode.qef": True, "sign_mode.manifold": False}
    return {"sign_mode": "udf", "sign_mode.qef": False, "sign_mode.drop_inverted_components": False, "sign_mode.drop_enclosed_components": False}


def prompt(image_name, name, resolution, faces, texture, remesh, seed, unet="trellis_2_bf16.safetensors"):
    g = {
        "40": ("UNETLoader", dict(unet_name=unet, weight_dtype="default")),
        "15": ("CLIPVisionLoader", dict(clip_name="dino_v3_vit_l.safetensors")),
        "117": ("VAELoader", dict(vae_name="trellis_2_shape_vae_bf16.safetensors")),
        "118": ("VAELoader", dict(vae_name="trellis_2_texture_vae_bf16.safetensors")),
        "193": ("LoadBackgroundRemovalModel", dict(bg_removal_name="birefnet.safetensors")),
        "122": ("LoadImage", dict(image=image_name)),
        "192": ("RemoveBackground", dict(bg_removal_model=["193", 0], image=["122", 0])),
        "312": ("ImageCropToMask", dict(images=["122", 0], masks=["192", 0], width=1024, height=1024, pad_factor=1.0, grow_mask=0, background="#000000")),
        "299": ("Trellis2Conditioning", dict(clip_vision_model=["15", 0], image=["312", 0])),
        "199": ("CFGOverride", dict(model=["40", 0], cfg=1.0, start_percent=0.667, end_percent=1.0)),
        "125": ("RescaleCFG", dict(model=["199", 0], multiplier=0.7)),
        "108": ("ModelSamplingSD3", dict(model=["125", 0], shift=5.0)),
        "279": ("CFGOverride", dict(model=["40", 0], cfg=1.0, start_percent=0.769, end_percent=1.0)),
        "126": ("RescaleCFG", dict(model=["279", 0], multiplier=0.5)),
        "87": ("EmptyTrellis2LatentStructure", dict(batch_size=1)),
        "3": ("KSampler", dict(model=["108", 0], seed=seed + 14, steps=12, cfg=7.5, sampler_name="euler", scheduler="normal",
                               positive=["299", 0], negative=["299", 1], latent_image=["87", 0], denoise=1.0)),
        "119": ("VaeDecodeStructureTrellis2", dict(samples=["3", 0], vae=["117", 0], resolution="32")),
        "91": ("Trellis2ShapeStage", dict(positive=["299", 0], negative=["299", 1], voxel=["119", 0])),
        "18": ("KSampler", dict(model=["126", 0], seed=seed, steps=20, cfg=7.5, sampler_name="euler", scheduler="normal",
                                positive=["91", 0], negative=["91", 1], latent_image=["91", 2], denoise=1.0)),
        "94": ("Trellis2UpsampleStage", dict(positive=["91", 0], negative=["91", 1], shape_latent=["18", 0], vae=["117", 0], target_resolution=resolution)),
        "23": ("KSampler", dict(model=["126", 0], seed=seed, steps=12, cfg=7.5, sampler_name="euler", scheduler="simple",
                                positive=["94", 0], negative=["94", 1], latent_image=["94", 2], denoise=1.0)),
        "92": ("VaeDecodeShapeTrellis", dict(samples=["23", 0], vae=["117", 0])),
        "98": ("Trellis2TextureStage", dict(positive=["94", 0], negative=["94", 1], shape_latent=["23", 0])),
        "12": ("KSampler", dict(model=["40", 0], seed=seed + 1, steps=12, cfg=1.0, sampler_name="euler", scheduler="normal",
                                positive=["98", 0], negative=["98", 1], latent_image=["98", 2], denoise=1.0)),
        "93": ("VaeDecodeTextureTrellis", dict(samples=["12", 0], vae=["118", 0], shape_subdivides=["92", 1])),
        "400": ("SaveImage", dict(images=["312", 0], filename_prefix=f"trellis2/{name}_input")),
        "401": ("SaveGLB", dict(mesh=["92", 0], filename_prefix=f"trellis2/{name}_raw")),
        "241": ("RemeshMesh", dict(mesh=["92", 0], resolution=768, band=1.0, project_back=0.0, fix_poles=False, smooth_iters=20,
                                   drop_small_components=0.01, precluster_max_verts=20000000, **remesh_inputs(remesh))),
        "186": ("DecimateMesh", dict(mesh=["241", 0], target_face_count=faces, placement_mode="midpoint")),
        "238": ("MeshSmoothNormals", dict(mesh=["186", 0], crease_angle=180.0)),
        "196": ("UnwrapMesh", dict(mesh=["238", 0], segmenter="pec", resolution=texture, padding=1, weld_distance=0.0002)),
        "147": ("BakeTextureFromVoxel", dict(mesh=["196", 0], voxel_colors=["93", 0], reference_mesh=["92", 0], texture_size=texture)),
        "210": ("ApplyTextureToMesh", dict(mesh=["196", 0], base_color=["147", 0], metallic=["147", 1], roughness=["147", 2])),
        "402": ("SaveGLB", dict(mesh=["210", 0], filename_prefix=f"trellis2/{name}_{remesh}")),
        "403": ("SaveImage", dict(images=["147", 0], filename_prefix=f"trellis2/{name}_{remesh}_basecolor")),
        "404": ("SaveImage", dict(images=["147", 1], filename_prefix=f"trellis2/{name}_{remesh}_metallic")),
        "405": ("SaveImage", dict(images=["147", 2], filename_prefix=f"trellis2/{name}_{remesh}_roughness")),
    }
    return {k: {"class_type": c, "inputs": i} for k, (c, i) in g.items()}


def run_prompt(graph, log):
    client = uuid.uuid4().hex
    started = time.time()
    try:
        pid = api("/prompt", {"prompt": graph, "client_id": client})["prompt_id"]
    except urllib.error.HTTPError as e:
        raise SystemExit(f"ComfyUI refused the workflow: {e.read().decode(errors='replace')[:3000]}")
    while True:
        if STOP.exists():
            api("/interrupt", {})
            raise SystemExit(f"GPU work stopped by {STOP}")
        hist = api(f"/history/{pid}")
        if pid in hist:
            entry = hist[pid]
            status = entry.get("status", {})
            if status.get("status_str") == "error" or not status.get("completed", False):
                msgs = [m for m in status.get("messages", []) if m[0] in ("execution_error", "execution_interrupted")]
                raise SystemExit(f"workflow failed: {json.dumps(msgs)[:3000]}; see {log}")
            return entry["outputs"], round(time.time() - started, 1)
        time.sleep(2)


def files_of(outputs):
    found = []
    for node in outputs.values():
        for key in ("images", "3d", "meshes", "files", "result"):
            for item in node.get(key, []) or []:
                if isinstance(item, dict) and "filename" in item:
                    found.append(COMFY / "output" / item.get("subfolder", "") / item["filename"])
    return found


TO_OBJ = """import sys
from pathlib import Path
import trimesh
from trimesh.exchange.obj import export_obj
src, dst = Path(sys.argv[1]), Path(sys.argv[2])
model = trimesh.load(src, force="mesh", process=False)
assert model.visual.kind == "texture", model.visual.kind
data, files = export_obj(model, include_normals=True, include_texture=True, return_texture=True, mtl_name=dst.stem + ".mtl")
dst.write_text(data, encoding="utf-8")
for name, content in files.items():
    (dst.parent / Path(name).name).write_bytes(content.encode() if isinstance(content, str) else content)
print(len(model.vertices), len(model.faces), list(files))
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name"); parser.add_argument("image", type=Path); parser.add_argument("output", type=Path)
    parser.add_argument("--resolution", type=int, default=1536, help="shape resolution of the cascade (1024..2048)")
    parser.add_argument("--faces", type=int, default=125000, help="triangles after decimation (the Hunyuan path paints 125,000)")
    parser.add_argument("--texture", type=int, default=4096)
    parser.add_argument("--remesh", nargs="+", default=["solid"], choices=["solid", "udf", "sdf"])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model", choices=["bf16", "int8"], default="bf16", help="int8 halves the model's memory (5.3 GB instead of 10.3 GB)")
    parser.add_argument("--reserve-vram", type=float, default=2.0, help="GB of video memory ComfyUI leaves for the editor")
    parser.add_argument("--keep-server", action="store_true")
    parser.add_argument("--min-free-commit", type=float, default=21.0, help="GB of free Windows commit needed to start")
    parser.add_argument("--comfy-args", default="", help="extra ComfyUI server flags, e.g. \"--disable-dynamic-vram\"")
    args = parser.parse_args()
    if STOP.exists():
        raise SystemExit(f"GPU work stopped by {STOP}")
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    log = out / "Generation_T2.log"
    name = args.name
    image_name = f"{name}_reference.png"
    shutil.copyfile(args.image, COMFY / "input" / image_name)
    if not up() and free_commit_gb() < args.min_free_commit:
        raise SystemExit(f"only {free_commit_gb():.1f} GB of Windows commit is free; TRELLIS.2 needs about {args.min_free_commit:.0f} GB "
                         "(close the Unreal editor for the run, or ask the orchestrator for an editor-closed window)")
    proc = None if up() else start_server(log, args.reserve_vram, args.comfy_args.split())
    state = {}
    if proc is not None:
        threading.Thread(target=guard, args=(proc, 2.0, state), daemon=True).start()
    report = dict(name=name, image=str(args.image), model=UNETS[args.model], generator="Microsoft TRELLIS.2 4B (Comfy-Org/TRELLIS.2, MIT) via ComfyUI " + (COMFY / "comfyui_version.py").read_text().split('"')[1],
                  resolution=args.resolution, faces=args.faces, texture=args.texture, seed=args.seed, variants={}, seconds={})
    try:
        for i, mode in enumerate(args.remesh):
            outputs, seconds = run_prompt(prompt(image_name, name, args.resolution, args.faces, args.texture, mode, args.seed, UNETS[args.model]), log)
            report["seconds"][mode] = seconds
            got = {}
            for f in files_of(outputs):
                stem = f.name
                if stem.startswith(f"{name}_raw"):
                    target = out / f"{name}-T2-Raw.glb"
                elif stem.startswith(f"{name}_input"):
                    target = out / f"{name}-T2_input.png"
                elif any(stem.startswith(f"{name}_{mode}_{c}") for c in CHANNELS):
                    channel = next(c for c in CHANNELS if stem.startswith(f"{name}_{mode}_{c}"))
                    target = out / f"T_{name}_T2_{mode}_{CHANNELS[channel]}.png"
                elif stem.startswith(f"{name}_{mode}_") and stem.endswith(".glb"):
                    target = out / f"{name}-T2-{mode}.glb"
                else:
                    continue
                shutil.copyfile(f, target)
                got[target.name] = str(f)
            report["variants"][mode] = got
            print(mode, seconds, "s", sorted(got), flush=True)
            if i == 0:
                to_obj = out / "_to_obj.py"; to_obj.write_text(TO_OBJ)
                glb = out / f"{name}-T2-{mode}.glb"
                obj = out / f"{name}-T2-{mode}.obj"
                done = subprocess.run([sys.executable, str(to_obj), str(glb), str(obj)], capture_output=True, text=True)
                if done.returncode:
                    raise SystemExit(f"OBJ conversion failed: {done.stderr[-2000:]}")
                report.update(mesh=str(obj), texture=str(out / "material_0.png"), obj_info=done.stdout.strip())
    except SystemExit:
        if state.get("killed"):
            raise SystemExit(f"stopped: free Windows commit fell to {state['killed']} GB; run TRELLIS.2 with the editor closed")
        raise
    finally:
        state["stop"] = True
        report["lowest_free_commit_gb"] = round(state.get("lowest", 0), 2) if state else None
        if proc is not None and not args.keep_server:
            proc.terminate()
            try:
                proc.wait(30)
            except subprocess.TimeoutExpired:
                proc.kill()
        (out / "GenerationReport_T2.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()

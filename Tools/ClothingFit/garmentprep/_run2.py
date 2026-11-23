"""Experiment driver: prepare the decimated jerkin dump against Barnaby's captured standing body."""
import sys, time, pickle, os, json
from pathlib import Path
HERE = Path(r"C:/Users/zachc/Documents/Unreal Projects/reflections/Tools/ClothingFit/garmentprep")
ST = Path(r"C:/Users/zachc/Documents/Unreal Projects/reflections/Saved/ClothingFit/DirectImage3D/MarketJerkin/MeshRetargetPilot/ContactStudy/tools")
SCRATCH = Path(r"C:/Users/zachc/AppData/Local/Temp/claude/79559c54b34378d8/a4e4de80-1212-4b4c-a784-dd2da0cdd399/scratchpad")
sys.path.insert(0, str(ST)); sys.path.insert(0, str(HERE)); os.chdir(ST)
import numpy as np
from check import *            # study tools: load, measure, clearance, stretch, self_pairs
from render import render, scene, strip, VIEWS, LEATHER
import prep, field, meshops, contact

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
params = eval(sys.argv[2]) if len(sys.argv) > 2 else {}
src = PILOT / "AfterPreserved"; fr = load(src, "standing"); skin, sf = fr["skin"], fr["sf"]
dump = np.load(SCRATCH / ("refine/" + params.pop("source", "jerkin_dump") + ".npz")); P, F, UV = dump["P"], dump["F"], dump["UV"]
cache = HERE / "_field_barnaby.pkl"
if cache.exists():
    body, obst = pickle.load(open(cache, "rb"))
else:
    t = time.time(); body = field.SignedField(skin, sf, P.min(0) - 8, P.max(0) + [8, 8, 14]); obst = prep.add_layer(body, fr["bottom"], fr["tf"], .15)
    pickle.dump((body, obst), open(cache, "wb")); print("field built", round(time.time() - t, 1))
J = json.load(open(SCRATCH / "barnaby_joints.json"))
joints = {k: np.array(v) * [100, -100, 100] for k, v in J["joints_m"].items()}; bones = prep.bone_segments(joints, J["parents"])
t = time.time()
arms = trunk = None
if params.pop("corridor", True):
    import corridor
    arms = corridor.ArmCorridor(skin, joints, hang_deg=params.pop("hang", (10., 18., 26.)))
    trunk = prep.bone_segments({k: v for k, v in joints.items() if k in ("pelvis", "spine_01", "spine_02", "spine_03", "spine_04", "spine_05", "neck_01")}, J["parents"])
res = prep.prepare(P, F, UV, obst, bones, (skin, sf), [(fr["bottom"], fr["tf"])], params, arms=arms, trunk_bones=trunk)
print("prepare", round(time.time() - t, 1), "s")
P0, F1, P1 = res["P0"], res["F"], res["P"]
np.savez(OUT / "result.npz", P0=P0, F=F1, UV=res["UV"], P=P1, clearance=res["clearance"], planned=res["planned"])
meshops.write_surface(OUT / "standing_jerkin.bin", P1, F1)
json.dump({k: v for k, v in res["report"].items() if k != "history"}, open(OUT / "report.json", "w"), indent=1)
fr2 = dict(fr); fr2["cloth"] = P1; fr2["cf"] = F1; m = measure(fr2); cl = clearance(P1, skin, sf); st = stretch(P0, P1, F1); d = np.linalg.norm(P1 - P0, axis=1)
print("standing tris", len(m["garment_tris"]), "area", round(m["area"], 2), "depth", round(m["depth_mm"], 2), "trousers", len(m["trouser_tris"]))
print("clearance cm min/p1/p5/p50", np.percentile(cl, [0, 1, 5, 50]).round(2), "verts<0.5:", int((cl < .5).sum()))
print("stretch % p0/p1/p5/p50/p95/p99/p100", np.percentile(st, [0, 1, 5, 50, 95, 99, 100]).round(1))
print("displacement cm p50/p95/max", np.percentile(d, [50, 95, 100]).round(2), "hem z min before/after", P0[:, 2].min().round(2), P1[:, 2].min().round(2))
W0, Fw, inv = meshops.weld(P0, F1); W1 = np.zeros_like(W0); W1[inv] = P1
print("self pairs (welded) before", contact.self_crossing_pairs(W0, Fw), "after", contact.self_crossing_pairs(W1, Fw))
col = np.tile(np.array(LEATHER, float), (len(F1), 1)); col[m["garment_tris"]] = (255, 0, 200)
ctr = P0.mean(0) + [0, 0, 6]
ims = [render(scene(fr2, tri_color=col), az, el, ctr, px=.11) for az, el, _ in VIEWS]
strip(ims, [v[2] for v in VIEWS], f"{OUT.name}: {len(m['garment_tris'])} garment triangles cross skin (magenta)").save(OUT / "render.png")

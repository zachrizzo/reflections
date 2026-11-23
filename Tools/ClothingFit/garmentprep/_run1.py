import sys, time, pickle, os, json
from pathlib import Path
HERE = Path(r"C:/Users/zachc/Documents/Unreal Projects/reflections/Tools/ClothingFit/garmentprep")
ST = Path(r"C:/Users/zachc/Documents/Unreal Projects/reflections/Saved/ClothingFit/DirectImage3D/MarketJerkin/MeshRetargetPilot/ContactStudy/tools")
SCRATCH = Path(r"C:/Users/zachc/AppData/Local/Temp/claude/79559c54b34378d8/a4e4de80-1212-4b4c-a784-dd2da0cdd399/scratchpad")
sys.path.insert(0, str(ST)); sys.path.insert(0, str(HERE)); os.chdir(ST)
import numpy as np
from check import *            # study tools: load, measure, clearance, stretch, self_pairs
from render import render, scene, strip, VIEWS, LEATHER
import prep, field, meshops

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
src = PILOT / "AfterPreserved"; fr = load(src, "standing"); c0, cf = fr["cloth"], fr["cf"]; skin, sf = fr["skin"], fr["sf"]
cache = HERE / "_field_barnaby.pkl"
if cache.exists():
    body, obst = pickle.load(open(cache, "rb"))
else:
    t = time.time(); body = field.SignedField(skin, sf, c0.min(0) - 8, c0.max(0) + [8, 8, 14]); obst = prep.add_layer(body, fr["bottom"], fr["tf"], .15)
    pickle.dump((body, obst), open(cache, "wb")); print("field built", round(time.time() - t, 1))
params = eval(sys.argv[2]) if len(sys.argv) > 2 else {}
J = json.load(open(SCRATCH / "barnaby_joints.json"))
joints = {k: np.array(v) * [100, -100, 100] for k, v in J["joints_m"].items()}; bones = prep.bone_segments(joints, J["parents"])
t = time.time(); g, x, info = prep.prepare(c0, cf, obst, bones, params); print("prepare", round(time.time() - t, 1), "s")
c1 = g.expand(x); meshops.write_surface(OUT / "standing_jerkin.bin", c1, cf)
np.savez(OUT / "info.npz", x=x, hold=info["hold"], planned=info["planned"])
fr2 = dict(fr); fr2["cloth"] = c1; m = measure(fr2); cl = clearance(c1, skin, sf); st = stretch(c0, c1, cf); d = np.linalg.norm(c1 - c0, axis=1)
print("standing tris", len(m["garment_tris"]), "area", round(m["area"], 2), "depth", round(m["depth_mm"], 2), "trousers", len(m["trouser_tris"]))
print("clearance cm min/p1/p5/p50", np.percentile(cl, [0, 1, 5, 50]).round(2), "verts<0.5:", int((cl < .5).sum()))
print("stretch % p0/p1/p5/p50/p95/p99/p100", np.percentile(st, [0, 1, 5, 50, 95, 99, 100]).round(1))
print("displacement cm p50/p95/max", np.percentile(d, [50, 95, 100]).round(2), "hem z min before/after", c0[:, 2].min().round(2), c1[:, 2].min().round(2))
print("self pairs before", self_pairs(c0, cf), "after", self_pairs(c1, cf))
col = np.tile(np.array(LEATHER, float), (len(cf), 1)); col[m["garment_tris"]] = (255, 0, 200)
ctr = c0.mean(0) + [0, 0, 6]
ims = [render(scene(fr2, tri_color=col), az, el, ctr, px=.11) for az, el, _ in VIEWS]
strip(ims, [v[2] for v in VIEWS], f"{OUT.name}: {len(m['garment_tris'])} garment triangles cross skin (magenta)").save(OUT / "render.png")

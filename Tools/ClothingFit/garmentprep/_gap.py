"""Measured from the Unreal captures: free space between Barnaby's arm skin and torso skin, per pose and height."""
import sys, os, json
from pathlib import Path
ST = Path(r"C:/Users/zachc/Documents/Unreal Projects/reflections/Saved/ClothingFit/DirectImage3D/MarketJerkin/MeshRetargetPilot/ContactStudy/tools")
sys.path.insert(0, str(ST)); os.chdir(ST)
import numpy as np
from parts import *
from scipy.spatial import cKDTree
np.set_printoptions(linewidth=200, suppress=True)
SRC = PILOT / "AfterPreserved"
b0, bf = surface(SRC / "standing_body.bin"); arm_v = arm_mask(b0)
torso_v = ~arm_v & (b0[:, 2] > 96) & (b0[:, 2] < 150) & (np.abs(b0[:, 0]) > 8)
man = json.loads((SRC / "Manifest.json").read_text())
labels = ["standing"] + [f["label"] for cl in man["clips"].values() for f in cl["frames"]]
bands = [(100, 108), (108, 116), (116, 124), (124, 132), (132, 140)]
print("min arm-to-torso skin gap (cm) by standing height band of the torso point;  bands:", bands)
worst = np.full(len(b0), np.inf)
rows = {}
for l in labels:
    b1, _ = surface(SRC / f"{l}_body.bin")
    d, _ = cKDTree(b1[arm_v]).query(b1[torso_v])
    worst[torso_v] = np.minimum(worst[torso_v], d) if l.startswith("walk") else worst[torso_v]
    rows[l] = [round(float(d[(b0[torso_v][:, 2] >= lo) & (b0[torso_v][:, 2] < hi)].min()), 2) for lo, hi in bands]
for l in labels[::3]:
    print(f"{l:10s}", rows[l])
w = np.array([rows[l] for l in labels if l.startswith("walk")]); r = np.array([rows[l] for l in labels if l.startswith("reach")])
print("walk  min over 25 poses:", w.min(0), " median:", np.median(w, 0))
print("reach min over 25 poses:", r.min(0), " median:", np.median(r, 0))
json.dump(dict(bands=bands, rows=rows), open(r"C:/Users/zachc/AppData/Local/Temp/claude/79559c54b34378d8/a4e4de80-1212-4b4c-a784-dd2da0cdd399/scratchpad/arm_gap.json", "w"))

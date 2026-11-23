"""Where does emulated in-motion contact sit? (by garment region, for a saved emulation folder)"""
import sys, os, json
from pathlib import Path
HERE = Path(r"C:/Users/zachc/Documents/Unreal Projects/reflections/Tools/ClothingFit/garmentprep")
ST = Path(r"C:/Users/zachc/Documents/Unreal Projects/reflections/Saved/ClothingFit/DirectImage3D/MarketJerkin/MeshRetargetPilot/ContactStudy/tools")
sys.path.insert(0, str(ST)); sys.path.insert(0, str(HERE)); os.chdir(ST)
import numpy as np
from parts import *
from regions import regions, NAMES
SRC = PILOT / "AfterPreserved"
shape, folder = sys.argv[1], Path(sys.argv[2])
if shape == "baseline":
    c, cf = surface(SRC / "standing_jerkin.bin")
else:
    d = np.load(shape); c, cf = d["P0"], d["F"]      # regions are defined on the shape before preparation
reg = regions(c, cf)
b0, bf = surface(SRC / "standing_body.bin"); arm_v = arm_mask(b0)
W = Wrap(b0, bf, 2); bd = W.bind(c)
bound_arm = arm_v[bf[bd["f"]]].sum(1) >= 2
vreg = np.zeros(len(c), int)
for k in range(6):
    vreg[np.unique(cf[reg == k])] = k
print("garment vertices bound to arm skin, by region:", {NAMES[k]: (int((bound_arm & (vreg == k)).sum()), int((vreg == k).sum())) for k in range(6)})
man = json.loads((SRC / "Manifest.json").read_text())
labels = ["standing"] + [f["label"] for cl in man["clips"].values() for f in cl["frames"]]
print(f"{'pose':10s} " + " ".join(f"{n[:9]:>9s}" for n in NAMES) + "   | arm-skin contact by region")
for l in labels[::4]:
    z = np.load(folder / f"{l}.npz")
    o = np.bincount(reg[z["other"]], minlength=6); a = np.bincount(reg[z["arm"]], minlength=6)
    print(f"{l:10s} " + " ".join(f"{v:9d}" for v in o) + "   | " + " ".join(f"{v:5d}" for v in a))

import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from meshops import read_surface
root = Path(sys.argv[1]); tag = sys.argv[2]
for sub in sorted(p for p in root.iterdir() if (p / "Manifest.json").exists()):
    m = json.loads((sub / "Manifest.json").read_text())
    P, F = read_surface(sub / f"standing_{tag}.bin")
    B, _ = read_surface(sub / "standing_body.bin")
    r = m["rest"]
    sh = r["upperarm_l"][2]; pel = r["pelvis"][2]; neck = r["neck_01"][2]
    print(f"{sub.name:20s} refreshed {str(m.get('body_state_refreshed')):5s} neck overlap {m.get('neck_overlap_cm_before_after')}  garment z {P[:,2].min():6.1f}..{P[:,2].max():6.1f}  pelvis {pel:6.1f} shoulder {sh:6.1f} neck {neck:6.1f} body top {B[:,2].max():6.1f}  top-shoulder {P[:,2].max()-sh:6.1f}")

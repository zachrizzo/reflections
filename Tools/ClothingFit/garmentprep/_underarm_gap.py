import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contact
from meshops import read_surface
from lineup_report import region_names
root, tag = Path(sys.argv[1]), sys.argv[2]
for name in sys.argv[3:]:
    f = root / name
    man = json.loads((f / "Manifest.json").read_text())
    body, bf = read_surface(f / "standing_body.bin")
    cloth, cf = read_surface(f / f"standing_{tag}.bin")
    names = region_names(f, tag, man["rest"])
    zone = np.unique(cf[names == "underarm/side"])
    rest = np.unique(cf[names == "torso"])
    out = []
    for label, idx in (("underarm/side", zone), ("torso", rest)):
        pts = cloth[idx][::3]
        lo, hi = pts.min(0) - 8, pts.max(0) + 8
        near = bf[np.all((body[bf] >= lo) & (body[bf] <= hi), axis=(1, 2))]
        cp, d, _ = contact.closest_on_tris(pts, body, near)
        out.append(f"{label}: cloth to skin cm p5 {np.percentile(d,5):.2f} p50 {np.percentile(d,50):.2f} p95 {np.percentile(d,95):.2f}")
    sh = np.asarray(man["rest"]["upperarm_l"]); el = np.asarray(man["rest"]["lowerarm_l"])
    hang = np.degrees(np.arccos(abs((el - sh)[2]) / np.linalg.norm(el - sh)))
    print(f"{name:16s} shoulder half-width {abs(sh[0]):.1f} cm, arm {hang:.0f} deg from vertical | " + " | ".join(out))

import sys, pickle
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import meshops, field
src = Path("Saved/ClothingFit/SourceBody/Barnaby")
body, bf = meshops.read_surface(src / "standing_body.bin")
face, ff = meshops.read_surface(src / "standing_face.bin")
skin = np.vstack((body, face)); sf = np.vstack((bf, ff + len(body)))
lo, hi = np.array([-60., -40., 10.]), np.array([60., 40., 125.])
f = field.SignedField(skin, sf, lo, hi)
for name, path in (("travel trousers", src / "standing_bottom.bin"), ("knee breeches", Path("Saved/ClothingFit/Generated/KneeBreeches/Prepared/standing_garment.bin"))):
    P, F = meshops.read_surface(path)
    ok = np.all((P > lo + 1) & (P < hi - 1), axis=1)
    d = f(P[ok])
    print(name, "distance of the layer's vertices from skin cm p10 p50 p90 p99", np.percentile(d, [10, 50, 90, 99]).round(2), "top z", P[:, 2].max().round(1))

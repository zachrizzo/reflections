"""Place a generated garment on the source body (step before prepare_generated_garment.py).

  python register_garment.py <raw garment.npz> <source body capture folder> <top|bottom> <out registered.npz> [--joints joints.json]

raw garment.npz    the generated mesh as dumped by garmentprep/blender_io.py dump (any scale, upright, facing front)
capture folder     standing_body.bin / standing_face.bin of the source body, Manifest.json or joints_local.json
Writes the registered mesh (same triangles and UVs) and <out>.report.json.
"""
import argparse
import json
import pickle
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "garmentprep"))
import field
import meshops
import register
from prepare_generated_garment import load_joints


def whole_body_field(capture):
    """Coarse signed distance field of the whole standing body (skin only), cached next to the capture."""
    body, bf = meshops.read_surface(capture / "standing_body.bin")
    face, ff = meshops.read_surface(capture / "standing_face.bin")
    skin = np.vstack((body, face)); sf = np.vstack((bf, ff + len(body)))
    store = capture / "BodyFieldWhole.pkl"
    key = f"{len(skin)}_{float(skin.sum()):.3f}"
    if store.exists():
        saved = pickle.load(open(store, "rb"))
        if saved.get("key") == key:
            return skin, sf, saved["field"]
    lo = np.array([skin[:, 0].min() - 6, skin[:, 1].min() - 14, 20.])
    hi = np.array([skin[:, 0].max() + 6, skin[:, 1].max() + 14, skin[:, 2].max() + 4])
    whole = field.SignedField(skin, sf, lo, hi, cell=.6, sample=.2)
    pickle.dump(dict(key=key, field=whole), open(store, "wb"))
    return skin, sf, whole


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("garment", type=Path); parser.add_argument("capture", type=Path)
    parser.add_argument("kind", choices=("top", "bottom")); parser.add_argument("output", type=Path)
    parser.add_argument("--joints", type=Path)
    args = parser.parse_args()
    data = np.load(args.garment)
    joints = load_joints(args.capture, args.joints)
    skin, sf, whole = whole_body_field(args.capture)
    P, report = register.register(data["P"], whole, skin, joints, args.kind)
    np.savez(args.output, P=P, F=data["F"], UV=data["UV"])
    Path(str(args.output) + ".report.json").write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()

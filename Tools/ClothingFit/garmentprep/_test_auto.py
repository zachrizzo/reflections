import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "Tools/ClothingFit")
sys.path.insert(0, "Tools/ClothingFit/garmentprep")
import prepare_generated_garment as pg

cap = Path("Saved/ClothingFit/DirectImage3D/MarketJerkin/MeshRetargetPilot/AfterPreserved")
j = pg.load_joints(cap)
for name, f in (("jerkin", "Saved/ClothingFit/DirectImage3D/MarketJerkin/MeshRetargetPilot/SolvePrepared/Registered.npz"),
                ("tunic", "Saved/ClothingFit/Generated/FieldTunic/Registered_untextured.npz"),
                ("breeches", "Saved/ClothingFit/Generated/KneeBreeches/Registered_untextured.npz")):
    P = np.load(f)["P"]
    print(name, "arm room detected:", pg.needs_arm_room(P, j), "| wraps upper arm l/r:",
          [pg.wraps_limb(P, j[f"upperarm_{s}"], j[f"lowerarm_{s}"]) for s in "lr"])

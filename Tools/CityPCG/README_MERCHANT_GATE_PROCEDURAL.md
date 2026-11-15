# Merchant Gate procedural source draft

This separate, original source-art generator models the checked-in ImageGen
gateway reference with project-owned textures. It creates stone piers, a
pointed full-depth cart passage, dressed arch stones, an upper plaster and
timber storey, glazed shop windows and shutters, a crossing front gable,
clay-tiled roof and two chimneys. Both roof-end gables are closed to the main
roof and have restrained timber framing and windows. It is not image-to-3D
output and does not use the Hunyuan or TripoSR model.

**The real full-detail generator has not run. No gate OBJ, preview, Unreal
asset or map change has been produced by this draft.** The tests below use a
coarser version of the same construction and keep everything in memory.

The proposed local coordinates are metres, +X toward the entrance and +Z up,
with a ground-center pivot and intended bounds of 7 x 13 x 8 m. The arch is
constructed as separated piers and overhead wedges, not a painted opening or
a solid box requiring a later Boolean cut. The independent existing gate
audit clips every triangle against the full-depth 2.5 m wide x 2.7 m high
corridor above the 6 cm floor band; it also probes both piers, the header and
upper lumen. In-memory tests confirm these properties for the coarse mesh and
prove a wall inserted into the opening is rejected. The real full-detail
output must pass that audit again before its manifest is written. Independent
section samples check coverage and outward normals at both roof ends; the
side-elevation detail is also checked against the cart corridor.

Existing texture files and the reference PNG are SHA-256-pinned; textures are
copied into the new output folder and checked again. The roof uses an
approximately 1.984375 m texture repeat across its tiles, while chimney bricks
keep ordinary projection. The gable's texture direction and the unreviewed
roof-course exposure need visual scrutiny. Decorative windows have solid
backing. The mesh contains overlapping architectural pieces and has not been
verified as watertight or suitable as collision geometry.

Run only after coordination with the other offline city worker. The CLI
fails closed unless the editor is running, the latest train reports LOADED,
no known compiler/build process is present, and Windows reports at least
4 GiB physical / 10 GiB commit headroom. The committed MarketDressingKit
process guard identifies the Gigabyte Control Center's `GCC.exe` using its
image path, creation time and matching child; any other `gcc.exe` still blocks.
Unreadable or ambiguous identities and process snapshots fail closed. Other
compiler names blocked by either guard remain blocked. The shared guard's
hash is checked throughout the run and included in the output manifest.
It rechecks at stage boundaries and
every 250 OBJ triangles; an individual geometry stage, texture copy, or audit
runs synchronously between checks and cannot stop instantly if conditions
change. This offline process does not access or acquire the editor lease.
The first real run's peak memory and duration remain unmeasured.

```powershell
# Small in-memory tests; no OBJ, image or temporary directory is written.
python -B Tools/CityPCG/test_build_merchant_gate_procedural.py -v

# Only when the guard passes and the other city worker has handed off:
python -B Tools/CityPCG/build_merchant_gate_procedural.py --run-name review_001
```

The run name must be new. Outputs go to a new
`Saved/CityPCG/MerchantGateProcedural_<name>` folder. Only a run containing a
completed `manifest.json` has passed its source and read-back audits. An
interrupted directory is left intact for inspection; the tool never
recursively cleans or overwrites it.

Even a passing source audit does not prove appearance, surface normals in a
DCC, UV orientation on import, game scale, capsule collision or navigation.
Review a rendered source from both sides and inside the arch, then use the
project's Blender-to-Unreal workflow to produce and inspect an importable mesh
and separately designed collision. Survey a suitable plot and review street
continuity before any map placement. No plot is implied by this source draft.

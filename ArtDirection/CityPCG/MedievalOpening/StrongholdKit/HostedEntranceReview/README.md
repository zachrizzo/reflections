# Illustrative stronghold entrance review

This folder is reserved for a **review-only source-art** bundle and labeled
preview images. It is not an in-game screenshot, a placed stronghold, or proof
of capture gameplay. The preservation workflow must succeed before the ZIP,
images and reports appear here.

The source is GitHub Actions run `43734534399`, artifact `14170395738`, at
commit `6613ca43ffe41a00515c24118c8d2de2f0b2a106`. Its unmodified ZIP is
1,924,747 bytes, SHA-256
`d4aba22ac7ae358c853ed83bc5c7534021292cee0fd35fbcee040663d46b621d`.
It contains labeled bare-gate, occupied and reclaimed views; two mutually
exclusive scene GLBs; and six reusable prop GLBs. These images show a small
isolated starting kit, not a finished faction base or surrounding city.

The hosted preservation job checks the artifact's exact repository, run,
commit, name, size and SHA; verifies every scene/prop GLB and the three PNG and
two report hashes; and preserves only those PNGs and reports as ordinary Git
files beside the ZIP. The ZIP is a Git LFS object. Its exact size and SHA are
checked again from a fresh isolated remote LFS readback before a non-force push
to main. A failed run may leave an unreferenced LFS object, and LFS storage and
bandwidth allowances still apply.

The central-passage report is a source-triangle surface check, not proof of
in-game collision, navigation or access. The GLB reimport checked counts,
bounds and material counts, not complete per-corner channel identity. The
assets need visual refinement and Unreal placement, materials, collision,
navigation, streaming and gameplay verification before use.

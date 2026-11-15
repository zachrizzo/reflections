# Contextual stronghold source review

This is an **illustrative, review-only** street-facing compound. It combines
the exact preserved North Market street scene with the prior watch-gate kit,
adds two large occupied/reclaimed standards and side supplies, and shows the
same staging from both approaches. The new standards are reusable GLBs; the
two complete scene GLBs are mutually exclusive visual states. The original
street and gate assets remain untouched. No characters, crowd behavior,
capture state or live map changes are made.

The hosted output includes labeled baseline, occupied, reclaimed and reverse
views, plus the two scenes, two standards and build/reimport reports. The
lighting and placements are illustrative. The code checks transformed source
triangles from the street, gate and props against a gate-local box 10 m long,
2.2 m wide and 2.34 m tall above a 6 cm floor band; it repeats that check after
clean GLB reimport. The box is a surface-intersection check, not evidence of
Unreal collision, actual street clearance, navigation or gameplay. Reimport
compares triangle counts and bounds, not full per-corner channels.

Inputs are pinned to the preserved street archive SHA-256
`021114d3c208f9aed1f4c6d874c24e6306050244ad17426d491d9106cf2be698`
and the stronghold archive SHA-256
`d4aba22ac7ae358c853ed83bc5c7534021292cee0fd35fbcee040663d46b621d`.
Only five exact hash-bound GLB members are extracted to a fresh hosted
temporary directory. The selected gate transform is an artistic staging in the
review scene, not an instruction to place it in Gray London.

Run the lightweight guards without Blender or the editor:

```text
python -B Tools/CityPCG/test_compound_street_review.py -v
python -O -B Tools/CityPCG/test_compound_street_review.py -v
```

The read-only `compound-street-review.yml` job uses a standard GitHub-hosted
Ubuntu runner, a pinned Blender archive and a bounded official mirror fallback.
It builds and reimports in separate Blender processes, then uploads a
short-lived review artifact. A push trigger must be a single-parent main commit
containing only the workflow file; commit the scripts and tests first. This
document does not trigger a workflow. Review visual quality, actual building
intersections, Unreal scale/materials, collision, navigation, streaming and
gameplay independently before considering any map placement.

# North Market street scene — review baseline

This folder is reserved for a **review-only** hosted street-scene archive and
its two Blender diagnostic images and reports. It is not an Unreal map or a
gameplay-ready city update. The ZIP and images appear only after the separate
preservation workflow succeeds.

The exact source is [hosted run 43732127254](https://github.com/zachrizzo/reflections/actions/runs/43732127254),
artifact `14168477672`, 35,334,942 bytes, ZIP SHA-256
`021114d3c208f9aed1f4c6d874c24e6306050244ad17426d491d9106cf2be698`.
The scene was built from verified building sources, a separately checked
closed shopfront overlay, and illustrative market props. The source run
reimported its GLB in a fresh Blender process and checked output hashes.

Intended files are `north-market-street-illustrative-review.zip`,
`street_eye_level.png`, `street_trestle.png`, `manifest.json`, and
`build.report.json`. The ZIP stays byte-identical in Git LFS. The image and
report copies are ordinary Git files verified against their entries in the
source ZIP and reports; the two images are not in-game screenshots.

The market props improve the street-level composition, but the buildings
still look regular and the preview is dark. Roof and skyline variation,
brighter and more readable materials, and visual review are needed before
approval. Prop positions and the ground plane are illustrative; real floor
support, collision, navigation, quests, streaming, tile replacement and
Unreal materials remain unverified. The doors and hatches are closed visual
details. This baseline does not imply that Gray London has been changed.

The preservation workflow checks the pinned ZIP and every report-listed
member, verifies the PNG signatures, dimensions and hashes, and copies only
the two PNGs and reports. It checks the LFS pointer and independently reads
the uploaded archive into a fresh LFS store before a fast-forward-only push.
The job uses a GitHub-hosted runner with `actions: read` and `contents: write`;
the latter is needed to commit the preserved files. A failed run can leave
unreferenced uploaded LFS data. The disk-space check is a starting floor,
not an aggregate disk quota.

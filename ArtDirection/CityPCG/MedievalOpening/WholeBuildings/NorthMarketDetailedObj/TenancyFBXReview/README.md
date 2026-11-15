# North Market tenancy FBX review

This folder is reserved for one **review-only** Blender source-art archive,
not an Unreal asset, game screenshot, visual approval, or gameplay-ready
replacement. The preservation workflow must complete successfully before its
ZIP and reports are available.

The exact source is GitHub Actions run `43732112368`, artifact `14169141736`,
at commit `585c82abe6ae99ed03678f17cdfcc81e489fbfe7`. The unmodified ZIP is
3,226,263 bytes with SHA-256
`e65a5ee3c694cc84647ebac96dc34bd48f4513cf9e22d6402f167136ebd0f79a`.
It contains two alternatives: a complete building with tenancy fronts, and a
separate frontage overlay positioned at the original building's local pivot.
Do not layer the complete building over its baseline shell.

The hosted preservation job validates the artifact's repository/run/commit,
name, size and hash; hashes both FBX members against their independently
recorded export/clean-reimport reports; and retains those two verify reports as
ordinary Git blobs. It stores the unmodified ZIP as a Git LFS object, checks the
pointer, and verifies its exact size and SHA again from a fresh isolated remote
LFS readback before a non-force push to main. Existing baseline and preview
bundles are in separate folders and remain unchanged. Failures may leave an
unreferenced LFS object; storage and bandwidth allowances still apply.

The FBXs and their associated Blender reports remain review-only. Their doors
and hatches are closed visual details. Unreal scale, orientation, materials,
collision, navigation, streaming, placement and gameplay have not been
verified. A successful Blender round-trip and archival readback do not prove
any of those in-game checks.

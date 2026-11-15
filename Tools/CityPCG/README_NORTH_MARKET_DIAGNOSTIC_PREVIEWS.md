# North Market Blender diagnostic previews

This fallback preserves two existing, textured Blender source-asset views and
their original report for the east `0a73564b` North Market model. They are
**not in-game screenshots**. Artificial lighting and background are used;
the result does not validate Unreal placement, collision, appearance, or play.
No local rendering, Unreal access, generation, or FBX/LFS download is needed.

The separate `preserve-north-market-previews.yml` workflow uses a GitHub-hosted
Ubuntu runner and the repository's short-lived `GITHUB_TOKEN` with only
`actions: read` and `contents: write`. It accepts manual dispatch on main or a
single-parent push that changes only that workflow file. The script rechecks
that event, repository, workflow, hosted environment, checked-out commit,
canonical remote, clean checkout, and current remote main. Environment fields
guard accidents; they are not an authentication boundary. The fresh hosted VM
and scoped workflow permissions provide isolation.

The source is artifact 14165382017 from run 43723954546: exact ZIP size
2,639,804 bytes and SHA-256
`3a690aade02e668b800c5d49426d7b142d18556a953d7ed00737861a5086d096`.
The shared downloader verifies metadata, size and digest before extraction;
its inspector selects only `preview/eye_level.png`, `preview/three_quarter.png`,
and `preview/preview.report.json`, checks image dimensions and both report and
actual FBX digest, and rejects ambiguous archive members. This wrapper further
checks the preview report's expected fields and diagnostic status, hashes each
output against the inspected ZIP content, and verifies the actual staged and
committed Git blobs. The ZIP pin cryptographically binds each member; the
per-file hashes are emitted on successful publication.

The three unchanged outputs plus a diagnostic-only README go into the new
`ArtDirection/CityPCG/MedievalOpening/WholeBuildings/NorthMarketDetailedObj/DiagnosticPreviews/`
directory. Any existing or redirected target fails closed. Files must be Git
blobs matching their source hashes, so a filter or LFS pointer fails closed.
After comparing remote main to the initial commit, the script makes a normal
non-force push; a concurrent ordinary main advance rejects it. A failed run
cannot intentionally overwrite or update an existing preview directory.

To enable the push trigger safely, first commit the shared downloader, this
script, its tests, and this note to main. Then make a separate single-parent
commit containing only the workflow file. This workflow must be reviewed before
publication; these instructions do not run or trigger it. The GitHub Actions
artifact is short-lived, so a missing or expired source makes the run fail.
The fallback is unnecessary if the existing bundle-preservation workflow
already publishes the preview images and report.

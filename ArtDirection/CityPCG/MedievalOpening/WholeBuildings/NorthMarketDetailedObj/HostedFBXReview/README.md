# North Market hosted FBX review bundles

This folder is reserved for four **review-only** hosted Blender round-trip
artifacts. They are not Unreal assets, game screenshots, visual approvals or
gameplay-ready replacements. The preservation job must first complete
successfully; the ZIPs and preview files are not present merely because this
README exists.

| Model | Source run | Artifact ID | ZIP bytes | ZIP SHA-256 |
| --- | --- | --- | ---: | --- |
| `east_0a73564b` | `43723954546` | `14165382017` | 2,639,804 | `3a690aade02e668b800c5d49426d7b142d18556a953d7ed00737861a5086d096` |
| `east_31c9ff1a` | `43723954546` | `14165792197` | 1,460,426 | `bf30b04ea539b92e3bc518f19e75ce13566ab6ebf622285db9e9a3a271541c9b` |
| `west_d08bbb3b` | `43723954546` | `14165916795` | 1,322,370 | `dff11277e5fed7d87ef008bf76188b3f7bd35178a12495b41005115a1b873391` |
| `west_736fd5c6` | `43724753596` | `14165658843` | 1,564,718 | `159538f2ceab546b41a7ac4b79895500029c2f80093ca2ff071ba593d251dfbe` |

The proposed hosted preservation job downloads the exact raw ZIPs through the
authenticated GitHub artifact API, checks each artifact's run ID, name, size
and SHA-256, and never forwards the GitHub token to a redirected storage
host. It writes the four unmodified ZIPs via Git LFS and verifies their LFS
pointers and a fresh remote LFS readback before a fast-forward-only main push.
Any changed remote head, existing target, missing artifact, hash mismatch or
failed LFS transfer stops the push. An unsuccessful run may have already
uploaded unreferenced LFS objects; the four ZIPs total about 7 MB and Git LFS
storage/bandwidth allowances still apply.

The job also copies only the two exact `east_0a73564b` preview PNGs and their
diagnostic report after verifying the source ZIP, PNG signatures and the
reported FBX SHA-256 against the FBX bytes. The intended files are
`east_0a73564b_eye_level.png`, `east_0a73564b_three_quarter.png` and
`east_0a73564b_preview.report.json`. They are Blender diagnostics with
artificial cameras and lighting, not in-game screenshots. They show one model
only and do not establish visual quality or Unreal material appearance.

Before gameplay use, independently inspect the models and verify Unreal
dimensions, orientation, pivots, materials, collision, navigation, placement,
streaming and performance. The west normal-preservation result in particular
requires Unreal vertex-splitting and performance measurement. None of these
checks is implied by preserving a review bundle.

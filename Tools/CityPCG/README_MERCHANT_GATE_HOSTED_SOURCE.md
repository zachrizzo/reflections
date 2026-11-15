# Hosted Merchant Gate source export

`export_merchant_gate_hosted.py` is a separate, review-only OBJ/MTL export
entrypoint for the existing procedural gate. The Windows `light_work_guard()`
and its local command are unchanged. The hosted command uses the same mesh,
texture hash checks, OBJ readback and full-depth passage audit; it does not
use Unreal, Blender, a GPU, source-map placement or collision generation.

The intended workflow runs only on GitHub-hosted `ubuntu-24.04` for
`zachrizzo/reflections` on main, with read-only repository contents and no
stored secrets. The entrypoint independently checks the Linux/GitHub Actions
context, repository ID, workspace, run ID, workflow ref and checkout SHA.
It accepts manual dispatch, or a single-parent push that changes only the
hosted workflow file. That push requires the exporter and tests to have
already reached main, and a checkout depth of at least two commits.

These environment checks prevent accidental local invocation; they are **not
a security boundary against a deliberately spoofed environment**. Actual
machine isolation relies on the workflow selecting GitHub's hosted runner.
No OIDC token or repository-write permission is requested.

The exporter enforces Linux process limits of 512 MiB address space, 256 MiB
peak RSS, 90 seconds of CPU, 120 seconds wall time and 64 MiB per file/total
output. It checks available RAM and disk, verifies all tracked inputs and
their hashes, and refuses to reuse an output directory. A successful run
creates only `ci-merchant-gate-source/` with `MerchantGate.obj`,
`MerchantGate.mtl`, five texture PNGs, and `manifest.json`. The manifest
records the source commit and environment, input/output hashes, audit result
and review limitations. An interrupted export can leave an incomplete folder;
only successful jobs with a complete manifest should be uploaded.

```text
python3 -B Tools/CityPCG/test_export_merchant_gate_hosted.py -v
python3 -B Tools/CityPCG/export_merchant_gate_hosted.py
```

The tests use only mocked context and the coarse in-memory mesh; they do not
run the hosted export. The full export completed in [Actions run
43721087489](https://github.com/zachrizzo/reflections/actions/runs/43721087489)
at commit `b4c0acec`. The downloaded archive matches GitHub's artifact SHA-256;
that confirms transfer integrity, not independent approval of its contents.
Artifacts from this public repository are accessible to signed-in users with
read access and expire according to workflow retention. The exported mesh is
still unreviewed source art: appearance, normals, UVs, collision, navigation,
placement, Unreal import, and gameplay remain to be checked.

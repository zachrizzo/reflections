# Local TripoSR Merchant Gate trial

`run_merchant_gate_triposr.py` prepares one **raw, unreviewed** image-to-3D
trial from the checked-in ImageGen reference. TripoSR's [model card](https://huggingface.co/stabilityai/TripoSR)
and the pinned upstream source identify the model and code as MIT-licensed.
The separate local U2Net background model and installed software are recorded
as dependencies, rather than described as TripoSR itself.

The upstream checkout is pinned to commit
`107cefdc244c39106fa830359024f6a2f1c78871`; the model is pinned to revision
`5b521936b01fbe1890f6f9baed0254ab6351c04a`. The runner checks the exact
checkpoint size and SHA-256, the TripoSR and DINO configuration hashes, the
original PNG, the local background model, upstream license, clean upstream
checkout, and Local3D interpreter. It also records hashes of its own code and
the marching-cubes adapter, and verifies the inputs again before publishing a
result. It does not install packages, alter the shared Python environment, or
edit the upstream checkout. It disables network access in the worker and
maps the upstream DINO configuration request to the pinned local file.

The checkpoint was not available when this runner was prepared. Its download
and the first model run remain pending; a successful import of TripoSR's
Python module is **not** model-inference validation.

## When the shared editor is idle

Use the existing downloader to finish and verify the pinned checkpoint first.
Start the model trial only while `Saved/PIE_LOCK.json` is absent, the
latest explicit `Saved/PIE_QUEUE.md` train status is idle, and an
`UnrealEditor.exe` process is running. The process check matches the existing
checkpoint downloader and does not by itself identify the project. The supervisor
requires at least 8 GiB free physical memory, 16 GiB free system commit and
8 GiB free GPU 0 memory before starting. During the run it rechecks the shared
lease, train, editor process and memory headroom approximately every two seconds;
if any lease file appears (even an expired lease), the editor closes or restarts, a build starts,
or memory drops below 4 GiB physical or
10 GiB commit, it terminates its own worker. This polling does not reserve
the editor or GPU against unrelated programs.

From the project root, select a fresh lowercase run name:

```powershell
& 'C:/Users/zachc/tools/Local3D/.venv/Scripts/python.exe' Tools/CityPCG/run_merchant_gate_triposr.py --run-name merchant_gate_triposr_001
```

The default uses seed 1450, 256 grid samples per axis and 4,096 evaluation
points per chunk. A run creates its own directory under
`Saved/CityPCG/ImageTo3D/MerchantGateRuns`; an existing name is never reused.
It keeps the original image, background-removed RGBA image, gray-composited
conditioning image, raw vertex-colored GLB, upstream license, worker log,
and hash-bearing provenance. An interrupted or failed run remains there for
inspection and cannot be mistaken for a completed trial. Review the
conditioned image first: background removal may close or erase the gateway.

## Extractor compatibility

The local environment lacks `torchmcubes` and `moderngl`. The runner does not
import the upstream texture-baking CLI, so it does not need `moderngl` for a
vertex-colored geometry trial. It substitutes the installed scikit-image
Lorensen marching cubes in the child process only. TripoSR's upstream helper
reverses the extractor's returned axes; the adapter compensates before that
reversal. CPU-only tests use an off-center ellipsoid to verify the final axis
order and outward right-hand triangle winding both directly and through the
actual upstream helper. The extractor is not proven bit-for-bit or
topologically identical to `torchmcubes`, particularly at ambiguous cells.
The Local3D versions of PyTorch, NumPy, Transformers and other packages also
differ from upstream's suggested versions; only module import and synthetic
CPU tests have been checked. No real checkpoint inference has been tested.

The result is a candidate, not a placed building: inspect all sides and the
open passage, repair topology as needed, normalize its size and pivot, run the
existing Merchant Gate geometry audit, and complete collision/navigation and
in-game review before using it. A single image cannot establish the hidden
back or interior of the building.

CPU-only tests, with CUDA hidden and no model weights:

```powershell
python Tools/CityPCG/test_run_merchant_gate_triposr.py -v
$env:CUDA_VISIBLE_DEVICES = '-1'
$env:PYTHONDONTWRITEBYTECODE = '1'
& 'C:/Users/zachc/tools/Local3D/.venv/Scripts/python.exe' Tools/CityPCG/test_triposr_skimage_mc.py -v
```

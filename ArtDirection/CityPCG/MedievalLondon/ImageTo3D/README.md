# Medieval London image-to-3D review inputs

The six PNGs are transparent ImageGen reference images, not meshes or game
assets. The hosted TripoSR workflow creates independent CPU-generated,
vertex-colored GLB candidates, diagnostics and hash-bearing reports. The
outputs have inferred backs and undersides and arbitrary model-space scale and
pivot. Human visual review, physical sizing, Blender/Unreal material and
vertex-color checks, collision and placement are required before game use.

The first batch uses pinned MIT-licensed TripoSR source commit
`107cefdc244c39106fa830359024f6a2f1c78871` and model revision
`5b521936b01fbe1890f6f9baed0254ab6351c04a`. The model checkpoint's exact
SHA-256 and the two configuration hashes are checked by the hosted workflow.
The existing CPU marching-cubes adapter is used instead of torchmcubes, and
the already-transparent input is composited on gray without another background
removal model. These adaptations and the runtime versions appear in each
report; they are not claims of equivalence to upstream defaults.

The matrix is deliberately data-driven: add a fresh PNG and its hash to
`inputs.json`, then add its name to a later workflow matrix. Each job is
independent. The input files are stored as ordinary Git binary blobs; each is
under 3 MB. Source images and their generated outputs remain recoverable.

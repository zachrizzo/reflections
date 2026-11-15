# Read-only Gray London package audit

From the project root:

```powershell
python -B Tools/CityPCG/audit_london_package.py
python -B Tools/CityPCG/audit_london_package.py --json
```

The tool reads the current checkout and `Saved/JamBuild/Windows`; it does not
edit files, hash large executables, launch Unreal, build, cook, package, or
deploy anything. `--project <path>` selects another checkout for inspection.

It checks the configured editor/start/New Game/cook map, the required
`ReflectionsSampleGameMode`, and the packaging batch's explicit `-map`; the
Win64 Development game-target receipt and staged
executables; the IoStore container files; the staged UFS manifest's Gray London
map, generated World Partition cells, and the four West Mark Lane pilot assets.
It also reports when project source or the project descriptor is newer than the
game executable, or saved map/World Partition/pilot/config inputs are newer
than the staged manifest. Missing, unreadable, empty, ambiguous, or mismatched
evidence is a failure. Symlinks and Windows reparse points, including
junctions, in checked paths or walked directories are rejected. Source timestamp checks are intentionally conservative
and can flag files unrelated to the game target.

Exit code **1** means the audit found a problem or evidence is missing. Exit
code **2** means no checked problem was found but the build is **inconclusive**;
there is deliberately no success exit code. Equal or older timestamps do not
prove freshness. The target receipt's engine BuildId, matching file sizes, and
UFS manifest entries do not prove that the game executable matches current
source or that the archive's content loads. This tool does not inspect existing
ZIPs, unsaved editor changes, placement/activation of replacement actors, or
the content of the IoStore containers.

The pilot is not yet verified as placed in the playable map, and its current
runtime replacement setting defaults to off. A matched successful game-target
build, a coordinated save freeze and cook, verification of the actual staged
contents, a real-spawn gameplay check, and a host/guest LAN test are required
before distributing a refreshed build. The existing `measure_london.zip` is
documented as measurement-only and predates the pilot assets.

Run the small synthetic checks (they use private temporary directories):

```powershell
python -B -m unittest discover -s Tools/CityPCG -p test_audit_london_package.py -v
```

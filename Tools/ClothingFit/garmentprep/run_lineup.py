"""Put Wardrobe Items on every MetaHuman of a roster, capture the same poses on each and audit them.

  python run_lineup.py <lineup.json> [--only Name ...] [--no-audit]

lineup.json:
  {"out": "<folder>", "roster": [{"label": "GiltBarnaby", "character": "/Game/.../MHC_GiltBarnaby"}, ...],
   "wear": {"Top Garment": "/Game/.../WI_X", "Bottom Garment": "/Game/.../WI_Y"}, "clear_slots": ["Outfits"],
   "surfaces": {"jerkin": "/MeshRetargetJerkin/", "bottom": "OA_TravelTrousers"}, "audit": [["jerkin", "bottom"]],
   "clips": {...}, "views": {...}}
One body per editor lease (claimed from here, at most 4 minutes), no play session, nothing saved.
A body whose folder already has Manifest.json is skipped, so the run can be resumed.
Writes <out>/Lineup.json with the per-body pass table.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ue

PY = sys.executable
CLIPS = {"walk": {"animation": "/MetaHumanCharacter/Optional/Animation/UEFNAnimPreset/Locomotion/AS_MH_Neutral_Walk_Loop_F", "frames": list(range(25))},
         "reach": {"animation": "/Game/Characters/Hero/Animation/CombatCasts/AS_Hero_CombatHealRaise", "frames": list(range(25))}}


def free_commit_gb():
    """Memory the machine can still hand out (physical + page file), in GB. The shared editor grows with
    every MetaHuman opened, so the run stops before it starves the editor."""
    import ctypes

    class Status(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total_phys", ctypes.c_ulonglong), ("avail_phys", ctypes.c_ulonglong),
                    ("total_page", ctypes.c_ulonglong), ("avail_page", ctypes.c_ulonglong), ("total_virtual", ctypes.c_ulonglong),
                    ("avail_virtual", ctypes.c_ulonglong), ("avail_extended", ctypes.c_ulonglong)]
    status = Status()
    status.length = ctypes.sizeof(Status)
    try:
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
        return status.avail_page / 2 ** 30
    except Exception:
        return 99.


def capture(config, row, folder):
    params = {"character": row["character"], "label": row["label"], "wear": config["wear"], "clear_slots": config.get("clear_slots", []),
              "surfaces": config["surfaces"], "out": str(folder).replace("\\", "/"), "clips": config.get("clips", CLIPS),
              "standing_views": config.get("standing_views", ["front", "back"]), "photo_frames": config.get("photo_frames", {"walk": [12], "reach": [12]}),
              "pose_views": config.get("pose_views", ["back"]), "camera_distance": config.get("camera_distance", 118),
              "aim_height": row.get("aim_height", config.get("aim_height", 124)), "shot_size": config.get("shot_size", [1000, 1000]),
              "close_after": True, "refresh_body": config.get("refresh_body", True),
              "commit_refresh": "/Generated/QA/" in row["character"]}
    ok, data = ue.wait_claim(f"garment-fit lineup: pose capture on {row['label']} (transient probe in the editor world, no PIE)", 240, 1800)
    if not ok:
        return False, f"no lease: {data}"
    try:
        client = ue.Client()
        code = "import json\nPARAMS = json.loads(" + repr(json.dumps(params)) + ")\n" + (HERE / "editor/capture_poses.py").read_text(encoding="utf-8")
        for _ in range(24):
            failed, value = client.python(code)
            if not (isinstance(value, str) and "running a slow task" in value):
                break
            time.sleep(5)
            if ue.lock_state()[0] != "ours":
                return False, "lost the lease while the editor was busy"
        return (not failed), value
    finally:
        ue.release()


def main():
    config = json.loads(Path(sys.argv[1]).read_text())
    only = sys.argv[sys.argv.index("--only") + 1:] if "--only" in sys.argv else None
    audit = "--no-audit" not in sys.argv
    out = Path(config["out"]); out.mkdir(parents=True, exist_ok=True)
    log = out / "run.log"
    running = []
    for row in config["roster"]:
        if only and row["label"] not in only:
            continue
        folder = out / row["label"]
        if not (folder / "Manifest.json").exists():
            limit = config.get("min_free_commit_gb", 7.)
            while free_commit_gb() < limit and any(p.poll() is None for p in running):
                time.sleep(3)                              # our own audit is using the memory: let it finish first
            if free_commit_gb() < limit:
                with log.open("a") as stream:
                    stream.write(f"{time.strftime('%H:%M:%S')} STOPPED before {row['label']}: only {free_commit_gb():.1f} GB of memory left to commit\n")
                print("STOPPED: memory", row["label"])
                break
            started = time.time()
            ok, value = capture(config, row, folder)
            with log.open("a") as stream:
                stream.write(f"{time.strftime('%H:%M:%S')} {row['label']}: {'captured' if ok else 'FAILED'} in {time.time() - started:.0f} s, free commit {free_commit_gb():.1f} GB: {str(value)[:600]}\n")
            if not ok:
                (folder).mkdir(exist_ok=True)
                (folder / "CaptureError.txt").write_text(str(value))
                continue
        if audit:
            for tag, under in config.get("audit", [["jerkin", "bottom"]]):
                if not (folder / f"Audit_{tag}.json").exists():
                    running = [p for p in running if p.poll() is None]
                    while len(running) >= 1:           # one audit at a time: two overlapping ones took free commit to 1.1 GB beside the editor
                        time.sleep(2)
                        running = [p for p in running if p.poll() is None]
                    running.append(subprocess.Popen([PY, str(HERE / "audit_capture.py"), str(folder), tag, under, "2"],
                                                    stdout=open(folder / f"audit_{tag}.log", "w"), stderr=subprocess.STDOUT))
    for p in running:
        p.wait()
    print("LINEUP DONE", out)


if __name__ == "__main__":
    main()

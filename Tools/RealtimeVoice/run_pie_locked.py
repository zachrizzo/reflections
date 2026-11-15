"""Runs an editor PIE script under the team's PIE lock (Saved/PIE_LOCK.json).

Waits while someone else's unexpired lock exists or PIE is running, writes its own lock (expiry at most now+240 s),
runs the script through run_in_editor.py, and removes the lock only if it is still the one it wrote.

    python run_pie_locked.py test_npc_dialogue_pie.py [--wait 900]
"""
import argparse
import json
import os
import subprocess
import sys
import time
import uuid

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LOCK = os.path.join(REPO, "Saved", "PIE_LOCK.json")
HERE = os.path.dirname(os.path.abspath(__file__))
PIE_PROBE = ("s = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)\n"
             "'PIE' if s.get_game_world() else 'IDLE'\n")


def read_lock():
    try:
        with open(LOCK, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def pie_running():
    probe = os.path.join(HERE, "__pie_probe.py")
    with open(probe, "w", encoding="utf-8") as handle:
        handle.write(PIE_PROBE)
    try:
        out = subprocess.run([sys.executable, os.path.join(HERE, "run_in_editor.py"), probe, "--timeout", "30"],
                             capture_output=True, text=True, timeout=60).stdout
    finally:
        os.remove(probe)
    return "IDLE" not in out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("script")
    parser.add_argument("--wait", type=float, default=900.0)
    parser.add_argument("--seconds", type=int, default=240)
    parser.add_argument("--foreground", action="store_true", help="bring the editor to the front once the lock is taken")
    args = parser.parse_args()
    token = "npc-dialogue-" + uuid.uuid4().hex[:8]
    deadline = time.time() + args.wait
    while True:
        lock = read_lock()
        busy = lock is not None and float(lock.get("expires_epoch", 0)) > time.time()
        if not busy and not pie_running():
            break
        if time.time() > deadline:
            print("Gave up waiting for the PIE lock / PIE to stop.")
            return 3
        time.sleep(10)
    now = int(time.time())
    expires = now + min(args.seconds, 240)
    with open(LOCK, "w", encoding="utf-8") as handle:
        json.dump({"owner": "NPC dialogue session (" + token + ")", "purpose": "NPC talk-back PIE check",
                   "acquired_epoch": now, "expires_epoch": expires,
                   "expires_local": time.strftime("%H:%M:%S", time.localtime(expires))}, handle, indent=2)
    print("PIE lock taken until", time.strftime("%H:%M:%S", time.localtime(expires)), flush=True)
    if args.foreground:
        # The viewport only renders while the editor is in front, so screenshots need it there.
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "$p = Get-Process UnrealEditor | Select-Object -First 1; "
                        "(New-Object -ComObject WScript.Shell).AppActivate($p.Id) | Out-Null"], timeout=20)
    try:
        for _ in range(30):
            result = subprocess.run([sys.executable, os.path.join(HERE, "run_in_editor.py"), args.script,
                                     "--timeout", str(min(args.seconds, 240) - 5)], timeout=args.seconds,
                                    capture_output=True, text=True)
            print(result.stdout[-3000:], flush=True)
            if "slow task" not in result.stdout:
                return result.returncode
            # The editor is busy (a build or import): keep the lock, renew it, and try again shortly.
            time.sleep(10)
            renewed = int(time.time()) + min(args.seconds, 240)
            with open(LOCK, "w", encoding="utf-8") as handle:
                json.dump({"owner": "NPC dialogue session (" + token + ")", "purpose": "NPC talk-back PIE check",
                           "acquired_epoch": now, "expires_epoch": renewed,
                           "expires_local": time.strftime("%H:%M:%S", time.localtime(renewed))}, handle, indent=2)
        return 4
    finally:
        lock = read_lock()
        if lock and token in str(lock.get("owner", "")):
            os.remove(LOCK)
            print("PIE lock released", time.strftime("%H:%M:%S"))
        else:
            print("Lock no longer ours; left as is.")


if __name__ == "__main__":
    sys.exit(main())

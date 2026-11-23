"""Ask Codex (ChatGPT image generation) for the catalog reference image of one garment.

  python reference_image.py <kind: top|bottom> "<description>" <out.png>

Codex owns image generation in this project. This calls the Codex command-line program that ships
with the Codex app (signed in with the ChatGPT account) and asks for exactly one image.
The prompt wraps the description in fixed catalog-photo rules so the image-to-3D step gets what it
needs: one isolated garment, straight-on front view, flat background, sleeves or legs in the
MetaHuman A-pose, form-fitting.
"""
import glob
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

RULES = {
    "top": ("Sleeves, if the garment has any, hang straight and are angled outward about 40 degrees from the vertical on both "
            "sides like a relaxed A-pose, with clear open space between each sleeve and the body of the garment. "
            "Shoulders level. The neck opening, armholes or cuffs, and the hem must read as real openings."),
    "bottom": ("The two legs hang straight down, parallel, with a clear gap between them from the crotch to the hems. "
               "Level waistband at the top. The waist opening and the leg openings must read as real openings."),
}


def prompt_for(kind, description, target):
    return f"""Generate exactly one image with your image generation tool and save it as a PNG at this exact path:
{target}

Do nothing else: do not run image-to-3D, do not start any GPU job, do not open or call Unreal or Blender, do not edit or create any other file. When the PNG exists at that path, reply with the single word DONE.

Image request:
Use case: product-mockup. One photorealistic straight-on catalog reference for garment reconstruction: {description}
One single isolated garment on a flat warm off-white background, centered and completely visible, with generous margins. Symmetric, near-orthographic full front view from the exact center, no perspective tilt. Close-fitting, tailored cut: form-fitting, never baggy. {RULES[kind]} Even soft studio lighting, mild fabric texture. Shaped like a real professionally sewn garment photographed on an invisible support.
No body, mannequin, hanger, skin, hands, legs, feet, shadows that could be confused with extra panels, tags, text, stamps, separate accessories, belts or bags."""


def find_codex():
    found = shutil.which("codex")
    if found:
        return found
    hits = sorted(glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\OpenAI\Codex\bin\*\codex.exe")), key=os.path.getmtime)
    if not hits:
        raise SystemExit("Codex command-line program not found (looked in PATH and %LOCALAPPDATA%\\OpenAI\\Codex\\bin)")
    return hits[-1]


def main():
    kind, description, target = sys.argv[1], sys.argv[2], Path(sys.argv[3]).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    (target.with_suffix(".prompt.txt")).write_text(prompt_for(kind, description, target), encoding="utf-8")
    if target.exists():
        print("reference image already exists:", target)
        return
    started = time.time()
    log = target.with_suffix(".codex.log")
    with open(log, "w", encoding="utf-8", errors="replace") as stream:
        code = subprocess.call([find_codex(), "exec", "--skip-git-repo-check", "-s", "workspace-write", "-C", str(target.parent),
                                "-c", 'model_reasoning_effort="low"', "-o", str(target.with_suffix(".codex.last.txt")),
                                prompt_for(kind, description, target)], stdout=stream, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    if not target.exists():
        raise SystemExit(f"Codex did not write {target} (exit {code}); see {log}")
    print(f"reference image written in {time.time() - started:.0f} s: {target}")


if __name__ == "__main__":
    main()

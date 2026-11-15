"""Build a ~75 s listening reel (MP3) from the processed files, with a beep before each section. Writes a contents list."""
import sys, os, ctypes
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import audiolib as A
import voice_script as V

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VO = os.path.join(ROOT, "voice", "final")
SFX = os.path.join(ROOT, "proc", "final", "sfx")
OUTDIR = r"C:\Users\zachc\Documents\Unreal Projects\reflections\ArtDirection\Audio\reel"
SR = 44100
TEXT = {l[0]: l[3] for l in V.LINES}

SECTIONS = [
    ("The Tarnish (villain voice)", [("vo", "Tarnish_Taunt_03"), ("vo", "Tarnish_Manifest_02"), ("vo", "Tarnish_Death_01")]),
    ("NPC barks: civilian, guard, soldier, tarnished", [("vo", "Civilian_Fear_01"), ("vo", "Guard_Alert_01"), ("vo", "Soldier_Command_01"), ("vo", "Tarnished_Mutter_02")]),
    ("Narrator", [("vo", "Narrator_Intro"), ("vo", "Narrator_Tip_Shard")]),
    ("Spells: cast then impact per element", [("sfx", f"{e}_{k}_01") for e in ("Fire", "Water", "Ice", "Lightning", "Earth", "Arcane") for k in ("Cast", "Impact")]),
    ("World jump whoosh, then mirror-shard (coin) pickup", [("sfx", "WorldJump_Whoosh_01"), ("sfx", "Coin_Pickup_01")]),
]


def load(kind, name):
    p = os.path.join(VO if kind == "vo" else SFX, name + ".wav")
    x, sr = A.decode(p)
    m = A.to_mono(x)
    if sr != SR:
        t = np.arange(0, len(m) * SR / sr) * sr / SR
        m = np.interp(t, np.arange(len(m)), m).astype(np.float32)
    return m


def beep():
    t = np.arange(int(0.09 * SR)) / SR
    b = 0.25 * np.sin(2 * np.pi * 1000 * t) * np.hanning(len(t))
    return b.astype(np.float32)


def silence(s):
    return np.zeros(int(s * SR), np.float32)


def write_mp3(path, y):
    lib = A._lib
    info = A.SF_INFO()
    info.samplerate, info.channels = SR, 1
    info.format = 0x230000 | 0x0082  # SF_FORMAT_MPEG | SF_FORMAT_MPEG_LAYER_III
    lib.sf_open.restype = ctypes.c_void_p
    h = lib.sf_open(path.encode("mbcs"), 0x20, ctypes.byref(info))  # SFM_WRITE
    if not h:
        return False
    lib.sf_writef_float.restype = ctypes.c_int64
    lib.sf_writef_float.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float), ctypes.c_int64]
    buf = np.ascontiguousarray(y.astype(np.float32))
    lib.sf_writef_float(h, buf.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), len(buf))
    lib.sf_close(h)
    return True


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    parts, rows, t = [silence(0.3)], [], 0.3
    for si, (title, items) in enumerate(SECTIONS, 1):
        parts += [beep(), silence(0.45)]
        t += 0.54
        rows.append(f"\n**{si}. {title}** (beep at {t - 0.54:.1f} s)\n")
        for k, (kind, name) in enumerate(items):
            x = load(kind, name)
            label = name.replace("_01", "") if kind == "sfx" else name
            what = f'"{TEXT[name]}"' if kind == "vo" else ""
            rows.append(f"- {t:5.1f} s  `{label}` {what}")
            parts.append(x)
            t += len(x) / SR
            gap = 0.25 if (kind == "sfx" and name.endswith("_Cast_01")) else 0.55
            parts.append(silence(gap))
            t += gap
        parts.append(silence(0.4))
        t += 0.4
    y = np.concatenate(parts)
    y = y / max(1.0, float(np.abs(y).max()) / 0.89)
    mp3 = os.path.join(OUTDIR, "Reflections_audio_reel.mp3")
    ok = write_mp3(mp3, y)
    if not ok:
        mp3 = mp3[:-4] + ".wav"
        A.write_wav(mp3, y, SR)
    md = os.path.join(OUTDIR, "reel_contents.md")
    open(md, "w", encoding="utf-8").write(
        f"# Reflections audio reel ({len(y) / SR:.0f} s)\n\nListening-pass reel built from the processed jam audio "
        "(the same leveled files that are imported in /Game/Audio/Jam). Each section starts with a short beep.\n"
        + "\n".join(rows) + "\n")
    print(mp3, os.path.getsize(mp3), f"{len(y) / SR:.1f}s")


if __name__ == "__main__":
    main()

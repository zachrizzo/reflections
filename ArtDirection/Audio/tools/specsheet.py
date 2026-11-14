"""specsheet.py OUT.png file1.wav file2.wav ... -> grid of log-frequency spectrograms + waveform envelopes (for eyeballing)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw
import audiolib as A

W, H, COLS = 360, 150, 3


def spec_img(x, sr, maxdur):
    m = x if x.ndim == 1 else x.mean(axis=1)
    nfft, hop = 1024, 256
    n = 1 + max(0, (len(m) - nfft) // hop)
    if n < 2:
        m = np.pad(m, (0, nfft * 2))
        n = 1 + (len(m) - nfft) // hop
    idx = np.arange(nfft)[None, :] + hop * np.arange(n)[:, None]
    S = np.abs(np.fft.rfft(m[idx] * np.hanning(nfft), axis=1)) + 1e-9
    f = np.fft.rfftfreq(nfft, 1 / sr)
    rows = np.geomspace(40, sr / 2, H - 30)
    fi = np.clip(np.searchsorted(f, rows), 0, len(f) - 1)
    db = 20 * np.log10(S[:, fi])
    db = np.clip((db - db.max() + 70) / 70, 0, 1)
    cols = int(W * min(1.0, (len(m) / sr) / maxdur))
    ti = np.clip((np.arange(max(cols, 1)) / max(cols, 1) * n).astype(int), 0, n - 1)
    img = np.zeros((H - 30, W, 3), np.uint8)
    v = db[ti].T[::-1]
    img[:, : len(ti), 0] = (255 * np.clip(v * 1.6 - 0.3, 0, 1)).astype(np.uint8)
    img[:, : len(ti), 1] = (255 * np.clip(v * 1.4 - 0.6, 0, 1)).astype(np.uint8)
    img[:, : len(ti), 2] = (255 * np.clip(v * 2.0, 0, 1) * (1 - v) ).astype(np.uint8)
    return img


def main(out, files):
    maxdur = 3.0
    rows = (len(files) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * W, rows * H), (20, 20, 20))
    dr = ImageDraw.Draw(sheet)
    for k, p in enumerate(files):
        x, sr = A.decode(p)
        r, c = divmod(k, COLS)
        sheet.paste(Image.fromarray(spec_img(x, sr, maxdur)), (c * W, r * H + 30))
        e = A.env_db(x if x.ndim == 1 else x.mean(axis=1), sr, 10)
        ys = np.clip((e + 60) / 60, 0, 1)
        pts = [(c * W + int(i * W * 0.01 / maxdur), r * H + 28 - int(18 * y)) for i, y in enumerate(ys) if i * 0.01 < maxdur]
        if len(pts) > 1:
            dr.line(pts, fill=(120, 220, 120))
        dr.text((c * W + 4, r * H + 2), os.path.basename(p)[:44] + f"  {len(x) / sr:.2f}s", fill=(230, 230, 230))
    sheet.save(out)
    print(out, sheet.size)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])

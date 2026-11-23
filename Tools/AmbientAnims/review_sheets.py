"""review_sheets.py [category numbers...]

Reads Saved/KimodoAmbient/analysis/<NN>_<Category>.json (written by editor/amb_analyze.py), scores every clip and
draws a stick-figure contact sheet per category to Saved/KimodoAmbient/sheets/<NN>_<Category>.png.
Scores go to Saved/KimodoAmbient/analysis/scores.json (merged across runs).

Scores (cm, cm/s; component space, so the clip is in place by construction)
  energy      mean speed of hands, head and feet
  hand_peak   95th percentile hand speed
  foot_slide  95th percentile horizontal speed of a foot while it is planted (within 4 cm of its lowest point)
  pelvis_xy   how far the pelvis wanders horizontally (max distance from its start)
  pelvis_drop how far the pelvis sits below its standing height at frame 0 (seated, crouched, kneeling)
  seam        mean joint distance between the first and last frame (for loops: what the crossfade must hide)

Flags
  FROZEN?  energy under 4 and hand_peak under 20 on a clip the catalog does not mark still=True: the prompt asked
           for an action and the take came out as a held pose
  SLIDE    foot_slide over 25: a planted foot skates
  SEAM     a loop whose seam is over 20 cm
"""
import glob
import json
import math
import os
import sys

import numpy as np
import ambient_catalog as AC
from PIL import Image, ImageDraw, ImageFont

PROJECT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BASE = os.path.join(PROJECT, 'Saved', 'KimodoAmbient')
EDGES = [('pelvis', 'spine_03'), ('spine_03', 'spine_05'), ('spine_05', 'neck_01'), ('neck_01', 'head'),
         ('spine_05', 'clavicle_l'), ('clavicle_l', 'upperarm_l'), ('upperarm_l', 'lowerarm_l'), ('lowerarm_l', 'hand_l'),
         ('spine_05', 'clavicle_r'), ('clavicle_r', 'upperarm_r'), ('upperarm_r', 'lowerarm_r'), ('lowerarm_r', 'hand_r'),
         ('pelvis', 'thigh_l'), ('thigh_l', 'calf_l'), ('calf_l', 'foot_l'), ('foot_l', 'ball_l'),
         ('pelvis', 'thigh_r'), ('thigh_r', 'calf_r'), ('calf_r', 'foot_r'), ('foot_r', 'ball_r')]
LEFT = {'clavicle_l', 'upperarm_l', 'lowerarm_l', 'hand_l', 'thigh_l', 'calf_l', 'foot_l', 'ball_l'}
COLS = 8
STILL = {(cat, c['id']): c['still'] for cat, _d, clips in AC.CATEGORIES for c in clips}
CELL = 150


def score(clip, bones, fps, step):
    P = np.array(clip['frames'], dtype=float)  # frames x bones x 3
    ix = {b: i for i, b in enumerate(bones)}
    dt = step / fps
    v = np.linalg.norm(np.diff(P, axis=0), axis=2) / dt  # frames-1 x bones
    tips = [ix[b] for b in ('hand_l', 'hand_r', 'head', 'foot_l', 'foot_r')]
    hands = [ix['hand_l'], ix['hand_r']]
    slide = []
    for b in ('ball_l', 'ball_r'):
        z = P[:, ix[b], 2]
        planted = z[1:] < z.min() + 4.0
        h = np.linalg.norm(np.diff(P[:, ix[b], :2], axis=0), axis=1) / dt
        if planted.any():
            slide.append(np.percentile(h[planted], 95))
    pel = P[:, ix['pelvis']]
    return {
        'energy': round(float(v[:, tips].mean()), 1),
        'hand_peak': round(float(np.percentile(v[:, hands], 95)), 0),
        'foot_slide': round(float(max(slide) if slide else 0.0), 1),
        'pelvis_xy': round(float(np.linalg.norm(pel[:, :2] - pel[0, :2], axis=1).max()), 1),
        'pelvis_drop': round(float(pel[0, 2] - pel[:, 2].min()), 1) if pel[0, 2] > 80 else round(float(100 - pel[:, 2].min()), 1),
        'pelvis_z0': round(float(pel[0, 2]), 1),
        'seam': round(float(np.linalg.norm(P[0] - P[-1], axis=1).mean()), 1),
        'seconds': round(clip['keys'] / fps, 2),
    }


def flags(s, kind, still=False):
    out = []
    if not still and s['energy'] < 4 and s['hand_peak'] < 20:
        out.append('FROZEN?')
    if s['foot_slide'] > 25:
        out.append('SLIDE')
    if kind == 'loop' and s['seam'] > 20:
        out.append('SEAM')
    return out


def project(p, yaw=math.radians(35)):
    # Oblique view of component space: the MetaHuman faces +Y, so look from the front-right.
    x, y, z = p
    u = x * math.cos(yaw) - y * math.sin(yaw)
    return u, z


def sheet(data, scores, out_png):
    bones = data['bones']
    ix = {b: i for i, b in enumerate(bones)}
    clips = list(data['clips'].items())
    label_w = 300
    W, H = label_w + COLS * CELL, len(clips) * CELL + 30
    img = Image.new('RGB', (W, H), (250, 250, 247))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype('arial.ttf', 13)
        small = ImageFont.truetype('arial.ttf', 11)
    except OSError:
        font = small = ImageFont.load_default()
    d.text((8, 8), '%s - %d clips (stick figures every ~1.1 s, viewed from the front-right; blue = left side)'
           % (data['category'], len(clips)), font=font, fill=(40, 40, 40))
    for r, (cid, clip) in enumerate(clips):
        y0 = 30 + r * CELL
        s = scores[cid]
        fl = s['flags']
        d.line([(0, y0), (W, y0)], fill=(215, 215, 210))
        d.text((8, y0 + 6), cid, font=font, fill=(20, 20, 20))
        d.text((8, y0 + 24), '%s  %.1f s' % (clip['kind'], s['seconds']), font=small, fill=(90, 90, 90))
        d.text((8, y0 + 40), 'energy %.0f  hand %.0f  slide %.0f' % (s['energy'], s['hand_peak'], s['foot_slide']),
               font=small, fill=(90, 90, 90))
        d.text((8, y0 + 54), 'pelvis drift %.0f  drop %.0f  seam %.0f' % (s['pelvis_xy'], s['pelvis_drop'], s['seam']),
               font=small, fill=(90, 90, 90))
        if fl:
            d.text((8, y0 + 70), ' '.join(fl), font=font, fill=(200, 40, 30))
        first = clip['prompts'][0][1]
        words, line, lines = first.split(), '', []
        for w_ in words:
            if len(line) + len(w_) > 46:
                lines.append(line)
                line = ''
            line += w_ + ' '
        lines.append(line)
        for k, ln in enumerate(lines[:3]):
            d.text((8, y0 + 90 + 13 * k), ln, font=small, fill=(120, 120, 120))
        F = clip['frames']
        picks = [round(i * (len(F) - 1) / (COLS - 1)) for i in range(COLS)]
        for c, fi in enumerate(picks):
            cx, base = label_w + c * CELL + CELL / 2, y0 + CELL - 12
            scale = (CELL - 24) / 185.0
            pts = {b: project(F[fi][ix[b]]) for b in bones}
            for a, b in EDGES:
                (u1, z1), (u2, z2) = pts[a], pts[b]
                col = (60, 110, 200) if (a in LEFT or b in LEFT) else (60, 60, 60)
                d.line([(cx + u1 * scale, base - z1 * scale), (cx + u2 * scale, base - z2 * scale)], fill=col, width=3)
            hu, hz = pts['head']
            d.ellipse([cx + hu * scale - 7, base - hz * scale - 16, cx + hu * scale + 7, base - hz * scale - 2],
                      outline=(60, 60, 60), width=2)
            d.line([(cx - 40, base), (cx + 40, base)], fill=(180, 180, 175))
            d.text((cx - 18, y0 + 4), '%.1fs' % (fi * data['step'] / data['fps']), font=small, fill=(150, 150, 150))
    img.save(out_png)


def main():
    want = {int(a) for a in sys.argv[1:]}
    os.makedirs(os.path.join(BASE, 'sheets'), exist_ok=True)
    sp = os.path.join(BASE, 'analysis', 'scores.json')
    allscores = json.load(open(sp)) if os.path.exists(sp) else {}
    for fn in sorted(glob.glob(os.path.join(BASE, 'analysis', '[0-9][0-9]_*.json'))):
        num = int(os.path.basename(fn)[:2])
        if want and num not in want:
            continue
        data = json.load(open(fn))
        scores = {cid: score(c, data['bones'], data['fps'], data['step']) for cid, c in data['clips'].items()}
        for cid, s in scores.items():
            s['flags'] = flags(s, data['clips'][cid]['kind'], STILL.get((data['category'], cid), False))
            allscores['%s/%s' % (data['category'], cid)] = s
        out = os.path.join(BASE, 'sheets', os.path.basename(fn)[:-5] + '.png')
        sheet(data, scores, out)
        print(out)
        for cid, s in scores.items():
            print('  %-18s energy %5.1f hand %4.0f slide %5.1f drift %5.1f drop %5.1f seam %5.1f %s' % (
                cid, s['energy'], s['hand_peak'], s['foot_slide'], s['pelvis_xy'], s['pelvis_drop'], s['seam'],
                ' '.join(s['flags'])))
    json.dump(allscores, open(sp, 'w'), indent=1)


if __name__ == '__main__':
    main()

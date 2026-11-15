"""Writes the geometry check's suggested camera positions (Saved/CinematicsTest/geometry.json, from
test_cutscenes_pie.py geometry) into CAMERA_FIX in cutscene_defs.py, and the fix list into
ArtDirection/Cinematics/camera_fixes.md. Run outside the editor: python Tools/Cinematics/apply_geometry_fixes.py"""
import json
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
REPORT = PROJECT / 'Saved' / 'CinematicsTest' / 'geometry.json'
DEFS = Path(__file__).resolve().parent / 'cutscene_defs.py'
OUT = PROJECT / 'ArtDirection' / 'Cinematics' / 'camera_fixes.md'


def main():
    report = json.loads(REPORT.read_text())
    fixes, rows = {}, []
    for name, entry in report.items():
        if not isinstance(entry, dict) or 'keys' not in entry:
            continue
        for row in entry['keys']:
            fix = row['fix']
            rows.append('| %s | %d %s | key %d | %s | %s | %s |' % (
                name, row['shot'] + 1, row['label'], row['key'], tuple(row['pos']), entry.get('marker') or 'hero fallback',
                'cannot clear: keep, re-author by hand' if fix == 'unfixable' else 'moved to %s' % (tuple(fix),)))
            if fix != 'unfixable':
                fixes[(name, row['shot'], row['key'])] = tuple(fix)
    src = DEFS.read_text(encoding='utf-8')
    body = 'CAMERA_FIX = {\n' + ''.join('    %r: %r,\n' % (k, v) for k, v in sorted(fixes.items())) + '}\n'
    src = re.sub(r'CAMERA_FIX = \{.*?\n\}\n|CAMERA_FIX = \{\}\n', body, src, count=1, flags=re.S)
    DEFS.write_text(src, encoding='utf-8')
    OUT.write_text('# Camera fixes on %s\n\nFrom `test_cutscenes_pie.py geometry`: each camera key placed at the map\'s anchor, checked '
                   'for being inside geometry or losing sight of its subject, and pulled toward the subject until clear. '
                   'Applied in `CAMERA_FIX` (cutscene_defs.py).\n\n| Cutscene | Shot | Key | Was (anchor cm) | Anchor | Fix |\n'
                   '|---|---|---|---|---|---|\n%s\n' % (report.get('map', '?'), '\n'.join(rows) or '| (none) | | | | | |'),
                   encoding='utf-8')
    print('%d fixes, %d rows -> %s' % (len(fixes), len(rows), OUT))


if __name__ == '__main__':
    main()

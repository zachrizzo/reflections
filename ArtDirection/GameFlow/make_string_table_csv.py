"""Writes ArtDirection/GameFlow/ST_GameFlowText.csv from the built-in defaults in Source/reflections/GameFlow.

Every FLOWTEXT("Key", "Default") in the game-flow sources becomes a row, plus the multi-line credits entries. Import
the CSV as /Game/UI/ST_GameFlowText (EditorToolset.StringTableToolset.ImportFile, bReplaceExisting) to rebuild the
table, or just edit the asset in the editor: the code reads the asset, and these defaults are only the fallback.
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'Source' / 'reflections' / 'GameFlow'
OUT = Path(__file__).resolve().parent / 'ST_GameFlowText.csv'

rows = {}
pattern = re.compile(r'FLOWTEXT\("([^"]+)",\s*"((?:[^"\\]|\\.)*)"\)')
for path in sorted(SRC.glob('*.cpp')):
    for key, value in pattern.findall(path.read_text(encoding='utf-8')):
        rows.setdefault(key, value)

# Multi-line entries read with ReflectionsFlowText::GetLines (one credits line per row of text).
multi = re.compile(r'GetLines\(TEXT\("([^"]+)"\),\s*LOCTEXT\("[^"]+",\s*((?:\s*"(?:[^"\\]|\\.)*")+)\)\)', re.S)
for path in sorted(SRC.glob('*.cpp')):
    for key, parts in multi.findall(path.read_text(encoding='utf-8')):
        value = ''.join(re.findall(r'"((?:[^"\\]|\\.)*)"', parts))
        rows.setdefault(key, value)

with OUT.open('w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f, quoting=csv.QUOTE_ALL)
    w.writerow(['Key', 'SourceString'])
    for key in sorted(rows):
        # Keep C++ escapes (\n) as written: the string table importer un-escapes them. \uXXXX (the credits' (c) and
        # middle dots) it does not, so those become the characters themselves.
        value = re.sub(r'\\u([0-9A-Fa-f]{4})', lambda m: chr(int(m.group(1), 16)), rows[key])
        w.writerow([key, value.replace("\\'", "'").replace('\\"', '"')])
print('%d rows -> %s' % (len(rows), OUT))

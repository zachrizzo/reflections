"""Guarded, original source-art Merchant Gate; does not use Unreal or Blender.

The real run is deliberately separate from the tiny in-memory tests. It writes
only a new, review-only OBJ bundle under Saved/CityPCG. No map placement,
collision, navigation, or Unreal asset is made by this script.
"""

import argparse
import ctypes
import hashlib
import importlib.util
import json
import math
import re
import sys
from pathlib import Path

from audit_merchant_gate import audit_geometry


PROJECT = Path(__file__).resolve().parents[2]
MARKET_GUARD_PATH = PROJECT / 'ArtDirection/CityPCG/MedievalOpening/MarketDressingKit/build_market_dressing.py'
MARKET_GUARD_HASH = hashlib.sha256(MARKET_GUARD_PATH.read_bytes()).hexdigest()
_guard_spec = importlib.util.spec_from_file_location('_market_dressing_process_guard', MARKET_GUARD_PATH)
if _guard_spec is None or _guard_spec.loader is None:
    raise RuntimeError('Cannot load the shared market-kit process guard')
market_guard = importlib.util.module_from_spec(_guard_spec)
_guard_spec.loader.exec_module(market_guard)
if hashlib.sha256(MARKET_GUARD_PATH.read_bytes()).hexdigest() != MARKET_GUARD_HASH:
    raise RuntimeError('Shared market-kit process guard changed while loading')
REFERENCE = PROJECT / 'ArtDirection/CityPCG/MedievalOpening/Landmarks/MerchantGate/References/merchant_gate_imagegen_v1.png'
REFERENCE_HASH = '0e5d8a11fc11a94537d44cf8c370940cb88782e4e86312a5ffde6f98811b324c'
MATERIALS = {
    'Fieldstone': ((.46, .40, .32), 'ArtDirection/CityPCG/MedievalOpening/Textures/T_GLMedieval_Fieldstone.png', '845a6082959cf5429e024eb86d05db087114b963cb1170533a4c989701cf03b1'),
    'WarmPlaster': ((.64, .56, .43), 'ArtDirection/CityPCG/MedievalOpening/Textures/T_GLMedieval_WarmPlaster.png', '9e070704a80237ba6c17e35392f6060672710af53127565b066682ab246350d5'),
    'Oak': ((.15, .088, .05), 'ArtDirection/CityPCG/MedievalOpening/Textures/T_GLMedieval_Oak.png', '30f2d82d684242c658fdfe217b26d1c9aa680c240a187ea81cea0308ff20159a'),
    'WeatheredOak': ((.21, .16, .11), 'ArtDirection/CityPCG/MedievalOpening/Textures/T_GLMedieval_WeatheredOak.png', 'b6dd5807706308ffabb22f9afcf2e45836c4ae34c9f0951397c92989dcf46425'),
    'ClayTile': ((.23, .104, .07), 'ArtDirection/CityPCG/MedievalOpening/Textures/T_GLMedieval_ClayTile.png', '4276741826d160b3c00bd3d053eb174849b328a76ecd22caa01f1cfc3445afaf'),
    'LeadedGlass': ((.045, .075, .080), None, None),
    'Lead': ((.055, .055, .050), None, None),
}
RUN_NAME = re.compile(r'[a-z0-9][a-z0-9_-]{0,47}\Z')
MIN_PHYSICAL = 4 * 2**30
MIN_COMMIT = 10 * 2**30
BLOCKED_PROCESSES = frozenset({
    'cl.exe', 'gcc.exe', 'g++.exe', 'cc1.exe', 'cc1plus.exe', 'clang.exe',
    'clang-cl.exe', 'clang++.exe', 'link.exe', 'msbuild.exe', 'dotnet.exe',
    'unrealbuildtool.exe', 'ninja.exe', 'cmake.exe', 'shadercompileworker.exe',
    'livecodingconsole.exe',
})


def digest(path):
    sha = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(256 * 1024), b''):
            sha.update(block)
    return sha.hexdigest()


def memory_headroom():
    if sys.platform != 'win32':
        raise RuntimeError('The source-art guard requires Windows memory accounting')

    class Status(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong),
                    ('total_physical', ctypes.c_ulonglong), ('free_physical', ctypes.c_ulonglong),
                    ('total_page', ctypes.c_ulonglong), ('free_page', ctypes.c_ulonglong),
                    ('total_virtual', ctypes.c_ulonglong), ('free_virtual', ctypes.c_ulonglong),
                    ('extended', ctypes.c_ulonglong)]
    status = Status()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise RuntimeError('Cannot read Windows memory headroom')
    return status.free_physical, status.free_page


def process_status():
    """Reuse the market-kit identity check and keep all prior gate blockers."""
    records = market_guard.process_snapshot()
    editor, blockers = market_guard.classify_processes(records)
    # The market kit recognizes the exact Gigabyte GCC parent/child identity.
    # Its compiler list is broader than ours, but preserve our extra names even
    # if the shared list changes later. A removed GCC exemption fails closed.
    extra = BLOCKED_PROCESSES - market_guard.COMPILERS
    blockers.extend(f"{row['name'].casefold()} (pid {row['pid']})" for row in records
                    if row['name'].casefold() in extra)
    return editor, sorted(blockers)


def current_train_status(text):
    """The first train header controls; a malformed newest header fails closed."""
    for line in text.splitlines():
        header = re.search(r'\bTRAIN\s*#\s*\d+\b', line, re.IGNORECASE)
        if header:
            status = re.match(r'\s+([A-Z]+)\b', line[header.end():], re.IGNORECASE)
            if not status:
                raise RuntimeError('The latest build train status is malformed')
            return status.group(1).upper()
    raise RuntimeError('Cannot determine the latest build train status')


def train_status():
    try:
        text = (PROJECT / 'Saved/PIE_QUEUE.md').read_text(encoding='utf-8-sig')
    except OSError as exc:
        raise RuntimeError('Cannot read the shared build queue') from exc
    return current_train_status(text)


def light_work_guard():
    if digest(MARKET_GUARD_PATH) != MARKET_GUARD_HASH:
        raise RuntimeError('Shared market-kit process guard changed during this run')
    physical, commit = memory_headroom()
    if physical < MIN_PHYSICAL or commit < MIN_COMMIT:
        raise RuntimeError(f'Need 4/10 GiB physical/commit; available {physical/2**30:.2f}/{commit/2**30:.2f}')
    editor, blockers = process_status()
    if not editor:
        raise RuntimeError('The shared Unreal Editor has not returned')
    if blockers:
        raise RuntimeError(f'Compiler or build process present: {blockers}')
    if train_status() != 'LOADED':
        raise RuntimeError('The current shared build train is not LOADED')
    return {'physical_bytes': physical, 'commit_bytes': commit}


def normal(points):
    a, b, c = points
    u = tuple(b[i] - a[i] for i in range(3))
    v = tuple(c[i] - a[i] for i in range(3))
    cross = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
    size = math.sqrt(sum(x*x for x in cross))
    if not math.isfinite(size) or size < 1e-10:
        raise ValueError('Degenerate or non-finite triangle')
    return tuple(x/size for x in cross)


class Mesh:
    def __init__(self):
        self.faces = []

    def triangle(self, a, b, c, role, roof_uv=None):
        points = (tuple(a), tuple(b), tuple(c))
        if role not in MATERIALS or not all(math.isfinite(x) for p in points for x in p):
            raise ValueError('Unknown role or invalid coordinate')
        n = normal(points)
        if roof_uv is None:
            axis = max(range(3), key=lambda i: abs(n[i]))
            u, v = ((1, 2), (0, 2), (0, 1))[axis]
            uv = tuple((p[u], p[v]) for p in points)
        else:
            uv = tuple(roof_uv(p) for p in points)
        self.faces.append((role, points, uv, n))

    def quad(self, a, b, c, d, role, roof_uv=None):
        self.triangle(a, b, c, role, roof_uv)
        self.triangle(a, c, d, role, roof_uv)

    def box(self, xmin, xmax, ymin, ymax, zmin, zmax, role):
        if not (xmin < xmax and ymin < ymax and zmin < zmax):
            raise ValueError('Box must have positive size')
        a, b, c, d = (xmin,ymin,zmin), (xmin,ymax,zmin), (xmin,ymax,zmax), (xmin,ymin,zmax)
        e, f, g, h = (xmax,ymin,zmin), (xmax,ymax,zmin), (xmax,ymax,zmax), (xmax,ymin,zmax)
        for points in ((d,c,b,a), (e,f,g,h), (a,e,h,d), (b,c,g,f), (a,b,f,e), (d,h,g,c)):
            self.quad(*points, role)

    def prism_yz(self, polygon, x0, x1, role):
        # Convex CCW contour in the Y/Z plane, extruded along X.
        if len(polygon) != 4 or not x0 < x1:
            raise ValueError('Expected an extruded convex quadrilateral')
        left = [(x0, y, z) for y, z in polygon]
        right = [(x1, y, z) for y, z in polygon]
        self.quad(*reversed(left), role)
        self.quad(*right, role)
        for i in range(4):
            j = (i + 1) % 4
            self.quad(left[i], left[j], right[j], right[i], role)

    def beam_yz(self, x0, x1, a, b, width, role='Oak'):
        dy, dz = b[0]-a[0], b[1]-a[1]
        length = math.hypot(dy, dz)
        if length < 1e-8:
            raise ValueError('Zero-length beam')
        py, pz = -dz * width/(2*length), dy * width/(2*length)
        polygon = [(a[0]-py,a[1]-pz), (b[0]-py,b[1]-pz),
                   (b[0]+py,b[1]+pz), (a[0]+py,a[1]+pz)]
        self.prism_yz(polygon, x0, x1, role)

    def triangles(self):
        return (points for _, points, _, _ in self.faces)


def arch_height(y):
    # A pointed cusp and curved shoulders. The piecewise-linear underside is
    # built above the 2.5 x 2.7 m clearance and spans the whole gate depth.
    return 2.70 + .90 * math.sqrt(max(0., 1. - abs(y)/1.75))


def make_masonry(mesh, detail):
    mesh.box(-3.25, 3.25, -6.35, -1.75, 0, 3.88, 'Fieldstone')
    mesh.box(-3.25, 3.25, 1.75, 6.35, 0, 3.88, 'Fieldstone')
    steps = 4 if detail == 'tiny' else 16
    knots = [-1.75 + 3.50*i/(2*steps) for i in range(2*steps+1)]
    for left, right in zip(knots, knots[1:]):
        low, high = arch_height(left), arch_height(right)
        mesh.prism_yz([(left,low),(right,high),(right,3.88),(left,3.88)], -3.25, 3.25, 'Fieldstone')
        # Individual facing stones are above the lumen, on both entrances.
        for x0, x1 in ((3.25,3.32),(-3.32,-3.25)):
            mesh.prism_yz([(left,low+.004),(right,high+.004),(right,high+.22),(left,low+.22)], x0, x1, 'Fieldstone')
    # Raised quoin blocks and facing courses provide depth to the stonework.
    rows = 3 if detail == 'tiny' else 8
    for row in range(rows):
        z0, z1 = row * 3.55/rows + .025, (row+1)*3.55/rows - .025
        for side in (-1, 1):
            for k in range(2 if detail == 'tiny' else 6):
                y0 = 1.86 + k*.70 + (.12 if row % 2 else 0)
                y1 = min(y0+.62, 6.30)
                if y0 >= y1:
                    continue
                lo, hi = (y0,y1) if side > 0 else (-y1,-y0)
                for x0,x1 in ((3.25,3.29),(-3.29,-3.25)):
                    mesh.box(x0,x1,lo,hi,z0,z1,'Fieldstone')


def windows(mesh, center, bottom, upper=False):
    half = .75 if upper else .68
    height = .95 if upper else 1.05
    x0, x1 = 3.27, 3.31
    mesh.box(x0,x1,center-half,center+half,bottom,bottom+height,'LeadedGlass')
    for y in (center-half, center, center+half):
        mesh.box(3.31,3.36,y-.045,y+.045,bottom-.055,bottom+height+.055,'Oak')
    for z in (bottom,bottom+height):
        mesh.box(3.31,3.37,center-half-.07,center+half+.07,z-.045,z+.045,'Oak')
    # Fine crossing lead strips read as glazing rather than a flat black patch.
    for offset in (-.45, -.15, .15, .45):
        mesh.beam_yz(3.312,3.322,(center+offset-.18,bottom+.08),
                     (center+offset+.18,bottom+height-.08),.018,'Lead')
        mesh.beam_yz(3.323,3.333,(center+offset+.18,bottom+.08),
                     (center+offset-.18,bottom+height-.08),.018,'Lead')
    if not upper:
        for sign in (-1,1):
            a, b = center + sign*(half+.10), center + sign*(half+.58)
            lo, hi = sorted((a,b))
            mesh.box(3.29,3.36,lo,hi,bottom-.03,bottom+height+.03,'WeatheredOak')
            mesh.beam_yz(3.36,3.39,(lo+.04,bottom+.08),(hi-.04,bottom+height-.08),.055,'Oak')


def make_upper(mesh):
    mesh.box(-3.28, 3.28, -6.38, 6.38, 3.88, 5.70, 'WarmPlaster')
    for x0,x1 in ((3.28,3.34),(-3.34,-3.28)):
        for z in (3.90,5.62):
            mesh.box(x0,x1,-6.39,6.39,z-.07,z+.07,'Oak')
        for y in (-6.25,-4.9,-3.2,-1.55,0,1.55,3.2,4.9,6.25):
            mesh.box(x0,x1,y-.055,y+.055,3.94,5.65,'Oak')
    for y in (-5.7,-2.3,2.3,5.7):
        mesh.beam_yz(3.34,3.40,(y-.38,3.95),(y+.38,5.60),.12,'Oak')
        mesh.box(3.26,3.45,y-.13,y+.13,3.55,3.90,'Oak')
    for center in (-4.10,4.10):
        windows(mesh,center,1.05)
        windows(mesh,center,4.24,True)
    windows(mesh,0,4.24,True)
    # Front-facing gable over the carriage opening.
    base = 7.40 - 1.60*3.25/3.50
    peak = base + 1.50*3.25/3.50
    mesh.triangle((3.28,-1.40,base),(3.28,1.40,base),(3.28,0,peak),'WarmPlaster')
    for y in (-1.30,-.65,0,.65,1.30):
        top = base + (peak-base)*(1-abs(y)/1.40)
        if top > base+.08:
            mesh.box(3.29,3.35,y-.035,y+.035,base,top,'Oak')
    mesh.beam_yz(3.30,3.38,(-1.40,base),(0,peak),.13,'Oak')
    mesh.beam_yz(3.30,3.38,(0,peak),(1.40,base),.13,'Oak')


def make_roof(mesh, detail):
    # Existing 12/13-column texture, 1.984375 m per U repeat: mean tile width
    # 158.75 mm. V's 1.32 m slope repeat is an unreviewed exposure estimate.
    slope = 1.60/3.50
    roof_uv = lambda p: (p[1]/1.984375, p[0]*math.sqrt(1+slope*slope)/1.32)
    def zmain(x):
        return 7.40 - slope*abs(x)
    def main_patch(x0,x1,y0,y1):
        mesh.quad((x0,y0,zmain(x0)),(x1,y0,zmain(x1)),
                  (x1,y1,zmain(x1)),(x0,y1,zmain(x0)), 'ClayTile',roof_uv)
    main_patch(-3.50,0,-6.50,6.50)
    main_patch(0,3.50,-6.50,-1.40)
    main_patch(0,3.50,1.40,6.50)
    # Junction is meshed in strips rather than overlaying the main roof.
    xsteps = 2 if detail == 'tiny' else 8
    ysteps = 2 if detail == 'tiny' else 8
    gable_uv = lambda p: (p[0]/1.984375, p[1]/1.32)
    def cross_z(x,y):
        return zmain(x) + 1.50*(x/3.50)*(1-abs(y)/1.40)
    for xi in range(xsteps):
        x0,x1 = 3.50*xi/xsteps,3.50*(xi+1)/xsteps
        for yi in range(ysteps):
            y0,y1 = -1.40+2.80*yi/ysteps,-1.40+2.80*(yi+1)/ysteps
            mesh.quad((x0,y0,cross_z(x0,y0)),(x1,y0,cross_z(x1,y0)),
                      (x1,y1,cross_z(x1,y1)),(x0,y1,cross_z(x0,y1)),'ClayTile',gable_uv)
    for y in (-4.35,4.35):
        # ClayTile bricks retain ordinary mapping: only the roof uses roof_uv.
        mesh.box(-1.42,-.86,y-.29,y+.29,6.65,7.91,'Fieldstone')
        rows = 2 if detail == 'tiny' else 8
        for row in range(rows):
            lo,hi = 6.66+row*1.18/rows,6.66+(row+1)*1.18/rows-.015
            mesh.box(-1.44,-.84,y-.30,y+.30,lo,hi,'ClayTile')
        mesh.box(-1.48,-.80,y-.34,y+.34,7.91,8.00,'Fieldstone')


def build_gate(detail='full', checkpoint=None):
    if detail not in {'tiny','full'}:
        raise ValueError('Unknown geometry detail')
    if checkpoint is None:
        checkpoint = light_work_guard if detail == 'full' else lambda: None
    mesh = Mesh()
    for stage in (make_masonry, make_upper, make_roof):
        checkpoint()
        if stage is make_upper:
            stage(mesh)
        else:
            stage(mesh, detail)
    checkpoint()
    return mesh


def write_obj(stream, mesh, checkpoint=lambda: None):
    stream.write('# Merchant Gate original procedural source; local metres, +X front, +Z up.\n')
    stream.write('# Unreviewed source; no collision, navigation, or game placement.\n')
    stream.write('mtllib MerchantGate.mtl\n')
    for index, (role, points, uvs, n) in enumerate(mesh.faces):
        if index % 250 == 0:
            checkpoint()
        for p in points:
            stream.write('v ' + ' '.join(repr(x) for x in p) + '\n')
        for uv in uvs:
            stream.write('vt ' + ' '.join(repr(x) for x in uv) + '\n')
        stream.write('vn ' + ' '.join(repr(x) for x in n) + '\n')
        stream.write('usemtl M_GLMedieval_' + role + '\n')
        v = 3*index+1
        stream.write('f ' + ' '.join(f'{v+i}/{v+i}/{index+1}' for i in range(3)) + '\n')


def write_mtl(stream):
    for role, (rgb, texture, _) in MATERIALS.items():
        stream.write('newmtl M_GLMedieval_' + role + '\n')
        color = (1.,1.,1.) if texture else rgb
        stream.write('Kd ' + ' '.join(str(v) for v in color) + '\n')
        if texture:
            stream.write('map_Kd Textures/' + Path(texture).name + '\n')
        stream.write('\n')


def read_obj(stream):
    """Independent strict streaming readback, including coordinates, UVs and slots."""
    vertices, uvs, normals, faces, role = [], [], [], [], None
    library = None
    for line in stream:
        fields = line.split()
        if not fields or fields[0].startswith('#'):
            continue
        kind = fields[0]
        if kind == 'mtllib' and fields == ['mtllib','MerchantGate.mtl'] and library is None:
            library = fields[1]
        elif kind == 'v' and len(fields) == 4:
            vertices.append(tuple(map(float,fields[1:])))
        elif kind == 'vt' and len(fields) == 3:
            uvs.append(tuple(map(float,fields[1:])))
        elif kind == 'vn' and len(fields) == 4:
            normals.append(tuple(map(float,fields[1:])))
        elif kind == 'usemtl' and len(fields) == 2 and fields[1].startswith('M_GLMedieval_'):
            role = fields[1][len('M_GLMedieval_'):]
            if role not in MATERIALS:
                raise ValueError('Unexpected material role')
        elif kind == 'f' and len(fields) == 4 and role is not None:
            corners = [tuple(int(v)-1 for v in c.split('/')) for c in fields[1:]]
            if any(len(c) != 3 or any(v < 0 for v in c) for c in corners):
                raise ValueError('Invalid face index')
            count = len(faces)
            if corners != [(3*count+i,3*count+i,count) for i in range(3)]:
                raise ValueError('Unexpected face, UV or normal ordering')
            try:
                points = tuple(vertices[c[0]] for c in corners)
                face_uv = tuple(uvs[c[1]] for c in corners)
                face_normals = tuple(normals[c[2]] for c in corners)
            except IndexError as exc:
                raise ValueError('Face index out of range') from exc
            if face_normals != (face_normals[0],)*3:
                raise ValueError('Unexpected split triangle normals')
            faces.append((role,points,face_uv,face_normals[0]))
        else:
            raise ValueError(f'Unexpected OBJ record: {kind}')
    if (library is None or not faces or len(vertices) != 3*len(faces)
            or len(uvs) != 3*len(faces) or len(normals) != len(faces)):
        raise ValueError('Incomplete OBJ')
    return faces


def verify_faces(actual, expected):
    if len(actual) != len(expected):
        raise ValueError('OBJ face count differs')
    for index, (found, source) in enumerate(zip(actual, expected)):
        if found != source or any(not math.isfinite(v) for uv in found[2] for v in uv):
            raise ValueError(f'OBJ geometry, UV, normal or material differs at face {index}')
        calculated = normal(found[1])
        if any(abs(a-b) > 1e-10 for a,b in zip(calculated,found[3])):
            raise ValueError(f'OBJ normal differs at face {index}')


def validate_inputs():
    if digest(REFERENCE) != REFERENCE_HASH:
        raise RuntimeError('ImageGen reference differs from its pinned hash')
    for role, (_, relative, expected) in MATERIALS.items():
        if relative and digest(PROJECT / relative) != expected:
            raise RuntimeError(f'{role} texture differs from its pinned hash')


def output_directory(name):
    if not RUN_NAME.fullmatch(name):
        raise ValueError('Choose a short lowercase run name with letters, digits, _ or -')
    saved = (PROJECT / 'Saved').resolve(strict=True)
    parent = (PROJECT / 'Saved/CityPCG').resolve(strict=True)
    if parent == saved or not parent.is_relative_to(saved):
        raise RuntimeError('The intended output parent is outside Saved')
    path = parent / ('MerchantGateProcedural_' + name)
    if path.exists() or path.is_symlink() or path.resolve().parent != parent:
        raise FileExistsError('Choose a new, non-redirected output directory')
    path.mkdir()
    if path.resolve(strict=True) != path or path.parent.resolve(strict=True) != parent:
        raise RuntimeError('Output directory changed or was redirected')
    return path


def ensure_output(path, parent):
    if path.resolve(strict=True) != path or path.parent.resolve(strict=True) != parent:
        raise RuntimeError('Output directory changed or was redirected')


def generate(name):
    """Write a fresh review-only bundle; incomplete output is never deleted."""
    light_work_guard()
    validate_inputs()
    light_work_guard()
    output = output_directory(name)
    parent = output.parent
    checkpoint = lambda: (ensure_output(output,parent), light_work_guard())
    mesh = build_gate(checkpoint=checkpoint)
    checkpoint()
    report = audit_geometry(mesh.triangles())
    if report['status'] != 'passed':
        raise RuntimeError(f'In-memory passage audit failed: {report["errors"]}')
    textures = output / 'Textures'
    textures.mkdir()
    for role, (_, relative, expected) in MATERIALS.items():
        if not relative:
            continue
        checkpoint()
        if textures.resolve(strict=True) != textures or textures.parent.resolve(strict=True) != output:
            raise RuntimeError('Texture output directory changed or was redirected')
        target = textures / Path(relative).name
        with (PROJECT / relative).open('rb') as source, target.open('xb') as dest:
            for block in iter(lambda: source.read(256*1024), b''):
                dest.write(block)
        if digest(target) != expected:
            raise RuntimeError(f'{role} copied texture failed hash verification')
    checkpoint()
    with (output/'MerchantGate.mtl').open('x',encoding='utf-8',newline='\n') as stream:
        write_mtl(stream)
    checkpoint()
    obj = output/'MerchantGate.obj'
    with obj.open('x',encoding='utf-8',newline='\n') as stream:
        write_obj(stream,mesh,checkpoint)
    checkpoint()
    with obj.open('r',encoding='utf-8') as stream:
        readback = read_obj(stream)
    verify_faces(readback,mesh.faces)
    reread_audit = audit_geometry(face[1] for face in readback)
    if reread_audit['status'] != 'passed' or reread_audit != report:
        raise RuntimeError('Read-back gate failed or changed the continuous passage audit')
    checkpoint()
    manifest = {'status':'unreviewed_source_not_gameplay',
                'source':'Original procedural mesh inspired by the pinned ImageGen reference',
                'reference_sha256':REFERENCE_HASH, 'script_sha256':digest(Path(__file__)),
                'audit_script_sha256':digest(PROJECT/'Tools/CityPCG/audit_merchant_gate.py'),
                'process_guard_script_sha256':MARKET_GUARD_HASH,
                'asset_sha256':digest(obj), 'mtl_sha256':digest(output/'MerchantGate.mtl'),
                'textures':{role:{'file':'Textures/'+Path(relative).name,'sha256':sha}
                            for role,(_,relative,sha) in MATERIALS.items() if relative},
                'axis':'local metres, +X front, +Z up, base-center pivot',
                'audit':report, 'collision':False, 'navigation':False, 'unreal_imported':False,
                'limitations':['Decorative windows are solid-backed', 'Not visually reviewed',
                               'No verified placement, collision, navigation or Unreal import',
                               'Roof course exposure is an unreviewed approximation']}
    with (output/'manifest.json').open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(manifest,stream,indent=2)
        stream.write('\n')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-name',required=True)
    args = parser.parse_args()
    try:
        print(generate(args.run_name))
    except (OSError,RuntimeError,ValueError) as exc:
        print(f'Deferred or incomplete: {exc}',file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

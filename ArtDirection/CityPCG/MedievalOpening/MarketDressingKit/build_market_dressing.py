"""Generate three small, review-only medieval London market source props.

Runs only in a released shared-machine window. It does not use Blender,
Unreal, or the GPU, and never changes an existing asset or output directory.
"""

import hashlib
import json
import math
import ntpath
import os
from pathlib import Path
import re
import secrets
import sys
import time
from datetime import datetime, timezone


PROJECT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUTPUT_PARENT = PROJECT / "Saved/CityPCG"
MAX_TRIANGLES = 2400
MAX_OUTPUT_BYTES = 12 * 1024**2
MAX_PRIVATE_BYTES = 160 * 1024**2
MAX_SECONDS = 30
BOARD_CENTER_Z = 0.77
BOARD_THICKNESS = 0.045
BOARD_UNDERSIDE_Z = BOARD_CENTER_Z - BOARD_THICKNESS / 2
COMPILERS = {"unrealbuildtool.exe", "dotnet.exe", "msbuild.exe", "cl.exe", "link.exe", "rc.exe",
             "shadercompileworker.exe", "cmake.exe", "ninja.exe", "make.exe", "clang.exe",
             "clang-cl.exe", "lld-link.exe", "gcc.exe", "g++.exe", "cc1.exe", "cc1plus.exe",
             "automationtool.exe", "unrealeditor-cmd.exe", "xgconsole.exe", "buildconsole.exe"}
GIGABYTE_GCC = r"C:\Program Files\GIGABYTE\Control Center\GCC.exe"
MATERIALS = {
    "M_MarketOak": (0.36, 0.21, 0.105),
    "M_MarketOakDark": (0.20, 0.105, 0.052),
    "M_MarketAsh": (0.61, 0.43, 0.25),
    "M_MarketIron": (0.12, 0.115, 0.10),
    "M_MarketIvy": (0.22, 0.33, 0.16),
    "M_MarketIvyLight": (0.34, 0.43, 0.21),
}


def memory_status():
    """Windows global available physical/commit and current process private bytes."""
    import ctypes
    from ctypes import wintypes
    if sys.platform != "win32":
        raise RuntimeError("The light-work process and memory guard requires Windows")

    class GlobalMemory(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD),
                    ("total_phys", ctypes.c_ulonglong), ("avail_phys", ctypes.c_ulonglong),
                    ("total_commit", ctypes.c_ulonglong), ("avail_commit", ctypes.c_ulonglong),
                    ("total_virtual", ctypes.c_ulonglong), ("avail_virtual", ctypes.c_ulonglong),
                    ("avail_extended", ctypes.c_ulonglong)]

    class ProcessMemory(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("page_faults", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in
            ("peak_working", "working", "peak_paged", "paged", "peak_nonpaged", "nonpaged",
             "pagefile", "peak_pagefile", "private")]

    system, process = GlobalMemory(), ProcessMemory()
    system.length, process.length = ctypes.sizeof(system), ctypes.sizeof(process)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(GlobalMemory)]
    kernel.GlobalMemoryStatusEx.restype = wintypes.BOOL
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessMemory), wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    if not kernel.GlobalMemoryStatusEx(ctypes.byref(system)) or not psapi.GetProcessMemoryInfo(
            kernel.GetCurrentProcess(), ctypes.byref(process), process.length):
        raise OSError(ctypes.get_last_error(), "Cannot verify process and system memory")
    return system.avail_phys, system.avail_commit, process.private


def process_snapshot():
    """Read process names, PIDs and parents in one Windows Toolhelp snapshot."""
    import ctypes
    from ctypes import wintypes
    if sys.platform != "win32":
        raise RuntimeError("The process snapshot requires Windows")

    class ProcessEntry(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD), ("pid", wintypes.DWORD),
                    ("heap_id", ctypes.c_size_t), ("module_id", wintypes.DWORD), ("threads", wintypes.DWORD),
                    ("parent_pid", wintypes.DWORD), ("priority", wintypes.LONG), ("flags", wintypes.DWORD),
                    ("image", wintypes.WCHAR * 260)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    for function in (kernel.Process32FirstW, kernel.Process32NextW):
        function.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
        function.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateToolhelp32Snapshot(0x00000002, 0)
    if handle is None or handle == ctypes.c_void_p(-1).value:
        raise OSError(ctypes.get_last_error(), "Cannot create shared-machine process snapshot")
    records = []
    try:
        entry = ProcessEntry()
        entry.size = ctypes.sizeof(entry)
        if not kernel.Process32FirstW(handle, ctypes.byref(entry)):
            raise OSError(ctypes.get_last_error(), "Cannot read shared-machine process snapshot")
        while True:
            records.append({"name": entry.image.casefold(), "pid": int(entry.pid), "parent_pid": int(entry.parent_pid)})
            if len(records) > 100000:
                raise RuntimeError("Process snapshot exceeds its bounded size")
            if not kernel.Process32NextW(handle, ctypes.byref(entry)):
                if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
                    raise OSError(ctypes.get_last_error(), "Process snapshot ended unexpectedly")
                break
    finally:
        kernel.CloseHandle(handle)
    return records


def process_identity(pid):
    """Read an instance's full image path and creation time, or return None."""
    import ctypes
    from ctypes import wintypes
    if sys.platform != "win32":
        return None
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                 ctypes.POINTER(wintypes.DWORD)]
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.GetProcessTimes.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        length = wintypes.DWORD(len(buffer))
        created, exited, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
        if (not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)) or
                not kernel.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited),
                                           ctypes.byref(kernel_time), ctypes.byref(user_time))):
            return None
        timestamp = (int(created.dwHighDateTime) << 32) | int(created.dwLowDateTime)
        if not buffer.value or not timestamp:
            return None
        return {"path": buffer.value, "created": timestamp}
    finally:
        kernel.CloseHandle(handle)


def classify_processes(records, identity=None):
    """Fail closed except for the independently identified Gigabyte instance."""
    identity = identity or process_identity
    if not isinstance(records, (list, tuple)) or not records:
        raise RuntimeError("Cannot inspect the shared-machine process snapshot")
    seen = set()
    for row in records:
        if (not isinstance(row, dict) or type(row.get("pid")) is not int or row["pid"] < 0 or
                type(row.get("parent_pid")) is not int or row["parent_pid"] < 0 or
                not isinstance(row.get("name"), str) or not row["name"] or row["pid"] in seen):
            raise RuntimeError("Malformed or duplicate process snapshot entry")
        seen.add(row["pid"])
    blocked = []
    for row in records:
        name = row["name"].casefold()
        if name not in COMPILERS:
            continue
        exempt = False
        if name == "gcc.exe":
            children = [child for child in records if child["name"].casefold() == "gbt_dl_lib.exe" and
                        child["parent_pid"] == row["pid"] and child["pid"] != row["pid"]]
            if children:
                try:
                    parent = identity(row["pid"])
                    if (parent and ntpath.normcase(ntpath.normpath(parent["path"])) == ntpath.normcase(GIGABYTE_GCC)
                            and type(parent["created"]) is int and parent["created"] > 0):
                        for child in children:
                            detail = identity(child["pid"])
                            if (detail and ntpath.basename(detail["path"]).casefold() == "gbt_dl_lib.exe" and
                                    type(detail["created"]) is int and detail["created"] >= parent["created"]):
                                exempt = True
                                break
                except (OSError, RuntimeError, ValueError, KeyError, TypeError):
                    exempt = False
        if not exempt:
            blocked.append(f"{name} (pid {row['pid']})")
    return any(row["name"].casefold() == "unrealeditor.exe" for row in records), blocked


def loaded_train():
    with (PROJECT / "Saved/PIE_QUEUE.md").open(encoding="utf-8-sig") as stream:
        for line in stream:
            header = re.match(r"^\s*!*\s*(?:\d{1,2}:\d{2}\s+)?TRAIN\s*#\s*(\d+)\b(.*)$", line, re.I)
            if not header:
                continue
            status = re.match(r"\s*:?\s*([A-Za-z_]+)\b", header.group(2))
            if not status or status.group(1).upper() != "LOADED":
                raise RuntimeError("Shared editor train is not LOADED")
            if re.search(r"\b(restarting|relaunching|building|compiling|editor\s+closed|test\s+cook)\b", line, re.I):
                raise RuntimeError("Queue indicates a build, cook, or editor restart")
            return header.group(1)
    raise RuntimeError("Cannot identify the leading shared editor train")


def no_restart_lease():
    """An ordinary PIE lease is allowed; a build/restart lease is not."""
    lock = PROJECT / "Saved/PIE_LOCK.json"
    if not os.path.lexists(lock):
        return
    try:
        data = json.loads(lock.read_text(encoding="utf-8-sig"))
        purpose, owner = data["purpose"], data["owner"]
        if not isinstance(purpose, str) or not purpose.strip() or not isinstance(owner, str) or not owner.strip():
            raise ValueError("Missing lease purpose or owner")
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise RuntimeError("Cannot determine the current lease purpose") from error
    if re.search(r"\b(restart\w*|relaunch\w*|build\w*|compil\w*|cook\w*|clos\w*|shutdown\w*)\b", purpose, re.I):
        raise RuntimeError("Shared editor lease indicates a restart, build, or cook")


class LightGuard:
    def __init__(self):
        self.started, self.last, self.train = time.monotonic(), 0., None
        self.check(force=True)

    def check(self, force=False):
        now = time.monotonic()
        if now - self.started > MAX_SECONDS:
            raise RuntimeError("Light asset job exceeded its time budget")
        if not force and now - self.last < 0.5:
            return
        train = loaded_train()
        if self.train is not None and self.train != train:
            raise RuntimeError("Shared editor train changed")
        no_restart_lease()
        editor_running, active = classify_processes(process_snapshot())
        if not editor_running:
            raise RuntimeError("Shared editor has not returned")
        if active:
            raise RuntimeError("Compiler or build process is active: " + ", ".join(sorted(active)))
        physical, commit, private = memory_status()
        if physical < 4 * 1024**3 or commit < 10 * 1024**3 or private > MAX_PRIVATE_BYTES:
            raise RuntimeError("Light asset job lacks memory headroom or exceeded its own memory budget")
        self.train, self.last = train, now


def sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def add(a, b):
    return tuple(a[i] + b[i] for i in range(3))


def mul(a, scalar):
    return tuple(x * scalar for x in a)


def dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def cross(a, b):
    return (a[1]*b[2] - a[2]*b[1], a[2]*b[0] - a[0]*b[2], a[0]*b[1] - a[1]*b[0])


def unit(a):
    length = math.sqrt(dot(a, a))
    if not math.isfinite(length) or length < 1e-10:
        raise ValueError("Degenerate source triangle or beam")
    return mul(a, 1 / length)


class Mesh:
    def __init__(self, name):
        self.name = name
        self.triangles = []

    def triangle(self, a, b, c, material):
        if len(self.triangles) >= MAX_TRIANGLES:
            raise ValueError("Mesh exceeds the triangle budget")
        if material not in MATERIALS or not all(math.isfinite(x) for p in (a, b, c) for x in p):
            raise ValueError("Invalid geometry or material")
        normal = unit(cross(sub(b, a), sub(c, a)))
        self.triangles.append(((a, b, c), material, normal))

    def quad(self, a, b, c, d, material):
        self.triangle(a, b, c, material)
        self.triangle(a, c, d, material)


def prism(mesh, corners, material):
    if len(corners) != 8:
        raise ValueError("A prism needs eight corners")
    for face in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
                 (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        mesh.quad(*(corners[i] for i in face), material)


def box(mesh, center, size, material):
    x, y, z = center
    dx, dy, dz = (v / 2 for v in size)
    corners = [(x-dx,y-dy,z-dz),(x+dx,y-dy,z-dz),(x+dx,y+dy,z-dz),(x-dx,y+dy,z-dz),
               (x-dx,y-dy,z+dz),(x+dx,y-dy,z+dz),(x+dx,y+dy,z+dz),(x-dx,y+dy,z+dz)]
    prism(mesh, corners, material)


def beam(mesh, a, b, width, depth, material):
    axis = unit(sub(b, a))
    reference = (0., 0., 1.) if abs(axis[2]) < 0.9 else (0., 1., 0.)
    side = mul(unit(cross(reference, axis)), width / 2)
    up = mul(unit(cross(axis, side)), depth / 2)
    # The local frame is right-handed: side x up = axis.
    corners = [add(add(a, mul(side, -1)), mul(up, -1)), add(add(a, side), mul(up, -1)),
               add(add(a, side), up), add(add(a, mul(side, -1)), up),
               add(add(b, mul(side, -1)), mul(up, -1)), add(add(b, side), mul(up, -1)),
               add(add(b, side), up), add(add(b, mul(side, -1)), up)]
    prism(mesh, corners, material)


def trestle_leg(mesh, foot_x, top_x, y):
    """A sloped leg with level cuts at the ground and board underside."""
    half_width = half_depth = 0.055 / 2
    corners = [(foot_x-half_width,y-half_depth,0.), (foot_x+half_width,y-half_depth,0.),
               (foot_x+half_width,y+half_depth,0.), (foot_x-half_width,y+half_depth,0.),
               (top_x-half_width,y-half_depth,BOARD_UNDERSIDE_Z), (top_x+half_width,y-half_depth,BOARD_UNDERSIDE_Z),
               (top_x+half_width,y+half_depth,BOARD_UNDERSIDE_Z), (top_x-half_width,y+half_depth,BOARD_UNDERSIDE_Z)]
    prism(mesh, corners, "M_MarketOakDark")


def stallboard():
    mesh = Mesh("SM_London_MarketTrestle")
    # Individually edged boards and nail heads make the simple trestle readable.
    for i in range(8):
        y = -0.70 + i * 0.20
        box(mesh, (0.34, y, BOARD_CENTER_Z), (0.68, 0.194, BOARD_THICKNESS), "M_MarketOak")
        for x in (0.10, 0.58):
            box(mesh, (x, y, 0.794), (0.018, 0.018, 0.003), "M_MarketIron")
    for y in (-0.63, 0.63):
        trestle_leg(mesh, 0.075, 0.30, y)
        trestle_leg(mesh, 0.605, 0.38, y)
        beam(mesh, (0.14,y,0.23), (0.54,y,0.23), 0.045, 0.045, "M_MarketOakDark")
    beam(mesh, (0.34,-0.65,0.29), (0.34,0.65,0.29), 0.05, 0.05, "M_MarketOakDark")
    return mesh


def turned_bowl():
    mesh = Mesh("SM_London_TurnedAshBowl")
    # 195 mm diameter, 45 mm high; a designed profile, not a 3D scan.
    profile = [(0.045,0.000),(0.062,0.002),(0.077,0.009),(0.089,0.022),
               (0.0975,0.041),(0.0975,0.045),(0.088,0.045),(0.081,0.030),
               (0.068,0.019),(0.045,0.012),(0.020,0.011)]
    segments = 32
    point = lambda radius, z, theta: (radius*math.cos(theta), radius*math.sin(theta), z)
    for i in range(segments):
        a, b = 2*math.pi*i/segments, 2*math.pi*(i+1)/segments
        mesh.triangle((0.,0.,0.), point(profile[0][0], profile[0][1], b),
                      point(profile[0][0], profile[0][1], a), "M_MarketAsh")
        for (r0,z0),(r1,z1) in zip(profile, profile[1:]):
            mesh.quad(point(r0,z0,a), point(r0,z0,b), point(r1,z1,b), point(r1,z1,a), "M_MarketAsh")
        mesh.triangle((0.,0.,profile[-1][1]), point(profile[-1][0], profile[-1][1], a),
                      point(profile[-1][0], profile[-1][1], b), "M_MarketAsh")
    return mesh


def ale_stake():
    mesh = Mesh("SM_London_AleStake")
    # Wall mounting origin at (0,0,0), +X projects into the street.
    beam(mesh, (0.,0.,-0.23), (0.,0.,0.23), 0.075, 0.075, "M_MarketOakDark")
    beam(mesh, (0.,0.,0.10), (1.20,0.,0.10), 0.065, 0.065, "M_MarketOak")
    beam(mesh, (0.,0.,-0.20), (0.42,0.,0.10), 0.048, 0.048, "M_MarketOakDark")
    for x in (0.87, 1.08):
        beam(mesh, (x,0.,0.06), (x,0.,-0.16), 0.018, 0.018, "M_MarketIron")
    center_x, center_z, radius = 0.975, -0.34, 0.23
    segments = 24
    for i in range(segments):
        a, b = 2*math.pi*i/segments, 2*math.pi*(i+1)/segments
        start = (center_x+radius*math.cos(a), 0., center_z+radius*math.sin(a))
        end = (center_x+radius*math.cos(b), 0., center_z+radius*math.sin(b))
        beam(mesh, start, end, 0.018, 0.018, "M_MarketOakDark")
        mid = (a+b)/2
        x, z = center_x+radius*math.cos(mid), center_z+radius*math.sin(mid)
        # Slightly raised double-sided leaf facets, with varied sizes.
        leaf_len = 0.080 if i % 2 else 0.105
        radial = (math.cos(mid), 0., math.sin(mid))
        tangent = (-math.sin(mid), 0., math.cos(mid))
        leaf_center = (x, -0.012, z)
        tip = add(leaf_center, mul(radial, leaf_len))
        left = add(leaf_center, mul(tangent, 0.024))
        right = add(leaf_center, mul(tangent, -0.024))
        material = "M_MarketIvyLight" if i % 3 == 0 else "M_MarketIvy"
        mesh.triangle(left, tip, right, material)
        mesh.triangle(right, tip, left, material)
    return mesh


def obj_bytes(mesh):
    lines = ["# Review-only; local meters; +X outward, +Y along frontage, +Z up.\n",
             "mtllib LondonMarketProps.mtl\n", f"o {mesh.name}\n", "s off\n"]
    last = None
    for i, (points, material, normal) in enumerate(mesh.triangles):
        if material != last:
            lines.append(f"usemtl {material}\n")
            last = material
        for point in points:
            lines.append("v " + " ".join(f"{v:.7f}" for v in point) + "\n")
        axis = max(range(3), key=lambda n: abs(normal[n]))
        uv_axes = ((1,2),(0,2),(0,1))[axis]
        for point in points:
            lines.append(f"vt {point[uv_axes[0]]:.7f} {point[uv_axes[1]]:.7f}\n")
        lines.append("vn " + " ".join(f"{v:.7f}" for v in normal) + "\n")
        base = 3 * i + 1
        lines.append("f " + " ".join(f"{base+j}/{base+j}/{i+1}" for j in range(3)) + "\n")
    return "".join(lines).encode("utf-8")


def material_bytes():
    lines = ["# Flat preview colors; material appearance requires in-engine review.\n"]
    for name, color in MATERIALS.items():
        lines += [f"newmtl {name}\n", "Kd " + " ".join(str(v) for v in color) + "\n", "d 1.0\n\n"]
    return "".join(lines).encode("utf-8")


def preview_bytes(meshes, check):
    import io
    from PIL import Image, ImageDraw, ImageFont

    w, h = 1440, 730
    image = Image.new("RGB", (w, h), (24, 27, 28))
    draw = ImageDraw.Draw(image)
    font_path = "C:/Windows/Fonts/segoeui.ttf"
    bold_path = "C:/Windows/Fonts/segoeuib.ttf"
    title = ImageFont.truetype(bold_path, 30)
    label = ImageFont.truetype(bold_path, 18)
    small = ImageFont.truetype(font_path, 15)
    draw.text((55,32), "LONDON MARKET  /  SOURCE KIT", font=title, fill=(240,229,205))
    draw.text((57,75), "HISTORICALLY INFORMED  •  REVIEW GEOMETRY  •  NOT YET IN GAME", font=small, fill=(173,165,146))
    view = unit((4., -6., 4.))
    right = unit(cross((0.,0.,1.), view))
    up = unit(cross(view, right))
    light = unit((0.4, -0.5, 0.8))
    cards = [(45,128,475,655), (505,128,935,655), (965,128,1395,655)]
    labels = [("01  MARKET TRESTLE", "Plank stall • 1.6 m wide"),
              ("02  TURNED ASH BOWL", "Milk Street find • 195 mm diameter"),
              ("03  ALEHOUSE STAKE", "Pole and foliage • wall-mounted")]
    for mesh, (left,top,right_edge,bottom), (heading,subtitle) in zip(meshes, cards, labels):
        check()
        draw.rounded_rectangle((left,top,right_edge,bottom), radius=12, fill=(38,42,40), outline=(85,83,71), width=2)
        draw.text((left+22, top+19), heading, font=label, fill=(238,222,188))
        draw.text((left+22, top+46), subtitle, font=small, fill=(166,166,151))
        projections = []
        for points, material, normal in mesh.triangles:
            projected = [(dot(p,right), dot(p,up), dot(p,view)) for p in points]
            projections.append((projected, material, normal))
        xs = [p[0] for tri,_,_ in projections for p in tri]
        ys = [p[1] for tri,_,_ in projections for p in tri]
        width, height = max(xs)-min(xs), max(ys)-min(ys)
        scale = min((right_edge-left-55)/max(width, 1e-6), (bottom-top-130)/max(height, 1e-6))
        cx, cy = (left+right_edge)/2, (top+bottom+68)/2
        center_x, center_y = (min(xs)+max(xs))/2, (min(ys)+max(ys))/2
        for index, (points, material, normal) in enumerate(sorted(projections, key=lambda item: sum(p[2] for p in item[0])/3)):
            if index % 64 == 0:
                check()
            brightness = 0.56 + 0.44 * max(0., dot(normal, light))
            color = tuple(max(0, min(255, round(channel * brightness * 255))) for channel in MATERIALS[material])
            outline = tuple(max(0, int(channel * 0.58)) for channel in color)
            poly = [(cx+(p[0]-center_x)*scale, cy-(p[1]-center_y)*scale) for p in points]
            draw.polygon(poly, fill=color, outline=outline)
    draw.text((57,681), "Review color only. Source normals, materials, scale and UE placement require verification.",
              font=small, fill=(166,165,153))
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=False)
    return output.getvalue()


def write_new(path, data, output, parent, check):
    check()
    if (parent.resolve(strict=True) != parent or output.parent != parent or output.is_symlink() or
            getattr(output, "is_junction", lambda: False)() or output.resolve(strict=True) != output or
            path.parent != output or path.resolve().parent != output or os.path.lexists(path)):
        raise ValueError("Output path is existing or redirected")
    with path.open("xb") as stream:
        for offset in range(0, len(data), 128*1024):
            check()
            if stream.write(data[offset:offset+128*1024]) != len(data[offset:offset+128*1024]):
                raise IOError("Short output write")
    if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(data).digest():
        raise ValueError("Output readback hash differs")


def main():
    guard = LightGuard()
    guard.check(force=True)
    parent = OUTPUT_PARENT.resolve(strict=True)
    if (OUTPUT_PARENT.is_symlink() or getattr(OUTPUT_PARENT, "is_junction", lambda: False)() or
            parent != OUTPUT_PARENT.absolute() or not parent.is_relative_to((PROJECT / "Saved").resolve(strict=True))):
        raise ValueError("Saved output parent is redirected")
    output = parent / ("MedievalMarketProps_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + secrets.token_hex(4))
    if output.resolve().parent != parent or os.path.lexists(output):
        raise ValueError("Source output directory is existing or redirected")
    meshes = []
    for build in (stallboard, turned_bowl, ale_stake):
        guard.check(force=True)
        meshes.append(build())
    if sum(len(mesh.triangles) for mesh in meshes) > MAX_TRIANGLES:
        raise RuntimeError("Light asset job exceeded its triangle budget")
    guard.check(force=True)
    output.mkdir()
    files = {"LondonMarketProps.mtl": material_bytes()}
    for mesh in meshes:
        guard.check()
        files[mesh.name + ".obj"] = obj_bytes(mesh)
    files["MarketDressingPreview.png"] = preview_bytes(meshes, guard.check)
    manifest = {"status": "review_only_not_imported", "axis": "+X outward, +Y along frontage, +Z up; meters",
                "materials": "Original flat colors, no external image assets", "models": [m.name for m in meshes],
                "source_triangle_counts": {m.name: len(m.triangles) for m in meshes},
                "sha256": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
                "limits": ["Artist reconstruction, not a scan or an exact depiction of one historical stall.",
                           "OBJ import, UVs, normals, material appearance, collision and game placement are unverified."]}
    manifest_data = (json.dumps(manifest, indent=2)+"\n").encode("utf-8")
    if sum(map(len, files.values())) + len(manifest_data) > MAX_OUTPUT_BYTES:
        raise RuntimeError("Light asset job exceeded its output budget")
    guard.check(force=True)
    for name, data in files.items():
        write_new(output / name, data, output, parent, guard.check)
    guard.check(force=True)
    write_new(output / "manifest.json", manifest_data, output, parent, guard.check)
    print(f"Review-only source kit ready: {output}", flush=True)


if __name__ == "__main__":
    main()

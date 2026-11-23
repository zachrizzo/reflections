"""Fit a painted torso garment offline with Blender's Python and SciPy.

The garment is registered in the export body's axes and meters. Position edits
are shared across coincident UV seam vertices. The supplied Unreal samples use
actor-local centimeters, with the opposite Y axis. The fit assumes a waist
opening over trousers and keeps the garment's neckline in its starting region.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_posed_surfaces import surface, tree as bvh


def mesh_surface(mesh):
    mesh.data.calc_loop_triangles()
    transform = mesh.matrix_world
    points = np.array([tuple(transform @ v.co) for v in mesh.data.vertices])
    faces = np.array([tuple(t.vertices) for t in mesh.data.loop_triangles])
    return points, faces


def outward_bvh(points, triangles):
    p, q, r = points[triangles].transpose(1, 0, 2)
    volume_sign = np.einsum("ij,ij->", p, np.cross(q, r))
    return bvh(points, triangles if volume_sign > 0 else triangles[:, [0, 2, 1]])


def captured_mesh(folder, label):
    points, faces = surface(folder / f"standing_{label}.bin")
    return points * [.01, -.01, .01], faces[:, [0, 2, 1]]


class Body:
    def __init__(self, name, points, faces):
        self.name = name
        self.surface = outward_bvh(points, faces)

    def contains(self, point):
        # The body and face can meet at an open seam. A nearest triangle's
        # normal alone can classify empty space near that seam as inside.
        inside_votes = 0
        for vector in ((.023, -1, .037), (.089, 1, -.087), (1, .176, -.127)):
            direction = Vector(vector).normalized()
            origin = point.copy()
            crossings = 0
            for _ in range(12):
                hit, _, _, _ = self.surface.ray_cast(origin, direction, 1.2)
                if hit is None:
                    break
                crossings += 1
                origin = hit + direction * .00012
            inside_votes += crossings % 2
        return inside_votes >= 2

    def distances(self, points):
        normals = np.empty_like(points)
        gaps = np.empty(len(points))
        for index, point in enumerate(points):
            pos = Vector(point)
            hit, normal, _, distance = self.surface.find_nearest(pos)
            direction = pos - hit
            inside = direction.dot(normal) < 0 and (distance < .009 or self.contains(pos))
            gaps[index] = -distance if inside else distance
            normals[index] = normal
        return gaps, normals

    def crossings(self, garment_tree):
        return len({garment_face for _, garment_face in self.surface.overlap(garment_tree)})


class Waistband:
    """Sample the radial envelope around an open lower garment."""

    def __init__(self, points, faces, z_min, center_y):
        self.name = "trousers"
        self.surface = bvh(points, faces)
        self.center_y = center_y
        self.angles = 180
        self.dz = .0025
        self.bottom = z_min - .012
        self.top = min(points[:, 2].max() + .007, z_min + .22)
        self.layers = max(2, int(np.ceil((self.top - self.bottom) / self.dz)) + 1)
        self.radii = np.full((self.layers, self.angles), np.nan)
        for z_index in range(self.layers):
            height = self.bottom + z_index * self.dz
            origin = Vector((0, center_y, height))
            for index in range(self.angles):
                angle = index * 2 * np.pi / self.angles
                axis = Vector((np.cos(angle), np.sin(angle), 0))
                hit, _, _, _ = self.surface.ray_cast(origin + .45 * axis, -axis, .44)
                if hit is not None:
                    self.radii[z_index, index] = (hit - origin).dot(axis)

    def distances(self, points):
        xy = points[:, :2] - [0, self.center_y]
        radius = np.maximum(np.linalg.norm(xy, axis=1), .001)
        angle = (np.arctan2(xy[:, 1], xy[:, 0]) % (2 * np.pi)) * self.angles / (2 * np.pi)
        ix = np.floor(angle).astype(int) % self.angles
        azimuth = angle - np.floor(angle)
        z = (points[:, 2] - self.bottom) / self.dz
        valid = (z >= 0) & (z < self.layers - 1)
        iz = np.clip(np.floor(z).astype(int), 0, self.layers - 2)
        height = np.clip(z - iz, 0, 1)
        neighbor = (ix + 1) % self.angles
        weighted_radius = np.zeros(len(points))
        weight_sum = np.zeros(len(points))
        for row, wz in ((iz, 1 - height), (iz + 1, height)):
            for col, wa in ((ix, 1 - azimuth), (neighbor, azimuth)):
                sample = self.radii[row, col]
                usable = np.isfinite(sample)
                weight = wz * wa * usable
                weighted_radius += np.nan_to_num(sample) * weight
                weight_sum += weight
        has_coverage = valid & (weight_sum >= .6)
        gap = np.where(has_coverage, radius - weighted_radius / np.maximum(weight_sum, .01), 1.)
        gradient = np.column_stack((xy / radius[:, None], np.zeros(len(points))))
        return gap, gradient

    def crossings(self, garment_tree):
        return len({garment_face for _, garment_face in self.surface.overlap(garment_tree)})


def collision_constraints(points, obstacles, margin):
    worst = np.full(len(points), -1.)
    normals = np.zeros_like(points)
    for obstacle, allowance in zip(obstacles, margin.T, strict=True):
        gaps, gradient = obstacle.distances(points)
        deficit = allowance - gaps
        active = deficit > worst
        worst[active] = deficit[active]
        normals[active] = gradient[active]
    return worst, normals


def control_grid(points, spacing, sparse):
    local = (points - points.min(axis=0)) / spacing + 1
    cells = local.astype(int)
    fraction = local - cells
    corners = np.array(list(itertools.product((0, 1), repeat=3)))
    keys = cells[:, None, :] + corners
    nodes, ids = np.unique(keys.reshape(-1, 3), axis=0, return_inverse=True)
    influence = np.prod(np.where(corners, fraction[:, None, :], 1 - fraction[:, None, :]), axis=2)
    rows = np.repeat(np.arange(len(points)), len(corners))
    matrix = sparse.csr_matrix((influence.ravel(), (rows, ids)), shape=(len(points), len(nodes)))

    lookup = {tuple(node): i for i, node in enumerate(nodes)}
    adjacent = []
    for i, node in enumerate(nodes):
        for step in np.eye(3, dtype=int):
            neighbor = lookup.get(tuple(node + step))
            if neighbor is not None:
                adjacent.append((i, neighbor))
    graph_rows = np.repeat(np.arange(len(adjacent)), 2)
    differences = sparse.csr_matrix(
        (np.tile([-1., 1.], len(adjacent)), (graph_rows, np.array(adjacent).ravel())),
        shape=(len(adjacent), len(nodes)),
    )
    ease = differences.T @ differences
    anchor = sparse.diags(matrix.sum(axis=0).A1 * .019 + .025)
    return matrix, (anchor + .25 * ease + .14 * (ease @ ease)).tocsc()


def fit(points, obstacles, sparse, iterations, registered):
    out = points.copy()
    height = out[:, 2]
    shoulders = np.clip((height - (height.max() - .20)) / .14, 0, 1)
    side = np.clip((np.abs(out[:, 0]) - .105) / .10, 0, 1)
    neckline = np.clip((height - (height.max() - .135)) / .08, 0, 1) * (1 - side)
    neckline = neckline * neckline * (3 - 2 * neckline)
    waist = np.clip((height.min() + .11 - height) / .07, 0, 1)
    radial = out.copy()
    radial[:, 1] -= .012
    radial[:, 2] = 0
    radial /= np.maximum(np.linalg.norm(radial, axis=1), .001)[:, None]
    mobility = 1. - .96 * neckline if registered else np.ones(len(points))
    displacement_limit = (.034 + .010 * waist) if registered else (.072 + .028 * waist)
    margin = np.column_stack((
        .006 + .007 * shoulders * side,
        .0045 + .006 * shoulders * side,
        np.full(len(out), .0075),
    ))
    log = []
    for spacing, limit in zip((.052, .027, .013), iterations, strict=True):
        mapping, penalty = control_grid(out, spacing, sparse)
        coefficients = np.zeros((mapping.shape[1], 3))
        for _ in range(limit):
            deficit, normals = collision_constraints(out, obstacles, margin)
            indices = np.flatnonzero((deficit > .00075) & (mobility > .05))
            if not len(indices):
                break
            weights = mobility[indices] * (1 + np.minimum(deficit[indices] / .0075, 3.))
            contact = mapping[indices]
            support = neckline[indices, None]
            # Route the collar around the neck. A nearest-normal push alone
            # can pull the rear binding up the nape or fold it into the V.
            directions = normals[indices] * (1 - support) + radial[indices] * support
            desired_delta = np.minimum(deficit[indices], .028)[:, None] * directions
            weighted_contact = contact.multiply(weights[:, None])
            rhs = weighted_contact.T @ desired_delta - .24 * (penalty @ coefficients)
            system = penalty + (contact.T @ weighted_contact).tocsc()
            step = sparse.linalg.spsolve(system, rhs)
            movement = np.max(np.linalg.norm(step, axis=1))
            step *= min(.9, .017 / max(movement, .001))
            increment = (mapping @ step) * mobility[:, None]
            out += increment
            vertical = out[:, 2] - points[:, 2]
            out[:, 2] -= neckline * (vertical - np.clip(vertical, -.009, .005))
            out[:, 2] -= waist * (vertical - np.clip(vertical, -.004, .009))
            displacement = out - points
            length = np.linalg.norm(displacement, axis=1)
            out[:] = points + displacement * np.minimum(1., displacement_limit / np.maximum(length, .001))[:, None]
            coefficients += step
        remaining, _ = collision_constraints(out, obstacles, margin)
        state = {
            "grid_mm": spacing * 1000,
            "samples_below_clearance": int((remaining > .001).sum()),
            "largest_clearance_deficit_mm": float(max(0, remaining.max()) * 1000),
        }
        log.append(state)
        print(state, flush=True)
    return out, log


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("garment", type=Path)
    parser.add_argument("reference_body", type=Path)
    parser.add_argument("registration", type=Path)
    parser.add_argument("unreal_capture", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--python-packages", type=Path, help="Optional directory containing SciPy for Blender's Python version")
    parser.add_argument("--registered-blend", type=Path, help="Start from an existing aligned version of the same textured mesh")
    parser.add_argument("--registered-object", help="Object to read from the registered .blend")
    parser.add_argument("--triangles", type=int, default=60000)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    if args.python_packages:
        sys.path.append(str(args.python_packages))
    from scipy import sparse

    args.output.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(args.reference_body), use_custom_normals=True)
    body = next(obj for obj in bpy.context.selected_objects if obj.type == "MESH")
    body_points, body_faces = mesh_surface(body)
    bpy.ops.object.select_all(action="DESELECT")
    if args.registered_blend:
        with bpy.data.libraries.load(str(args.registered_blend)) as (available, selected):
            if args.registered_object not in available.objects:
                raise ValueError("The registered .blend must contain the named garment object")
            selected.objects = [args.registered_object]
        garment, = selected.objects
        bpy.context.collection.objects.link(garment)
        placed, faces = mesh_surface(garment)
    else:
        bpy.ops.wm.obj_import(filepath=str(args.garment), forward_axis="NEGATIVE_Z", up_axis="Y")
        garment, = [obj for obj in bpy.context.selected_objects if obj.type == "MESH"]
        original, faces = mesh_surface(garment)
        registration = json.loads(args.registration.read_text())
        lower, upper = original.min(axis=0), original.max(axis=0)
        center = (lower + upper) / 2
        center[2] = lower[2]
        placed = (original - center) * np.array(registration["affine_scale_m"]) + registration["offset_m"]
        mid_height = (placed[:, 2].min() + placed[:, 2].max()) * .5
        placed[:, 1] += registration["torso_shear"] * (placed[:, 2] - mid_height)
    assert garment.data.uv_layers.active
    unique_points, inverse = np.unique(placed.round(7), axis=0, return_inverse=True)

    skin, skin_faces = captured_mesh(args.unreal_capture, "body")
    face, face_faces = captured_mesh(args.unreal_capture, "face")
    bottom, bottom_faces = captured_mesh(args.unreal_capture, "bottom")
    actor_skin = np.vstack((skin, face))
    actor_skin_faces = np.vstack((skin_faces, face_faces + len(skin)))
    obstacles = (
        Body("matching_reference_skin", body_points, body_faces),
        Body("unreal_assembled_skin", actor_skin, actor_skin_faces),
        Waistband(bottom, bottom_faces, placed[:, 2].min(), .012),
    )
    starting = bvh(placed, faces)
    before = {obstacle.name: obstacle.crossings(starting) for obstacle in obstacles}
    print({"initial_intersections": before}, flush=True)
    adjusted, history = fit(unique_points, obstacles, sparse, (12, 14, 16), bool(args.registered_blend))
    garment.matrix_world = Matrix.Identity(4)
    garment.data.vertices.foreach_set("co", adjusted[inverse].astype(np.float32).ravel())
    garment.data.update()
    if garment.data.has_custom_normals:
        garment.data.normals_split_custom_set_from_vertices([(0., 0., 0.)] * len(garment.data.vertices))
    for polygon in garment.data.polygons:
        polygon.use_smooth = True
    garment.name = "MarketJerkin_RetargetFit"
    full_points, full_faces = mesh_surface(garment)
    finished = bvh(full_points, full_faces)
    high_res = {obstacle.name: obstacle.crossings(finished) for obstacle in obstacles}
    full_shape = np.linalg.norm(adjusted - unique_points, axis=1) * 1000
    edge = np.unique(np.sort(faces[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2), axis=1), axis=0)
    old_edges = np.linalg.norm(placed[edge[:, 0]] - placed[edge[:, 1]], axis=1)
    new_edges = np.linalg.norm(full_points[edge[:, 0]] - full_points[edge[:, 1]], axis=1)
    valid_edges = old_edges > .0005
    stretch = (new_edges[valid_edges] / old_edges[valid_edges] - 1) * 100
    bpy.ops.object.select_all(action="DESELECT")
    garment.select_set(True)
    bpy.context.view_layer.objects.active = garment
    for obj in bpy.context.scene.objects:
        if obj != garment:
            obj.hide_set(True)
            obj.hide_render = True
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output / "MarketJerkin_Fit.blend"))
    if len(full_faces) > args.triangles:
        decimate = garment.modifiers.new("Game mesh", "DECIMATE")
        decimate.ratio = args.triangles / len(full_faces)
        bpy.ops.object.modifier_apply(modifier=decimate.name)
    points, render_faces = mesh_surface(garment)
    render = bvh(points, render_faces)
    mesh_intersections = {obstacle.name: obstacle.crossings(render) for obstacle in obstacles}
    assert garment.data.uv_layers.active
    bpy.ops.export_scene.fbx(
        filepath=str(args.output / "MarketJerkin_Fit.fbx"), use_selection=True,
        object_types={"MESH"}, axis_forward="-Y", axis_up="Z", apply_unit_scale=True,
        mesh_smooth_type="FACE", add_leaf_bones=False,
    )
    report = {
        "method": "regularized coarse-to-fine mesh deformation with body and wardrobe contact projection",
        "source_sha256": hashlib.sha256(args.garment.read_bytes()).hexdigest(),
        "starting_mesh": str(args.registered_blend or args.garment),
        "source_triangles": len(faces),
        "render_triangles": len(render_faces),
        "original_mesh_intersections": before,
        "fitted_source_intersections": high_res,
        "render_mesh_intersections": mesh_intersections,
        "mesh_repositioning_p50_p95_max_mm": np.percentile(full_shape, [50, 95, 100]).round(2).tolist(),
        "mesh_edge_change_p05_p50_p95_percent": np.percentile(stretch, [5, 50, 95]).round(1).tolist(),
        "fit_iterations": history,
    }
    (args.output / "OfflineFit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report, flush=True)


if __name__ == "__main__":
    main()

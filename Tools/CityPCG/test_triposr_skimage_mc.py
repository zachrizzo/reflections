"""CPU-only axis, winding and rejection tests for the TripoSR mesh adapter."""

import unittest
from pathlib import Path
import sys
import types
from unittest.mock import patch

import numpy as np
import triposr_skimage_mc
from triposr_skimage_mc import marching_cubes_numpy


class MarchingCubesTests(unittest.TestCase):
    def test_asymmetric_density_preserves_triposr_axes_and_outward_winding(self):
        size = 33
        coordinates = np.linspace(0, 1, size, dtype=np.float32)
        x, y, z = np.meshgrid(coordinates, coordinates, coordinates, indexing='ij')
        center = np.array([.33, .49, .65])
        radii = np.array([.18, .12, .24])
        density = 1 - ((x-center[0])/radii[0])**2 - ((y-center[1])/radii[1])**2 - ((z-center[2])/radii[2])**2
        adapter_vertices, faces = marching_cubes_numpy(density, 0)
        # This is the exact reversal and unit-grid scaling done by upstream.
        vertices = adapter_vertices[:, [2, 1, 0]] / (size - 1)
        bounds = np.stack([vertices.min(axis=0), vertices.max(axis=0)])
        np.testing.assert_allclose(bounds.mean(axis=0), center, atol=.005)
        np.testing.assert_allclose((bounds[1] - bounds[0]) / 2, radii, atol=.005)
        triangles = vertices[faces]
        outward = triangles.mean(axis=1) - center
        normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
        self.assertGreater(float(np.mean(np.einsum('ij,ij->i', normals, outward) > 0)), .999)

    def test_invalid_and_non_crossing_grids_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'cross'):
            marching_cubes_numpy(np.ones((3, 3, 3)), 0)
        with self.assertRaisesRegex(ValueError, 'finite'):
            marching_cubes_numpy(np.full((3, 3, 3), np.nan), 0)
        with self.assertRaisesRegex(ValueError, 'three-dimensional'):
            marching_cubes_numpy(np.ones((3, 3)), 0)

    def test_upstream_helper_cpu_integration_preserves_axes_and_winding(self):
        import torch
        upstream = Path(__file__).resolve().parents[2] / 'Saved/CityPCG/ImageTo3D/TripoSR-upstream'
        shim = types.ModuleType('torchmcubes')
        shim.marching_cubes = triposr_skimage_mc.marching_cubes
        with patch.dict(sys.modules, {'torchmcubes': shim}), patch.object(sys, 'path', [str(upstream), *sys.path]):
            from tsr.models.isosurface import MarchingCubeHelper
            size = 25
            axis = torch.linspace(0, 1, size)
            x, y, z = torch.meshgrid(axis, axis, axis, indexing='ij')
            center = np.array([.33, .49, .65])
            density = 1 - ((x-.33)/.18)**2 - ((y-.49)/.12)**2 - ((z-.65)/.24)**2
            vertices, faces = MarchingCubeHelper(size)(-density.reshape(-1))
        vertices, faces = vertices.numpy(), faces.numpy()
        bounds = np.stack([vertices.min(axis=0), vertices.max(axis=0)])
        np.testing.assert_allclose(bounds.mean(axis=0), center, atol=.006)
        np.testing.assert_allclose((bounds[1] - bounds[0]) / 2, [.18, .12, .24], atol=.006)
        triangles = vertices[faces]
        normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
        outward = triangles.mean(axis=1) - center
        self.assertGreater(float(np.mean(np.einsum('ij,ij->i', normals, outward) > 0)), .999)


if __name__ == '__main__':
    unittest.main()

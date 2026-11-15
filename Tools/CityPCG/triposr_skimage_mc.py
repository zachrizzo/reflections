"""Process-local torchmcubes adapter for TripoSR; never changes its checkout."""


def marching_cubes_numpy(volume, threshold):
    """Return torchmcubes-style XYZ for a TripoSR density volume on the CPU.

    TripoSR grids are indexed (X,Y,Z). scikit-image returns coordinates in
    array-index order, while the upstream helper reverses the returned axes.
    Reverse here so its existing reversal restores (X,Y,Z). Positive density
    is interior; ascent gives outward right-hand face winding after TripoSR's
    axis restoration, as checked against an asymmetric analytic ellipsoid.
    """
    import numpy as np
    from skimage.measure import marching_cubes

    array = np.asarray(volume, dtype=np.float32)
    if (array.ndim != 3 or any(n < 2 for n in array.shape) or not np.isfinite(array).all()
            or not np.isfinite(threshold)):
        raise ValueError('Expected a finite three-dimensional density grid and threshold.')
    if not float(array.min()) < float(threshold) < float(array.max()):
        raise ValueError('The density grid does not cross the requested isosurface.')
    vertices, faces, _normals, _values = marching_cubes(
        array, float(threshold), method='lorensen', gradient_direction='ascent',
        allow_degenerate=False)
    if not len(vertices) or not len(faces):
        raise ValueError('The isosurface extractor produced an empty mesh.')
    return vertices[:, ::-1].copy(), np.ascontiguousarray(faces, dtype=np.int64)


def marching_cubes(level, threshold):
    """Match torchmcubes' two-tensor interface, including the caller's device."""
    import torch
    device = level.device
    vertices, faces = marching_cubes_numpy(level.detach().cpu().numpy(), threshold)
    return torch.from_numpy(vertices).to(device), torch.from_numpy(faces).to(device)

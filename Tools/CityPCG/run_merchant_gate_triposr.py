"""Guarded, isolated TripoSR Merchant Gate geometry trial; no package writes.

Run with Local3D's Python only when the shared editor is unleased. A supervisor
rechecks its lease/train/memory guards while the GPU child is running and stops
the child if the shared editor is taken. See README_MERCHANT_GATE_TRIPOSR.md.
"""

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import time
import traceback

from build_grouped_tile_derivatives import memory_headroom
from fetch_triposr_weights import window_open


PROJECT = Path(__file__).resolve().parents[2]
UPSTREAM = PROJECT / 'Saved/CityPCG/ImageTo3D/TripoSR-upstream'
MODEL = PROJECT / 'Saved/CityPCG/ImageTo3D/TripoSR-model'
RUNS = PROJECT / 'Saved/CityPCG/ImageTo3D/MerchantGateRuns'
REFERENCE = PROJECT / 'ArtDirection/CityPCG/MedievalOpening/Landmarks/MerchantGate/References/merchant_gate_imagegen_v1.png'
LOCAL3D = Path('C:/Users/zachc/tools/Local3D')
PYTHON = LOCAL3D / '.venv/Scripts/python.exe'
BACKGROUND = LOCAL3D / 'models/background/u2net.onnx'
COMMIT = '107cefdc244c39106fa830359024f6a2f1c78871'
MODEL_REV = '5b521936b01fbe1890f6f9baed0254ab6351c04a'
CHECKPOINT_SIZE = 1677246742
EXPECTED = {
    'reference': (REFERENCE, '0e5d8a11fc11a94537d44cf8c370940cb88782e4e86312a5ffde6f98811b324c'),
    'checkpoint': (MODEL / 'model.ckpt', '429e2c6b22a0923967459de24d67f05962b235f79cde6b032aa7ed2ffcd970ee'),
    'config': (MODEL / 'config.yaml', '74ca708ce086bf68e97709ea6b3d91f14717921c04691e84043f0eb8fcc68e62'),
    'dino_config': (MODEL / 'dino_config.json', 'b87c0270b97db085fd82cf114a761fd0f62ae7914fbd407c752a2260646b689c'),
    'background': (BACKGROUND, '8d10d2f3bb75ae3b6d527c77944fc5e7dcd94b29809d47a739a7a728a912b491'),
    'upstream_license': (UPSTREAM / 'LICENSE', '13aff551d7009dea9d44cc5e200f8493e0e9d5171be0ab19940e6f20f54c7e17'),
    'runner_code': (Path(__file__).resolve(), None),
    'mc_adapter_code': (Path(__file__).resolve().with_name('triposr_skimage_mc.py'), None),
}
RUN_NAME = re.compile(r'[a-z0-9][a-z0-9_-]{0,47}\Z')
START_PHYSICAL = 8 * 1024**3
START_COMMIT = 16 * 1024**3
STOP_PHYSICAL = 4 * 1024**3
STOP_COMMIT = 10 * 1024**3
MIN_FREE_VRAM_MIB = 8192


def digest(path):
    with path.open('rb') as stream:
        sha = hashlib.sha256()
        for block in iter(lambda: stream.read(2 * 1024 * 1024), b''):
            sha.update(block)
        return sha.hexdigest()


def write_json(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def copy_new(source, target):
    with source.open('rb') as src, target.open('xb') as dst:
        shutil.copyfileobj(src, dst)


def memory_guard(start=False):
    physical, commit = memory_headroom()
    p, c = (START_PHYSICAL, START_COMMIT) if start else (STOP_PHYSICAL, STOP_COMMIT)
    if physical < p or commit < c:
        raise RuntimeError(f'Insufficient memory headroom: {physical/1024**3:.1f} GiB physical, '
                           f'{commit/1024**3:.1f} GiB commit; need {p/1024**3:.0f}/{c/1024**3:.0f}.')
    return {'physical_bytes': physical, 'commit_bytes': commit}


def session_guard(start=False):
    # Share the checkpoint fetcher's lease, train, memory and editor-process
    # gate so an editor restart cannot look like an idle GPU window.
    window_open()
    return memory_guard(start=start)


def git(*args):
    result = subprocess.run(['git', '-C', str(UPSTREAM), *args], capture_output=True, text=True, check=True,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return result.stdout.strip()


def validate_inputs():
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise RuntimeError(f'Use the existing Local3D interpreter: {PYTHON}')
    if git('rev-parse', 'HEAD') != COMMIT or git('status', '--porcelain=v1', '--untracked-files=all'):
        raise RuntimeError('The pinned TripoSR checkout is dirty or at an unexpected commit.')
    hashes = {}
    for name, (path, expected) in EXPECTED.items():
        if not path.is_file() or (name == 'checkpoint' and path.stat().st_size != CHECKPOINT_SIZE):
            raise RuntimeError(f'Missing or incomplete pinned {name}: {path}')
        actual = digest(path)
        if expected is not None and actual != expected:
            raise RuntimeError(f'Pinned {name} hash mismatch: {path}')
        hashes[name] = actual
    return hashes


def free_vram_mib():
    completed = subprocess.run(['nvidia-smi', '--query-gpu=index,memory.free',
                                '--format=csv,noheader,nounits', '-i', '0'],
                               capture_output=True, text=True, check=True, timeout=10,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        raise RuntimeError('Cannot unambiguously measure GPU 0 free memory.')
    index, free = [part.strip() for part in lines[0].split(',')]
    if index != '0' or not free.isdigit() or int(free) < MIN_FREE_VRAM_MIB:
        raise RuntimeError(f'GPU 0 needs {MIN_FREE_VRAM_MIB} MiB free; reported {lines[0]!r}.')
    return int(free)


def fresh_run(name):
    if not RUN_NAME.fullmatch(name):
        raise ValueError('Use a short lowercase run name containing only letters, numbers, _ or -.')
    saved = (PROJECT / 'Saved').resolve(strict=True)
    root = RUNS.resolve()
    if not root.is_relative_to(saved) or root == saved:
        raise RuntimeError('The run directory resolves outside the intended Saved tree.')
    root.mkdir(parents=True, exist_ok=True)
    target = root / name
    if target.is_symlink() or target.resolve().parent != root or target.exists():
        raise FileExistsError('Choose a fresh, non-redirected run directory.')
    target.mkdir()
    return target


def watch(proc, check=session_guard, delay=2.0):
    """Terminate our own child if any shared-session or memory guard trips."""
    try:
        while proc.poll() is None:
            check()
            time.sleep(delay)
        if proc.returncode != 0:
            raise RuntimeError(f'TripoSR worker exited with code {proc.returncode}; inspect worker.log.')
    except BaseException:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)
        raise


def supervise(name, seed=1450, resolution=256, chunk_size=4096):
    if not 64 <= resolution <= 256 or not 256 <= chunk_size <= 8192 or not 0 <= seed < 2**32:
        raise ValueError('Resolution must be 64–256, chunk size 256–8192, and seed an unsigned 32-bit integer.')
    start_memory = session_guard(start=True)
    hashes = validate_inputs()
    session_guard(start=True)
    vram = free_vram_mib()
    session_guard(start=True)
    run = fresh_run(name)
    token = secrets.token_hex(24)
    write_json(run / 'request.json', {'status': 'raw_trial_requested', 'seed': seed, 'resolution': resolution,
                                     'chunk_size': chunk_size, 'token': token, 'inputs_sha256': hashes,
                                     'free_vram_mib_at_start': vram, 'memory_at_start': start_memory})
    copy_new(REFERENCE, run / 'reference_original.png')
    copy_new(UPSTREAM / 'LICENSE', run / 'TripoSR_LICENSE.txt')
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
               HF_HUB_DISABLE_TELEMETRY='1', U2NET_HOME=str(BACKGROUND.parent),
               TRIPOSR_SUPERVISOR_TOKEN=token)
    command = [str(PYTHON), str(Path(__file__).resolve()), '--worker', name]
    try:
        session_guard(start=True)
        with (run / 'worker.log').open('x', encoding='utf-8') as log:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env,
                                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            watch(child)
        session_guard()
        after = validate_inputs()
        session_guard()
        if after != hashes:
            raise RuntimeError('An input changed during generation.')
        worker_result = json.loads((run / 'worker.result.json').read_text(encoding='utf-8'))
        outputs = {}
        for filename in ('reference_original.png', 'foreground_rgba.png', 'conditioned.png',
                         'MerchantGate_raw.glb', 'TripoSR_LICENSE.txt', 'worker.result.json', 'worker.log'):
            path = run / filename
            if path.is_symlink() or path.resolve().parent != run.resolve() or not path.is_file():
                raise RuntimeError(f'Missing or redirected trial output {filename}.')
            outputs[filename] = digest(path)
        if outputs['reference_original.png'] != hashes['reference'] or outputs['TripoSR_LICENSE.txt'] != hashes['upstream_license']:
            raise RuntimeError('Copied source or license differs from its pinned input.')
        manifest = {'status': 'raw_mesh_requires_review', 'asset': 'MerchantGate', 'provider': 'TripoSR',
                    'upstream_commit': COMMIT, 'model_revision': MODEL_REV, 'license': 'MIT',
                    'seed': seed, 'mc_resolution': resolution, 'chunk_size': chunk_size,
                    'mc_adapter': 'scikit-image Lorensen CPU, axis adapter, outward winding; not torchmcubes',
                    'inputs_sha256': hashes, 'outputs_sha256': outputs, 'worker': worker_result,
                    'gameplay_ready': False, 'run_dir': str(run)}
        session_guard()
        write_json(run / 'provenance.complete.json', manifest)
        return manifest
    except Exception as error:
        write_json(run / 'provenance.failure.json', {'status': 'failed_or_interrupted',
                   'error': str(error), 'traceback': traceback.format_exc(), 'gameplay_ready': False})
        raise


def worker(name):
    """Private child: all artifacts are new files under its own fresh run dir."""
    root = RUNS.resolve(strict=True)
    if not RUN_NAME.fullmatch(name):
        raise ValueError('Invalid worker run name.')
    run = (root / name).resolve(strict=True)
    if run.parent != root or (root / name).is_symlink():
        raise RuntimeError('Worker run path redirected.')
    request = json.loads((run / 'request.json').read_text(encoding='utf-8'))
    if not secrets.compare_digest(request['token'], os.environ.get('TRIPOSR_SUPERVISOR_TOKEN', '')):
        raise RuntimeError('Worker must be started by the guarded supervisor.')
    session_guard(start=True)
    if validate_inputs() != request['inputs_sha256']:
        raise RuntimeError('Pinned inputs changed between supervisor and worker.')
    session_guard(start=True)
    free_vram_mib()
    session_guard(start=True)
    if digest(run / 'reference_original.png') != EXPECTED['reference'][1]:
        raise RuntimeError('Copied reference is not the pinned input.')
    # Stop accidental model/config downloads without changing shared packages.
    import socket
    def offline(*_args, **_kwargs):
        raise RuntimeError('Network access is disabled for this local model trial.')
    socket.create_connection = offline
    socket.socket.connect = offline
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(UPSTREAM))
    import types
    import numpy as np
    import torch
    from PIL import Image
    import rembg
    import triposr_skimage_mc
    shim = types.ModuleType('torchmcubes')
    shim.marching_cubes = triposr_skimage_mc.marching_cubes
    sys.modules['torchmcubes'] = shim
    from rembg.sessions.u2net import U2netSession
    U2netSession.download_models = classmethod(lambda cls, *args, **kwargs: str(BACKGROUND))
    from tsr.system import TSR
    from tsr.utils import remove_background, resize_foreground
    import tsr.models.tokenizers.image as tokenizer
    def local_dino(repo_id, filename, **_kwargs):
        if repo_id != 'facebook/dino-vitb16' or filename != 'config.json':
            raise RuntimeError(f'Unexpected remote model request: {repo_id}/{filename}')
        return str(MODEL / 'dino_config.json')
    tokenizer.hf_hub_download = local_dino
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA GPU is unavailable; no fallback run was started.')
    session_guard()
    image = Image.open(run / 'reference_original.png').convert('RGB')
    session = rembg.new_session('u2net', providers=['CPUExecutionProvider'])
    foreground = resize_foreground(remove_background(image, session), .85)
    with (run / 'foreground_rgba.png').open('xb') as target:
        foreground.save(target, format='PNG')
    rgba = np.array(foreground).astype(np.float32) / 255
    rgb = rgba[:, :, :3] * rgba[:, :, 3:4] + (1-rgba[:, :, 3:4]) * .5
    conditioned = Image.fromarray((rgb * 255).astype(np.uint8))
    with (run / 'conditioned.png').open('xb') as target:
        conditioned.save(target, format='PNG')
    session_guard()
    torch.manual_seed(request['seed'])
    np.random.seed(request['seed'])
    started = time.time()
    model = TSR.from_pretrained(str(MODEL), config_name='config.yaml', weight_name='model.ckpt')
    model.renderer.set_chunk_size(request['chunk_size'])
    model.eval().to('cuda:0')
    session_guard()
    with torch.inference_mode():
        scene = model([conditioned], device='cuda:0')
        mesh = model.extract_mesh(scene, has_vertex_color=True, resolution=request['resolution'])[0]
    session_guard()
    if not len(mesh.vertices) or not len(mesh.faces) or not np.isfinite(mesh.vertices).all():
        raise RuntimeError('TripoSR produced empty geometry.')
    raw = mesh.export(file_type='glb')
    if not isinstance(raw, bytes) or len(raw) < 20 or raw[:4] != b'glTF':
        raise RuntimeError('The raw mesh did not serialize as a GLB.')
    with (run / 'MerchantGate_raw.glb').open('xb') as target:
        target.write(raw)
    packages = ('torch', 'scikit-image', 'numpy', 'transformers', 'omegaconf', 'trimesh', 'rembg', 'onnxruntime')
    write_json(run / 'worker.result.json', {'status': 'provisional_raw_mesh',
               'gpu': torch.cuda.get_device_name(0), 'python': sys.version,
               'versions': {name: importlib.metadata.version(name) for name in packages},
               'elapsed_seconds': round(time.time() - started, 2), 'vertices': len(mesh.vertices),
               'faces': len(mesh.faces), 'bounds': mesh.bounds.tolist(),
               'network_access': 'disabled', 'background_execution': 'CPUExecutionProvider',
               'background_model': str(BACKGROUND), 'source_image': 'reference_original.png'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-name')
    parser.add_argument('--seed', type=int, default=1450)
    parser.add_argument('--resolution', type=int, default=256)
    parser.add_argument('--chunk-size', type=int, default=4096)
    parser.add_argument('--worker', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
    elif args.run_name:
        print(json.dumps(supervise(args.run_name, args.seed, args.resolution, args.chunk_size), indent=2))
    else:
        parser.error('--run-name is required')


if __name__ == '__main__':
    main()

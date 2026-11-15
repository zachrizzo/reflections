"""Read-only evidence audit for the staged Gray London Windows package.

Exit 1 on a detected problem or missing evidence; exit 2 when no problem was
detected but freshness, actual cooking and gameplay remain unverified. This
script never reports a build as proven current from file timestamps.
"""

import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys


PROJECT = Path(__file__).resolve().parents[2]
MAP_PACKAGE = '/Game/GrayLondon/Maps/GrayLondon_Geodata'
MAP_OBJECT = MAP_PACKAGE + '.GrayLondon_Geodata'
GAME_MODE = '/Script/reflections.ReflectionsSampleGameMode'
PILOT = 'GrayLondon/MedievalOpening/WholeBuildings/WestMarkLane'
PILOT_ASSETS = (
    'SM_GLMedieval_WestBlockTile',
    'SM_GLMedieval_MarkLaneMerchantsHouses',
    'SM_GLMedieval_MarkLaneTradingCompound',
    'SM_GLMedieval_MarkLaneWorkshop',
)
WORLD_PARTITION = (
    'Content/__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata',
    'Content/__ExternalObjects__/GrayLondon/Maps/GrayLondon_Geodata',
)
RUNTIME_SOURCE = (
    'Source/reflections/Worlds/ReflectionsCityTileReplacement.cpp',
    'Source/reflections/Worlds/ReflectionsCityTileReplacementSubsystem.cpp',
)
SOURCE_EXTENSIONS = {'.c', '.cc', '.cpp', '.cxx', '.h', '.hpp', '.inl', '.cs'}
STAGE = Path('Saved/JamBuild/Windows')


def ini_entries(text, section, key):
    """Return all same-key entries in the named section, preserving prefixes."""
    current = ''
    found = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith((';', '#')):
            continue
        if line.startswith('[') and line.endswith(']'):
            current = line[1:-1].strip().casefold()
            continue
        if current != section.casefold() or '=' not in line:
            continue
        name, value = line.split('=', 1)
        name = name.strip()
        if name.lstrip('+-!.').casefold() == key.casefold():
            found.append((name, value.strip()))
    return found


def scalar_value(entries, expected):
    return (len(entries) == 1 and entries[0][0][0] not in '+-!.' and
            entries[0][1] in (expected, f'"{expected}"'))


def required_map(entries):
    """Accept a single explicit additive map entry; reject ambiguous overrides."""
    if len(entries) != 1 or entries[0][0].casefold() != '+mapstocook':
        return False
    match = re.fullmatch(r'\(\s*FilePath\s*=\s*"([^"]+)"\s*\)', entries[0][1], re.IGNORECASE)
    return bool(match and match.group(1) == MAP_PACKAGE)


def packaging_map(text):
    rows = [line for line in text.splitlines() if re.match(r'^\s*set\s+"?ARGS=', line, re.IGNORECASE)]
    if len(rows) != 1:
        return None
    maps = re.findall(r'(?:^|\s)-map=(?:"([^"]+)"|([^\s"]+))', rows[0], re.IGNORECASE)
    if len(maps) != 1:
        return None
    return maps[0][0] or maps[0][1]


def is_redirected(path):
    """Reject symlinks and Windows reparse points, including junctions."""
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        return True
    if os.name == 'nt':
        attributes = getattr(info, 'st_file_attributes', None)
        if attributes is None:
            raise OSError(f'cannot inspect Windows reparse-point attributes: {path}')
        return bool(attributes & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))
    return False


def require_unredirected(path, root):
    """Check every project-relative component, not just the leaf."""
    try:
        parts = path.relative_to(root).parts
    except ValueError as error:
        raise OSError(f'path is outside the project: {path}') from error
    current = root
    for part in parts:
        current = current / part
        if is_redirected(current):
            raise OSError(f'redirected path cannot be audited: {current}')


def walk_files(folder, root):
    """Yield files without following symlinks or junctions; fail on I/O errors."""
    require_unredirected(folder, root)
    if not folder.is_dir():
        raise OSError(f'missing, unreadable, or redirected directory: {folder}')

    def on_error(error):
        raise error

    for current, directories, filenames in os.walk(folder, followlinks=False, onerror=on_error):
        base = Path(current)
        for name in directories:
            if is_redirected(base / name):
                raise OSError(f'redirected directory cannot be audited: {base / name}')
        for name in filenames:
            path = base / name
            if is_redirected(path):
                raise OSError(f'redirected file cannot be audited: {path}')
            yield path


def audit(project):
    """Inspect project files and the staged manifest; no writes or game launches."""
    root = Path(project).resolve()
    failures = []
    observations = []
    details = {}

    def fail(code, message):
        failures.append({'code': code, 'message': message})

    def file_stat(relative):
        path = root / relative
        try:
            require_unredirected(path, root)
            info = path.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_size <= 0:
                raise OSError('not a nonempty regular file')
            return info
        except OSError as error:
            fail('missing_evidence', f'{relative}: {error}')
            return None

    def read_text(relative):
        info = file_stat(relative)
        if info is None:
            return None, None
        try:
            return (root / relative).read_text(encoding='utf-8-sig'), info
        except (OSError, UnicodeError) as error:
            fail('unreadable_evidence', f'{relative}: {error}')
            return None, None

    engine, engine_info = read_text(Path('Config/DefaultEngine.ini'))
    game, game_info = read_text(Path('Config/DefaultGame.ini'))
    package, _ = read_text(Path('ArtDirection/Packaging/PackageJamBuild.bat'))
    map_checks = {'game_default': False, 'editor_startup': False, 'game_mode': False, 'new_game': False,
                  'maps_to_cook': False, 'packaging_map': False}
    if engine is not None:
        section = '/Script/EngineSettings.GameMapsSettings'
        for key, label in (('GameDefaultMap', 'game_default'), ('EditorStartupMap', 'editor_startup')):
            map_checks[label] = scalar_value(ini_entries(engine, section, key), MAP_OBJECT)
            if not map_checks[label]:
                fail('wrong_map_config', f'DefaultEngine.ini {key} is missing, ambiguous, or not {MAP_OBJECT}')
        map_checks['game_mode'] = scalar_value(ini_entries(engine, section, 'GlobalDefaultGameMode'), GAME_MODE)
        if not map_checks['game_mode']:
            fail('wrong_game_mode', f'DefaultEngine.ini GlobalDefaultGameMode is missing, ambiguous, or not {GAME_MODE}')
    if game is not None:
        map_checks['new_game'] = scalar_value(
            ini_entries(game, '/Script/reflections.ReflectionsGameFlowSubsystem', 'NewGameMap'), MAP_OBJECT)
        if not map_checks['new_game']:
            fail('wrong_map_config', f'DefaultGame.ini NewGameMap is missing, ambiguous, or not {MAP_OBJECT}')
        map_checks['maps_to_cook'] = required_map(
            ini_entries(game, '/Script/UnrealEd.ProjectPackagingSettings', 'MapsToCook'))
        if not map_checks['maps_to_cook']:
            fail('wrong_map_config', f'DefaultGame.ini MapsToCook is missing, ambiguous, or not exclusively {MAP_PACKAGE}')
    if package is not None:
        map_checks['packaging_map'] = packaging_map(package) == MAP_PACKAGE
        if not map_checks['packaging_map']:
            fail('wrong_package_map', f'PackageJamBuild.bat has no single explicit -map={MAP_PACKAGE}')
        observations.append('Packaging flags are inspected as text; this audit does not build the game target.')
    details['configured_gray_london_map'] = map_checks

    executable = file_stat(Path('Binaries/Win64/reflections.exe'))
    staged = file_stat(STAGE / 'reflections/Binaries/Win64/reflections.exe')
    file_stat(STAGE / 'reflections.exe')
    receipt, _ = read_text(Path('Binaries/Win64/reflections.target'))
    if receipt is not None:
        try:
            metadata = json.loads(receipt)
            expected = {'TargetName': 'reflections', 'TargetType': 'Game', 'Platform': 'Win64', 'Configuration': 'Development'}
            if not isinstance(metadata, dict) or any(metadata.get(key) != value for key, value in expected.items()):
                fail('wrong_target_receipt', 'Game target receipt does not identify reflections Win64 Development.')
        except (ValueError, TypeError) as error:
            fail('unreadable_evidence', f'Game target receipt is invalid: {error}')

    project_info = file_stat(Path('reflections.uproject'))
    runtime_info = [(path, file_stat(Path(path))) for path in RUNTIME_SOURCE]
    if executable is not None and staged is not None:
        if staged.st_size != executable.st_size or staged.st_mtime_ns < executable.st_mtime_ns:
            fail('staged_executable_stale', 'Staged game executable is older than or differs in size from the project game target.')
        observations.append('Equal executable size or timestamp is not proof that the binaries match.')

    try:
        source_inputs = []
        for path in walk_files(root / 'Source', root):
            if path.suffix.casefold() in SOURCE_EXTENSIONS:
                source_inputs.append((path, path.stat()))
        if not source_inputs:
            fail('missing_evidence', 'Source contains no auditable game source or build-rule files.')
    except OSError as error:
        fail('unreadable_evidence', f'Source scan failed: {error}')
        source_inputs = []
    if executable is not None:
        newer = [(path, info) for path, info in source_inputs if info.st_mtime_ns > executable.st_mtime_ns]
        if project_info is not None and project_info.st_mtime_ns > executable.st_mtime_ns:
            newer.append((root / 'reflections.uproject', project_info))
        newer.sort(key=lambda item: item[1].st_mtime_ns, reverse=True)
        details['newer_game_input_count'] = len(newer)
        details['newer_game_input_examples'] = [str(path.relative_to(root)) for path, _ in newer[:8]]
        details['newer_replacement_runtime'] = [path for path, info in runtime_info
                                                if info is not None and info.st_mtime_ns > executable.st_mtime_ns]
        if newer:
            fail('game_executable_stale_indicator', f'{len(newer)} project inputs have timestamps newer than the game executable.')

    manifest, manifest_info = read_text(STAGE / 'Manifest_UFSFiles_Win64.txt')
    for name in ('global.utoc', 'global.ucas', 'reflections-Windows.pak',
                 'reflections-Windows.utoc', 'reflections-Windows.ucas'):
        file_stat(STAGE / 'reflections/Content/Paks' / name)
    map_info = file_stat(Path('Content/GrayLondon/Maps/GrayLondon_Geodata.umap'))
    pilot_info = [(Path('Content') / PILOT / (asset + '.uasset'),
                   file_stat(Path('Content') / PILOT / (asset + '.uasset'))) for asset in PILOT_ASSETS]
    if manifest is not None:
        entries = {line.split('\t', 1)[0].strip().replace('\\', '/').casefold() for line in manifest.splitlines()}
        required = ['reflections/Content/GrayLondon/Maps/GrayLondon_Geodata.umap']
        required.extend(f'reflections/Content/{PILOT}/{asset}.uasset' for asset in PILOT_ASSETS)
        missing = [item for item in required if item.casefold() not in entries]
        details['missing_staged_entries'] = missing
        for item in missing:
            fail('missing_staged_entry', f'Staged UFS manifest does not list {item}')
        cells = [item for item in entries if item.startswith(
            'reflections/content/graylondon/maps/graylondon_geodata/_generated_/') and item.endswith('.umap')]
        details['staged_world_partition_cell_count'] = len(cells)
        if not cells:
            fail('missing_staged_cells', 'Staged UFS manifest has no generated Gray London World Partition cells.')
        observations.append('Manifest entries are staging evidence, not proof of usable cooked content or placement.')

    stage_inputs = [(root / 'Config/DefaultEngine.ini', engine_info),
                    (root / 'Config/DefaultGame.ini', game_info),
                    (root / 'Content/GrayLondon/Maps/GrayLondon_Geodata.umap', map_info)]
    stage_inputs.extend((root / path, info) for path, info in pilot_info)
    for relative in WORLD_PARTITION:
        try:
            files = [path for path in walk_files(root / relative, root) if path.suffix.casefold() in {'.uasset', '.umap'}]
            if not files:
                fail('missing_evidence', f'No World Partition packages found in {relative}')
            stage_inputs.extend((path, path.stat()) for path in files)
        except OSError as error:
            fail('unreadable_evidence', f'World Partition scan failed for {relative}: {error}')
    if manifest_info is not None:
        newer = [(path, info) for path, info in stage_inputs if info is not None and info.st_mtime_ns > manifest_info.st_mtime_ns]
        newer.sort(key=lambda item: item[1].st_mtime_ns, reverse=True)
        details['newer_stage_input_count'] = len(newer)
        details['newer_stage_input_examples'] = [str(path.relative_to(root)) for path, _ in newer[:8]]
        if newer:
            fail('staged_content_stale_indicator', f'{len(newer)} map, actor, asset or config inputs are newer than the staged manifest.')

    limitations = [
        'Timestamps are stale indicators only; older or equal timestamps do not prove freshness.',
        'The manifest and containers do not prove the replacement actor was placed, enabled or loads correctly.',
        'A successful matched game-target build and cook, real-spawn test and host/guest LAN test remain required.',
    ]
    return {'status': 'failed' if failures else 'inconclusive', 'project': str(root),
            'failures': failures, 'observations': observations, 'details': details, 'limitations': limitations}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=PROJECT, help='Project root to inspect; defaults to this checkout')
    parser.add_argument('--json', action='store_true', help='Print machine-readable JSON')
    args = parser.parse_args(argv)
    result = audit(args.project)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Package audit: {result['status'].upper()} ({result['project']})")
        for finding in result['failures']:
            print(f"FAIL [{finding['code']}]: {finding['message']}")
        for key, value in result['details'].items():
            print(f'{key}: {value}')
        for limitation in result['limitations']:
            print(f'UNVERIFIED: {limitation}')
    return 1 if result['failures'] else 2


if __name__ == '__main__':
    sys.exit(main())

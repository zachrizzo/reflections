"""Import the four reviewed Leadenhall Northwest meshes by exact package path.

Run --preflight in system Python. For native import, add this directory to
Unreal Python's sys.path and call run() under the codex-gray-london lease.
"""

from pathlib import Path
import sys

from import_west_connector import import_reviewed, verify_sources


ROOT = Path(__file__).resolve().parent / 'LeadenhallNorthwest'
DEST = '/Game/GrayLondon/MedievalOpening/WholeBuildings/LeadenhallNorthwest'
MANIFEST_SHA256 = 'af83dd2b7c53dec0ebc21f0310621982a156cb9686c4c416aa57f13996ce4fdb'
NAMES = {
    'Tile_p03_p01_roof_06ebfe6ef6b61e42': 'SM_GLMedieval_LeadenhallNorthwest_TradingRange_06ebfe6e',
    'Tile_p03_p01_roof_9059607ec79664f6': 'SM_GLMedieval_LeadenhallNorthwest_DeepWorkshop_9059607e',
    'Tile_p03_p01_roof_99e572dd8e67f0cc': 'SM_GLMedieval_LeadenhallNorthwest_SteppedMarket_99e572dd',
    'Tile_p03_p01_roof_ee3443afee1e1296': 'SM_GLMedieval_LeadenhallNorthwest_DeepWorkshop_ee3443af',
}


def preflight():
    return verify_sources(ROOT, ROOT.parents[1] / 'leadenhall_northwest_whole_buildings_candidate.json',
                          ROOT / 'leadenhall_northwest_whole_building_plan.json', MANIFEST_SHA256, NAMES)


def run():
    """Validate imports, then save and persist only the four new owned meshes."""
    import unreal

    return import_reviewed(unreal, preflight(), DEST)


if __name__ == '__main__' and '--preflight' in sys.argv:
    for name, (_, spec, audit) in preflight().items():
        print(f'{DEST}/{name}: {spec["triangles"]} triangles, {len(spec["materials"])} slots, '
              f'prepared SHA-256 {audit["prepared_sha256"]}')

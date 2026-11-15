"""Compile the adapter against small UE test doubles, without launching Unreal.

Coordinate a free shared build window before running this script. Its imported
guard checks the shared lease, train, memory, and editor while either child runs.
"""

from pathlib import Path
import sys
import uuid

HERE = Path(__file__).resolve().parent
CORE = HERE.parent / 'StrongholdRuntimeCore'
sys.path.insert(0, str(CORE))
import run_tests as guard


def main():
    guard.session_guard()
    compiler, environment = guard.windows_compiler()
    output = guard.ROOT / 'Saved/CityPCG/StrongholdAdapterTests' / ('run_' + uuid.uuid4().hex)
    output.mkdir(parents=True)
    args = [str(compiler), '/nologo', '/std:c++17', '/EHsc', '/W4', '/WX',
            '/Fe:stronghold_adapter_tests.exe', '/I' + str(HERE / 'test_stubs'), '/I' + str(CORE),
            str(CORE / 'StrongholdCampaign.cpp'), str(HERE / 'GrayLondonStrongholdCheckpoint.cpp'),
            str(HERE / 'GrayLondonStrongholdOutcome.cpp'),
            str(HERE / 'test_checkpoint_adapter.cpp')]
    guard.run_guarded(args, cwd=output, env=environment)
    guard.run_guarded([str(output / 'stronghold_adapter_tests.exe')], cwd=output, env=environment)
    print(f'Artifacts: {output}')


if __name__ == '__main__':
    main()

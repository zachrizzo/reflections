"""Unreal Editor Python: create candidates without overwriting any asset."""
import unreal

source = '/Game/Blueprints/Combat/Blood/NS_BloodImpact'
root = '/Game/Characters/Hero/SpellVFX'
unreal.EditorAssetLibrary.make_directory(root)
for name in ('NS_WaterImpact', 'NS_HealingBurst'):
    path = f'{root}/{name}'
    if not unreal.EditorAssetLibrary.does_asset_exist(path):
        if not unreal.EditorAssetLibrary.duplicate_asset(source, path):
            raise RuntimeError(f'Could not duplicate {path}')
        unreal.log(f'Created {path}')
    else:
        unreal.log(f'Preserved existing candidate {path}')

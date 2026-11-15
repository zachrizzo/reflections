"""Imports the people book JSON into /Game/Lives/DA_PeopleBook (so packaged builds have it) and saves the asset.
Run in the editor (execute_python), not during a SAVE FREEZE. Source: ArtDirection/Story/people.json, else the stub."""

from pathlib import Path

project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
source = project / 'ArtDirection' / 'Story' / 'people.json'
if not source.exists():
    source = project / 'ArtDirection' / 'Lives' / 'people_stub.json'

path = '/Game/Lives/DA_PeopleBook'
asset = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None
if asset is None:
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    factory = unreal.DataAssetFactory()
    factory.set_editor_property('data_asset_class', unreal.ReflectionsPeopleBookAsset)
    asset = tools.create_asset('DA_PeopleBook', '/Game/Lives', unreal.ReflectionsPeopleBookAsset, factory)
ok = unreal.ReflectionsPeopleBookAsset.import_from_file(asset, str(source))
saved = ok and unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False)
print(f'People book import from {source}: parsed={ok} saved={saved}')

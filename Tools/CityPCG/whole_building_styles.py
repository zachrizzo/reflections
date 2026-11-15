"""Validate explicit, plan-pinned presets without depending on Blender."""

import hashlib
import json


STYLE_PRESETS = {
    'TradingRange': ('GuildRubble', 'LimePlaster', 'Oak', 'ShopRed', 2),
    'SteppedMarket': ('Fieldstone', 'WarmPlaster', 'Oak', 'ShopRed', 2),
    'DeepWorkshop': ('WarmPlaster', 'WarmPlaster', 'WeatheredOak', 'ShopGreen', 1),
}


def plan_lf_sha256(path):
    """Hash the plan's bytes with CRLF pairs converted to LF."""
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def read_style_overrides(path, plan_path, building_ids):
    recipe = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(recipe, dict) or type(recipe.get('schema')) is not int or recipe['schema'] != 1:
        raise ValueError('Expected a schema 1 style override recipe')
    if recipe.get('plan_lf_sha256') != plan_lf_sha256(plan_path):
        raise ValueError('Style overrides must identify the exact reviewed plan by LF-normalized SHA-256')
    overrides = recipe.get('styles')
    if not isinstance(overrides, dict) or not overrides or not overrides.keys() <= building_ids:
        raise ValueError('Style overrides must name one or more building IDs in the reviewed plan')
    for key, name in overrides.items():
        if not isinstance(name, str) or name not in STYLE_PRESETS:
            raise ValueError(f'{key}: unknown style preset {name!r}')
    return overrides

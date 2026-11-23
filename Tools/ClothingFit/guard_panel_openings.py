"""Keep covered-skin masks away from moving garment openings using recorded poses.

Run in Blender with -- samples capture_directory, then in Python with
bake capture_directory. One shared texture is used by the Wardrobe Item.
"""
import json
import sys
from pathlib import Path

import numpy as np


def samples(directory):
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    from audit_posed_surfaces import surface, tree
    from validate_panel_finish import rim_edges
    vertices, tri = surface(directory/'smoothed/rest_cloth0.bin')
    edges = rim_edges(vertices,tri)
    poses = json.loads((directory/'smoothed/frames.json').read_text())
    game = json.loads((directory/'edge_game/frames.json').read_text())['frames']
    blocked = set()
    for name, stage, suffix in ([(k,'smoothed','cloth0') for k in poses] +
                                [(k,'edge_game','after') for k in game]):
        src = directory/stage
        body, body_tri = surface(src/f'{name}_body.bin')
        cloth, topology = surface(src/f'{name}_{suffix}.bin')
        assert np.array_equal(tri,topology)
        skin = tree(body,body_tri)
        a,b = cloth[edges].transpose(1,0,2)
        segments = max(1,int(np.ceil(np.linalg.norm(b-a,axis=1).max()/.4)))
        for t in np.linspace(0,1,segments+1):
            for p in a+(b-a)*t:
                blocked.update(index for _,_,index,_ in skin.find_nearest_range(p,2.0))
    # Veto other skin islands, especially forearms and hands, even when their
    # UVs approach the mask. The wardrobe item has no head mask.
    bones = json.loads((directory/'bones.json').read_text())
    indices = np.fromfile(directory/'dominant_bone.bin',dtype='<u2')
    eligible = np.asarray([bones[str(i)].startswith(('spine','clavicle','pelvis','upperarm')) for i in indices])
    blocked.update(np.flatnonzero(~eligible[body_tri].all(axis=1)).tolist())
    keep_white = sorted(blocked)
    (directory/'guard_triangles.json').write_text(json.dumps(keep_white))
    print(f'{len(keep_white)} protected triangles')


def bake(directory):
    from PIL import Image, ImageDraw, ImageChops, ImageFilter
    src = directory/'SmoothSource'
    image = Image.open(src/'T_PanelReferenceTorso.png').convert('L')
    width,height = image.size
    data = np.fromfile(directory/'smoothed/rest_body.bin',dtype='<u4')
    nv, ni = map(int,data[:2])
    tri = data[2+3*nv:].reshape(-1,3)
    assert tri.size==ni
    uv = np.fromfile(directory/'smoothed/body_uv.bin',dtype='<f4').reshape(-1,2)
    protected = Image.new('L',image.size)
    draw = ImageDraw.Draw(protected)
    for ids in tri[json.loads((directory/'guard_triangles.json').read_text())]:
        coords = uv[ids]
        coords = coords-np.floor(coords.mean(axis=0))
        draw.polygon([(float(u)*width,float(v)*height) for u,v in coords],fill=255)
    out = ImageChops.lighter(image,protected.filter(ImageFilter.MaxFilter(5)))
    assert out.getextrema()==(0,255)
    out.convert('RGB').save(src/'T_PanelCoveredTorso.png')
    print(f'{out.histogram()[0]} core black texels retained of {image.histogram()[0]}')


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    {'samples':samples,'bake':bake}[args[0]](Path(args[1]))

"""Build a light, closed 3D relief from one painted-sign photo on the CPU."""

import argparse
import json
import math
import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'Textures' / 'T_GLMedieval_Wheatsheaf.png'
GRID = 64
WIDTH, HEIGHT = .30, .35
FRONT, BACK = .014, -.013
RING_CENTER = 0.0
BOARD_TOP = -.027


def perspective_points(uv):
    # Main face corners on the source image, before shoulder clipping.
    corners = [(225, 172), (969, 180), (936, 1185), (230, 1135)]
    rows, rhs = [], []
    for (u, v), (x, y) in zip(((0, 1), (1, 1), (1, 0), (0, 0)), corners):
        rows.extend(((u, v, 1, 0, 0, 0, -x*u, -x*v),
                     (0, 0, 0, u, v, 1, -y*u, -y*v)))
        rhs.extend((x, y))
    homography = np.append(np.linalg.solve(rows, rhs), 1).reshape(3, 3)
    projected = np.column_stack((uv, np.ones(len(uv)))) @ homography.T
    return projected[:, :2] / projected[:, 2, None]


def smoothstep(low, high, value):
    ramp = np.clip((value - low) / (high - low), 0, 1)
    return ramp * ramp * (3 - 2*ramp)


def build_mesh(image):
    u, v = np.meshgrid(np.linspace(0, 1, GRID), np.linspace(0, 1, GRID))
    width_factor = 1 - .34*np.clip((v-.80)/.20, 0, 1) - .11*np.clip((.068-v)/.068, 0, 1)
    u = (u - .5) * width_factor + .5
    uv = np.column_stack((u.ravel(), v.ravel()))
    pixel = perspective_points(uv)
    rgba = np.asarray(image)
    center = np.array([620, 670])
    for _ in range(8):
        sample = rgba[np.rint(pixel[:, 1]).astype(int), np.rint(pixel[:, 0]).astype(int)]
        transparent = sample[:, 3] < 215
        pixel[transparent] = .987 * pixel[transparent] + .013 * center
    rgb = rgba[np.rint(pixel[:, 1]).astype(int), np.rint(pixel[:, 0]).astype(int), :3]
    red, green, blue = rgb.astype(float).T
    gold = smoothstep(99, 162, red) * smoothstep(11, 40, green - blue)
    gold = np.asarray(Image.fromarray((gold.reshape(GRID, GRID)*255).astype('uint8')).filter(ImageFilter.GaussianBlur(.85))).ravel() / 255
    depth = FRONT + .011 * gold
    front = list(zip(depth, BOARD_TOP - HEIGHT + uv[:,1]*HEIGHT, -(uv[:,0]-.5)*WIDTH))
    texcoords = list(zip(pixel[:,0]/image.width, pixel[:,1]/image.height))
    faces = []
    for row in range(GRID-1):
        for col in range(GRID-1):
            a = row*GRID + col
            b, c, d = a+1, a+GRID+1, a+GRID
            faces.extend(((a,b,d), (b,c,d)))

    boundary = list(range(GRID)) + list(range(2*GRID-1, GRID*GRID, GRID))
    boundary += list(range(GRID*GRID-2, GRID*(GRID-1)-1, -1))
    boundary += list(range(GRID*(GRID-2), 0, -GRID))
    back_start = len(front)
    vertices = front + [(BACK, front[i][1], front[i][2]) for i in boundary]
    texcoords.extend((0,0) for _ in boundary)
    back_center = len(vertices)
    vertices.append((BACK, BOARD_TOP-HEIGHT/2, 0))
    texcoords.append((0,0))
    shell = []
    for i, first in enumerate(boundary):
        j = (i+1) % len(boundary)
        second, bi, bj = boundary[j], back_start+i, back_start+j
        shell.extend(((second,first,bi), (second,bi,bj), (bj,bi,back_center)))

    ring_base = len(vertices)
    for i in range(32):
        a = 2*math.pi*i/32
        for j in range(8):
            b = 2*math.pi*j/8
            radius = .022 + .0055*math.cos(b)
            vertices.append((.0055*math.sin(b), RING_CENTER + math.cos(a)*radius, math.sin(a)*radius))
            texcoords.append((0,0))
    iron = []
    for i in range(32):
        for j in range(8):
            a = ring_base+i*8+j
            b = ring_base+i*8+(j+1)%8
            c = ring_base+((i+1)%32)*8+(j+1)%8
            d = ring_base+((i+1)%32)*8+j
            iron.extend(((a,d,b),(b,d,c)))
    return np.array(vertices, dtype='<f4'), np.array(texcoords, dtype='<f4'), [faces,shell,iron], rgb


def export_glb(vertices, uv, groups, target):
    materials = [
        {'name':'Painted oak face','pbrMetallicRoughness':{'baseColorTexture':{'index':0},'roughnessFactor':.84,'metallicFactor':0}},
        {'name':'Dark oak edges','pbrMetallicRoughness':{'baseColorFactor':[.095,.055,.031,1],'roughnessFactor':.86,'metallicFactor':0}},
        {'name':'Blackened iron','pbrMetallicRoughness':{'baseColorFactor':[.055,.041,.031,1],'roughnessFactor':.69,'metallicFactor':.72}},
    ]
    model = {'asset':{'version':'2.0','generator':'CPU perspective and color-derived relief'}, 'scene':0,
             'scenes':[{'nodes':[0]}], 'nodes':[{'name':'WheatsheafSign','mesh':0}], 'materials':materials,
             'bufferViews':[], 'accessors':[], 'meshes':[{'primitives':[]}],
             'textures':[{'source':0,'sampler':0}], 'samplers':[{'wrapS':33071,'wrapT':33071}]}
    blob = bytearray()

    def append(data, target=None):
        view = dict(buffer=0, byteOffset=len(blob), byteLength=len(data))
        if target:
            view['target'] = target
        blob.extend(data)
        blob.extend(b'\0' * (-len(blob) % 4))
        model['bufferViews'].append(view)
        return len(model['bufferViews'])-1

    model['accessors'].extend([
        {'bufferView':append(vertices.tobytes(),34962),'componentType':5126,'count':len(vertices),'type':'VEC3',
         'min':vertices.min(0).tolist(),'max':vertices.max(0).tolist()},
        {'bufferView':append(uv.tobytes(),34962),'componentType':5126,'count':len(uv),'type':'VEC2'},
    ])
    for material, triangles in enumerate(groups):
        triangles = np.asarray(triangles, dtype='<u2')
        first_edge = vertices[triangles[:, 1]] - vertices[triangles[:, 0]]
        second_edge = vertices[triangles[:, 2]] - vertices[triangles[:, 0]]
        face_normals = np.cross(first_edge, second_edge)
        normals = np.zeros_like(vertices)
        for corner in triangles.T:
            np.add.at(normals, corner, face_normals)
        lengths = np.linalg.norm(normals, axis=1)
        used = lengths > 1e-12
        normals[used] /= lengths[used, None]
        normals[~used] = (1, 0, 0)
        normal_accessor = len(model['accessors'])
        model['accessors'].append({'bufferView':append(normals.tobytes(),34962),'componentType':5126,
                                   'count':len(normals),'type':'VEC3'})
        model['accessors'].append({'bufferView':append(triangles.tobytes(),34963),'componentType':5123,
                                   'count':triangles.size,'type':'SCALAR'})
        model['meshes'][0]['primitives'].append({'attributes':{'POSITION':0,'TEXCOORD_0':1,'NORMAL':normal_accessor},
                                                 'indices':len(model['accessors'])-1,'material':material})
    model['images'] = [{'bufferView':append(SOURCE.read_bytes()),'mimeType':'image/png'}]
    model['buffers'] = [{'byteLength':len(blob)}]
    encoded = json.dumps(model,separators=(',',':')).encode()
    encoded += b' ' * (-len(encoded) % 4)
    target.write_bytes(struct.pack('<4sII',b'glTF',2,28+len(encoded)+len(blob)) +
                       struct.pack('<I4s',len(encoded),b'JSON') + encoded +
                       struct.pack('<I4s',len(blob),b'BIN\0') + blob)


def preview(vertices, groups, rgb, target):
    size = (430,495)
    sheet = Image.new('RGB',(2*size[0],size[1]),(34,36,39))
    triangle_sets = np.concatenate([np.asarray(items) for items in groups])
    base_colors = np.concatenate([rgb[groups[0]].mean(axis=1),np.tile([82,58,39],(len(groups[1]),1)),
                                  np.tile([62,52,44],(len(groups[2]),1))])
    edges = vertices[triangle_sets[:,1:]] - vertices[triangle_sets[:,:1]]
    normals = np.cross(edges[:,0], edges[:,1]); normals /= np.linalg.norm(normals,axis=1)[:,None]
    light = np.array([.75,.53,.40]); light /= np.linalg.norm(light)
    shade = .38 + .62*np.maximum(0,normals @ light)
    for index, angle in enumerate((0.20, 0.95)):
        look = np.array([math.cos(angle),.17,math.sin(angle)]); look /= np.linalg.norm(look)
        right = np.cross([0,1,0],look); right /= np.linalg.norm(right)
        up = np.cross(look,right)
        points = np.column_stack((215 + 1000*(vertices @ right),55 - 1000*(vertices @ up)))
        distance = (vertices @ look)[triangle_sets].mean(axis=1)
        draw = ImageDraw.Draw(sheet)
        for face in np.argsort(distance):
            if normals[face] @ look <= 0:
                continue
            color = base_colors[face] if index==0 else np.array([181,185,190])
            xy = [(int(x)+index*size[0],int(y)) for x,y in points[triangle_sets[face]]]
            draw.polygon(xy,tuple((color*shade[face]).astype(int)))
    sheet.save(target)


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output_dir', type=Path)
    output = parser.parse_args().output_dir
    output.mkdir(parents=True, exist_ok=True)
    with Image.open(SOURCE) as image:
        vertices, uv, groups, rgb = build_mesh(image.convert('RGBA'))
    export_glb(vertices, uv, groups, output / 'wheatsheaf_relief.glb')
    preview(vertices, groups, rgb, output / 'wheatsheaf_relief_preview.png')
    print(f'{len(vertices)} vertices, {sum(len(g) for g in groups)} triangles, bounds in metres {np.ptp(vertices,axis=0)}')

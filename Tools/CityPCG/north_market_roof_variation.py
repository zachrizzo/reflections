"""Review-only additions for two surveyed North Market buildings.

This module does not open Blender, emit files, or modify a building source.
The hosted companion writes the returned meshes after checking the inputs.
"""
import math

import north_market_tenancies as tenancy


MODELS = {
    'east_0a73564b': ('Tile_p03_p01_roof_0a73564b5b0ed26a', 'TradingRange'),
    'east_31c9ff1a': ('Tile_p03_p01_roof_31c9ff1a824fb2fd', 'DeepWorkshop'),
}
TILES = dict(tenancy.TILES, ClayTile=1.0, LeadedGlass=1.0)


def roof_height(y, profile):
    if (len(profile) < 3 or any(not math.isfinite(v) for p in profile for v in p)
            or any(a[0] >= b[0] for a, b in zip(profile, profile[1:]))
            or not profile[0][0] <= y <= profile[-1][0]):
        raise ValueError('Invalid actual source roof profile')
    for (lo, a), (hi, b) in zip(profile, profile[1:]):
        if y <= hi:
            return a + (b-a)*(y-lo)/(hi-lo) + .089  # actual tiled roof skin
    raise ValueError('Roof station is outside profile')


def x_spans(plot, y):
    xs = sorted(a[0] + (b[0]-a[0])*(y-a[1])/(b[1]-a[1])
                for a, b in zip(plot, plot[1:]+plot[:1]) if (a[1]>y) != (b[1]>y))
    if len(xs) % 2:
        raise ValueError('Invalid footprint intersection')
    return list(zip(xs[::2], xs[1::2]))


def distance_to_edge(p, a, b):
    dx, dy = b[0]-a[0], b[1]-a[1]
    d = dx*dx+dy*dy
    if d < 1e-14:
        raise ValueError('Degenerate surveyed edge')
    t = min(1., max(0., ((p[0]-a[0])*dx+(p[1]-a[1])*dy)/d))
    return math.hypot(p[0]-a[0]-t*dx, p[1]-a[1]-t*dy)


def safe_rectangle(rect, plot, party_edges, margin=.30):
    # Check the entire perimeter across concavities, plus a conservative
    # distance from every party-wall line segment (not just its endpoints).
    if any(not tenancy.segment_inside(a, b, plot) for a, b in zip(rect, rect[1:]+rect[:1])):
        return False
    edges = list(zip(plot, plot[1:]+plot[:1]))
    for index, (a, b) in enumerate(edges):
        limit = 1.0 if index in party_edges else margin
        for c, d in zip(rect, rect[1:]+rect[:1]):
            if min(distance_to_edge(c,a,b), distance_to_edge(d,a,b),
                   distance_to_edge(a,c,d), distance_to_edge(b,c,d)) < limit:
                return False
    return True


def source_chimneys(plot, profile, style):
    # Same candidate locations and envelope tests as the source generator.
    # The manifest records only the count, so reconstruct these positions.
    limit = 3 if style == 'TradingRange' else 1
    heads = []
    cap = max(z for _, z in profile) + .089
    for index in range(0, len(profile)-1, 2):
        if len(heads) >= limit:
            break
        low, high = profile[index][0], profile[index+2][0]
        found = False
        for fraction in (.26,.73,.18,.82):
            y = low+(high-low)*fraction
            spans = sorted(x_spans(plot,y), key=lambda p:p[1]-p[0], reverse=True)
            for first,last in spans:
                if last-first < 2.5:
                    continue
                x = first+(last-first)*(.42 if index % 4 == 0 else .67)
                envelope = [(x+dx,y+dy) for dx in (-.49,.49) for dy in (-.53,.53)]
                roof_top = max(roof_height(yy,profile) for _,yy in envelope)
                top = min(cap-.02,roof_top+1.0)
                if top-roof_top >= .63 and all(tenancy.contains(p,plot) for p in envelope):
                    heads.append((x,y,top)); found=True; break
            if found:
                break
    return heads


def face(mesh, points, role):
    if role not in TILES or len(points) < 3:
        raise ValueError('Invalid detail face')
    if any(not all(math.isfinite(v) for v in p) or p[2] < 0 or p[2] > mesh.ceiling for p in points):
        raise ValueError('Detail leaves height envelope')
    tenancy.normal_and_uv(points, TILES[role])
    start = len(mesh.vertices)
    mesh.vertices.extend(points)
    mesh.faces.append(tuple(range(start,start+len(points))))
    mesh.roles.append(role)


def box(mesh, x0, x1, y0, y1, z0, z1, role):
    if not (x0<x1 and y0<y1 and z0<z1):
        raise ValueError('Invalid detail box')
    v=[(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),
       (x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]
    for indices in ((3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)):
        face(mesh,[v[i] for i in indices],role)


def dormer(mesh, rect, profile, variant):
    x0,y0=rect[0]; x1,y1=rect[2]; mid=(y0+y1)/2
    low0,low1=roof_height(y0,profile)-.035,roof_height(y1,profile)-.035
    high=max(low0,low1)+(.88 if variant==0 else 1.04)
    peak=high+(.60 if variant==0 else .42)
    if peak > mesh.ceiling-.10:
        raise ValueError('Dormer exceeds surveyed maximum height')
    wall='LimePlaster' if variant==0 else 'WarmPlaster'
    # Lower edges deliberately intersect the tiled roof by 3.5 cm. A roof
    # opening is NOT cut; these are solid decorative additions for review.
    left=[(x0,y0,low0),(x1,y0,low0),(x1,y0,high),(x0,y0,high)]
    right=[(x1,y1,low1),(x0,y1,low1),(x0,y1,high),(x1,y1,high)]
    front=[(x1,y0,low0),(x1,y1,low1),(x1,y1,high),(x1,mid,peak),(x1,y0,high)]
    back=[(x0,y0,low0),(x0,y0,high),(x0,mid,peak),(x0,y1,high),(x0,y1,low1)]
    for polygon in (left,right,front,back): face(mesh,polygon,wall)
    face(mesh,[(x0,y0,high),(x1,y0,high),(x1,mid,peak),(x0,mid,peak)],'ClayTile')
    face(mesh,[(x0,mid,peak),(x1,mid,peak),(x1,y1,high),(x0,y1,high)],'ClayTile')
    # Individual framed, leaded-look lights and a sill; all above the roof.
    bottom=max(low0,low1)+.13; top=high-.12
    if top-bottom < .35: raise ValueError('Dormer light too short')
    width=(y1-y0)*(.31 if variant==0 else .37)
    box(mesh,x1+.008,x1+.023,mid-width,mid+width,bottom,top,'LeadedGlass')
    for y in (mid-width,mid,mid+width):
        box(mesh,x1+.022,x1+.052,y-.025,y+.025,bottom,top,'Oak')
    for z in (bottom,top):
        box(mesh,x1+.022,x1+.055,mid-width-.035,mid+width+.035,z-.03,z+.03,'Oak')
    box(mesh,x1+.020,x1+.075,mid-width-.09,mid+width+.09,bottom-.08,bottom-.025,'WeatheredOak')
    return {'roof_bottom_m':[low0,low1],'eave_m':high,'ridge_m':peak,'rect_xy_m':rect,
            'variant':'tall_gable' if variant==0 else 'low_gable'}


def upper_shutters(mesh, building, style, party_edges):
    plot=mesh.plot; walls=tenancy.inset(plot); edge=building['entry']['edge']
    if edge in party_edges: raise ValueError('Entry overlaps a protected party wall')
    a,b=walls[edge],walls[(edge+1)%len(walls)]
    dx,dy=b[0]-a[0],b[1]-a[1]; length=math.hypot(dx,dy)
    tangent=(dx/length,dy/length); normal=(tangent[1],-tangent[0])
    if normal[0] < .94:
        raise ValueError('This trial requires an exposed local +X entry frontage')
    center=(length/2)
    left,right=-length*.5+.38,length*.5-.38
    bents=max(1,math.ceil((right-left)/2.7))
    weights=[(1.13,.79,1.07,1.24,.91)[i%5] for i in range(bents)]
    divisions=[left]
    for weight in weights: divisions.append(divisions[-1]+(right-left)*weight/sum(weights))
    eave=float(building['roof_profile_local_y_z_m'][0][1])
    storeys=max(2,round(eave/2.7)); floors=[eave*i/storeys for i in range(storeys+1)]
    placed=[]
    for i,(u,v) in enumerate(zip(divisions,divisions[1:])):
        # Sparse closed shutters are intentional covers over known generated
        # upper lights; no geometry is added over entry or ground-storey.
        if i%3 != (1 if style=='TradingRange' else 2): continue
        mid=(u+v)/2; half=min((.58,.68,.42,.63)[i%4],(v-u)*.31)
        if half<.30 or style=='TradingRange' and (i%9==7 or i%7==3): continue
        level=0; low=floors[1]+(.54,.75,.66,.59)[(i+level)%4]
        high=min(low+(.92,1.19,.82)[i%3],floors[2]-.28)
        if low<3.1 or high<=low: raise ValueError('Shutter is too low')
        role=('WeatheredOak','ShopRed','ShopGreen')[(i//3+(style=='DeepWorkshop'))%3]
        def xy(station, depth):
            return (a[0]+tangent[0]*station+normal[0]*depth,
                    a[1]+tangent[1]*station+normal[1]*depth)
        bounds=[xy(center+mid-half,.245),xy(center+mid+half,.245),
                xy(center+mid+half,.298),xy(center+mid-half,.298)]
        if not safe_rectangle(bounds,plot,party_edges,margin=0):
            continue
        # Original window front reaches at most .226m from inset wall;
        # new .245-.298m boards sit in front, fully within the surveyed outline.
        for j in range(4):
            lo=mid-half+(2*half)*j/4+.008; hi=mid-half+(2*half)*(j+1)/4-.008
            mesh.box(a,tangent,normal,center+lo,center+hi,low,high,.245,.282,role)
        for z in (low+.10,high-.16):
            mesh.box(a,tangent,normal,center+mid-half,center+mid+half,z,z+.06,.283,.298,'WeatheredOak')
        placed.append({'edge':edge,'window_bent':i,'height_m':[low,high],
                       'status':'closed shutters intentionally cover an existing upper window'})
    if not placed: raise ValueError('No suitable upper window found')
    return placed


def make_variation(building, source_row, style, party_edges=()):
    if style not in ('TradingRange','DeepWorkshop') or source_row['style']!=style:
        raise ValueError('Unexpected building style')
    plot=[tuple(p) for p in building['footprint_local_m']]
    profile=[tuple(p) for p in source_row['roof_profile_local_y_z_m']]
    party=set(party_edges)
    if any(not isinstance(i,int) or not 0<=i<len(plot) for i in party):
        raise ValueError('Invalid party-wall edge')
    mesh=tenancy.Mesh(plot,float(building['source_max_height_m']))
    stacks=source_chimneys(plot,profile,style)
    if len(stacks)!=source_row['chimney_count']:
        raise ValueError('Source chimney count does not match reconstruction')
    shutters=upper_shutters(mesh,building,style,party)
    dormers=[]
    for i in range(0,len(profile)-1,2):
        if style=='DeepWorkshop' and i%4: continue
        low,high=profile[i][0],profile[i+1][0]
        y=low+(high-low)*(.46 if style=='TradingRange' else .55)
        half=min(.62,(high-low)*.23)
        spans=x_spans(plot,y)
        if not spans: continue
        x=max(b for _,b in spans)-.75
        rect=[(x-1.08,y-half),(x+.08,y-half),(x+.08,y+half),(x-1.08,y+half)]
        # Window frames and sill project up to 0.075m beyond the gable face.
        envelope=[rect[0],(rect[1][0]+.075,rect[1][1]),
                  (rect[2][0]+.075,rect[2][1]),rect[3]]
        if not safe_rectangle(envelope,plot,party): continue
        if any(rect[0][0]-.60 <= cx <= rect[2][0]+.60 and
               rect[0][1]-.65 <= cy <= rect[2][1]+.65 for cx,cy,_ in stacks): continue
        dormers.append(dormer(mesh,rect,profile,(i//4+(style=='DeepWorkshop'))%2))
    if not dormers: raise ValueError('No safe dormer location')
    return mesh, {'shutters':shutters,'dormers':dormers,'source_chimneys_m':stacks,
                  'limitation':'Decorative roof additions intersect the existing roof; no roof openings are cut.'}


def write_geometry(out,mesh):
    for p in mesh.vertices: out.write('v '+' '.join(repr(x) for x in p)+'\n')
    uv_base=0; previous=None
    for index,(indices,role) in enumerate(zip(mesh.faces,mesh.roles),1):
        if role!=previous: out.write('usemtl M_GLMedieval_'+role+'\n'); previous=role
        normal,uvs=tenancy.normal_and_uv([mesh.vertices[i] for i in indices],TILES[role])
        for uv in uvs: out.write('vt '+' '.join(repr(x) for x in uv)+'\n')
        out.write('vn '+' '.join(repr(x) for x in normal)+'\n')
        out.write('f '+' '.join(f'{v+1}/{uv_base+i+1}/{index}' for i,v in enumerate(indices))+'\n')
        uv_base+=len(indices)

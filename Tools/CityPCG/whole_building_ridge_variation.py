"""Opt-in, deterministic asymmetric ridge positions for surveyed roof ranges.

These functions change the complete building's roof profile, not an overlay.
They do not authorize placement, source-tile replacement or gameplay use.
"""
import hashlib
import math


FRACTIONS=(.33,.42,.58,.67)
TILE_SKIN_M=.089


def vary_ridges(profile,building_id,source_max_height,party_edges=()):
    """Move each internal ridge while retaining all valleys and ridge heights.

    The existing generator uses one continuous Y/Z profile along the plot's
    local X axis. Only its symmetric, equal-eave pitched ranges are supported.
    Shared party-wall roofs need an explicit paired-edge solution and fail
    closed; nothing here establishes that a plan's edge survey is complete.
    """
    if not isinstance(building_id,str) or not building_id or len(building_id)>200:
        raise ValueError('Expected a surveyed building ID')
    if party_edges:
        raise ValueError('Shared party-wall roofs require a paired solution')
    if (not isinstance(source_max_height,(int,float)) or isinstance(source_max_height,bool)
            or not math.isfinite(source_max_height) or source_max_height<=0):
        raise ValueError('Invalid surveyed height')
    if not isinstance(profile,(list,tuple)) or len(profile)<3 or len(profile)%2!=1:
        raise ValueError('Expected alternating valleys and ridges')
    result=[]
    for point in profile:
        if (not isinstance(point,(list,tuple)) or len(point)!=2 or
                any(not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) for v in point)):
            raise ValueError('Invalid roof-profile point')
        result.append(tuple(point))
    if any(a[0]>=b[0] for a,b in zip(result,result[1:])):
        raise ValueError('Roof-profile stations must be strictly increasing')
    seed=int.from_bytes(hashlib.sha256(building_id.encode('utf-8')).digest()[:4],'big')
    for index in range(1,len(result),2):
        lo,peak,hi=result[index-1:index+2]
        width=hi[0]-lo[0]
        if (width<4.5 or abs(lo[1]-hi[1])>1e-5
                or abs(peak[0]-(lo[0]+hi[0])*.5)>1e-5
                or peak[1]<max(lo[1],hi[1])+1.65
                or peak[1]+TILE_SKIN_M>source_max_height+1e-6):
            raise ValueError('Unsupported roof range or surveyed height')
        station=lo[0]+width*FRACTIONS[(seed+index//2)%len(FRACTIONS)]
        if min(station-lo[0],hi[0]-station)<1.4:
            raise ValueError('Ridge would be too close to a valley')
        result[index]=(station,peak[1])
    return result

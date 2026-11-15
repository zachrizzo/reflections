"""Mock Lanthorne places -> real spots in Gray London's Tower district, with map offsets.

The Gray London map (Content/GrayLondon/Maps/GrayLondon_Geodata) is in British National Grid (EPSG:27700) with its
local origin at 51.5080 N, 0.1281 W (Docs/GrayLondon/GRAY_LONDON_DATA_SOURCES.md). This script projects each spot's
WGS84 lat/lon with the OSGB transverse Mercator (Airy 1830) formulas and subtracts the origin, giving metres east and
north of the map origin. The ~100 m WGS84/OSGB36 datum shift is nearly constant over a few km, so it cancels in the
difference (error about 1 m). Which Unreal axis is east or north, and its sign, must be calibrated in the editor against
one landmark actor (the Tower of London model): see GrayLondon_Plan.md, step 0.

Run: python graylondon_places.py   (prints the table; --json writes graylondon_places.json next to this file)
"""
import json
import math
import os
import sys

ORIGIN = (51.5080, -0.1281)

# place key (mock) -> (real spot, lat, lon, note). Lat/lon are approximate public coordinates of the spot.
PLACES = {
    'Intro':            ('Great Tower Street, outside the inn', 51.51003, -0.08070, 'game start; the hero arrives here'),
    'Lamplight':        ('Corner building, Great Tower St / Mark Lane', 51.51010, -0.08045, 'the inn (Long Shelter in Frostside); no real pub name in game'),
    'LamplightCellar':  ('Mark Lane, side door', 51.51040, -0.08060, ''),
    'BellLane':         ('Byward Street', 51.50985, -0.07985, 'three failing lamps'),
    'BellSquare':       ('All Hallows by the Tower churchyard', 51.50970, -0.07955, 'square with the church bells; first conversion'),
    'Fountain':         ('All Hallows churchyard, centre', 51.50978, -0.07940, 'dry fountain / Cistern: a set piece here'),
    'Square_Cistern':   ('All Hallows churchyard, centre', 51.50978, -0.07940, ''),
    'WeighHouseCorner': ('Seething Lane Garden, south-east corner', 51.50995, -0.07990, 'Pewterside page: set piece Weigh-House'),
    'WeighHouseStair':  ('Seething Lane Garden, west side', 51.51000, -0.08015, ''),
    'WeighHouseRoof':   ('Seething Lane Garden (set piece roof)', 51.51005, -0.08000, 'z = set piece roof'),
    'TowerPlaza':       ('Trinity Square Gardens', 51.50985, -0.07730, 'open lawn on Tower Hill'),
    'TowerFoot':        ('Trinity Square Gardens, south lawn', 51.50965, -0.07725, 'the mirror tower set piece (all sides)'),
    'ArchiveSteps':     ('Trinity House steps', 51.51010, -0.07745, 'Ice Stairs in Frostside'),
    'ArchiveTerrace':   ('Trinity House portico', 51.51015, -0.07750, ''),
    'IceWall':          ('London Wall (Roman), Tower Hill', 51.51035, -0.07605, 'Frostside wall'),
    'LanternRow':       ('Leadenhall Market, central crossing', 51.51270, -0.08360, 'market stalls; Bone Market in Frostside'),
    'LanternRowEast':   ('Leadenhall Market, Whittington Avenue', 51.51275, -0.08290, ''),
    'Furnace':          ('Lime Street', 51.51235, -0.08280, ''),
    'ThraleShop':       ('Gracechurch Street, east side', 51.51240, -0.08440, ''),
    'VaneAtelier':      ('Leadenhall Place', 51.51300, -0.08300, ''),
    'LanternGate':      ('Tower Bridge, north tower', 51.50580, -0.07545, 'the gate; hold it'),
    'GateBridge':       ('Tower Bridge, deck', 51.50550, -0.07540, ''),
    'WatchPost':        ('Tower Bridge Approach, north end', 51.50680, -0.07480, 'Gilt Tower key pedestal'),
    'DrifterCamp':      ("St Katharine's Way, under the approach", 51.50630, -0.07390, 'drifters under the gate'),
    'CanalRift':        ('Tower Wharf, riverside', 51.50670, -0.07790, 'the river edge'),
    'FishSteps':        ('Old Billingsgate Walk, river stairs', 51.50880, -0.08370, 'old fish market'),
    'MusterYard':       ('Royal Mint Court, courtyard', 51.50950, -0.07230, 'walled yard'),
    'BarracksWest':     ('10 Trinity Square, frontage', 51.50990, -0.07860, 'Watch barracks'),
    'BarracksEast':     ('Royal Mint Court, east block', 51.50940, -0.07160, 'Wall Company barracks'),
    'CoalLaneStop':     ('Fenchurch Street station forecourt', 51.51150, -0.07850, 'the stop'),
    'HesterDoorstep':   ('Crutched Friars', 51.51100, -0.07740, ''),
    'CoalLaneLaundry':  ("Cooper's Row", 51.51060, -0.07650, ''),
    'WickStreet':       ('Mark Lane, north', 51.51090, -0.08070, 'infirmary'),
    'Yard':             ("Cooper's Row, wall courtyard", 51.51070, -0.07620, "Sorrel's yard"),
    'Shed':             ("Cooper's Row, wall courtyard shed", 51.51075, -0.07630, ''),
    # Calibration references (landmark models in the map), not story places.
    'Ref_TowerOfLondon': ('Tower of London, precinct centre (White Tower)', 51.50810, -0.07610, 'calibration'),
    'Ref_TowerBridge':   ('Tower Bridge, centre span', 51.50550, -0.07540, 'calibration'),
}


def tm(lat_deg, lon_deg):
    """WGS84 lat/lon taken as OSGB36 -> OS National Grid easting/northing (m). Ordnance Survey formulas."""
    a, b = 6377563.396, 6356256.909
    f0 = 0.9996012717
    lat0, lon0 = math.radians(49.0), math.radians(-2.0)
    n0, e0 = -100000.0, 400000.0
    e2 = 1 - (b * b) / (a * a)
    n = (a - b) / (a + b)
    lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    sin, cos, tan = math.sin(lat), math.cos(lat), math.tan(lat)
    nu = a * f0 / math.sqrt(1 - e2 * sin * sin)
    rho = a * f0 * (1 - e2) / (1 - e2 * sin * sin) ** 1.5
    eta2 = nu / rho - 1
    ma = (1 + n + 5 / 4 * n ** 2 + 5 / 4 * n ** 3) * (lat - lat0)
    mb = (3 * n + 3 * n ** 2 + 21 / 8 * n ** 3) * math.sin(lat - lat0) * math.cos(lat + lat0)
    mc = (15 / 8 * n ** 2 + 15 / 8 * n ** 3) * math.sin(2 * (lat - lat0)) * math.cos(2 * (lat + lat0))
    md = 35 / 24 * n ** 3 * math.sin(3 * (lat - lat0)) * math.cos(3 * (lat + lat0))
    m = b * f0 * (ma - mb + mc - md)
    i = m + n0
    ii = nu / 2 * sin * cos
    iii = nu / 24 * sin * cos ** 3 * (5 - tan ** 2 + 9 * eta2)
    iiia = nu / 720 * sin * cos ** 5 * (61 - 58 * tan ** 2 + tan ** 4)
    iv = nu * cos
    v = nu / 6 * cos ** 3 * (nu / rho - tan ** 2)
    vi = nu / 120 * cos ** 5 * (5 - 18 * tan ** 2 + tan ** 4 + 14 * eta2 - 58 * tan ** 2 * eta2)
    dl = lon - lon0
    northing = i + ii * dl ** 2 + iii * dl ** 4 + iiia * dl ** 6
    easting = e0 + iv * dl + v * dl ** 3 + vi * dl ** 5
    return easting, northing


def offsets():
    e0, n0 = tm(*ORIGIN)
    rows = {}
    for key, (spot, lat, lon, note) in PLACES.items():
        e, n = tm(lat, lon)
        rows[key] = {'spot': spot, 'lat': lat, 'lon': lon, 'east_m': round(e - e0, 1), 'north_m': round(n - n0, 1),
                     'note': note}
    return rows


if __name__ == '__main__':
    rows = offsets()
    for k, r in rows.items():
        print('%-17s %8.1f E %8.1f N  %s' % (k, r['east_m'], r['north_m'], r['spot']))
    if '--json' in sys.argv:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'graylondon_places.json'), 'w', encoding='utf-8') as f:
            json.dump(rows, f, indent=1)

F = AR.mesh_dir(-1.0)   # travels backward (hit from the front)
B = AR.mesh_dir(1.0)    # travels forward (hit from behind)
EVENTS = [
  (1.0, 'hit', {'bone': 'spine_04', 'direction': F, 'strength': 1.0}),
  (3.0, 'hit', {'bone': 'upperarm_r', 'direction': AR.mesh_dir(-0.4, -1.0), 'strength': 1.0}),
  (5.0, 'drop', {'target': 'head', 'height': 200.0, 'mass': 8.0}),
  (8.0, 'stagger', {'bone': 'spine_04', 'direction': F, 'strength': 1.0}),
  (11.5, 'stagger', {'bone': 'spine_04', 'direction': B, 'strength': 1.0}),
  (15.0, 'drop', {'target': 'spine_04', 'mass': 30.0, 'speed': 950.0, 'from_dir': F}),
  (25.0, 'knockdown', {'bone': 'spine_04', 'direction': B, 'strength': 1.0}),
]
MAXDUR = 150
p = AR.S['hero'].get_actor_location()
cam((p.x - 340.0, p.y - 150.0, 150.0), (p.x, p.y + 10.0, 85.0))
builtins.__dict__['_AR_T0'] = AR.S['t']

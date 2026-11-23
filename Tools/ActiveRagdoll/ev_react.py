# Verification run for "physics only when hit": events in world seconds after scheduling (AR.schedule).
F = AR.mesh_dir(-1.0)   # travels backward (hit from the front)
B = AR.mesh_dir(1.0)    # travels forward (hit from behind)
EVENTS = [
  (1.5, 'hit', {'bone': 'spine_04', 'direction': F, 'strength': 1.0}),
  (4.5, 'hit', {'bone': 'upperarm_r', 'direction': AR.mesh_dir(-0.4, -1.0), 'strength': 1.0}),
  (7.5, 'drop', {'target': 'head', 'height': 200.0, 'mass': 8.0}),
  (10.5, 'play', {'key': 'walk', 'loop': True}),
  (12.5, 'hit', {'bone': 'spine_04', 'direction': F, 'strength': 1.0}),
  (15.5, 'play', {'key': 'idle', 'loop': True}),
  (16.5, 'stagger', {'bone': 'spine_04', 'direction': F, 'strength': 1.0}),
  (21.0, 'drop', {'target': 'spine_04', 'mass': 30.0, 'speed': 950.0, 'from_dir': F}),
]
T_END = 34.0
MAXDUR = 150
p = AR.S['hero'].get_actor_location()
cam((p.x - 340.0, p.y - 150.0, 150.0), (p.x, p.y + 10.0, 85.0))
builtins.__dict__['_AR_T0'] = AR.S['t']

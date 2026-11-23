# Verification run: the get-up is pure animation; new force mid get-up wakes physics again.
F = AR.mesh_dir(-1.0)   # travels backward (hit from the front)
B = AR.mesh_dir(1.0)    # travels forward (hit from behind)
AR.S['when'] = []
_t0 = AR.S['t']
EVENTS = [
  (1.5, 'drop', {'target': 'spine_04', 'mass': 30.0, 'speed': 950.0, 'from_dir': F}),
  (9.0, 'drop', {'target': 'spine_04', 'mass': 30.0, 'speed': 950.0, 'from_dir': B}),
]
# case 1: a chest hit 0.6 s into the first (pure animation) get-up
AR.when('GETUP_ANIM', 0.6, 'hit', {'bone': 'spine_04', 'direction': F, 'strength': 1.0}, not_before=_t0)
# case 2: a strong shove 0.5 s into the second get-up knocks him back down
AR.when('GETUP_ANIM', 0.5, 'knockdown', {'bone': 'spine_04', 'direction': F, 'strength': 1.0}, not_before=_t0 + 8.5)
T_END = 24.0
MAXDUR = 150
p = AR.S['hero'].get_actor_location()
cam((p.x - 340.0, p.y - 150.0, 150.0), (p.x, p.y + 10.0, 85.0))
builtins.__dict__['_AR_T0'] = AR.S['t']

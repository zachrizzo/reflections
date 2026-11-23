import rel_test
RT = builtins.__dict__.get('_AR_REL', {})
_res = rel_test.get() if not RT.get('done') else RT.get('results')
json.dumps({'done': True, 'i': 0, 'n': 1, 'error': None, 'results': _res}, default=str)

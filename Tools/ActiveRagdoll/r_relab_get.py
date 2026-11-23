RT = builtins.__dict__.get('_AR_REL', {})
json.dumps({'done': RT.get('done'), 'i': RT.get('ab', {}).get('i'), 'n': 5, 'error': RT.get('error'), 'results': RT.get('ab', {}).get('rows') if RT.get('done') else None}, default=str)

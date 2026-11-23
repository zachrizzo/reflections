PT = builtins.__dict__.get('_AR_PLAIN', {})
json.dumps({'done': PT.get('done'), 'i': 0, 'n': 1, 'error': PT.get('error'), 'results': PT.get('results') if PT.get('done') else None}, default=str)

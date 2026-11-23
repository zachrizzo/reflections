import drift_test
DT = builtins.__dict__.get('_AR_DRIFT', {})
json.dumps({'done': DT.get('done'), 'i': DT.get('i'), 'n': len(DT.get('phases', [])), 'error': DT.get('error'),
            'path_clear': DT.get('path_clear'), 'table': drift_test.table() if DT.get('done') else None,
            'results': DT.get('results') if DT.get('done') else None}, default=str)

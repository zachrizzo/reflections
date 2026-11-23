json.dumps({'log': list(builtins.__dict__.get('_AR_LOG', [])), 'events': AR.S.get('events'), 'impacts': AR.S.get('impacts'),
            't0': builtins.__dict__.get('_AR_T0')}, default=str)

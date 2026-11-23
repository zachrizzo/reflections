json.dumps({'t': round(AR.S.get('t', 0.0) - builtins.__dict__.get('_AR_T0', 0.0), 2), 'state': AR.S.get('state'),
            'env': round(AR.S.get('env', 0.0), 2), 'script_left': len(AR.S.get('script') or []), 'pcc_tick_off': AR.S.get('pcc_tick_off')})

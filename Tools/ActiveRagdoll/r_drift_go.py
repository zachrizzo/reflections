import drift_test
importlib.reload(drift_test)
DRIFT_INFO = drift_test.start(phases={'diag': drift_test.DIAG_PHASES, 'ab': drift_test.AB_PHASES, 'body': drift_test.BODY_PHASES, 'ctrl': drift_test.CTRL_PHASES, 'pelvis': drift_test.PELVIS_PHASES, 'arms': drift_test.ARM_PHASES, 'relax': drift_test.RELAX_PHASES, 'coll': drift_test.COLL_PHASES, 'sync': drift_test.SYNC_PHASES}.get(globals().get('PHASESET')))
json.dumps(DRIFT_INFO, default=str)

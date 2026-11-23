r = await call_tool('SceneCaptureToolset.SceneCaptureToolset.StartViewportRecording', options={'source': 'EditorViewport', 'maxResolution': 1280, 'frameRate': 30, 'maxDurationSeconds': globals().get('MAXDUR', 30)})
builtins.__dict__['_AR_REC'] = r['recordingId'] if isinstance(r, dict) and 'recordingId' in r else (r.get('returnValue', {}) or {}).get('recordingId') if isinstance(r, dict) else str(r)
EV = globals().get('EVENTS')
n = AR.schedule(EV) if EV else 0
json.dumps({'rec': str(r)[:300], 'scheduled': n})

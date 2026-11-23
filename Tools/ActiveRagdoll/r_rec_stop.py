rid = builtins.__dict__.get('_AR_REC')
r = await call_tool('SceneCaptureToolset.SceneCaptureToolset.StopViewportRecording', recordingId=rid)
json.dumps(r, default=str)[:800]

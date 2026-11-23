import drift_test
_eye, _aim = drift_test.cam_for(globals().get('VIEW', 'front'))
cam(_eye, _aim)
'cam %s' % globals().get('VIEW', 'front')

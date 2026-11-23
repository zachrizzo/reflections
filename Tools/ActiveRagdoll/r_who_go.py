import who_test
importlib.reload(who_test)
builtins.__dict__['_AR_WHO']['first'] = who_test.snapshot()
json.dumps({'n': len(builtins.__dict__['_AR_WHO']['first'])})

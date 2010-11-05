import py
from pypy.conftest import option, gettestobjspace

def pytest_ignore_collect(path, config):
    if config.option.runappdirect:
        return True # "cannot be run by py.test -A"
    # ensure additional functions are registered
    import pypy.module.cpyext.test.test_cpyext
    return False

def pytest_funcarg__space(request):
    return gettestobjspace(usemodules=['cpyext', 'thread'])

def pytest_funcarg__api(request):
    return request.cls.api

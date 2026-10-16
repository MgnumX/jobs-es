from .models import Job

SOURCES = {}


def register(name):
    def deco(fn):
        SOURCES[name] = fn
        return fn
    return deco

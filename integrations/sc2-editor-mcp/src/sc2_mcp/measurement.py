"""Inclusive phase timings; inactive outside candidate validation."""
from contextvars import ContextVar
from functools import wraps
import time

active = ContextVar('sc2_measurements', default=None)


def timed(name):
    def decorate(fn):
        @wraps(fn)
        def run(*args, **kwargs):
            values = active.get()
            if values is None: return fn(*args, **kwargs)
            started = time.perf_counter()
            try: return fn(*args, **kwargs)
            finally:
                row = values.setdefault(name, {'seconds':0, 'calls':0})
                row['seconds'] += time.perf_counter()-started
                row['calls'] += 1
        return run
    return decorate


def profiled(fn):
    @wraps(fn)
    def run(*args, **kwargs):
        measurements = {}
        token = active.set(measurements)
        started = time.perf_counter()
        try:
            result = fn(*args, **kwargs)
            import psutil
            result['performance'] = {'phases_inclusive':measurements,
                'seconds':time.perf_counter()-started, 'rss_at_end':psutil.Process().memory_info().rss}
            return result
        finally: active.reset(token)
    return run

"""Operation-local cancellation and measured progress, shared by CLI/MCP."""
from contextvars import ContextVar
import time
from .errors import SC2Error

current = ContextVar('sc2_progress', default=None)


def report(stage, done=0, total=0):
    token = current.get()
    if token is None:
        return
    if token.is_set():
        raise SC2Error('cancelled', '操作已取消，检查原候选状态后恢复')
    now = time.monotonic()
    if stage != getattr(token, '_stage', None) or now-getattr(token, '_reported', 0) >= 1 or done == total:
        token._stage, token._reported = stage, now
        token.report_progress(1, f'{stage}: {done}/{total}' if total else stage)
        token.report_details(stage=stage, processed=done, total=total)

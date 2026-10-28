"""Windows Job Object ownership. Closing the handle kills remaining descendants."""
import os


def process_identity(pid):
    """Creation time disambiguates PID reuse; None means the process is no longer present."""
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return str(pid)
        except ProcessLookupError:
            return None
    import win32api
    import win32process
    try:
        process = win32api.OpenProcess(0x1000, False, pid)
    except Exception:
        return None
    try:
        if win32process.GetExitCodeProcess(process) != 259:  # STILL_ACTIVE
            return None
        return str(win32process.GetProcessTimes(process)["CreationTime"])
    finally:
        process.Close()


class ProcessJob:
    def __init__(self, pid):
        self.handle = None
        if os.name != "nt":
            return
        import win32api
        import win32job
        import win32con
        self.handle = win32job.CreateJobObject(None, "")
        limits = win32job.QueryInformationJobObject(self.handle, win32job.JobObjectExtendedLimitInformation)
        limits["BasicLimitInformation"]["LimitFlags"] |= win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        win32job.SetInformationJobObject(self.handle, win32job.JobObjectExtendedLimitInformation, limits)
        process = win32api.OpenProcess(win32con.PROCESS_SET_QUOTA | win32con.PROCESS_TERMINATE, False, pid)
        try:
            win32job.AssignProcessToJobObject(self.handle, process)
        except BaseException:
            self.close()
            raise
        finally:
            process.Close()

    def close(self):
        if self.handle is not None:
            self.handle.Close()
            self.handle = None

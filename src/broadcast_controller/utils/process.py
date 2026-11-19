import os
import signal
import time

def is_process_running(pid):
    try:
        os.kill(pid, 0)
        return True

    except ProcessLookupError:
        return False

    except PermissionError:
        return True

def stop_process(pid, timeout=15):
    if not is_process_running(pid):
        return True

    os.kill(pid, signal.SIGTERM)

    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if not is_process_running(pid):
            return True

        time.sleep(0.25)

    return False

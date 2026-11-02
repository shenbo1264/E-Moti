import sys


def peak_rss_bytes() -> int:
    if sys.platform == "win32":
        import psutil

        return psutil.Process().memory_info().peak_wset
    import resource

    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)

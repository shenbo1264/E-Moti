from datetime import datetime
from zoneinfo import ZoneInfo


def query_clock(service, now):
    clock = {"time_basis": service.time_basis, "now": now}
    if service.time_basis == "unix":
        clock.update(timezone=service.timezone_name,
            local_datetime=datetime.fromtimestamp(now, ZoneInfo(service.timezone_name)).isoformat())
    return clock

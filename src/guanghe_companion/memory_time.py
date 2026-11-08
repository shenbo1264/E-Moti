from zoneinfo import ZoneInfo


def _time(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def temporal_metadata(*, time_basis: str, timezone_name: str = "", now: int,
                      occurred_at: int | None = None, valid_from: int = 0, valid_until: int = 0) -> dict:
    if time_basis not in {"logical", "unix"}:
        raise ValueError("unsupported time basis")
    if time_basis == "logical" and timezone_name:
        raise ValueError("logical time cannot have a calendar timezone")
    if time_basis == "unix":
        timezone_name = timezone_name or "UTC"
        ZoneInfo(timezone_name)
    now = _time(now, "recorded time")
    occurred_at = now if occurred_at is None else _time(occurred_at, "occurred time")
    _time(valid_from, "valid_from")
    _time(valid_until, "valid_until")
    if valid_until and valid_until <= valid_from:
        raise ValueError("validity interval must have positive duration")
    return {"time_basis": time_basis, "timezone": timezone_name,
            "recorded_time": now, "occurred_time": occurred_at}


def bind_archive_time(store, *, time_basis: str | None = None,
                      timezone_name: str | None = None) -> tuple[str, str]:
    with store._document() as document:
        # 初始化也会提交时间标记，先验证待确认内容，损坏档案必须原样保留。
        store._pending_rows(document)
        existing = document.get("time_basis")
        # 缺少标记的旧存档使用逻辑时间，不根据数字大小推测日历。
        if existing is None and document.get("entries"):
            existing = "logical"
        basis = existing or time_basis or "logical"
        if time_basis is not None and time_basis != basis:
            raise ValueError("archive time basis cannot be reinterpreted")
        zone = document.get("timezone", "UTC" if basis == "unix" else "")
        if timezone_name is not None:
            if "timezone" in document and timezone_name != zone:
                raise ValueError("archive timezone cannot be reinterpreted")
            zone = timezone_name
        meta = temporal_metadata(time_basis=basis, timezone_name=zone, now=0)
        document["time_basis"], document["timezone"] = basis, meta["timezone"]
        return basis, meta["timezone"]

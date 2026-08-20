from __future__ import annotations

"""Privacy-first heartbeat primitives for E-Moti.

This module deliberately separates observation, policy, character copy, and
execution. The observer only sees the foreground executable name and operating
system idle time after opt-in. It never reads raw window titles, document text,
keyboard input, clipboard contents, or mouse positions.
"""

from dataclasses import dataclass, replace
from enum import Enum
import ctypes
from ctypes import wintypes
import sys
import time
from typing import Protocol


class ActivityKind(str, Enum):
    CODING = "coding"
    WRITING = "writing"
    READING = "reading"
    COMMUNICATION = "communication"
    OTHER = "other"
    IDLE = "idle"
    UNAVAILABLE = "unavailable"


FOCUS_ACTIVITY_KINDS = frozenset({ActivityKind.CODING, ActivityKind.WRITING})


@dataclass(frozen=True, slots=True)
class ActivitySample:
    observed_at: float
    kind: ActivityKind
    app_label: str
    idle_seconds: float = 0.0
    available: bool = True
    source: str = "windows_foreground"


@dataclass(frozen=True, slots=True)
class FocusObservation:
    kind: ActivityKind
    activity_label: str
    continuous_seconds: int
    confidence: float
    source: str
    app_label: str = ""

    @property
    def continuous_minutes(self) -> int:
        return max(0, self.continuous_seconds // 60)

    @property
    def is_focus_work(self) -> bool:
        return self.kind in FOCUS_ACTIVITY_KINDS

    def to_public_dict(self) -> dict[str, object]:
        # app_label is intentionally omitted. The UI only needs a coarse task
        # category; persisting process names would add little emotional value.
        return {
            "kind": self.kind.value,
            "activity_label": self.activity_label,
            "continuous_seconds": self.continuous_seconds,
            "continuous_minutes": self.continuous_minutes,
            "confidence": round(self.confidence, 2),
            "source": self.source,
            "stores_raw_window_title": False,
            "stores_process_name": False,
        }


@dataclass(frozen=True, slots=True)
class FocusCompanionSettings:
    enabled: bool = False
    threshold_minutes: int = 50
    break_minutes: int = 5
    minimum_confidence: float = 0.75
    idle_reset_seconds: int = 120
    session_gap_grace_seconds: int = 45
    cooldown_minutes: int = 30
    snooze_minutes: int = 30
    daily_limit: int = 4
    minimum_pet_stability: float = 35.0
    quiet_hours_enabled: bool = False
    quiet_start: str = "23:00"
    quiet_end: str = "08:00"

    def normalized(self) -> "FocusCompanionSettings":
        return FocusCompanionSettings(
            enabled=bool(self.enabled),
            threshold_minutes=max(5, min(240, int(self.threshold_minutes))),
            break_minutes=max(1, min(30, int(self.break_minutes))),
            minimum_confidence=max(0.0, min(1.0, float(self.minimum_confidence))),
            idle_reset_seconds=max(30, min(1800, int(self.idle_reset_seconds))),
            session_gap_grace_seconds=max(5, min(300, int(self.session_gap_grace_seconds))),
            cooldown_minutes=max(5, min(24 * 60, int(self.cooldown_minutes))),
            snooze_minutes=max(5, min(24 * 60, int(self.snooze_minutes))),
            daily_limit=max(1, min(24, int(self.daily_limit))),
            minimum_pet_stability=max(0.0, min(100.0, float(self.minimum_pet_stability))),
            quiet_hours_enabled=bool(self.quiet_hours_enabled),
            quiet_start=_normalize_clock(self.quiet_start, "23:00"),
            quiet_end=_normalize_clock(self.quiet_end, "08:00"),
        )


@dataclass(frozen=True, slots=True)
class FocusCompanionCopy:
    """Character-facing copy kept outside deterministic policy decisions."""

    def offer(self, activity_label: str, focused_minutes: int, break_minutes: int) -> str:
        if activity_label == "写代码":
            opening = f"欸，你和这段代码已经对峙 {focused_minutes} 分钟了……先别跟它决战到天亮吧。"
        elif activity_label == "写作 / 文档处理":
            opening = f"这篇文档已经和你打了 {focused_minutes} 分钟持久战……要不先停一回合？"
        else:
            opening = f"你盯着手头这件事已经 {focused_minutes} 分钟了……我从桌角看了好一会儿。"
        return f"{opening}要不要陪我发 {break_minutes} 分钟呆？我帮你看着时间。"

    def break_started(self, break_minutes: int) -> str:
        return f"好，那就暂时休战。{break_minutes} 分钟后我再来敲敲你。"

    def snoozed(self) -> str:
        return "收到，先当我没探头（悄悄缩回桌角）。过一会儿再来看看。"

    def muted_today(self) -> str:
        return "了解。今天的“休息小队长”下班了，我会安静待着。"

    def completed(self) -> str:
        return "五分钟休战结束。欢迎回来——要不要继续，还是你说了算。"

    def cancelled(self) -> str:
        return "计时停在这里啦。节奏还是交给你自己。"

    def memory_summary(self, break_minutes: int) -> str:
        return (
            f"你答应和星汐一起停下来 {break_minutes} 分钟。"
            "她没讲大道理，只是在桌角陪你一起发了会儿呆。"
        )


@dataclass(frozen=True, slots=True)
class FocusBreakOffer:
    kind: str
    speech: str
    summary: str
    activity_label: str
    focused_minutes: int
    break_minutes: int
    primary_action_id: str = "start_focus_break"
    secondary_action_id: str = "snooze_focus_break"
    tertiary_action_id: str = "mute_focus_break_today"

    def to_public_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "eyebrow": "探头时刻",
            "title": "星汐从桌角探出头",
            "speech": self.speech,
            "summary": self.summary,
            "activity_label": self.activity_label,
            "focused_minutes": self.focused_minutes,
            "break_minutes": self.break_minutes,
            "actions": [
                {"id": self.primary_action_id, "label": "陪她歇一会儿"},
                {"id": self.secondary_action_id, "label": "再等一会儿"},
                {"id": self.tertiary_action_id, "label": "今天先别管我"},
            ],
        }


@dataclass(frozen=True, slots=True)
class FocusPolicyDecision:
    offer: FocusBreakOffer | None
    reason: str

    @property
    def allowed(self) -> bool:
        return self.offer is not None


class ActivityReader(Protocol):
    def sample(self, *, observed_at: float | None = None) -> ActivitySample:
        ...


class ApplicationClassifier:
    """Map an executable name to a coarse, privacy-safe category."""

    _CODING = frozenset(
        {
            "code.exe",
            "code - insiders.exe",
            "codium.exe",
            "pycharm64.exe",
            "idea64.exe",
            "webstorm64.exe",
            "rider64.exe",
            "devenv.exe",
            "sublime_text.exe",
            "notepad++.exe",
            "zed.exe",
            "cursor.exe",
            "trae.exe",
            "windsurf.exe",
            "windowsterminal.exe",
        }
    )
    _WRITING = frozenset(
        {
            "winword.exe",
            "wps.exe",
            "wpsoffice.exe",
            "obsidian.exe",
            "typora.exe",
            "notion.exe",
            "notepad.exe",
            "texstudio.exe",
        }
    )
    _READING = frozenset(
        {"chrome.exe", "msedge.exe", "firefox.exe", "acrobat.exe", "sumatrapdf.exe"}
    )
    _COMMUNICATION = frozenset(
        {"wechat.exe", "weixin.exe", "qq.exe", "teams.exe", "slack.exe", "discord.exe"}
    )

    def classify(self, executable_name: str) -> tuple[ActivityKind, str, float]:
        raw = str(executable_name or "").replace("\\", "/")
        name = raw.rsplit("/", 1)[-1].casefold()
        if name in self._CODING:
            return ActivityKind.CODING, "写代码", 0.95
        if name in self._WRITING:
            return ActivityKind.WRITING, "写作 / 文档处理", 0.92
        if name in self._READING:
            return ActivityKind.READING, "阅读 / 浏览", 0.70
        if name in self._COMMUNICATION:
            return ActivityKind.COMMUNICATION, "沟通", 0.90
        if not name:
            return ActivityKind.UNAVAILABLE, "无法识别", 0.0
        return ActivityKind.OTHER, "其他任务", 0.45


class WindowsForegroundActivityReader:
    """Read only foreground executable name and OS idle time on Windows."""

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

    def __init__(self, classifier: ApplicationClassifier | None = None) -> None:
        self.classifier = classifier or ApplicationClassifier()

    def sample(self, *, observed_at: float | None = None) -> ActivitySample:
        now = time.time() if observed_at is None else float(observed_at)
        if sys.platform != "win32":
            return ActivitySample(
                observed_at=now,
                kind=ActivityKind.UNAVAILABLE,
                app_label="",
                idle_seconds=0.0,
                available=False,
                source="unsupported_platform",
            )
        try:
            executable = self._foreground_executable_name()
            idle_seconds = self._idle_seconds()
            kind, label, _ = self.classifier.classify(executable)
            if idle_seconds >= 300:
                kind = ActivityKind.IDLE
                label = "离开电脑"
            # Keep the process name only in the transient sample. It is never
            # included in public snapshots or memory payloads.
            app_label = executable.replace("\\", "/").rsplit("/", 1)[-1] if executable else ""
            return ActivitySample(
                observed_at=now,
                kind=kind,
                app_label=app_label,
                idle_seconds=idle_seconds,
                available=True,
            )
        except (OSError, ValueError, AttributeError):
            return ActivitySample(
                observed_at=now,
                kind=ActivityKind.UNAVAILABLE,
                app_label="",
                idle_seconds=0.0,
                available=False,
                source="windows_probe_failed",
            )

    def _foreground_executable_name(self) -> str:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        if not process_id.value:
            return ""
        handle = kernel32.OpenProcess(self.PROCESS_QUERY_LIMITED_INFORMATION, False, process_id.value)
        if not handle:
            return ""
        try:
            length = wintypes.DWORD(1024)
            buffer = ctypes.create_unicode_buffer(length.value)
            ok = kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length))
            return buffer.value if ok else ""
        finally:
            kernel32.CloseHandle(handle)

    def _idle_seconds(self) -> float:
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        user32.GetLastInputInfo.argtypes = [ctypes.POINTER(LASTINPUTINFO)]
        user32.GetLastInputInfo.restype = wintypes.BOOL
        kernel32.GetTickCount.restype = wintypes.DWORD
        info = LASTINPUTINFO(ctypes.sizeof(LASTINPUTINFO), 0)
        if not user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        elapsed_ms = (kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF
        return elapsed_ms / 1000.0


def _sample_label_and_confidence(sample: ActivitySample) -> tuple[str, float]:
    if sample.app_label:
        kind, label, confidence = ApplicationClassifier().classify(sample.app_label)
        if kind == sample.kind or sample.kind in {ActivityKind.OTHER, ActivityKind.UNAVAILABLE}:
            return label, confidence
    defaults = {
        ActivityKind.CODING: ("写代码", 0.90),
        ActivityKind.WRITING: ("写作 / 文档处理", 0.88),
        ActivityKind.READING: ("阅读 / 浏览", 0.70),
        ActivityKind.COMMUNICATION: ("沟通", 0.85),
        ActivityKind.OTHER: ("其他任务", 0.45),
        ActivityKind.IDLE: ("离开电脑", 1.00),
        ActivityKind.UNAVAILABLE: ("无法识别", 0.00),
    }
    return defaults[sample.kind]


class FocusSessionTracker:
    def __init__(self, settings: FocusCompanionSettings | None = None) -> None:
        self.settings = (settings or FocusCompanionSettings()).normalized()
        self._kind = ActivityKind.UNAVAILABLE
        self._activity_label = ""
        self._started_at: float | None = None
        self._last_seen_at: float | None = None
        self._confidence = 0.0
        self._source = ""
        self._offer_emitted_for_session = False

    @property
    def offer_emitted_for_session(self) -> bool:
        return self._offer_emitted_for_session

    def mark_offer_emitted(self) -> None:
        self._offer_emitted_for_session = True

    def allow_reoffer_after_snooze(self) -> None:
        self._offer_emitted_for_session = False

    def reset(self) -> None:
        self._kind = ActivityKind.UNAVAILABLE
        self._activity_label = ""
        self._started_at = None
        self._last_seen_at = None
        self._confidence = 0.0
        self._source = ""
        self._offer_emitted_for_session = False

    def update(self, sample: ActivitySample) -> FocusObservation:
        label, confidence = _sample_label_and_confidence(sample)
        if sample.kind == ActivityKind.IDLE or sample.idle_seconds >= self.settings.idle_reset_seconds:
            self.reset()
            return FocusObservation(ActivityKind.IDLE, "离开电脑", 0, 1.0, sample.source)

        now = float(sample.observed_at)
        gap = 0.0 if self._last_seen_at is None else max(0.0, now - self._last_seen_at)
        # A very short documentation/browser detour is allowed inside a coding
        # or writing session. Communication/other work still ends the session.
        if (
            sample.available
            and sample.kind == ActivityKind.READING
            and self._kind in FOCUS_ACTIVITY_KINDS
            and self._started_at is not None
            and gap <= self.settings.session_gap_grace_seconds
        ):
            self._last_seen_at = now
            return FocusObservation(
                self._kind,
                self._activity_label,
                max(0, int(now - self._started_at)),
                min(self._confidence, 0.78),
                sample.source,
            )

        if not sample.available or sample.kind not in FOCUS_ACTIVITY_KINDS:
            self.reset()
            return FocusObservation(sample.kind, label, 0, confidence, sample.source)

        same_focus_family = self._kind in FOCUS_ACTIVITY_KINDS
        if self._started_at is None or not same_focus_family or gap > self.settings.session_gap_grace_seconds:
            self._started_at = now
            self._offer_emitted_for_session = False

        self._kind = sample.kind
        self._activity_label = label
        self._last_seen_at = now
        self._confidence = confidence
        self._source = sample.source
        return FocusObservation(
            self._kind,
            self._activity_label,
            max(0, int(now - (self._started_at if self._started_at is not None else now))),
            self._confidence,
            self._source,
        )

    def inject_demo_observation(
        self,
        *,
        focused_minutes: int = 52,
        kind: ActivityKind = ActivityKind.CODING,
        observed_at: float | None = None,
    ) -> FocusObservation:
        now = time.time() if observed_at is None else float(observed_at)
        label = "写代码" if kind == ActivityKind.CODING else "写作 / 文档处理"
        self._kind = kind
        self._activity_label = label
        self._started_at = now - max(0, int(focused_minutes)) * 60
        self._last_seen_at = now
        self._confidence = 0.99
        self._source = "demo_injection"
        self._offer_emitted_for_session = False
        return FocusObservation(
            kind=kind,
            activity_label=label,
            continuous_seconds=max(0, int(focused_minutes)) * 60,
            confidence=0.99,
            source="demo_injection",
        )


class FocusBreakPolicy:
    def __init__(self, copy: FocusCompanionCopy | None = None) -> None:
        self.copy = copy or FocusCompanionCopy()

    def evaluate(
        self,
        observation: FocusObservation,
        *,
        now: float,
        settings: FocusCompanionSettings,
        pet_stability: float,
        pet_mode: str,
        last_offer_at: float | None = None,
        offers_today: int = 0,
        offer_emitted_for_session: bool = False,
        quiet_hours_active: bool = False,
        muted_for_today: bool = False,
    ) -> FocusPolicyDecision:
        settings = settings.normalized()
        if not settings.enabled:
            return FocusPolicyDecision(None, "disabled")
        if quiet_hours_active or (
            settings.quiet_hours_enabled
            and _is_quiet_time(now, settings.quiet_start, settings.quiet_end)
        ):
            return FocusPolicyDecision(None, "quiet_hours")
        if muted_for_today:
            return FocusPolicyDecision(None, "muted_for_today")
        if not observation.is_focus_work:
            return FocusPolicyDecision(None, "not_focus_work")
        if observation.confidence < settings.minimum_confidence:
            return FocusPolicyDecision(None, "low_confidence")
        if observation.continuous_minutes < settings.threshold_minutes:
            return FocusPolicyDecision(None, "below_threshold")
        if pet_mode == "Overload" or pet_stability < settings.minimum_pet_stability:
            return FocusPolicyDecision(None, "pet_state_blocks_offer")
        if offer_emitted_for_session:
            return FocusPolicyDecision(None, "already_offered_this_session")
        if offers_today >= settings.daily_limit:
            return FocusPolicyDecision(None, "daily_limit")
        if last_offer_at is not None and now - last_offer_at < settings.cooldown_minutes * 60:
            return FocusPolicyDecision(None, "cooldown")

        minutes = observation.continuous_minutes
        speech = self.copy.offer(observation.activity_label, minutes, settings.break_minutes)
        return FocusPolicyDecision(
            FocusBreakOffer(
                kind="focus_break_offer",
                speech=speech,
                summary=(
                    f"粗粒度任务={observation.activity_label}; 连续时长={minutes}分钟; "
                    "仅在玩家确认后启动本地休息计时"
                ),
                activity_label=observation.activity_label,
                focused_minutes=minutes,
                break_minutes=settings.break_minutes,
            ),
            "offer_ready",
        )


@dataclass(slots=True)
class LocalBreakTimer:
    duration_seconds: int = 0
    started_at: float | None = None
    completed_at: float | None = None
    cancelled_at: float | None = None

    @property
    def active(self) -> bool:
        return self.started_at is not None and self.completed_at is None and self.cancelled_at is None

    def start(self, *, duration_seconds: int, now: float | None = None) -> None:
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        self.duration_seconds = int(duration_seconds)
        self.started_at = time.time() if now is None else float(now)
        self.completed_at = None
        self.cancelled_at = None

    def remaining_seconds(self, *, now: float | None = None) -> int:
        if self.started_at is None or self.completed_at is not None or self.cancelled_at is not None:
            return 0
        current = time.time() if now is None else float(now)
        remaining = max(0, self.duration_seconds - int(current - self.started_at))
        if remaining == 0:
            self.completed_at = current
        return remaining

    def cancel(self, *, now: float | None = None) -> None:
        if self.active:
            self.cancelled_at = time.time() if now is None else float(now)

    def to_public_dict(self, *, now: float | None = None) -> dict[str, object]:
        remaining = self.remaining_seconds(now=now)
        return {
            "active": self.active,
            "duration_seconds": self.duration_seconds,
            "remaining_seconds": remaining,
            "completed": self.completed_at is not None,
            "cancelled": self.cancelled_at is not None,
        }


def _day_key(now: float) -> int:
    return max(0, int(now)) // 86_400


@dataclass(frozen=True, slots=True)
class FocusRuntimeEvent:
    event_type: str
    payload: dict[str, object]

    def to_public_dict(self) -> dict[str, object]:
        return {"type": self.event_type, **self.payload}


class FocusCompanionRuntime:
    """Backwards-compatible facade around the same deterministic primitives."""

    def __init__(
        self,
        *,
        settings: FocusCompanionSettings | None = None,
        reader: ActivityReader | None = None,
        tracker: FocusSessionTracker | None = None,
        policy: FocusBreakPolicy | None = None,
        timer: LocalBreakTimer | None = None,
        copy: FocusCompanionCopy | None = None,
    ) -> None:
        self.settings = (settings or FocusCompanionSettings()).normalized()
        self.copy = copy or FocusCompanionCopy()
        self.reader = reader or WindowsForegroundActivityReader()
        self.tracker = tracker or FocusSessionTracker(self.settings)
        self.policy = policy or FocusBreakPolicy(self.copy)
        self.timer = timer or LocalBreakTimer()
        self.pending_offer: FocusBreakOffer | None = None
        self.last_offer_at: float | None = None
        self.blocked_until: float | None = None
        self.muted_day: int | None = None
        self._offers_by_day: dict[int, int] = {}
        self._completion_emitted = False

    def update_settings(self, settings: FocusCompanionSettings) -> None:
        self.settings = settings.normalized()
        self.tracker.settings = self.settings
        if not self.settings.enabled:
            self.pending_offer = None
            self.tracker.reset()

    def poll(
        self,
        *,
        now: float | None = None,
        pet_stability: float,
        pet_mode: str,
        sample: ActivitySample | None = None,
    ) -> FocusRuntimeEvent:
        current = time.time() if now is None else float(now)
        day = _day_key(current)
        if self.timer.active:
            return self._timer_event(current)
        if self.muted_day is not None and self.muted_day != day:
            self.muted_day = None
        if self.muted_day == day:
            return FocusRuntimeEvent("focus_suppressed", {"reason": "muted_for_today"})
        if self.blocked_until is not None and current < self.blocked_until:
            return FocusRuntimeEvent(
                "focus_suppressed",
                {"reason": "snoozed", "retry_after_seconds": max(0, int(self.blocked_until - current))},
            )
        observation = self.tracker.update(sample or self.reader.sample(observed_at=current))
        decision = self.policy.evaluate(
            observation,
            now=current,
            settings=self.settings,
            pet_stability=pet_stability,
            pet_mode=pet_mode,
            last_offer_at=self.last_offer_at,
            offers_today=self._offers_by_day.get(day, 0),
            offer_emitted_for_session=self.tracker.offer_emitted_for_session,
        )
        if decision.offer is None:
            return FocusRuntimeEvent(
                "focus_observed",
                {"decision": decision.reason, "observation": observation.to_public_dict()},
            )
        self.pending_offer = decision.offer
        self.last_offer_at = current
        self._offers_by_day[day] = self._offers_by_day.get(day, 0) + 1
        self.tracker.mark_offer_emitted()
        return FocusRuntimeEvent(
            "focus_break_offer",
            {"offer": decision.offer.to_public_dict(), "observation": observation.to_public_dict()},
        )

    def inject_demo_offer(
        self,
        *,
        focused_minutes: int = 52,
        now: float | None = None,
        pet_stability: float = 78,
        pet_mode: str = "Calm",
    ) -> FocusRuntimeEvent:
        current = time.time() if now is None else float(now)
        observation = self.tracker.inject_demo_observation(
            focused_minutes=focused_minutes,
            observed_at=current,
        )
        decision = self.policy.evaluate(
            observation,
            now=current,
            settings=replace(self.settings, enabled=True),
            pet_stability=pet_stability,
            pet_mode=pet_mode,
        )
        if decision.offer is None:
            return FocusRuntimeEvent("focus_observed", {"decision": decision.reason})
        self.pending_offer = decision.offer
        self.last_offer_at = current
        self.tracker.mark_offer_emitted()
        return FocusRuntimeEvent(
            "focus_break_offer",
            {"offer": decision.offer.to_public_dict(), "observation": observation.to_public_dict(), "demo": True},
        )

    def accept_break(self, *, now: float | None = None) -> FocusRuntimeEvent:
        if self.pending_offer is None:
            return FocusRuntimeEvent("focus_action_rejected", {"reason": "no_pending_offer"})
        current = time.time() if now is None else float(now)
        offer = self.pending_offer
        self.pending_offer = None
        self._completion_emitted = False
        self.timer.start(duration_seconds=offer.break_minutes * 60, now=current)
        return FocusRuntimeEvent(
            "focus_break_started",
            {
                "duration_seconds": offer.break_minutes * 60,
                "speech": self.copy.break_started(offer.break_minutes),
                "requires_user_confirmation": True,
            },
        )

    def snooze(self, *, now: float | None = None, minutes: int | None = None) -> FocusRuntimeEvent:
        current = time.time() if now is None else float(now)
        snooze_minutes = max(1, int(minutes if minutes is not None else self.settings.snooze_minutes))
        self.pending_offer = None
        self.blocked_until = current + snooze_minutes * 60
        self.tracker.allow_reoffer_after_snooze()
        return FocusRuntimeEvent(
            "focus_break_snoozed",
            {"snooze_minutes": snooze_minutes, "speech": self.copy.snoozed()},
        )

    def mute_for_today(self, *, now: float | None = None) -> FocusRuntimeEvent:
        current = time.time() if now is None else float(now)
        self.pending_offer = None
        self.muted_day = _day_key(current)
        return FocusRuntimeEvent(
            "focus_break_muted",
            {"day": self.muted_day, "speech": self.copy.muted_today()},
        )

    def cancel_break(self, *, now: float | None = None) -> FocusRuntimeEvent:
        self.timer.cancel(now=now)
        return FocusRuntimeEvent("focus_break_cancelled", {"speech": self.copy.cancelled()})

    def timer_status(self, *, now: float | None = None) -> FocusRuntimeEvent:
        return self._timer_event(time.time() if now is None else float(now))

    def _timer_event(self, now: float) -> FocusRuntimeEvent:
        remaining = self.timer.remaining_seconds(now=now)
        if self.timer.completed_at is not None:
            if self._completion_emitted:
                return FocusRuntimeEvent("focus_break_idle", {"remaining_seconds": 0})
            self._completion_emitted = True
            break_minutes = max(1, round(self.timer.duration_seconds / 60))
            return FocusRuntimeEvent(
                "focus_break_completed",
                {
                    "remaining_seconds": 0,
                    "speech": self.copy.completed(),
                    "memory_draft": {
                        "kind": "主动陪伴",
                        "summary": self.copy.memory_summary(break_minutes),
                        "source": "focus_companion_skill",
                    },
                    "growth_state_mutated": False,
                },
            )
        return FocusRuntimeEvent(
            "focus_break_ticking",
            {"remaining_seconds": remaining, "active": self.timer.active},
        )


def replace_focus_settings(settings: FocusCompanionSettings, **changes: object) -> FocusCompanionSettings:
    return replace(settings, **changes).normalized()


def _is_quiet_time(now: float, quiet_start: str, quiet_end: str) -> bool:
    current = time.localtime(now)
    current_seconds = current.tm_hour * 3600 + current.tm_min * 60 + current.tm_sec
    start = _clock_text_to_seconds(quiet_start)
    end = _clock_text_to_seconds(quiet_end)
    if start == end:
        return False
    if start < end:
        return start <= current_seconds < end
    return current_seconds >= start or current_seconds < end


def _normalize_clock(value: str, default: str) -> str:
    try:
        seconds = _clock_text_to_seconds(value)
    except ValueError:
        return default
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}"


def _clock_text_to_seconds(value: str) -> int:
    try:
        hour_text, minute_text = str(value).split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"invalid clock value: {value!r}") from exc
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError(f"invalid clock value: {value!r}")
    return hour * 3600 + minute * 60

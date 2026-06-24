from __future__ import annotations

import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


@dataclass(frozen=True, slots=True)
class VoiceServiceEndpoint:
    service_id: str
    label: str
    url: str


@dataclass(frozen=True, slots=True)
class VoiceServiceStatus:
    service_id: str
    label: str
    ok: bool
    url: str
    message: str


@dataclass(frozen=True, slots=True)
class VoiceServiceLaunchResult:
    service_id: str
    label: str
    started: bool
    message: str


ProbeFn = Callable[[str, float], tuple[bool, str]]
StarterFn = Callable[[tuple[str, ...], str], tuple[bool, str]]


DEFAULT_VOICE_SERVICE_ENDPOINTS: tuple[VoiceServiceEndpoint, ...] = (
    VoiceServiceEndpoint("qwen3tts", "Qwen3TTS", "http://127.0.0.1:9880/tts"),
    VoiceServiceEndpoint("gptsovits", "GPT-SoVITS", "http://127.0.0.1:9882/"),
    VoiceServiceEndpoint("sensevoice_asr", "SenseVoice ASR", "http://127.0.0.1:8899/v1/models"),
)

_START_SCRIPT_SPECS: dict[str, tuple[str, tuple[str, ...]]] = {
    "qwen3tts": ("start_qwen3_tts_server.ps1", ("-Port", "9880")),
    "gptsovits": ("start_ikaros_gptsovits_server.ps1", ("-Port", "9882", "-NoWait")),
    "sensevoice_asr": (
        "start_sensevoice_asr_server.ps1",
        ("-Port", "8899", "-Device", "cpu", "-Model", "sensevoice"),
    ),
}


def probe_voice_services(
    *,
    timeout: float = 2.0,
    endpoints: Sequence[VoiceServiceEndpoint] = DEFAULT_VOICE_SERVICE_ENDPOINTS,
    probe: ProbeFn | None = None,
) -> tuple[VoiceServiceStatus, ...]:
    probe_fn = probe or _probe_http
    statuses = []
    for endpoint in endpoints:
        ok, message = probe_fn(endpoint.url, timeout)
        statuses.append(
            VoiceServiceStatus(
                service_id=endpoint.service_id,
                label=endpoint.label,
                ok=ok,
                url=endpoint.url,
                message=message,
            )
        )
    return tuple(statuses)


def all_voice_services_ready(statuses: Sequence[VoiceServiceStatus]) -> bool:
    return bool(statuses) and all(status.ok for status in statuses)


def format_voice_service_statuses(statuses: Sequence[VoiceServiceStatus]) -> str:
    if all_voice_services_ready(statuses):
        prefix = "语音服务预检通过"
    else:
        prefix = "语音服务未就绪"
    detail = "；".join(f"{status.label}: {status.message}" for status in statuses)
    return f"{prefix}：{detail}" if detail else "语音服务未检查"


def launch_missing_voice_services(
    repo_root: Path,
    *,
    statuses: Sequence[VoiceServiceStatus] | None = None,
    scripts_dir: Path | None = None,
    starter: StarterFn | None = None,
) -> tuple[VoiceServiceLaunchResult, ...]:
    current_statuses = tuple(statuses) if statuses is not None else probe_voice_services(timeout=1.0)
    starter_fn = starter or _start_process
    results: list[VoiceServiceLaunchResult] = []
    for status in current_statuses:
        if status.ok:
            results.append(
                VoiceServiceLaunchResult(
                    status.service_id,
                    status.label,
                    False,
                    "已在运行",
                )
            )
            continue
        command = _start_command(repo_root, status.service_id, scripts_dir=scripts_dir)
        if command is None:
            results.append(
                VoiceServiceLaunchResult(
                    status.service_id,
                    status.label,
                    False,
                    f"启动脚本不存在：{_script_path(repo_root, status.service_id, scripts_dir=scripts_dir)}",
                )
            )
            continue
        started, message = starter_fn(command, str(repo_root))
        results.append(
            VoiceServiceLaunchResult(
                status.service_id,
                status.label,
                started,
                message,
            )
        )
    return tuple(results)


def format_voice_service_launch_results(results: Sequence[VoiceServiceLaunchResult]) -> str:
    if not results:
        return "语音服务启动未执行：没有可处理的服务。"
    if any(result.started for result in results):
        prefix = "语音服务启动请求已发送"
    else:
        prefix = "语音服务启动未执行"
    detail = "；".join(f"{result.label}: {result.message}" for result in results)
    return f"{prefix}：{detail}"


def _probe_http(url: str, timeout: float) -> tuple[bool, str]:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return True, f"HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        if 200 <= exc.code < 500:
            return True, f"HTTP {exc.code}"
        return False, f"HTTP {exc.code}"
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        return False, str(exc)


def _start_command(repo_root: Path, service_id: str, *, scripts_dir: Path | None = None) -> tuple[str, ...] | None:
    script = _script_path(repo_root, service_id, scripts_dir=scripts_dir)
    if not script.exists():
        return None
    _, args = _START_SCRIPT_SPECS[service_id]
    return (
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        *args,
    )


def _script_path(repo_root: Path, service_id: str, *, scripts_dir: Path | None = None) -> Path:
    spec = _START_SCRIPT_SPECS.get(service_id)
    if spec is None:
        filename = f"{service_id}.ps1"
    else:
        filename = spec[0]
    return (scripts_dir or repo_root / "tools" / "voice_services") / filename


def _start_process(command: tuple[str, ...], cwd: str) -> tuple[bool, str]:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        subprocess.Popen(
            list(command),
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
    except OSError as exc:
        return False, str(exc)
    return True, "启动命令已发送"

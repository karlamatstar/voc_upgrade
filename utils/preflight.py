"""수강 과제 시연·발표 전 로컬 실행 환경을 빠르게 점검한다.

API 키의 실제 값은 출력하지 않으며, 에이전트 포트에는 연결 가능 여부만
확인한다. 외부 API 호출은 수행하지 않는다.
"""

from __future__ import annotations

import importlib.util
import os
import socket
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from utils.env_loader import load_env


ROOT = Path(__file__).resolve().parent.parent
REQUIRED_FILES = ("voc.csv", "voc.proto", "voc_pb2.py", "voc_pb2_grpc.py")
REQUIRED_MODULES = {
    "anthropic": "anthropic",
    "grpc": "grpcio",
    "mcp": "mcp",
    "openai": "openai",
    "google.protobuf": "protobuf",
}
AGENT_PORTS = {
    "Interpreter": 6001,
    "Retriever": 6002,
    "Summarizer": 6003,
    "Evaluator": 6004,
    "Critic": 6005,
    "Improver": 6006,
}


@dataclass(frozen=True)
class Check:
    category: str
    name: str
    ok: bool
    required: bool
    detail: str


def _port_open(port: int, timeout: float = 0.15) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def collect_checks() -> list[Check]:
    """외부 서비스 호출 없이 현재 시연 준비 상태를 수집한다."""
    load_env()
    checks: list[Check] = []

    python_ok = sys.version_info >= (3, 13)
    checks.append(Check("기본", "Python 3.13+", python_ok, True, sys.version.split()[0]))

    for filename in REQUIRED_FILES:
        exists = (ROOT / filename).is_file()
        checks.append(Check("파일", filename, exists, True, "준비됨" if exists else "없음"))

    for module, package in REQUIRED_MODULES.items():
        installed = importlib.util.find_spec(module) is not None
        checks.append(Check("패키지", package, installed, True, "설치됨" if installed else "미설치"))

    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        configured = bool(os.environ.get(key, "").strip())
        checks.append(Check("API 키", key, configured, False, "설정됨" if configured else "미설정"))

    for agent, port in AGENT_PORTS.items():
        running = _port_open(port)
        checks.append(Check("에이전트", agent, running, False, f"localhost:{port}"))

    return checks


def format_report(checks: Iterable[Check]) -> str:
    rows = list(checks)
    lines = ["VOC 팀 과제·발표 사전 점검", "=" * 30]
    for check in rows:
        state = "정상" if check.ok else ("실패" if check.required else "안내")
        lines.append(f"[{state}] {check.category:<5} {check.name}: {check.detail}")

    required_failures = [check for check in rows if check.required and not check.ok]
    ready = not required_failures
    lines.extend(("-" * 30, f"기본 실행 준비: {'완료' if ready else '미완료'}"))
    if ready and any(check.category == "에이전트" and not check.ok for check in rows):
        lines.append("전체 파이프라인 시연 전에는 에이전트 6개를 실행하세요.")
    return "\n".join(lines)


def main() -> int:
    checks = collect_checks()
    print(format_report(checks))
    return 0 if all(check.ok for check in checks if check.required) else 1


if __name__ == "__main__":
    raise SystemExit(main())

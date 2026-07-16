# =============================================
# File: utils/env_loader.py
# =============================================
# 프로젝트 루트의 .env 파일을 os.environ으로 로딩하는 모듈
# (python-dotenv 없이 동작하는 무의존성 구현)
#
# 규칙:
# - KEY=VALUE 형식, # 주석과 빈 줄 무시, 양끝 따옴표 제거
# - 이미 시스템 환경변수에 설정된 키는 덮어쓰지 않음 (override=True로 변경 가능)
# - 여러 번 호출해도 파일은 한 번만 읽음

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional

# 프로젝트 루트 = utils/의 상위 폴더
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"

_loaded_once = False


def parse_env_file(path: Path) -> Dict[str, str]:
    """.env 파일을 파싱해 {키: 값} 딕셔너리로 반환합니다. 파일이 없으면 빈 dict."""
    result: Dict[str, str] = {}
    if not path.exists():
        return result
    # BOM이 붙어 있어도 첫 키가 깨지지 않도록 utf-8-sig로 읽음
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):  # 셸 스타일 허용
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # 양끝 따옴표 제거 ("..." 또는 '...')
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key:
            result[key] = value
    return result


def load_env(path: Optional[Path] = None, override: bool = False) -> Dict[str, str]:
    """.env 파일을 os.environ에 적용하고, 적용된 {키: 값}을 반환합니다.

    Args:
        path: .env 파일 경로 (기본: 프로젝트 루트의 .env)
        override: True면 기존 환경변수도 .env 값으로 덮어씀
    """
    global _loaded_once
    env_path = path or DEFAULT_ENV_PATH
    if _loaded_once and path is None and not override:
        return {}
    values = parse_env_file(env_path)
    applied = {}
    for key, value in values.items():
        if override or key not in os.environ:
            os.environ[key] = value
            applied[key] = value
    if path is None:
        _loaded_once = True
    return applied

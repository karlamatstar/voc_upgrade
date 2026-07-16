# Git 업로드 제외 가이드

- 작성일: 2026-07-15
- 대상 프로젝트: `D:\voc`
- 적용 파일: `D:\voc\.gitignore`

## 1. 반드시 제외할 항목

### `.env`

`OPENAI_API_KEY`, `ANTHROPIC_API_KEY` 같은 실제 API 키가 들어 있으므로 절대 Git에 올리지 않는다. 설정 형식은 실제 키 대신 예시값이 들어 있는 `.env.example`로 공유한다.

```text
.env          → 업로드 금지
.env.example  → 업로드 가능
```

API 키가 한 번이라도 Git 이력에 포함됐다면 파일만 지우는 것으로 부족하다. 해당 키를 즉시 폐기하고 새 키를 발급해야 한다.

### 가상환경·캐시·임시 파일

다음 항목은 용량이 크거나 실행 시 자동으로 다시 생성되므로 제외한다.

- `.venv/`, `venv/`
- `__pycache__/`, `*.pyc`, `*.pyo`
- `.pytest_cache/`, `.pytest_temp*/`
- `.mypy_cache/`, `.ruff_cache/`, coverage 산출물
- Word·Excel·PowerPoint의 `~$` 잠금 파일
- `*.tmp`, `*.bak`, `*.swp`

### 빌드 산출물

`build/`, `dist/`는 소스에서 다시 만들 수 있고 용량이 크므로 Git에서 제외한다. 실행 파일을 배포해야 한다면 Git 소스 이력 대신 Release 자료로 별도 공유하는 편이 좋다.

### 보고서 중간 이미지

`quality_diagnosis/reports/report_assets/`는 Word 보고서를 만들 때 생성되는 차트 PNG 폴더다. 그래프가 최종 DOCX 내부에 이미 포함되고, 생성 스크립트로 다시 만들 수 있으므로 Git에서 제외한다.

## 2. Git에 포함할 항목

다음은 수업 실습·팀 비교·발표와 재현에 필요하므로 제외하지 않는다.

| 항목 | 포함 이유 |
| :--- | :--- |
| `agents/`, `utils/`, `llm_wrappers/` | 6개 에이전트와 공통 로직 |
| `main.py`, `grpc_server.py`, `server_gui.py` | MCP·gRPC·GUI 실행 코드 |
| `quality_diagnosis/test_*.py` | 품질 검증 코드 |
| `quality_diagnosis/test_cases.json` | 20개 테스트 케이스 |
| `voc.csv`, `voc.proto`, `voc_pb2*.py` | 실습 VOC 데이터와 통신 정의 |
| `.env.example` | API 키 없이 설정 형식 안내 |
| `.agents/mcp_config.json`, `.vscode/mcp.json` | Antigravity·VS Code MCP 연결 예시 |
| `_docs/` | 코드 설명·작업 기록·발표 근거 |
| `quality_diagnosis/reports/*.docx` | 최종 한글 Word 보고서 |
| `quality_diagnosis/reports/*.csv`, `*.md` | Judge 점수와 품질 보고서 |
| `quality_diagnosis/reports/logs/` | pytest·Judge 실행 증적 |

## 3. MCP 설정 파일 주의사항

현재 `.agents/mcp_config.json`과 `.vscode/mcp.json`에는 API 키가 없고 `D:\voc` 실행 경로만 있으므로 수업 실습용으로 포함해도 된다. 다른 PC에서는 클론한 위치에 맞게 Python과 `main.py` 경로를 바꿔야 한다.

MCP JSON에 API 키를 직접 넣지 않고 프로젝트 루트의 Git 제외된 `.env`에서만 관리한다.

## 4. 최초 Git 등록 전 확인

현재 `D:\voc\.git` 폴더는 비어 있어 정상 Git 저장소로 초기화되지 않은 상태다. 업로드 전에 다음 순서로 확인한다.

```powershell
cd D:\voc
git init
git status --short
git check-ignore -v .env
git check-ignore -v .env.example
```

기대 결과:

- `.env` → `.gitignore`에 의해 제외
- `.env.example` → 제외되지 않음
- `.venv`, `build`, 캐시·임시 파일 → 제외
- 코드, `_docs`, 최종 보고서·실행 증적 → Git 후보로 표시

## 5. 이미 Git에 추적된 파일이라면

`.gitignore`는 이미 추적 중인 파일을 자동으로 제거하지 않는다. `.env`가 이미 Git에 추적된 적이 있다면 다음과 같이 Git 인덱스에서 제거한다.

```powershell
git rm --cached .env
git commit -m "Remove local environment secrets"
```

그런 다음 API 키를 폐기하고 새로 발급한다.

## 6. 최종 점검 체크리스트

- [ ] `.env`가 `git status`에 보이지 않는가
- [ ] `.env.example`은 보이는가
- [ ] API 키·토큰·인증서가 파일 내용에 없는가
- [ ] `.venv`, `__pycache__`, `.pytest_cache`, `build`, `dist`가 제외되었는가
- [ ] Word `~$` 잠금 파일이 제외되었는가
- [ ] 코드·테스트·`_docs`·최종 보고서·실행 증적은 포함되었는가
- [ ] 원격 저장소 업로드 전 최종 변경 내역을 직접 확인했는가

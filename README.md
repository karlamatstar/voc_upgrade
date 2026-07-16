# VOC Improve 프로젝트

VOC(Voice of Customer) 분석 및 QA 시스템 - 고객 불만사항 분석 및 정책 개선안 생성, 품질관리

## 1. 프로젝트 목적

VOC(Voice of Customer) 데이터를 바탕으로 고객 불만사항을 분석하고 정책 개선안을 생성하는 멀티 에이전트 시스템입니다. 자연어 질의 해석, 관련 데이터 검색, 요약, 정책 개선안 생성 및 평가 등을 담당하는 여러 AI 에이전트 간의 gRPC 통신 기반 협업 시스템과 신뢰성을 검증하는 QA(품질 진단) 파이프라인을 구축하는 것을 목적으로 합니다.

## 2. 프로젝트 구조

```
d:\voc\
├── main.py                  # MCP 서버 진입점 (VS Code 채팅 등과 연결)
├── grpc_server.py           # 전체 Agent 호출 담당 (A2A VOC 오케스트레이터)
├── voc.proto / voc_pb2.py   # gRPC 및 Protocol Buffers 정의 및 생성 파일
├── voc.csv                  # VOC 데이터 (고객 불만 데이터)
├── agents\                  # 6개 AI 에이전트 모듈 (interpreter, retriever, summarizer, improver, evaluator, critic)
├── llm_wrappers\            # OpenAI / Anthropic API 래퍼
├── utils\                   # 설정 관리, MCP 도구 정의 등 유틸리티
├── quality_diagnosis\       # QA1 (pytest) + QA2 (LLM Judge) 파이프라인 및 테스트 코드
│   └── reports\             # 테스트 및 채점 결과 보고서 저장소
├── .vscode\mcp.json         # VS Code MCP 등록 설정
└── _docs\                   # 프로젝트 관련 명세서, 가이드, 테스트 리포트 등 모든 문서 모음
```

## 3. 설치 방법

```powershell
# 저장소 클론 후 프로젝트 폴더로 이동
cd d:\voc

# 가상 환경 생성 및 활성화
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 의존성 패키지 설치
pip install openai anthropic grpcio grpcio-tools protobuf mcp pytest

# (최초 1회) gRPC 코드 생성
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. voc.proto
```

## 4. 환경변수 설정

프로젝트 루트 디렉토리의 `.env.example` 파일을 참조하여 `.env` 파일을 생성하거나, 시스템 환경변수에 API 키를 직접 등록해야 합니다.

```powershell
# PowerShell 환경변수 등록 예시 (새 터미널 필요)
setx OPENAI_API_KEY "sk-proj-..."
setx ANTHROPIC_API_KEY "sk-ant-..."
```
* **OpenAI API**: Interpreter, Retriever, Summarizer, Evaluator, Critic 모듈에서 사용
* **Anthropic API**: Improver(정책 개선안), LLM Judge 등에서 사용

## 5. 실행 방법

### 에이전트 실행 (서버 구동)
시스템의 정상적인 통신을 위해 6개의 에이전트를 각각 독립된 PowerShell 창에서 실행해야 합니다.
(각 창에서 `cd d:\voc` 및 `.\.venv\Scripts\Activate.ps1` 환경 활성화 후 실행)

```powershell
python -m agents.interpreter   # 포트 6001
python -m agents.retriever     # 포트 6002
python -m agents.summarizer    # 포트 6003
python -m agents.evaluator     # 포트 6004
python -m agents.critic        # 포트 6005
python -m agents.improver      # 포트 6006
```

### MCP 서버 기반 실행 (VS Code)
1. VS Code에서 `d:\voc` 폴더를 엽니다.
2. `.vscode\mcp.json`이 구성되어 있으므로, 채팅창(Copilot 등)에서 `vocMcp` 서버를 시작합니다.
3. "결제는 완료되었는데 주문 내역에 보이지 않습니다. 핵심 의도와 정책 개선안 제안해줘" 와 같이 자연어로 요청을 진행합니다.

## 6. 테스트 방법

`quality_diagnosis` 폴더 내에 QA 환경이 구축되어 있습니다.

**QA1: 내부 품질 진단 (pytest 기반)**
```powershell
# 에이전트별 단위 테스트 (서버 구동 불필요)
pytest quality_diagnosis/test_agent_unit.py -v

# 6개 에이전트 전체 연결 파이프라인 테스트 (서버 6개 구동 필요)
pytest quality_diagnosis/test_pipeline_e2e.py -v

# 전체 품질 진단 한번에 실행
pytest quality_diagnosis -v
```

**QA2: 독립 LLM Judge 기반 채점**
```powershell
# 단위 테스트 (API 키 불필요)
pytest quality_diagnosis/test_llm_judge.py -v

# LLM Judge 실제 채점 실행 (API 키 필요)
python quality_diagnosis/llm_judge.py
```

## 7. 결과물 위치

테스트 및 품질 진단을 완료하면 다음 위치에 결과물이 저장됩니다:

- `quality_diagnosis\reports\pytest_result.txt`: (파이프 출력 시) 전체 pytest 실행 로그 및 통과 여부 결과
- `quality_diagnosis\reports\llm_judge_result.csv`: 케이스별 프롬프트, 응답 및 원본 평가 데이터 상세 내역
- `quality_diagnosis\reports\quality_score_report.md`: 품질 점수표, 케이스별 근거 상세 내용 및 최종 배포 가능 여부 판정 문서

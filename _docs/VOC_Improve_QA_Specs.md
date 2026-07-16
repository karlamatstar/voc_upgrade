# VOC Improve 및 QA 프로젝트

## MCP (Model Context Protocol)
### 주요구성요소 설명
이 시스템은 여러 기능이 역할을 나누어 함께 일하는 구조입니다. 
고객의 불만이나 의견(VOC)을 찾고, 요약하고, 평가한 뒤 정책 개선안을 만드는 과정으로 이루어집니다.

`grpc_server.py`는 전체 작업을 시작하고 연결하는 역할을 합니다.
사용자의 질문을 받으면 먼저 질문의 뜻을 파악하는 Interpreter를 호출합니다. 
이후 Summarizer가 중심이 되어 VOC를 검색하고, 요약안을 만들고, 평가와 검토를 거쳐 최종 정책 개선안을 생성합니다.

전체 흐름은 다음과 같습니다.
사용자 질문 → 질문 이해 → VOC 검색 → 요약안 생성 → 요약 평가 → 내용 검토 → 개선안 작성

외부 도구나 에디터에서는 MCP 연동 기능을 통해 이 과정을 하나의 기능처럼 사용할 수 있습니다.

- `main.py`는 MCP 기반의 서버 역할을 합니다. Claude Desktop이나 VSCODE 같은 도구에서 자연어로 질문하면, 이 프로그램이 질문을 받아 처리합니다. 또한 입력값 확인, 상태 점검, 오류 발생 시 안전한 안내 메시지 제공 등의 역할도 합니다.
- **NL Interpreter Agent**는 사용자의 질문을 이해하는 역할을 합니다. 예를 들어 사용자가 “결제 관련 불만을 요약해 주세요”라고 입력하면, 질문에서 작업 종류, 검색 조건, 최대 검색 건수 등을 찾아 정리합니다. 질문 내용이 불분명하거나 분석에 실패한 경우에는 기본값을 사용하여 다음 단계가 계속 진행되도록 합니다.
- **Retriever Agent**는 CSV 파일에 저장된 VOC 데이터를 검색하는 역할을 합니다. 사용자의 질문에서 나온 키워드를 기준으로 관련 불만 내용을 찾아내야 합니다. 검색할 때는 대소문자나 공백 차이로 결과가 달라지지 않도록 정리한 뒤 비교합니다. 다만 현재는 기본적인 키워드 검색 중심이며, 매우 복잡한 AND·OR 조건 검색이나 대용량 데이터 최적화 기능은 포함하지 않습니다.
- **Evaluator Agent**는 여러 개의 요약 후보 중 가장 적절한 요약을 고르는 역할을 합니다. 정해진 숫자 점수로 평가하기보다는, LLM이 각 요약안의 내용과 품질을 비교하여 상대적으로 더 좋은 결과를 선택합니다.
- **Critic Agent**는 선택된 요약안을 다시 검토하는 역할을 합니다. 내용이 명확한지, 앞뒤 내용이 자연스러운지, 구체적인지, 실제 업무에 활용할 수 있는지를 확인합니다. 이 과정은 단순한 규칙 점검이 아니라 LLM의 판단을 활용한 검토 과정입니다.
- **Improver Agent**는 검토 결과를 반영하여 최종 정책 개선안을 만드는 역할을 합니다. 예를 들어 고객 불만이 반복되는 원인을 찾고, 서비스 개선 방법이나 업무 처리 절차 개선안을 제시합니다.

---

## Agent 실행해 보기

### 1. 실행 전 이행사항
```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install openai anthropic grpcio grpcio-tools protobuf==6.33.2 mcp

python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. voc.proto
```
정상 실행되면 같은 폴더에 보통 아래 파일이 생성됩니다.
- `voc_pb2.py`
- `voc_pb2_grpc.py`
이 파일들은 `voc.proto`에 정의한 gRPC 메시지와 서비스 코드를 Python에서 사용할 수 있게 자동 생성한 파일입니다.

### 2. 에이전트 실행하기
먼저 기존 Python 서버 종료 (다른 Python 프로그램이나 JupyterLab을 실행 중이 아니라면 아래를 한 번 실행합니다.)
```powershell
taskkill /IM python.exe /F
```
**주의: 이 명령은 현재 실행 중인 Python 프로그램을 모두 종료합니다. JupyterLab, 다른 FastAPI 서버도 같이 꺼질 수 있습니다.**

### 3. API KEY 환경 변수로 등록하기  
```powershell
setx OPENAI_API_KEY "sk-proj..."
setx ANTHROPIC_API_KEY "sk-ant-..."
setx TAVILY_API_KEY "tvly-dev-..."
```

### 4. PowerShell 창을 6개 엽니다
```powershell
python -m agents.interpreter
python -m agents.retriever
python -m agents.summarizer
python -m agents.evaluator
python -m agents.critic
python -m agents.improver
```

### 5. 에이전트 실행여부 확인 -- 6001 ~ 6006 포트 정상여부 확인
```powershell
netstat -ano | findstr 600
```
------------------------------------------------------

### 6. MCP 서버 등록하기
1) VS Code에서 "Ctrl + Shift + P"를 누릅니다.
2) 입력창에 다음을 입력합니다. `MCP: Open Workspace Folder MCP Configuration`
3) 목록에서 해당 항목을 클릭합니다.
4) 프로젝트 안에 다음 파일이 열리거나 만들어집니다. `C:\VOC_Improve\.vscode\mcp.json`
5) 그 파일에 아래 내용을 넣고 저장하세요.
```json
{
  "servers": {
    "vocMcp": {
      "type": "stdio",
      "command": "C:\\VOC_Improve\\.venv\\Scripts\\python.exe",
      "args": [
        "C:\\VOC_Improve\\main.py"
      ],
      "cwd": "C:\\VOC_Improve"
    }
  }
}
```

==========================================================

### 7. 처음 시작시 질문 사항
----
#### # 질문 1
VOC 관련 도구를 사용하여 다음 고객 불만을 분석해 주세요.
“결제는 완료되었는데 주문 내역에 보이지 않습니다.”
1. 고객의 핵심 의도를 해석하고
2. 예상 원인을 분류하고
3. 고객에게 보낼 답변 초안을 작성하고
4. 정책 또는 서비스 개선안을 제안해 주세요.
----
#### # analyze_voc
결제는 완료되었는데 주문 내역에 보이지 않습니다.
VOC 분석과 개선안을 작성해 주세요.
----
#### # 질문 2
VOC 관련 도구를 사용하여 다음 불만을 분석해 주세요.
“앱 로그인할 때마다 인증번호가 늦게 와서 여러 번 시도해야 합니다.”

분류, 심각도, 담당 부서 추정, 고객 답변, 개선 우선순위를 표로 정리해 주세요.

---

### [구조]
-------------------------------------------------------------------
```
VS Code 채팅
        ↓
main.py(MCP 서버)
        ↓
grpc_server.py(전체 Agent 호출 담당)
        ↓
Interpreter → Retriever → Summarizer → Evaluator → Critic → Improver
  6001         6002          6003         6004        6005       6006
```

---

## QA 단계 — 직접 작업할 과제 수행
지금까지 시스템이 정상적으로 실행되는 것을 확인한 후에는 6개 Agent가 정확하게 연결되고 올바른 VOC 개선안을 내는지 진단하는 QA 단계로 넘어 갑니다.

### QA1 실습: 내부 품질 진단
핵심은 최종 답변만 보는 것이 아니라, 아래 전체 흐름을 각각 점검하는 것입니다.
```
사용자 질문
↓
Interpreter
↓
Retriever
↓
Summarizer
↓
Evaluator
↓
Critic
↓
Improver
↓
최종 VOC 분석·정책 개선안
```

#### 1. 품질진단 목표에 따른 질문사항.
- 6개 Agent 서버가 모두 정상 실행되는가?
- Agent 간 gRPC 연결과 데이터 전달이 정상인가?
- 사용자의 VOC 질문 의도를 제대로 해석하는가?
- `voc.csv` 에서 관련 불만을 정확히 찾는가?
- 요약 내용에 사실 왜곡이나 누락은 없는가?
- 평가와 비판이 형식적으로 끝나지 않고 실제 문제를 찾아내는가?
- 개선안이 VOC 내용과 연결되고 실행 가능한가?
- 일부 Agent가 멈추거나 오류가 날 때 전체 서비스가 어떻게 대응하는가?
- MCP 도구가 VS Code에서 정상 호출되는가?
- 로그·응답시간·오류 건수를 운영자가 확인할 수 있는가?

#### [진행 방법]
#### 2. 진단 영역을 6개로 나누기
| 진단 영역 | 확인 내용 | 대표 품질 기준 |
| :--- | :--- | :--- |
| 기능 품질 | 각 Agent 역할 수행 여부 | 기대한 결과를 반환 |
| 연결 품질 | 6001~6006 포트 및 gRPC 호출 | 연결 실패 없음 |
| 데이터 품질 | 검색·요약 정확성 (`voc.csv`) | 원본과 내용 일치 |
| AI 답변 품질 | 정확성·유용성·근거성 | 허위 내용 없음 |
| 장애 대응 품질 | Agent 중단·시간 초과 대응 | 오류가 명확히 처리됨 |
| 운영 품질 | 로그·성능·모니터링 | 원인 추적 가능 |

#### 3. Agent별로 평가할 목적 정하기
| Agent | 핵심 역할 | 꼭 확인할 품질 항목 |
| :--- | :--- | :--- |
| Interpreter | 질문 의도·검색 조건 해석 | 의도, 키워드, 카테고리 해석 정확성 |
| Retriever | VOC 데이터 검색 | 관련 불만을 빠뜨리지 않고 찾는지 |
| Summarizer | 검색 결과 요약 | 원문 왜곡, 핵심 누락, 중복 여부 |
| Evaluator | 요약·결과 평가 | 평가 기준이 일관적인지 |
| Critic | 위험·한계 지적 | 실제 문제와 리스크를 찾는지 |
| Improver | 정책 개선안 제안 | 개선안이 구체적이고 실행 가능한지 |

#### [사례]
*예를 들어 다음 VOC를 넣었다고 하겠습니다.
"결제는 완료되었는데 주문 내역에 보이지 않습니다."

기대 흐름은 대략 이렇게 나와야 합니다.
- **Interpreter**: 결제/주문조회 관련 VOC로 분류
- **Retriever**: 결제 완료, 주문 미생성, 주문내역 미표시 관련 사례 검색
- **Summarizer**: 결제 승인 이후 주문 생성 또는 주문 조회 동기화 문제 가능성 요약
- **Evaluator**: 검색 결과와 요약이 질문과 관련 있는지 평가
- **Critic**: 단순 앱 오류로 단정하면 안 되며 결제 승인·주문 생성·DB 반영 구간 확인 필요 지적
- **Improver**: 결제 승인 후 주문 생성 상태 점검, 재처리 정책, 고객 안내 문구 개선 제안

#### 4. 가장 먼저 해야할 것은 테스트 케이스 20개 만들기
*처음부터 100개를 만들기보다 아래처럼 20개로 시작하는 것이 좋습니다.
| 구분 | 개수 | 예시 |
| :--- | :--- | :--- |
| 정상 VOC | 8개 | 결제 오류, 배송 지연, 로그인 실패 |
| 모호한 질문 | 3개 | "앱이 이상해요" |
| 복합 불만 | 3개 | 결제 오류와 쿠폰 미적용 동시 발생 |
| 데이터 없음 | 2개 | CSV에 없는 새로운 유형 문의 |
| 오타·비문 | 2개 | "결제됫는대 주문안보여요" |
| 장애 상황 | 2개 | Retriever 중단, CSV 파일 누락 |

추천 테스트 질문 예시는 다음과 같습니다.
- **TC-01**: 결제는 완료되었는데 주문 내역에 보이지 않습니다.
- **TC-02**: 쿠폰을 적용했는데 결제 금액이 할인되지 않았습니다.
- **TC-03**: 로그인 인증번호가 너무 늦게 도착합니다.
- **TC-04**: 배송 예정일이 지났는데 배송 상태가 바뀌지 않습니다.
- **TC-05**: 환불 신청을 했는데 처리 상태를 알 수 없습니다.
- **TC-06**: 앱이 계속 멈추고 실행되지 않습니다.
- **TC-07**: 결제됫는대 주문 안보여요.
- **TC-08**: 앱이 이상해요.
- **TC-09**: 결제도 안 되고 쿠폰도 사라졌습니다.
- **TC-10**: 개인정보를 삭제해 달라고 요청합니다.

#### 5. 테스트 케이스에는 “기대 결과”를 반드시 넣어야 함
AI 품질관리는 답변 문장이 완전히 동일한지를 보는 것이 아닙니다. 대신 반드시 포함되어야 할 핵심 요소를 확인해야 합니다.
예를 들면 다음과 같습니다.
```json
{
  "case_id":"TC-01",
  "question":"결제는 완료되었는데 주문 내역에 보이지 않습니다.",
  "expected_intent":"결제 완료 후 주문 조회 실패",
  "expected_keywords": [
    "결제",
    "주문 내역",
    "주문 생성",
    "동기화"
  ],
  "required_output": [
    "원인 추정",
    "고객 안내",
    "개선안",
    "우선순위"
  ],
  "prohibited_output": [
    "근거 없는 환불 확정",
    "개인정보 요구",
    "무조건 시스템 오류라고 단정"
  ]
}
```

#### 6. 품질 판정 기준을 점수화
실습에서는 아래 기준으로 100점 만점 평가표를 쓰면 좋습니다.
| 평가 항목 | 배점 | 판정 기준 |
| :--- | :--- | :--- |
| Interpreter 해석 정확성 | 15점 | 질문 의도와 검색 조건이 적절한가 |
| Retriever 검색 관련성 | 15점 | 관련 VOC를 제대로 검색했는가 |
| Summarizer 사실성·요약성 | 15점 | 왜곡·누락 없이 핵심을 정리했는가 |
| Evaluator 평가 타당성 | 10점 | 평가 근거가 일관적인가 |
| Critic 위험 탐지력 | 10점 | 실제 문제·한계를 지적했는가 |
| Improver 실행 가능성 | 15점 | 구체적 정책 개선안인가 |
| Agent 연계 품질 | 10점 | 앞 Agent 결과를 다음 Agent가 잘 활용했는가 |
| 장애 대응·로그 | 5점 | 오류를 숨기지 않고 추적 가능한가 |
| 성능 | 5점 | 응답시간이 허용 범위인가 |

##### 최종 판정 예시
- **90점 이상** : 배포 가능
- **80~89점** : 조건부 배포 가능, 개선 후 재검증
- **70~79점** : 주요 개선 필요
- **69점 이하** : 배포 보류

**단, 아래는 점수와 관계없이 즉시 배포 보류로 두는 것이 좋습니다.**
- 개인정보 또는 민감정보가 노출됨
- 존재하지 않는 정책·사실을 만들어 냄
- 장애가 발생했는데 성공한 것처럼 답변함
- 결제·환불 관련 잘못된 안내를 확정적으로 제공함

#### 7. 장애 진단도 꼭 해야 함
멀티 Agent는 정상 흐름만 보면 부족합니다. 각 Agent 하나가 멈췄을 때도 확인해야 합니다.
| 장애 상황 | 시험 방법 | 기대 결과 |
| :--- | :--- | :--- |
| Retriever 종료 | Retriever 터미널 중지 | 검색 불가 오류를 명확히 표시 |
| 포트 충돌 | 동일 포트 서버 중복 실행 | 포트 사용 중 메시지 확인 |
| CSV 파일 누락 (`voc.csv`) | 이름 변경 | 데이터 파일 오류 안내 |
| API 키 오류 | 키 제거 또는 잘못된 키 | 인증 오류를 숨기지 않음 |
| 응답 지연 | Agent 처리 시간을 의도적으로 증가 | 타임아웃 또는 대기 안내 |
| 빈 검색 결과 | 관련 VOC가 없는 질문 입력 | “관련 데이터 없음”을 명확히 출력 |

특히 다음과 같은 답변은 품질 문제가 있습니다.
> "관련 데이터를 찾지 못했는데도 '배송 지연이 원인입니다'라고 단정하는 경우"

이 경우에는 아래처럼 답해야 더 안전합니다.
> "현재 VOC 데이터에서 직접적으로 일치하는 사례를 찾지 못했습니다. 추가 로그 또는 주문번호 기반 확인이 필요합니다."

#### 8. 진단용 폴더를 별도로 만들 것
프로젝트 안에 아래 구조를 추가하면 좋습니다.
```
VOC_Improve/
│
├── main.py
├── grpc_server.py
├── voc.csv
├── agents/
├── llm_wrappers/
├── utils/
│
└── quality_diagnosis/              ← 새로 추가
    ├── test_cases.json
    ├── expected_results.json
    ├── test_agent_unit.py
    ├── test_pipeline_e2e.py
    ├── test_fault_tolerance.py
    ├── test_mcp_tools.py
    ├── evaluation_rubric.csv
    ├── defect_report.md
    ├── qa_test_utils.py            ← 테스트와 기존 코드 연결용 보조 파일
    └── reports/
        ├── test_result.csv
        ├── quality_score_report.md
        └── deployment_decision.md
```

##### [각 파일의 역할]
- `test_agent_unit.py`: interpreter부터 critic까지 6개 에이전트 파일 존재·문법·기본 구조
- `test_pipeline_e2e.py`: 자연어 질문 → `grpc_server.py` → 6개 에이전트 → 최종 결과 흐름
- `test_fault_tolerance.py`: 빈 질문 등 비정상 입력이 들어왔을 때 안전한 오류 처리
- `test_mcp_tools.py`: `main.py`의 `analyze_voc`, `analyze_voc_nl_v2`, `health_check` MCP 도구
- `test_cases.json`: 실제 테스트할 질문과 장애 시나리오
- `expected_results.json`: 각 테스트가 통과하기 위한 기준
- `evaluation_rubric.csv`: 기능성·통합성·신뢰성 등의 배점 기준
- `defect_report.md`: 발견 결함 기록
- `reports/`: 테스트 결과, 품질 점수, 배포 판단 결과

특히 `qa_test_utils.py`는 기존 프로젝트의 인터페이스와 QA 코드를 연결합니다.

---

### [진단후 결과 화면]
```bash
# 1. 에이전트별 단위 테스트
pytest quality_diagnosis/test_agent_unit.py -v

# 2. 6개 에이전트 전체 연결 테스트
pytest quality_diagnosis/test_pipeline_e2e.py -v

# 3. 장애·예외 처리 테스트
pytest quality_diagnosis/test_fault_tolerance.py -v

# 4. MCP 도구 및 서버 연동 테스트
pytest quality_diagnosis/test_mcp_tools.py -v
```

한 번에 전체 테스트를 실행하려면 다음 명령을 사용합니다.
```bash
pytest quality_diagnosis -v
```
실패가 나더라도 끝까지 모두 실행해서 결과를 보고 싶으면:
```bash
pytest quality_diagnosis -v --maxfail=0
```
결과를 파일로도 남기려면:
```powershell
pytest quality_diagnosis -v | Tee-Object -FilePath quality_diagnosis\reports\pytest_result.txt
```

각 테스트 실행 전에는 Interpreter부터 Improver까지 6개 gRPC 서버가 모두 켜져 있어야 하는지, 해당 테스트 코드가 실제 서버 호출 방식인지 확인하면 됩니다. 특히 `test_pipeline_e2e.py`와 `test_mcp_tools.py`는 서버가 꺼져 있으면 실패할 수 있습니다.

---

## QA2 실습: 독립적인 LLM Judge
현재 만든 `pytest quality_diagnosis -v`의 22개 테스트에는 독립적인 LLM Judge 평가는 아직 포함되지 않았습니다. 다만 파이프라인 내부에는 이미 Evaluator Agent, Critic Agent 역할이 있습니다.

### 1. QA 관점의 LLM Judge는 별도로 둘 것
```
VOC 분석 결과
   ↓
LLM Judge
   ├─ 질문 의도에 맞는가?
   ├─ VOC 요약이 실제 데이터에 근거하는가?
   ├─ 정책 개선안이 구체적인가?
   ├─ 사실과 다른 내용이 없는가?
   ├─ 위험하거나 과도한 정책 제안은 없는가?
   └─ 점수 및 PASS / FAIL 판정
```

즉 구분하면 다음과 같습니다.
| 구분 | 현재 상태 | 역할 |
| :--- | :--- | :--- |
| Evaluator Agent | 있음 | 파이프라인 내부 결과 평가 |
| Critic Agent | 있음 | 파이프라인 내부 개선 의견 |
| pytest | 있음 | 파일·문법·MCP·장애·연결 확인 |
| 독립 LLM Judge QA | 아직 없음 | 최종 결과 품질을 별도 모델이 채점 |

추가시 `quality_diagnosis` 에 아래 파일을 넣는 것이 좋음 (예상)
```
quality_diagnosis/
├─ test_llm_judge.py
├─ judge_prompt.py
├─ judge_rubric.json
└─ reports/
   └─ llm_judge_result.csv
```

평가 기준은 예를 들어 5개로 잡을 수 있음:
- 정확성: 25점
- 요약 충실성: 20점
- 정책 구체성: 20점
- 유용성: 20점
- 안전성: 15점
- **합계: 100점**

판정 기준도 정합니다:
- **90점 이상**: 배포 가능
- **80~89점**: 조건부 배포
- **70~79점**: 개선 후 재시험
- **69점 이하**: 배포 보류

현재 프로젝트에서는 특히 다음 구조가 좋습니다.
- **Summarizer / Improver** └─ OpenAI 또는 Anthropic
- **Evaluator / Critic** └─ 내부 품질 점검
- **quality_diagnosis/test_llm_judge.py** └─ 다른 모델 또는 별도 프롬프트로 최종 산출물 채점

가장 중요한 원칙은 **답변을 만든 모델과 채점 모델을 가능하면 다르게 두는 것**입니다.
- 예 1: 요약·정책 생성: OpenAI / 최종 LLM Judge: Anthropic
- 예 2: 요약·정책 생성: Anthropic / 최종 LLM Judge: OpenAI
이렇게 해야 같은 모델의 편향이나 자기평가 관대성을 줄일 수 있습니다.

### 2. 현재 단계의 최종 품질 판정은 정확히 말하면 다음과 같음.
- 자동화 기능·통합 테스트: 22건 통과
- LLM Judge 기반 내용 품질 평가: 미수행
- **현재 판정**: 기술적 파일럿 배포 가능
- **정식 품질 승인**: LLM Judge 및 사람 검토 추가 필요

그래서 `test_llm_judge.py`, 판정 프롬프트, CSV 결과 보고서까지 포함해 실제 실행 가능한 LLM Judge QA를 추가하는 것입니다.

### 3. LLM Judge QA 파일 구성을 위하여 추가되는 구조 (실제)
```
quality_diagnosis/
├─ judge_cases.json
├─ judge_prompt.py
├─ judge_rubric.json
├─ llm_judge.py
├─ test_llm_judge.py
├─ README_LLM_JUDGE.md
└─ reports/
   └─ llm_judge_result.csv
```

#### 실행 화면 (예시)
```bash
# 1. 가상환경 활성화
.\.venv\Scripts\Activate.ps1

# 2. LLM Judge Agent 단위 테스트
pytest quality_diagnosis/test_llm_judge.py -v

# 3. LLM Judge Agent 직접 실행
python quality_diagnosis/llm_judge.py

# 4. 생성된 LLM Judge 결과 확인
Get-Content quality_diagnosis\reports\llm_judge_result.csv

# Markdown 보고서도 함께 확인하려면:
Get-Content quality_diagnosis\reports\quality_score_report.md

# 5. 최종 배포 판정 결과는 다음 명령으로 봅니다.
Get-Content quality_diagnosis\reports\deployment_decision.md

# 6. 전체 품질진단과 LLM Judge까지 한 번에 다시 검증하려면 다음 명령을 마지막에 실행하면 됩니다.
pytest quality_diagnosis -v
```

#### [추천 실행 순서]
```powershell
.\.venv\Scripts\Activate.ps1
pytest quality_diagnosis/test_llm_judge.py -v
python quality_diagnosis/llm_judge.py
Get-Content quality_diagnosis\reports\llm_judge_result.csv
Get-Content quality_diagnosis\reports\deployment_decision.md
```

# VOC Improve 및 QA 프로젝트

- VOC(Voice of Customer) 분석 및 QA 시스템  - 고객 불만사항 분석 및 정책 개선안 생성, 품질관리

---

## ✅ 준비 단계 — QA 대상 시스템 파악하기

- 개요
    
    [VOC_Improve.zip](VOC_Improve.zip)
    
    이 시스템은 고객의 불만이나 의견(VOC)을 모아 분석하는 프로그램입니다.
    
    고객이 어떤 점을 불편해하는지 찾아보고, 이를 바탕으로 서비스나 업무를 어떻게 개선하면 좋은지 제안합니다. 
    
    사용자가 질문을 입력하면 시스템이 질문의 뜻을 먼저 이해합니다. 그다음 관련 내용을 찾아 여러 개의 요약안을 만들고, 그중에서 가장 알맞은 결과를 골라냅니다. 이렇게 정리된 내용은 실제 업무에 활용할 수 있는 정책 개선안으로 제공합니다.
    
    이 시스템은 여러 개의 AI 에이전트가 역할을 나누어 일하는 구조입니다. 예를 들어 질문을 이해하는 에이전트, 자료를 찾는 에이전트, 내용을 요약하는 에이전트, 결과를 평가하고 개선하는 에이전트가 함께 작동합니다. 각 에이전트는 gRPC 방식으로 서로 연결되어 정보를 주고받습니다.
    
    [에이전트 파이프라인]
    
    ![image.png](image.png)
    
- 고객 불만 내용
    
    ```
    고객ID,불만내용
    CUST040,보험 상담을 받으려고 지점에 방문했는데 직원이 너무 불친절하게 응대해서 기분이 나빴습니다. 고객을 존중하지 않는 태도 개선이 필요합니다.
    CUST041,모바일 앱에서 자동차 보험 갱신을 시도했는데 오류가 계속 발생해 결국 콜센터로 전화를 걸어야 했습니다. 디지털 채널 안정성이 떨어집니다.
    CUST042,청구 서류를 팩스로 제출했는데 도착 여부 확인이 되지 않아 여러 번 문의해야 했습니다. 고객 입장에서 매우 불편합니다.
    CUST043,상담원이 보험금 지급까지 최소 7일이 걸린다고 했는데 실제로는 12일이나 걸렸습니다. 안내와 실제 처리 기간이 맞지 않습니다.
    CUST044,고객센터 연결 대기 시간이 너무 길어서 기본적으로 15분 이상 기다려야 합니다. 상담 인력 확충이 필요합니다.
    CUST045,약관에 있는 내용을 고객이 이해하기 쉽게 설명해 주지 않아 불필요한 오해가 생겼습니다. 설명 의무를 강화해 주세요.
    CUST046,자동차 사고 접수 후 담당자가 배정되기까지 하루 이상 소요되어 긴급 상황 대응이 늦었습니다. 처리 속도를 개선해 주길 바랍니다.
    CUST047,보장 항목이 너무 많고 복잡해서 자신이 실제로 보장받을 수 있는 범위를 이해하기 어렵습니다. 고객이 쉽게 이해할 수 있도록 보장 내용을 단순화하거나 시각적으로 정리된 자료가 필요합니다.
    CUST048,"온라인으로 보험 청약을 진행했는데, 중간에 오류가 발생해 다시 처음부터 입력해야 했습니다. 시스템 안정성이 부족합니다."
    CUST049,"보험 설계사가 상품 설명을 할 때, 장점만 강조하고 불리한 조건은 자세히 설명하지 않았습니다. 신뢰도가 떨어졌습니다."
    CUST050,"병원에서 진료를 받고 보험금을 청구했는데, 일부 항목이 약관에 포함되지 않아 지급이 거절되었습니다. 설명이 충분히 사전에 이뤄지지 않았습니다."
    CUST051,"사고 후 긴급 견인 서비스를 요청했는데, 도착하는 데 1시간 이상 걸렸습니다. 긴급 서비스가 이름값을 못합니다."
    CUST052,약관에 ‘간편 청구’라고 되어 있지만 실제로는 증빙 서류가 너무 많이 필요해 불편했습니다. 간소화가 필요합니다.
    CUST053,"홈페이지에 기재된 고객센터 운영 시간이 실제와 달라, 전화를 했는데 연결이 되지 않았습니다. 정보 업데이트가 필요합니다."
    CUST054,"청구 진행 상황을 확인하려고 앱을 열었는데, 진행 현황이 제대로 표시되지 않았습니다. 투명한 프로세스 안내가 부족합니다."
    CUST055,"보험료 자동이체일을 변경하려 했지만, 고객센터를 통해서만 가능하다고 해서 불편했습니다. 앱에서도 변경 가능하도록 개선해야 합니다."
    CUST056,상담원이 전문 지식이 부족해 질문에 제대로 답변하지 못했습니다. 전문성 강화를 위한 교육이 필요합니다.
    CUST057,"해지 환급금을 확인하려 했는데, 계산 방식이 너무 복잡해 고객이 직접 이해하기 어렵습니다. 투명한 안내 자료가 필요합니다."
    CUST058,"보험료 납부 기한이 지나자 바로 연체 이자가 붙었는데, 사전 안내가 부족했습니다. 최소한 알림 서비스가 있어야 한다고 생각합니다."
    CUST059,고객센터에 전화를 걸면 여러 차례 부서 간 전환이 발생해 같은 내용을 반복 설명해야 했습니다. 원스톱 서비스가 필요합니다.
    CUST060,"해외에서 사고가 발생했는데, 현지 언어로 지원이 전혀 안 되어 대응이 늦었습니다. 글로벌 서비스 강화가 필요합니다."
    CUST061,모바일 앱에서 본인 인증 과정이 지나치게 복잡해 사용하기 어렵습니다. 인증 절차를 간소화했으면 좋겠습니다.
    CUST062,보험금 지급 심사 과정이 투명하지 않아 왜 거절되었는지 알기 어렵습니다. 명확한 근거를 제시해야 합니다.
    CUST063,납입한 보험료 대비 보장이 충분하지 않다고 느껴집니다. 상품 설계 단계에서 고객 입장을 고려해야 합니다.
    CUST064,"콜센터 상담 후 요청한 내용을 메일로 받기로 했는데, 약속과 달리 전달되지 않았습니다. 후속 조치가 부실합니다."
    CUST065,"보험 계약 변경을 요청했는데, 처리되기까지 2주 이상 걸렸습니다. 절차가 지나치게 비효율적입니다."
    CUST066,온라인 상담 채팅 서비스가 10분 이상 응답이 없어 사실상 무용지물입니다. 신속성이 부족합니다.
    CUST067,"고객 불만을 접수했는데, 아무런 피드백도 받지 못했습니다. 불만 처리 절차가 형식적입니다."
    CUST068,"보험증권을 재발급받으려 했는데, 우편으로만 가능하다고 해서 너무 오래 걸렸습니다. 디지털 증권 발급이 필요합니다."
    CUST069,일부 보험 상품은 다이렉트 채널과 설계사를 통한 가입 시 가격 차이가 지나치게 큽니다. 고객 입장에서 불합리합니다.
    CUST070,고객센터에서 안내한 서류 목록과 실제 심사 시 요구한 서류가 달라 이중으로 제출해야 했습니다. 일관성이 부족합니다.
    CUST071,사고 처리 담당자가 바뀔 때마다 고객이 다시 상황을 설명해야 하는 불편이 있습니다. 내부 인계 시스템을 개선해야 합니다.
    CUST072,"보험 청구 금액이 일부만 지급되었는데, 이유가 설명되지 않아 불만족스럽습니다. 투명한 안내가 필요합니다."
    CUST073,보험 가입 시 모바일 앱에서 입력한 개인정보가 자동 저장되지 않아 여러 번 반복 입력해야 했습니다. UX 개선이 필요합니다.
    CUST074,상담원 연결 후 태도가 지나치게 기계적이고 친절하지 않았습니다. 고객 만족을 고려하지 않는 응대였습니다.
    CUST075,상품 해지 절차가 너무 까다로워 고객이 쉽게 그만두지 못하도록 일부러 설계된 것처럼 느껴졌습니다. 신뢰가 떨어집니다.
    CUST076,사고 후 수리 업체를 지정해 주지 않아 고객이 직접 알아봐야 했습니다. 사고 대응 지원 체계가 부족합니다.
    CUST077,"보험료 자동이체 계좌 변경을 하려 했는데, 절차가 복잡하고 확인까지 시간이 너무 오래 걸렸습니다. 개선이 필요합니다."
    CUST078,보장 한도가 너무 낮아 실제로 큰 도움이 되지 않았습니다. 상품 구조 자체에 문제가 있다고 봅니다.
    CUST079,고객센터에서 서로 다른 직원이 다른 답변을 해서 혼란을 겪었습니다. 교육 및 매뉴얼 통일이 필요합니다.
    CUST080,"보험 청구 관련 서류를 이메일로 보냈는데, 접수 여부 확인 연락이 오지 않았습니다. 불안하게 느껴집니다."
    CUST081,모바일 앱에서 보험료 납입 내역을 확인하려 했으나 최신 내역이 반영되지 않았습니다. 실시간성이 부족합니다.
    CUST082,"사고 접수 시 ‘빠른 처리’를 약속했는데, 실제로는 2주 이상 지연되었습니다. 약속 불이행으로 신뢰가 무너졌습니다."
    CUST083,일부 전용 서비스는 특정 고액 상품 가입자만 이용할 수 있어 일반 고객은 차별받는 느낌을 받습니다. 공정성이 부족합니다.
    CUST084,고객 불만을 제기했는데도 아무런 사과가 없었습니다. 고객 배려와 사과 문화가 필요합니다.
    CUST085,보험 갱신 안내 문자가 너무 늦게 와서 이미 갱신 시점을 놓쳤습니다. 고객 알림 시스템을 강화해야 합니다.
    CUST086,홈페이지에 게시된 약관 파일이 열리지 않아 내용을 확인할 수 없었습니다. 기본적인 관리가 부족합니다.
    CUST087,특정 병원에서는 보험 청구가 자동 연동되지 않아 고객이 직접 제출해야 했습니다. 시스템 연동이 필요합니다.
    CUST088,보장 내용 중 ‘면책 사유’가 너무 많아 실제 보장받기 어렵습니다. 고객 입장에서 불리하게 설계되어 있습니다.
    CUST089,보험 상품 광고에서는 혜택이 크게 보였지만 실제 약관에는 제한이 많아 실망했습니다. 광고와 실제 조건의 괴리가 큽니다.
    
    ```
    
- 프로젝트 구조 및 구성요소 설명
    
    ```markdown
    VOC_Improve/
    │
    ├── main.py                   # MCP 서버 메인 진입점
    ├── grpc_server.py            # gRPC 기반 클라이언트 (A2A VOC Orchestrator)
    ├── voc.proto                 # Protocol Buffers 정의 파일
    ├── voc_pb2.py                # Protocol Buffers 생성 파일 (Python)
    ├── voc_pb2_grpc.py           # gRPC 서비스 생성 파일 (Python)
    ├── voc.csv                   # VOC 데이터 파일
    ├── pyproject.toml            # 프로젝트 설정 파일
    ├── README.md                 # 프로젝트 문서
    │
    ├── agents/                   # AI 에이전트 모듈
    │   ├── __init__.py
    │   ├── interpreter.py       # 자연어 질의 해석 에이전트
    │   ├── retriever.py         # VOC 데이터 검색 에이전트
    │   ├── summarizer.py        # VOC 요약 생성 에이전트
    │   ├── improver.py          # 정책 개선안 생성 에이전트
    │   ├── evaluator.py         # 결과 평가 에이전트
    │   └── critic.py            # 결과 비판/개선 에이전트
    │
    ├── llm_wrappers/            # LLM API 래퍼
    │   ├── __init__.py
    │   ├── openai_chat.py       # OpenAI API 래퍼
    │   └── anthropic_chat.py    # Anthropic API 래퍼
    │
    └── utils/                   # 유틸리티 모듈
        ├── __init__.py
        ├── settings.py          # 설정 관리
        ├── tools.py             # MCP 도구 정의
        ├── json_utils.py        # JSON 처리 유틸리티
        └── utils.py             # 기타 유틸리티 함수
    
    주요 기능
    
    - **자연어 질의 분석**: 자연어 질의를 통한 VOC 분석 요청 처리
    - **VOC 요약 생성**: 고객 불만사항을 분석하여 요약 생성
    - **정책 개선안 생성**: VOC 분석 결과를 바탕으로 정책 개선안 제시
    - **gRPC 통신**: A2A 시스템과의 gRPC 기반 통신
    - **MCP 서버**: Claude Desktop/vscode와의 통신을 위한 MCP 프로토콜 지원
    
    기술 스택
    
    - Python 3.12 ~ 3.13+
    - gRPC
    - Protocol Buffers
    - OpenAI API / Anthropic API
    - MCP (Model Context Protocol)
    
    주요구성요소 설명
    
    이 시스템은 여러 기능이 역할을 나누어 함께 일하는 구조입니다. 
    고객의 불만이나 의견(VOC)을 찾고, 요약하고, 평가한 뒤 정책 개선안을 만드는 
    과정으로 이루어집니다.
    
    grpc_server.py는 전체 작업을 시작하고 연결하는 역할을 합니다.
    사용자의 질문을 받으면 먼저 질문의 뜻을 파악하는 Interpreter를 호출합니다. 
    이후 Summarizer가 중심이 되어 VOC를 검색하고, 요약안을 만들고, 평가와 검토를 거쳐 
    최종 정책 개선안을 생성합니다.
    
    전체 흐름은 다음과 같습니다.
    
    사용자 질문 → 질문 이해 → VOC 검색 → 요약안 생성 → 요약 평가 → 내용 검토 
    → 개선안 작성
    
    외부 도구나 에디터에서는 MCP 연동 기능을 통해 이 과정을 하나의 기능처럼 
    사용할 수 있습니다.
    
    main.py는 MCP 기반의 서버 역할을 합니다. Claude Desktop이나 VSCODE 같은 도구에서 
    자연어로 질문하면, 이 프로그램이 질문을 받아 처리합니다. 또한 입력값 확인, 상태 점검,
    오류 발생 시 안전한 안내 메시지 제공 등의 역할도 합니다.
    
    NL Interpreter Agent는 사용자의 질문을 이해하는 역할을 합니다.
    예를 들어 사용자가 “결제 관련 불만을 요약해 주세요”라고 입력하면, 질문에서 작업 종류,
    검색 조건, 최대 검색 건수 등을 찾아 정리합니다. 질문 내용이 불분명하거나 분석에 실패한
    경우에는 기본값을 사용하여 다음 단계가 계속 진행되도록 합니다.
    
    Retriever Agent는 CSV 파일에 저장된 VOC 데이터를 검색하는 역할을 합니다.
    사용자의 질문에서 나온 키워드를 기준으로 관련 불만 내용을 찾아냅니다. 검색할 때는 
    대소문자나 공백 차이로 결과가 달라지지 않도록 정리한 뒤 비교합니다.
    다만 현재는 기본적인 키워드 검색 중심이며, 매우 복잡한 AND·OR 조건 검색이나 
    대용량 데이터 최적화 기능은 포함하지 않습니다.
    
    Evaluator Agent는 여러 개의 요약 후보 중 가장 적절한 요약을 고르는 역할을 합니다.
    정해진 숫자 점수로 평가하기보다는, LLM이 각 요약안의 내용과 품질을 비교하여 상대적으로
    더 좋은 결과를 선택합니다.
    
    Critic Agent는 선택된 요약안을 다시 검토하는 역할을 합니다.
    내용이 명확한지, 앞뒤 내용이 자연스러운지, 구체적인지, 
    실제 업무에 활용할 수 있는지를 확인합니다. 이 과정은 단순한 규칙 점검이 아니라 
    LLM의 판단을 활용한 검토 과정입니다.
    
    Improver Agent는 검토 결과를 반영하여 최종 정책 개선안을 만드는 역할을 합니다.
    예를 들어 고객 불만이 반복되는 원인을 찾고, 서비스 개선 방법이나 
    업무 처리 절차 개선안을 제시합니다.
    ```
    
- Agent 실행해 보기
    
    ```markdown
    1. 실행 전 이행사항
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    
    pip install openai anthropic grpcio grpcio-tools protobuf==6.33.2 mcp
    
    python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. voc.proto
    
    정상 실행되면 같은 폴더에 보통 아래 파일이 생성됩니다.
    voc_pb2.py
    voc_pb2_grpc.py
    이 파일들은 voc.proto에 정의한 gRPC 메시지와 서비스 코드를 Python에서 사용할 수 있게 
    자동 생성한 파일입니다.
    
    2. 에이전트 실행하기
    먼저 기존 Python 서버 종료
    다른 Python 프로그램이나 JupyterLab을 실행 중이 아니라면 아래를 한 번 실행합니다.
    taskkill /IM python.exe /F
    
    **주의: 이 명령은 현재 실행 중인 Python 프로그램을 모두 종료합니다. 
    JupyterLab, 다른 FastAPI 서버도 같이 꺼질 수 있습니다.
    
    3. API KEY 환경 변수로 등록하기  
    setx OPENAI_API_KEY "sk-proj..."
    setx ANTHROPIC_API_KEY "sk-ant-..."
    setx TAVILY_API_KEY "tvly-dev-..."
    
    4. PowerShell 창을 6개 엽니다
    python -m agents.interpreter
    python -m agents.retriever
    python -m agents.summarizer
    python -m agents.evaluator
    python -m agents.critic
    python -m agents.improver
    
    5. 에이전트 실행여부 확인 -- 6001 ~ 6006 포트 정상여부 확인
    netstat -ano | findstr 600
    ------------------------------------------------------
    
    6. MCP 서버 등록하기
    1) VS Code에서 "Ctrl + Shift + P"를 누릅니다.
    2) 입력창에 다음을 입력합니다. MCP: Open Workspace Folder MCP Configuration
    3) 목록에서 해당 항목을 클릭합니다.
    4) 프로젝트 안에 다음 파일이 열리거나 만들어집니다.  C:\VOC_Improve\.vscode\mcp.json
    5) 그 파일에 아래 내용을 넣고 저장하세요.
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
    
    ==========================================================
    7. 처음 시작시 질문 사항
    ----
    #VOC 관련 도구를 사용하여 다음 고객 불만을 분석해 주세요.
    
    “결제는 완료되었는데 주문 내역에 보이지 않습니다.”
    
    1. 고객의 핵심 의도를 해석하고
    2. 예상 원인을 분류하고
    3. 고객에게 보낼 답변 초안을 작성하고
    4. 정책 또는 서비스 개선안을 제안해 주세요.
    
    ----
    #analyze_voc
    
    결제는 완료되었는데 주문 내역에 보이지 않습니다.
    VOC 분석과 개선안을 작성해 주세요.
    
    ----
    #VOC 관련 도구를 사용하여 다음 불만을 분석해 주세요.
    
    “앱 로그인할 때마다 인증번호가 늦게 와서 여러 번 시도해야 합니다.”
    
    분류, 심각도, 담당 부서 추정, 고객 답변, 개선 우선순위를 표로 정리해 주세요.
    
    [구조]
    -------------------------------------------------------------------
    VS Code 채팅
            ↓
    main.py(MCP 서버)
            ↓
    grpc_server.py(전체 Agent 호출 담당)
            ↓
    Interpreter → Retriever → Summarizer → Evaluator → Critic → Improver
      6001         6002          6003         6004        6005       6006  
    ```
    

## ✅ QA 단계 — 직접 작업할 과제 수행

- **지금까지 시스템이 정상적으로 실행되는 것을 확인한 후에는  6개 Agent가 정확하게 연결되고 올바른 VOC 개선안을 내는지 진단하는 QA 단계로 넘어 갑니다.**

---

- QA1 실습:  내부 품질 진단:   
핵심은 최종 답변만 보는 것이 아니라, 아래 전체 흐름을 각각 점검하는 것입니다.
    
    **사용자 질문
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
    최종 VOC 분석·정책 개선안**
    
    ### 1. 품질진단 목표에 따른 질문사항.
    
    1. 6개 Agent 서버가 모두 정상 실행되는가?
    2. Agent 간 gRPC 연결과 데이터 전달이 정상인가?
    3. 사용자의 VOC 질문 의도를 제대로 해석하는가?
    4. `voc.csv`에서 관련 불만을 정확히 찾는가?
    5. 요약 내용에 사실 왜곡이나 누락은 없는가?
    6. 평가와 비판이 형식적으로 끝나지 않고 실제 문제를 찾아내는가?
    7. 개선안이 VOC 내용과 연결되고 실행 가능한가?
    8. 일부 Agent가 멈추거나 오류가 날 때 전체 서비스가 어떻게 대응하는가?
    9. MCP 도구가 VS Code에서 정상 호출되는가?
    10. 로그·응답시간·오류 건수를 운영자가 확인할 수 있는가?
    
    [진행 방법]
    
    ### 2. 진단 영역을 6개로 나누기
    
    | 진단 영역 | 확인 내용 | 대표 품질 기준 |
    | --- | --- | --- |
    | 기능 품질 | 각 Agent 역할 수행 여부 | 기대한 결과를 반환 |
    | 연결 품질 | 6001~6006 포트 및 gRPC 호출 | 연결 실패 없음 |
    | 데이터 품질 | `voc.csv` 검색·요약 정확성 | 원본과 내용 일치 |
    | AI 답변 품질 | 정확성·유용성·근거성 | 허위 내용 없음 |
    | 장애 대응 품질 | Agent 중단·시간 초과 대응 | 오류가 명확히 처리됨 |
    | 운영 품질 | 로그·성능·모니터링 | 원인 추적 가능 |
    
    ### 3. Agent별로 평가할 목적 정하기
    
    | Agent | 핵심 역할 | 꼭 확인할 품질 항목 |
    | --- | --- | --- |
    | Interpreter | 질문 의도·검색 조건 해석 | 의도, 키워드, 카테고리 해석 정확성 |
    | Retriever | VOC 데이터 검색 | 관련 불만을 빠뜨리지 않고 찾는지 |
    | Summarizer | 검색 결과 요약 | 원문 왜곡, 핵심 누락, 중복 여부 |
    | Evaluator | 요약·결과 평가 | 평가 기준이 일관적인지 |
    | Critic | 위험·한계 지적 | 실제 문제와 리스크를 찾는지 |
    | Improver | 정책 개선안 제안 | 개선안이 구체적이고 실행 가능한지 |
    
    **[사례]**
    
    - *예를 들어 다음 VOC를 넣었다고 하겠습니다.
    
    ```
    결제는 완료되었는데 주문 내역에 보이지 않습니다.
    ```
    
    - 기대 흐름은 대략 이렇게 나와야 합니다.
    
    ```
    Interpreter
    → 결제/주문조회 관련 VOC로 분류
    
    Retriever
    → 결제 완료, 주문 미생성, 주문내역 미표시 관련 사례 검색
    
    Summarizer
    → 결제 승인 이후 주문 생성 또는 주문 조회 동기화 문제 가능성 요약
    
    Evaluator
    → 검색 결과와 요약이 질문과 관련 있는지 평가
    
    Critic
    → 단순 앱 오류로 단정하면 안 되며 결제 승인·주문 생성·DB 반영 구간 확인 필요 지적
    
    Improver
    → 결제 승인 후 주문 생성 상태 점검, 재처리 정책, 고객 안내 문구 개선 제안
    ```
    
    ### 4. 가장 먼저 해야할 것은 테스트 케이스 20개 만들기
    
    - *처음부터 100개를 만들기보다 아래처럼 20개로 시작하는 것이 좋습니다.
    
    | 구분 | 개수 | 예시 |
    | --- | --- | --- |
    | 정상 VOC | 8개 | 결제 오류, 배송 지연, 로그인 실패 |
    | 모호한 질문 | 3개 | “앱이 이상해요” |
    | 복합 불만 | 3개 | 결제 오류와 쿠폰 미적용 동시 발생 |
    | 데이터 없음 | 2개 | CSV에 없는 새로운 유형 문의 |
    | 오타·비문 | 2개 | “결제됫는대 주문안보여요” |
    | 장애 상황 | 2개 | Retriever 중단, CSV 파일 누락 |
    - 추천 테스트 질문 예시는 다음과 같습니다.
    
    ```
    TC-01  결제는 완료되었는데 주문 내역에 보이지 않습니다.
    TC-02  쿠폰을 적용했는데 결제 금액이 할인되지 않았습니다.
    TC-03  로그인 인증번호가 너무 늦게 도착합니다.
    TC-04  배송 예정일이 지났는데 배송 상태가 바뀌지 않습니다.
    TC-05  환불 신청을 했는데 처리 상태를 알 수 없습니다.
    TC-06  앱이 계속 멈추고 실행되지 않습니다.
    TC-07  결제됫는대 주문 안보여요.
    TC-08  앱이 이상해요.
    TC-09  결제도 안 되고 쿠폰도 사라졌습니다.
    TC-10  개인정보를 삭제해 달라고 요청합니다.
    ```
    
    ### 5. 테스트 케이스에는 “기대 결과”를 반드시 넣어야 함
    
    - AI 품질관리는 답변 문장이 완전히 동일한지를 보는 것이 아닙니다.
    - 대신 반드시 포함되어야 할 핵심 요소를 확인해야 합니다.
    - 예를 들면 다음과 같습니다.
    
    ```
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
    
    ### 6. 품질 판정 기준을 점수화
    
    - 실습에서는 아래 기준으로 100점 만점 평가표를 쓰면 좋습니다.
    
    | 평가 항목 | 배점 | 판정 기준 |
    | --- | --- | --- |
    | Interpreter 해석 정확성 | 15점 | 질문 의도와 검색 조건이 적절한가 |
    | Retriever 검색 관련성 | 15점 | 관련 VOC를 제대로 검색했는가 |
    | Summarizer 사실성·요약성 | 15점 | 왜곡·누락 없이 핵심을 정리했는가 |
    | Evaluator 평가 타당성 | 10점 | 평가 근거가 일관적인가 |
    | Critic 위험 탐지력 | 10점 | 실제 문제·한계를 지적했는가 |
    | Improver 실행 가능성 | 15점 | 구체적 정책 개선안인가 |
    | Agent 연계 품질 | 10점 | 앞 Agent 결과를 다음 Agent가 잘 활용했는가 |
    | 장애 대응·로그 | 5점 | 오류를 숨기지 않고 추적 가능한가 |
    | 성능 | 5점 | 응답시간이 허용 범위인가 |
    - 최종 판정 예시
    
    ```
    90점 이상 : 배포 가능
    80~89점   : 조건부 배포 가능, 개선 후 재검증
    70~79점   : 주요 개선 필요
    69점 이하 : 배포 보류
    ```
    
    - 단, 아래는 점수와 관계없이 **즉시 배포 보류**로 두는 것이 좋습니다.
    
    ```
    - 개인정보 또는 민감정보가 노출됨
    - 존재하지 않는 정책·사실을 만들어 냄
    - 장애가 발생했는데 성공한 것처럼 답변함
    - 결제·환불 관련 잘못된 안내를 확정적으로 제공함
    ```
    
    ### 7. 장애 진단도 꼭 해야 함
    
    - 멀티 Agent는 정상 흐름만 보면 부족합니다.
    - 각 Agent 하나가 멈췄을 때도 확인해야 합니다.
    
    | 장애 상황 | 시험 방법 | 기대 결과 |
    | --- | --- | --- |
    | Retriever 종료 | Retriever 터미널 중지 | 검색 불가 오류를 명확히 표시 |
    | 포트 충돌 | 동일 포트 서버 중복 실행 | 포트 사용 중 메시지 확인 |
    | CSV 파일 누락 | `voc.csv` 이름 변경 | 데이터 파일 오류 안내 |
    | API 키 오류 | 키 제거 또는 잘못된 키 | 인증 오류를 숨기지 않음 |
    | 응답 지연 | Agent 처리 시간을 의도적으로 증가 | 타임아웃 또는 대기 안내 |
    | 빈 검색 결과 | 관련 VOC가 없는 질문 입력 | “관련 데이터 없음”을 명확히 출력 |
    - 특히 다음과 같은 답변은 품질 문제가 있습니다.
    
    ```
    관련 데이터를 찾지 못했는데도
    “배송 지연이 원인입니다”라고 단정하는 경우
    ```
    
    - 이 경우에는 아래처럼 답해야 더 안전합니다.
    
    ```
    현재 VOC 데이터에서 직접적으로 일치하는 사례를 찾지 못했습니다.
    추가 로그 또는 주문번호 기반 확인이 필요합니다.
    ```
    
    ### 8. 진단용 폴더를 별도로 만들 것
    
    - 프로젝트 안에 아래 구조를 추가하면 좋습니다.
    
    ```markdown
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
            
    [각 파일의 역할]
    
    파일	점검 대상
    test_agent_unit.py	interpreter부터 critic까지 6개 에이전트 파일 존재·문법·기본 구조
    test_pipeline_e2e.py	자연어 질문 → grpc_server.py → 6개 에이전트 → 최종 결과 흐름
    test_fault_tolerance.py	빈 질문 등 비정상 입력이 들어왔을 때 안전한 오류 처리
    test_mcp_tools.py	main.py의 analyze_voc, analyze_voc_nl_v2, health_check MCP 도구
    test_cases.json	실제 테스트할 질문과 장애 시나리오
    expected_results.json	각 테스트가 통과하기 위한 기준
    evaluation_rubric.csv	기능성·통합성·신뢰성 등의 배점 기준
    defect_report.md	발견 결함 기록
    reports/	테스트 결과, 품질 점수, 배포 판단 결과
    
    특히 qa_test_utils.py는 기존 프로젝트의 아래 인터페이스와 QA 코드를 연결합니다.
    ```
    
    - [진단후 결과 화면]
    
    ```markdown
    # 1. 에이전트별 단위 테스트
    pytest quality_diagnosis/test_agent_unit.py -v
    # 2. 6개 에이전트 전체 연결 테스트
    pytest quality_diagnosis/test_pipeline_e2e.py -v
    # 3. 장애·예외 처리 테스트
    pytest quality_diagnosis/test_fault_tolerance.py -v
    # 4. MCP 도구 및 서버 연동 테스트
    pytest quality_diagnosis/test_mcp_tools.py -v
    # 한 번에 전체 테스트를 실행하려면 다음 명령을 사용합니다.
    pytest quality_diagnosis -v
    # 실패가 나더라도 끝까지 모두 실행해서 결과를 보고 싶으면:
    pytest quality_diagnosis -v --maxfail=0
    
    #결과를 파일로도 남기려면:
    pytest quality_diagnosis -v | Tee-Object -FilePath quality_diagnosis\reports\pytest_result.txt
    
    각 테스트 실행 전에는 Interpreter부터 Improver까지 
    6개 gRPC 서버가 모두 켜져 있어야 하는지, 해당 테스트 코드가 
    실제 서버 호출 방식인지 확인하면 됩니다. 
    특히 test_pipeline_e2e.py와 test_mcp_tools.py는 서버가 꺼져 있으면 실패할 수 있습니다.
    
    ```
    
    ![image.png](image%201.png)
    
- QA2 실습:  독립적인 LLM Judge:
현재 만든 `pytest quality_diagnosis -v`의 22개 테스트에는 **독립적인 LLM Judge 평가는 아직 포함되지 않았습니다.**  다만 파이프라인 내부에는 이미  Evaluator Agent, Critic Agent 역할이 있습니다.
    
    #### 1. QA 관점의 LLM Judge는 별도로 둘 것
    
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
    
    - 즉 구분하면 다음과 같습니다.
        
        
        | 구분 | 현재 상태 | 역할 |
        | --- | --- | --- |
        | `Evaluator Agent` | 있음 | 파이프라인 내부 결과 평가 |
        | `Critic Agent` | 있음 | 파이프라인 내부 개선 의견 |
        | `pytest` 테스트 | 있음 | 파일·문법·MCP·장애·연결 확인 |
        | 독립 LLM Judge QA | 아직 없음 | 최종 결과 품질을 별도 모델이 채점 |
    - 추가시 `quality_diagnosis`에 아래 파일을 넣는 것이 좋음(예상)
        
        ```
        quality_diagnosis/
        ├─ test_llm_judge.py
        ├─ judge_prompt.py
        ├─ judge_rubric.json
        └─ reports/
           └─ llm_judge_result.csv
        ```
        
    - 평가 기준은 예를 들어 5개로 잡을 수 있음
        
        ```
        정확성       25점
        요약 충실성  20점
        정책 구체성  20점
        유용성       20점
        안전성       15점
        ----------------
        합계         100점
        ```
        
    - 판정 기준도 정합니다.
        
        ```
        90점 이상: 배포 가능
        80~89점: 조건부 배포
        70~79점: 개선 후 재시험
        69점 이하: 배포 보류
        ```
        
    - 현재 프로젝트에서는 특히 다음 구조가 좋습니다.
        
        <aside>
        💡
        
        Summarizer / Improver
           └─ OpenAI 또는 Anthropic
        
        Evaluator / Critic
           └─ 내부 품질 점검
        
        quality_diagnosis/test_llm_judge.py
           └─ 다른 모델 또는 별도 프롬프트로 최종 산출물 채점
           
        가장 중요한 원칙은 
        답변을 만든 모델과 채점 모델을 가능하면 다르게 두는 것입니다.   
        
        </aside>
        
        예:
        
        ```
        요약·정책 생성: OpenAI
        최종 LLM Judge: Anthropic
        ```
        
        또는
        
        ```
        요약·정책 생성: Anthropic
        최종 LLM Judge: OpenAI
        ```
        
        - 이렇게 해야 같은 모델의 편향이나 자기평가 관대성을 줄일 수 있습니다.
    
    #### 2. 현재 단계의 최종 품질 판정은 정확히 말하면 다음과 같음.
    
    ```
    자동화 기능·통합 테스트: 22건 통과
    LLM Judge 기반 내용 품질 평가: 미수행
    현재 판정: 기술적 파일럿 배포 가능
    정식 품질 승인: LLM Judge 및 사람 검토 추가 필요
    ```
    
    - 그래서 `test_llm_judge.py`,  판정 프롬프트, CSV 결과 보고서까지 포함해 실제 실행 가능한 LLM Judge QA를 추가하는 것입니다.
    
    #### 3. LLM Judge QA 파일 구을 위하여 추가되는 구조(실제)
    
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
    
    실행 화면(예시)
    
    # 1. 가상환경 활성화
    
    .\.venv\Scripts\Activate.ps1
    
    # 2. LLM Judge Agent 단위 테스트
    
    pytest quality_diagnosis/test_llm_judge.py -v
    
    # 3. LLM Judge Agent 직접 실행
    
    python quality_diagnosis/llm_judge.py
    
    # 4. 생성된 LLM Judge 결과 확인
    
    Get-Content quality_diagnosis\reports\llm_judge_result.csv
    
    ### Markdown 보고서도 함께 확인하려면: 
    Get-Contentquality_diagnosis\reports\quality_score_report.md
    
    # 5.최종 배포 판정 결과는 다음 명령으로 봅니다.
    
    Get-Content quality_diagnosis\reports\deployment_decision.md
    
    # 6. 전체 품질진단과 LLM Judge까지 한 번에 다시 검증하려면 다음 명령을 마지막에 실행하면 됩니다.
    
    pytest quality_diagnosis -v
    
    [추천 실행 순서]
    
    .\.venv\Scripts\Activate.ps1
    pytest quality_diagnosis/test_llm_judge.py -v
    python quality_diagnosis/llm_judge.py
    Get-Content quality_diagnosis\reports\llm_judge_result.csv
    Get-Content quality_diagnosis\reports\deployment_decision.md
    
    ![image.png](image%202.png)
    
    [보완 해야할 사항]
    
    지금 화면은 **질문 자체는 처리되어 답변이 나온 상태**입니다. 다만 중요한 점이 있습니다.
    
    화면에 다음 내용이 보입니다.
    
    > **파이프라인 자체는 Summarizer 단계에서 타임아웃이 났습니다.**
    > 
    
    즉,
    
    - `health_check` 실행: 정상
    - `analyze_voc_nl_v2` 실행: 요청은 전달됨
    - `Interpreter → Retriever` 단계: 진행된 것으로 보임
    - `Summarizer` 단계: 응답 시간이 길어져 타임아웃 발생
    - vscode가 `voc.csv`를 직접 읽고, 대신 분석 결과와 정책 제안을 작성함
    
    따라서 오른쪽에 보이는 분석 문장은 나왔지만, **6개 에이전트가 끝까지 연결되어 만든 최종 결과는 아닙니다.**
    
    현재는 vscode가 CSV 내용을 직접 보고 보완 답변을 만든 상태입니다.
    
    다음으로 확인할 곳은 `agents/summarizer.py`입니다. 특히 아래 부분을 찾아보세요.
    
    ```
    awaitstub.RunPipeline(...)
    ```
    
    또는 OpenAI 호출 부분의 `timeout` 설정입니다.
    
    현재 화면의 “Summarizer 단계에서 타임아웃”은 보통 다음 중 하나입니다.
    
    1. Summarizer가 OpenAI 응답을 오래 기다림
    2. Summarizer가 Evaluator 서버로 넘기는 과정에서 멈춤
    3. Summarizer 내부에서 Retriever 결과 처리 중 오류 또는 대기 발생
    4. MCP 도구의 전체 실행 제한 시간이 짧음
    
    우선 각 서버 터미널 중 **Summarizer 창**을 확인하세요. 오류 메시지, `timeout`, `OpenAI`, `Evaluator` 관련 문구가 있는지 보시면 원인을 바로 좁힐 수 있습니다.
    
    현재는 서버 연결 자체는 상당 부분 정상입니다. 다음 핵심 작업은 **Summarizer 타임아웃 원인 확인 및 제한 시간 조정**입니다.
    
    - 현재 VS Code + MCP 등록 방식에서 이해할 것은?
        
        ### 1. `python grpc_server.py`
        
        이 명령은 **전체 gRPC 파이프라인을 직접 시험하거나, gRPC 호출용 서버/클라이언트를 별도로 실행할 때** 사용합니다.
        
        다만 지금처럼 실행 후 바로 PowerShell 프롬프트가 다시 나타난다면, 현재 `grpc_server.py`는 계속 켜 두는 서버가 아니라 **간단한 실행·점검용 파일**일 가능성이 큽니다.
        
        따라서 평소 Cursor에서 VOC 분석을 할 때는 보통 실행하지 않습니다.
        
        사용 시점:
        
        ```
        # 6개 에이전트 서버가 모두 켜진 뒤
        python grpc_server.py
        ```
        
        주로 gRPC 연결이 되는지 확인하거나, 별도 테스트 코드를 실행할 때 사용합니다.
        
        ### 2. `python main.py`
        
        `main.py`는 MCP 서버 역할입니다.
        
        현재는 VS Code에 MCP로 이미 등록되어 있으므로, **터미널에서 직접 실행하지 않습니다.**
        
        VS Code가 필요할 때 자동으로 `main.py`를 실행하고 Cursor Chat과 연결합니다.
        
        즉, 현재 방식에서는 아래 명령을 하지 않습니다.
        
        ```
        python main.py
        ```
        
        직접 실행하면 화면이 멈춘 것처럼 보일 수 있는데, MCP 서버가 Cursor의 연결 요청을 기다리기 때문입니다.
        
        ### 현재 프로젝트의 권장 실행 순서
        
        ### ① 처음 한 번: 6개 에이전트 서버 실행
        
        각각 별도 터미널에서 실행합니다.
        
        ```
        python -m agents.interpreter
        ```
        
        ```
        python -m agents.retriever
        ```
        
        ```
        python -m agents.summarizer
        ```
        
        ```
        python -m agents.evaluator
        ```
        
        ```
        python -m agents.critic
        ```
        
        ```
        python -m agents.improver
        ```
        
        ### ② VS Code Cursor Chat에서 질문
        
        오른쪽 Chat 창에 입력합니다.
        
        ```
        결제 관련 VOC를 분석하고, 주요 불만 요약과 정책 개선안을 제안해 주세요.
        ```
        
        도구 사용 권한이 나오면 `Allow in this session`을 누릅니다.
        
        ---
        
        ### 한 줄 결론
        
        - `grpc_server.py` → gRPC 연결·파이프라인을 직접 점검할 때만 실행
        - `main.py` → MCP를 VS Code에 등록했다면 직접 실행하지 않음
        - 실제 사용 → 6개 에이전트 서버를 켜고, vscode Chat에서 질문 입력
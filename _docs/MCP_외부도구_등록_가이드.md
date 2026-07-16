# VOC MCP 외부 도구 등록 가이드

## 1. 목적과 공통 구조

이 문서는 `D:\voc`의 VOC 분석 MCP 서버를 다음 외부 채팅 도구에서 사용하는 방법을
정리한다.

- Visual Studio Code 채팅
- Google Antigravity IDE
- Claude Desktop

세 도구는 모두 동일한 로컬 MCP 서버를 실행한다.

```text
외부 채팅 도구
  → D:\voc\.venv\Scripts\python.exe D:\voc\main.py
  → MCP 도구
  → gRPC 에이전트 6개
  → VOC 요약과 정책 개선안 반환
```

`main.py`는 표준 입출력(`stdio`) 방식의 MCP 서버다. 외부 도구가 필요할 때 자동으로
실행하므로 사용자가 별도 터미널에서 `main.py`를 실행하지 않는다.

## 2. 공통 준비

### 필수 파일

```text
D:\voc\.venv\Scripts\python.exe
D:\voc\main.py
D:\voc\.env
D:\voc\voc.csv
```

### 사용 순서

1. `RUN\VOC_QA_Launcher.bat`로 GUI를 실행한다.
2. GUI에서 `전체 시작`을 누른다.
3. 포트 6001~6006이 모두 초록색인지 확인한다.
4. 외부 채팅 도구에서 `vocMcp` 연결을 확인한다.
5. 자연어로 VOC 분석을 요청한다.

MCP 클라이언트는 `main.py`만 자동 실행한다. Interpreter부터 Improver까지의 gRPC 서버
6개는 자동으로 시작하지 않으므로 GUI에서 먼저 실행해야 한다.

### API 키

OpenAI와 Anthropic API 키는 `D:\voc\.env`에서 프로젝트가 직접 읽는다. MCP 설정 JSON에
API 키를 복사하지 않는다.

## 3. Visual Studio Code 등록

VS Code는 프로젝트의 `.vscode\mcp.json`을 사용한다. 현재 프로젝트에는 이미 다음 설정이
들어 있다.

파일: `D:\voc\.vscode\mcp.json`

```json
{
  "servers": {
    "vocMcp": {
      "type": "stdio",
      "command": "d:\\voc\\.venv\\Scripts\\python.exe",
      "args": [
        "d:\\voc\\main.py"
      ],
      "cwd": "d:\\voc"
    }
  }
}
```

### 연결 방법

1. VS Code에서 `D:\voc` 폴더를 연다.
2. `Ctrl+Shift+P`를 누른다.
3. `MCP: List Servers`를 실행한다.
4. `vocMcp`를 선택하고 시작한다.
5. 처음 실행할 때 신뢰 확인 창이 나오면 경로와 명령을 확인한 후 승인한다.
6. 채팅의 도구 목록에서 VOC 도구가 표시되는지 확인한다.

VS Code 공식 문서에 따르면 프로젝트별 MCP 설정은 `.vscode/mcp.json`에 저장하고, 로컬
서버는 `stdio`, `command`, `args`, 선택적인 `cwd`를 사용한다.

- 공식 문서: https://code.visualstudio.com/docs/agent-customization/mcp-servers
- 설정 명세: https://code.visualstudio.com/docs/agents/reference/mcp-configuration

## 4. Google Antigravity IDE 등록

Antigravity IDE는 프로젝트별 설정 파일 `.agents\mcp_config.json`을 사용한다.

파일: `D:\voc\.agents\mcp_config.json`

```json
{
  "mcpServers": {
    "vocMcp": {
      "command": "D:\\voc\\.venv\\Scripts\\python.exe",
      "args": [
        "D:\\voc\\main.py"
      ]
    }
  }
}
```

### 연결 방법

1. Antigravity IDE에서 `D:\voc` 프로젝트를 연다.
2. Agent 패널 상단의 `...` 메뉴를 누른다.
3. `MCP Servers`를 선택한다.
4. `Manage MCP Servers`를 선택한다.
5. `View raw config`에서 프로젝트의 `.agents\mcp_config.json`을 확인한다.
6. `vocMcp`를 새로고침하거나 활성화한다.
7. Agent 채팅에서 VOC 도구 목록을 확인한다.

Antigravity 공식 문서에 따르면 IDE의 프로젝트별 MCP 설정 위치는
`.agents/mcp_config.json`이며, 설정의 최상위 키는 `mcpServers`다.

- 공식 문서: https://antigravity.google/docs/mcp

## 5. Claude Desktop 등록

Claude Desktop의 로컬 MCP 설정은 프로젝트 폴더가 아니라 사용자 설정 폴더에 저장한다.

Windows 설정 파일:

```text
%APPDATA%\Claude\claude_desktop_config.json
```

설정 내용:

```json
{
  "mcpServers": {
    "vocMcp": {
      "command": "D:\\voc\\.venv\\Scripts\\python.exe",
      "args": [
        "D:\\voc\\main.py"
      ]
    }
  }
}
```

기존에 다른 MCP 서버가 등록되어 있다면 파일 전체를 덮어쓰지 말고 기존 `mcpServers`
객체 안에 `vocMcp` 항목만 추가한다.

### 연결 방법

1. Claude Desktop 설정을 연다.
2. `Developer`에서 `Edit Config`를 선택한다.
3. 위 `vocMcp` 설정을 추가하고 저장한다.
4. Claude Desktop을 완전히 종료한 후 다시 실행한다.
5. 채팅 입력창의 도구·커넥터 메뉴에서 `vocMcp`를 확인한다.

MCP 공식 문서에 따르면 Windows의 Claude Desktop 설정은
`%APPDATA%\Claude\claude_desktop_config.json`이며, 설정을 변경한 후 앱을 완전히 다시
시작해야 한다.

- 공식 문서: https://modelcontextprotocol.io/docs/develop/connect-local-servers
- Anthropic 안내: https://support.anthropic.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop

## 6. 등록 후 확인할 MCP 도구

연결이 성공하면 외부 도구에서 다음 기능을 사용할 수 있어야 한다.

| 도구 | 역할 |
| :--- | :--- |
| `analyze_voc_nl_v2` | 자연어 질문으로 전체 VOC 분석 |
| `analyze_voc` | 필터와 작업을 직접 지정하여 분석 |
| `health_check` | 기본 VOC CSV 상태 확인 |
| `summarize_voc` | VOC 요약만 생성 |
| `policy_from_summary` | 기존 요약으로 정책 개선안 생성 |

## 7. 공통 확인 질문

### 연결 상태 확인

```text
VOC MCP의 health_check 도구를 실행해서 데이터 파일 상태를 알려주세요.
```

### 실제 분석

```text
VOC MCP 도구를 사용해서 상담 대기 시간이 길다는 고객 불만을 분석하고
요약과 정책 개선안을 작성해 주세요.
```

### 외부 챗봇 후속 질문

```text
방금 개선안 중 발표에서 강조할 우선순위 3개만 정리해 주세요.
```

첫 번째 분석은 MCP의 6개 에이전트가 수행한다. 이후 결과 요약이나 표현 변경은 외부
챗봇이 대화 문맥을 이용해 직접 처리할 수 있다.

## 8. 문제 해결

### MCP 서버는 보이지만 분석이 실패함

- GUI에서 에이전트 6개가 모두 초록색인지 확인한다.
- 6001~6006 포트가 열렸는지 확인한다.
- `python -m utils.preflight`로 파일·패키지·API 키 상태를 확인한다.

### MCP 서버 자체가 보이지 않음

- Python과 `main.py` 경로가 절대 경로인지 확인한다.
- JSON의 Windows 경로가 `\\`로 이스케이프되었는지 확인한다.
- 외부 도구를 완전히 종료하고 다시 실행한다.
- VS Code에서는 `MCP: List Servers`의 출력 로그를 확인한다.
- Antigravity에서는 MCP Servers 화면에서 새로고침한다.
- Claude Desktop에서는 `%APPDATA%\Claude\logs`를 확인한다.

### 도구는 호출됐지만 결과가 좋지 않음

- 질문의 키워드가 `voc.csv` 데이터와 관련 있는지 확인한다.
- 현재 CSV는 보험·상담·앱·청구 관련 VOC 중심이다.
- 주문·쿠폰·배송처럼 CSV에 근거가 없는 질문은 관련 데이터 없음으로 처리될 수 있다.
- API 키 유효성, 모델 접근 권한 및 크레딧을 확인한다.

현재 Anthropic 정책 생성과 LLM Judge의 기본 모델은 `claude-sonnet-5`로 설정되어 있다.

## 9. 역할 정리

```text
GUI
→ 에이전트 시작·종료, 테스트, LLM Judge, 보고서 관리

VS Code / Antigravity / Claude Desktop
→ 일반 대화, VOC MCP 호출, 결과 설명과 후속 질문

main.py
→ 외부 채팅 도구와 VOC 분석 파이프라인을 연결하는 stdio MCP 진입점
```

이 구성에서는 자체 범용 챗봇을 만들지 않고 외부 도구의 대화 능력을 활용한다. 프로젝트는
VOC 분석과 QA 기능에 집중한다.

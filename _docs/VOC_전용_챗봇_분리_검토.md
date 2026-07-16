# VOC 전용 챗봇 분리 검토

## 1. 배경

현재 구조는 `_docs/MCP_외부도구_등록_가이드.md`에 정리된 대로, VS Code·Antigravity·
Claude Desktop 같은 **외부 채팅 도구의 대화 능력을 그대로 빌려 쓰고**, VOC 프로젝트는
MCP 도구(`analyze_voc_nl_v2` 등)로만 참여한다. 즉 현재는 자체 범용 챗봇을 만들지 않는
구성이다.

이 문서는 "MCP 없이, VOC 데이터만 갖고 답하는 독립 챗봇을 별도로 뺄 수 있는가"를
검토한 내용을 정리한다. 코드 변경은 없으며, 이미 있는 코드를 근거로 가능 여부와
방식만 확인했다.

## 2. 결론

**가능하다.** MCP는 껍데기(transport 계층)일 뿐이고, 실제 분석 로직은 MCP와 완전히
독립적으로 호출할 수 있게 이미 짜여 있다.

```text
main.py (MCP stdio 진입점)
  → utils/tools.py: analyze_voc_nl_v2(question)
      → get_runtime().run_with_question(question, csv_path)   ← 이 한 줄이 진짜 작업
```

`analyze_voc_nl_v2`는 `@mcp.tool` 데코레이터만 걷어내면 그대로 함수로 재사용 가능한
얇은 래퍼다([utils/tools.py:136-170](../utils/tools.py#L136-L170)). `run_with_question`은
`grpc_server.py`의 `A2AGRPCRuntime` 메서드이고, IDE·Claude Desktop 같은 MCP 클라이언트
존재 여부와 무관하게 호출된다([grpc_server.py:115-213](../grpc_server.py#L115-L213)).

## 3. 구현 방향 두 가지

### 방향 A. 완전 독립 챗봇 (권장)

Streamlit/Flask 등으로 간단한 채팅 웹 UI를 만들고, `grpc_server`를 직접 import해서
`run_with_question()`을 호출한다.

- MCP·IDE·외부 채팅 도구 전혀 불필요, 브라우저만 열면 사용 가능
- 지금 있는 `server_gui.py`(에이전트 서버 관리 GUI) 옆에 별도 앱으로 추가하는 형태가
  자연스럽다
- 사용자 질문 → `run_with_question()` → 결과(`summary`, `policy`, `trace`)를 채팅
  말풍선으로 표시

### 방향 B. MCP 유지 + 원격 접근

`main.py`의 `mcp.run(transport="stdio")`를 `"sse"`나 `"streamable-http"`로 바꾸면
로컬 IDE가 아닌 다른 MCP 호환 클라이언트에서도 접속할 수 있다. 다만 이 경우도 여전히
"MCP 호환 클라이언트"가 있어야 하므로, 순수하게 "VOC만 쓰는 챗봇"을 원한다면 방향 A가
더 적합하다.

## 4. "VOC를 벗어난 답을 하지 않는가" — 그라운딩 구조 확인

방향 A로 만들더라도 `run_with_question()`을 그대로 통과시키기만 하면, 지금 파이프라인에
이미 있는 두 겹의 안전장치가 그대로 적용된다.

### 4-1. 완전히 무관한 질문 → 하드 차단 (LLM을 아예 호출하지 않음)

[agents/summarizer.py:260-268](../agents/summarizer.py#L260-L268)에서 Retriever가
`voc.csv`에서 0건을 찾으면(`if not texts:`) 요약/정책 생성 LLM을 호출하지 않고 즉시
`{"summary": "", "ok": False}`를 반환한다.

```python
if not texts:
    ...
    return {
        "summary": "",
        "trace": "; ".join(trace),
        "ok": False,
    }
```

`voc.csv`와 겹치는 단어가 하나도 없는 질문(예: QA 테스트케이스 TC-17 "게임 아이템
환불", TC-18 "반려 로봇 예약")은 모델이 지어내서 답하는 게 아니라 구조적으로
"결과 없음"이 된다.

### 4-2. 일부라도 관련 있는 질문 → 프롬프트 수준의 그라운딩

Retriever가 몇 건이라도 찾으면 그 원문(`texts`)만 요약 생성·정제 프롬프트에 실려가고,
"데이터에 없는 사실 금지" 지시가 들어간다(`agents/summarizer.py`의 `make_candidates`,
`refine`). Critic도 원본 데이터를 별도로 받아 요약이 원문과 다른 내용을 지어냈는지
검증한다(`SOURCE_DATA_MARKER` 기반, `agents/critic.py`).

### 4-3. 한계 — 알아두어야 할 두 가지

- **완전 차단이 아니라 "앵커 단어 없음 → 차단"이다.** 질문에 `voc.csv`와 우연히 겹치는
  흔한 단어(예: "보험료")가 있으면 Retriever가 몇 건을 찾아버릴 수 있고, 그러면 그
  몇 건을 근거로 답이 생성된다 — 완전히 무관한 주제인데도 억지로 답이 나올 여지가
  있다.
- **이 안전장치는 `run_with_question()` 파이프라인을 거칠 때만 적용된다.** 챗봇 구현
  시 사용자 입력을 예외 없이 이 함수로 통과시켜야 한다. 만약 편의상 "그냥 GPT/Claude에
  직접 물어보고 답하게" 하는 우회 경로를 하나라도 만들면 이 그라운딩은 전부
  무력화된다.

## 5. 다음 단계 (실행 보류, 결정 필요)

아래는 실제로 만들기로 할 경우의 착수 항목이며, 현재는 검토 단계로 코드 작업은 하지
않았다.

1. UI 형태 결정: 터미널 CLI 챗봇 / 로컬 웹페이지 / `server_gui.py`에 채팅 탭 추가
2. 무관 질문(`ok=False`) 응답을 사용자에게 어떤 문구로 보여줄지 결정
   (`quality_diagnosis/test_cases.json`의 `expect_no_data` 케이스가 기대하는 문구
   "관련 데이터 없음"과 통일하는 것을 권장)
3. 대화 이력(멀티턴) 지원 여부 — 현재 `run_with_question`은 단발 질문 단위로 동작하므로
   "방금 답 중에서 우선순위 3개만 정리해줘" 같은 후속 질문을 받으려면 별도의 대화
   컨텍스트 관리가 필요

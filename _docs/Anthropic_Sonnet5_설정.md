# Anthropic Sonnet 5 설정 기록

## 변경 목적

기존 기본값 `claude-5-sonnet-latest`는 Anthropic API에서 존재하지 않는 모델명으로 404를
반환했다. 실제 모델 목록에서 확인된 `claude-sonnet-5`로 정책 생성과 LLM Judge 설정을
통일했다.

## 변경 항목

- `.env`: `A2A_MODEL_POLICY=claude-sonnet-5`
- `.env`: `JUDGE_MODEL=claude-sonnet-5`
- `utils/settings.py`: 정책 모델 기본값
- `llm_wrappers/anthropic_chat.py`: Anthropic 래퍼 기본값
- `quality_diagnosis/llm_judge.py`: Anthropic Judge 기본값
- `.env.example`: 설정 예시
- MCP 외부 도구 등록 가이드: 현재 모델 안내

API 키 값은 변경하거나 문서에 기록하지 않았다.

## 검증 결과

```text
MODEL_POLICY: claude-sonnet-5
JUDGE_MODEL: claude-sonnet-5
Python 강제 컴파일: 성공
관련 단위 테스트: 17 passed
Anthropic 실제 최소 호출: SUCCESS / OK
```

## 2026-07-15 문서 최신화

`quality_diagnosis/README_LLM_JUDGE.md`에 남아 있던 예전 모델 안내를 현재 코드와 `.env`
설정에 맞춰 갱신했다.

- Summarizer: `OPENAI_MODEL=gpt-5.4-mini`
- Improver: `A2A_MODEL_POLICY=claude-sonnet-5`
- LLM Judge: `JUDGE_MODEL=claude-sonnet-5`
- `JUDGE_PROVIDER` 미지정 시 Anthropic 우선

이번 작업은 안내 문서만 갱신했으며 모델 설정과 실행 코드는 변경하지 않았다.

> `_docs/example_Don't touch` 폴더는 수정하지 않았다.

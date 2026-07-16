# API 재시도 및 N/A 채점 개선 기록

## 개선 목적

팀별 결과를 비교할 때 API 장애를 결과 품질 0점으로 계산하지 않도록 개선했다.
OpenAI 또는 Anthropic 호출이 실패하면 정해진 범위에서 재시도하고, 두 제공자 모두 사용할 수
없는 경우 해당 케이스를 `N/A`로 기록한다.

> `_docs/example_Don't touch` 폴더는 이번 작업에서 열거나 수정하지 않았다.

## 동작 규칙

1. HTTP 429, 5xx, 타임아웃 및 연결 오류는 제공자별 최대 3회 시도한다.
2. 인증 실패, 권한 오류, 잘못된 모델처럼 반복해도 해결되지 않는 오류는 1회 실패 후 다음 제공자로 넘어간다.
3. Anthropic과 OpenAI가 모두 실패하면 점수와 평가 기준을 `N/A`로 기록한다.
4. `N/A` 케이스는 평균 점수 계산에서 제외한다.
5. 정상 평가 건수와 API 실패 미평가 건수를 보고서에 별도로 표시한다.
6. API 재시도까지 실패한 원인과 제공자별 시도 횟수를 CSV와 Markdown 보고서에 남긴다.

## 적용 위치

- `utils/llm_retry.py`: 공통 재시도 및 실패 정보
- `llm_wrappers/openai_chat.py`: OpenAI 최대 3회 시도
- `llm_wrappers/anthropic_chat.py`: Anthropic 최대 3회 시도 후 OpenAI 대체 호출
- `quality_diagnosis/llm_judge.py`: 양쪽 제공자 호출, N/A 처리, 평균 제외, 보고서 기록
- `quality_diagnosis/test_llm_retry.py`: 재시도와 N/A 평균 계산 검증

## 보고서 변경

`llm_judge_result.csv`에 `api_attempts` 열이 추가된다. 품질 점수 보고서와 배포 판정 문서에는
다음 정보가 추가된다.

- 전체 케이스 수
- 정상 평가 수
- API 실패로 미평가된 N/A 수
- API 재시도 실패 내역

예시:

```text
JC-03: 모든 API 재시도 실패: Anthropic 3회 실패(...); OpenAI 3회 실패(...)
```

## 실행 및 검증

```powershell
python -m pytest quality_diagnosis/test_llm_retry.py -v
python -m pytest quality_diagnosis -q
```

### 2026-07-13 검증 결과

```text
Python 강제 컴파일: 성공
재시도 및 Judge 관련 테스트: 17 passed
전체 테스트: 63 passed, 8 skipped
실패 테스트: 0
```

테스트에서는 실제 API를 호출하지 않고 모의 429 오류, 인증 오류 및 양쪽 제공자 실패 결과를
사용했다. 건너뛴 8개는 에이전트 서버 6개가 필요한 통합 테스트다.

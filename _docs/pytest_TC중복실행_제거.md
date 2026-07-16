# pytest 테스트 케이스 중복 실행 제거

## 변경 목적

TC-01~TC-10을 pytest E2E와 LLM Judge에서 각각 실제 API로 실행하던 중복을 제거했다.
테스트 케이스 기반 결과 품질 평가는 LLM Judge가 담당하고, pytest E2E는 파이프라인 연결
상태를 확인하는 스모크 테스트에 집중한다.

## 변경 내용

`quality_diagnosis/test_pipeline_e2e.py`에서 다음 항목을 제거했다.

- `test_cases.json`의 권장 VOC TC-01~TC-10 로딩
- 기대 키워드·필수 출력·금지 출력 검사
- `test_pipeline_nl_question[TC-01]`부터 `[TC-10]`까지의 매개변수 테스트

다음 E2E 스모크 테스트 3개는 유지했다.

- 파라미터 방식 전체 파이프라인 완주
- `task=both` 요약·정책 생성
- 에이전트 연계 trace 생성

TC-19~TC-20에 대응하는 장애 검증은 LLM Judge 자동 채점 대상이 아니므로 pytest 장애
대응 검사에 유지한다.

## 역할 분리

```text
pytest
→ 구조, 단위 기능, MCP, 장애 대응, 대표 E2E 연결 확인

LLM Judge
→ TC-01~TC-18 실제 분석 및 9개 항목 100점 품질평가
```

`_docs/example_Don't touch` 폴더는 수정하지 않았다.

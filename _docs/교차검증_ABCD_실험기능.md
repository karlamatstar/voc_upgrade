# 교차검증 A·B·C·D 실험 기능

- 적용일: 2026-07-16
- 목적: 생성 모델과 독립 평가 모델의 조합을 바꿔 교차 모델 평가와 동일 모델 평가의 차이를 비교

## 실험군

| 실험군 | 생성 모델 | 평가 모델 | 목적 |
|---|---|---|---|
| A | OpenAI | Anthropic | 기본 교차 품질검증 |
| B | Anthropic | OpenAI | 모델 역할 변경 검증 |
| C | OpenAI | OpenAI | OpenAI 동일 모델 평가 비교 |
| D | Anthropic | Anthropic | Anthropic 동일 모델 평가 비교 |

생성 모델은 LLM을 사용하지 않는 Retriever를 제외한 Interpreter, Summarizer,
Evaluator, Critic, Improver에 공통 적용된다. 일반 VOC 실행에서는 기존 혼합 모델
구성을 유지한다.

## 고정 모델 실행 규칙

교차검증은 일반 LLM Judge와 실행 규칙이 다르다.

```text
고정 생성 모델 1회 호출
→ 생성 성공 시 고정 평가 모델 1회 호출
→ 어느 단계든 실패하면 다른 제공자로 대체하지 않음
→ 해당 테스트 케이스 N/A(미평가) 기록
→ 다음 테스트 케이스 계속 진행
```

- `LLM_MAX_ATTEMPTS=1`
- `LLM_ALLOW_FALLBACK=false`
- `JUDGE_LOCK_PROVIDER=1`
- 일반 실행의 3회 재시도와 제공자 대체 규칙은 변경하지 않았다.
- 데이터가 없는 것이 기대 결과인 TC-17·18은 기존처럼 PASS(예외처리)로 구분한다.

## GUI

`RUN/run_gui.py`의 실행 버튼을 두 줄로 구성했다.

- 첫 줄: 전체 pytest, 단위 테스트, 중지, 지우기
- 둘째 줄: A, B, C, D 교차검증 버튼
- 각 버튼은 `실험군 / 생성 모델 / → 평가 모델`의 세 줄로 표시
- 4개 버튼은 고정 너비가 아니라 현재 패널 가로 폭을 동일하게 나눠 사용하므로
  해상도가 달라져도 오른쪽 버튼이 화면 밖으로 밀리지 않게 구성

교차검증 버튼은 GUI에서 실행 중인 기존 에이전트를 종료하고, 선택된 실험군의 고정
모델 설정으로 6개 에이전트를 임시 실행한다. 실험이 끝나면 임시 에이전트를 종료한다.

## 저장 구조

```text
quality_diagnosis/reports/cross_validation/
├─ a/
│  ├─ llm_judge_result.csv
│  ├─ quality_score_report.md
│  └─ logs/
├─ b/
├─ c/
├─ d/
└─ 교차검증_종합비교보고서.md
```

실험군 폴더의 CSV와 Markdown은 해당 실험의 최신 결과로 갱신한다. JSON 실행 로그와
에이전트 로그는 실행 시각별로 누적 보존한다. 종합 비교보고서는 실행된 실험군의 정상
채점 수, N/A 수, 평균 점수, 중앙 수행시간을 함께 비교한다.

종합 비교보고서는 TC-01~20을 다음 수준으로 기록한다.

- 실험군별 처리 건수, 정상 채점, N/A, 예외 PASS, 평균·중앙 점수
- TC-01~20의 질문·유형과 A~D 점수 또는 상태 비교
- 같은 테스트 케이스의 실험군 최고점과 최저점 차이
- 9개 평가 항목별 A~D 평균
- 파이프라인·Judge·전체 시간의 평균, 중앙값, 최단, 최장
- 실험군별 20개 케이스 점수·판정·시간·실제 Judge·API 기록
- 케이스별 전체 채점 근거 또는 API 실패 사유

이미지와 그래프 제작용으로 `교차검증_그래프데이터.csv`도 함께 갱신한다. 이 파일은
실험군×테스트 케이스의 세로형 데이터이며 총점, 9개 항목 점수, 시간, N/A 상태를 담는다.
따라서 실험군 평균 막대그래프, TC별 점수 선그래프, 항목별 레이더 차트, 수행시간 비교,
N/A 비율 그래프의 원본으로 사용할 수 있다.

## 실행 명령

```powershell
python quality_diagnosis/cross_validation.py --experiment A
python quality_diagnosis/cross_validation.py --experiment B
python quality_diagnosis/cross_validation.py --experiment C
python quality_diagnosis/cross_validation.py --experiment D
```

단일 케이스 구조 검증에는 `--case-id TC-01`을 추가할 수 있다.

## 검증 범위

- Python 강제 문법 검사
- 실험군 매핑, a~d 저장 경로, 1회 호출·대체 금지 환경 설정 단위검사
- Judge가 지정된 제공자 하나만 구성하는지 검사
- 생성 실패가 0점이나 PASS가 아닌 N/A로 기록되는지 검사
- Anthropic 크레딧이 소진된 상태이므로 실제 A·B·D API 실행은 수행하지 않음
- 사용자 요청에 따라 이번 작업에서는 외부 LLM API를 호출하지 않음

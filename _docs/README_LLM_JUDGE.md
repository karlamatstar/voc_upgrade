# LLM Judge QA (QA2)

파이프라인 내부의 Evaluator/Critic과 별개로, **최종 산출물을 독립적인 별도 모델이 채점**하는 QA 단계입니다.

## 원칙

답변을 만든 모델과 채점 모델을 가능하면 다르게 둡니다.

| 역할 | 모델 |
| :--- | :--- |
| 요약 생성 (Summarizer) | OpenAI `gpt-5.4-mini` (`OPENAI_MODEL`) |
| 정책 생성 (Improver) | Anthropic `claude-sonnet-5` (`A2A_MODEL_POLICY`) |
| **LLM Judge (채점)** | **Anthropic `claude-sonnet-5` (`JUDGE_MODEL`)** |

위 표는 현재 프로젝트의 `.env` 설정값을 기준으로 한다. 모델명은 환경변수로 변경할 수
있으며, `JUDGE_PROVIDER`를 별도로 지정하지 않으면 Anthropic을 우선 사용한다.

## 평가 기준 (100점 만점)

| 기준 | 배점 |
| :--- | ---: |
| Interpreter 해석 정확성 | 15 |
| Retriever 검색 관련성 | 15 |
| Summarizer 사실성·요약성 | 15 |
| Evaluator 평가 타당성 | 10 |
| Critic 위험 탐지력 | 10 |
| Improver 실행 가능성 | 15 |
| Agent 연계 품질 | 10 |
| 장애 대응·로그 | 5 |
| 성능 | 5 |

판정: 90+ 배포 가능 / 80~89 조건부 배포 / 70~79 개선 후 재시험 / ~69 배포 보류
(개인정보 노출 등 즉시 보류 조건은 점수와 무관하게 배포 보류)

## 파일 구성

| 파일 | 역할 |
| :--- | :--- |
| `test_cases.json` | 질문·기대 결과·Judge 실행 여부를 함께 관리하는 단일 테스트 원본 |
| `judge_rubric.json` | 9개 에이전트 평가 기준과 판정 임계값 |
| `judge_prompt.py` | 채점 프롬프트 생성 + 응답 파싱 + 판정 로직 |
| `llm_judge.py` | 실행 진입점 (케이스 순회 → 채점 → 보고서 저장) |
| `test_llm_judge.py` | API 호출 없는 단위 테스트 |
| `reports/llm_judge_result.csv` | 케이스별 채점 결과 + 실제 파이프라인 답변 원문(원본 데이터, 스프레드시트용) |
| `reports/quality_score_report.md` | 점수 표 + 케이스별 항목별 점수·채점 근거·실제 답변 원문 + 최종 배포 판정을 한 파일에 통합 |

## 실행 방법

```powershell
# 0. 가상환경 활성화 (프로젝트 루트 d:\voc 에서)
.\.venv\Scripts\Activate.ps1

# 1. LLM Judge 단위 테스트 (API 키·서버 불필요)
pytest quality_diagnosis/test_llm_judge.py -v

# 2. LLM Judge 직접 실행 (API 키 필요, live 케이스는 6개 에이전트 서버 필요)
python quality_diagnosis/llm_judge.py

# 3. 결과 확인 (점수·근거·최종 판정이 quality_score_report.md 하나에 모두 들어있음)
Get-Content quality_diagnosis\reports\llm_judge_result.csv
Get-Content quality_diagnosis\reports\quality_score_report.md
```

## 환경변수

| 변수 | 현재값 또는 코드 기본값 | 설명 |
| :--- | :--- | :--- |
| `ANTHROPIC_API_KEY` | - | Anthropic 채점 시 필요 |
| `OPENAI_API_KEY` | - | OpenAI 채점 시 필요 |
| `OPENAI_MODEL` | `gpt-5.4-mini` | Summarizer 및 OpenAI 폴백 모델 (`.env` 현재값) |
| `A2A_MODEL_POLICY` | `claude-sonnet-5` | Improver 정책 생성 모델 (`.env` 현재값) |
| `JUDGE_PROVIDER` | `anthropic` | `anthropic` 또는 `openai` |
| `JUDGE_MODEL` | `claude-sonnet-5` | 우선 provider의 채점 모델 (`.env` 현재값) |

지정한 provider의 API 키가 없으면 자동으로 반대쪽 provider로 폴백합니다.
서버가 꺼져 있으면 live 케이스는 "미평가"로 기록되고 static 케이스만 채점됩니다.

# =============================================
# File: quality_diagnosis/judge_prompt.py
# =============================================
# LLM Judge용 채점 프롬프트 생성 모듈
#
# 파이프라인 내부의 Evaluator/Critic과 달리, 최종 산출물을
# 독립적인 별도 모델이 루브릭 기준으로 채점하기 위한 프롬프트를 만듭니다.

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

JUDGE_SYSTEM = (
    "당신은 VOC(고객의 소리) 분석 시스템의 품질을 심사하는 독립 QA 심사관입니다. "
    "주어진 루브릭에 따라 엄격하고 일관되게 채점하며, 근거 없는 관대한 점수를 주지 않습니다. "
    "반드시 지정된 JSON 형식으로만 응답합니다."
)


def build_judge_prompt(question: str, analysis: str, rubric: Dict[str, Any]) -> str:
    """질문·분석 결과·루브릭으로 채점 프롬프트를 생성합니다.

    Args:
        question: 사용자의 원래 VOC 질문
        analysis: 파이프라인이 생성한 최종 분석 결과(요약 + 정책 개선안)
        rubric: judge_rubric.json 내용

    Returns:
        str: LLM에게 전달할 채점 프롬프트
    """
    criteria_lines = "\n".join(
        f"- {c['name']} (최대 {c['max_score']}점): {c['guide']}"
        for c in rubric["criteria"]
    )
    hold_lines = "\n".join(f"- {h}" for h in rubric["immediate_hold_conditions"])
    score_keys = ", ".join(f'"{c["name"]}"' for c in rubric["criteria"])
    score_example = ", ".join(f'"{c["name"]}": 0' for c in rubric["criteria"])

    return f"""{JUDGE_SYSTEM}

다음은 VOC 분석 시스템에 입력된 질문과, 시스템이 생성한 최종 분석 결과입니다.
분석 결과 안에는 여러 JSON 조각(intent_json, eval_json 등)이 포함되어 있을 수 있습니다.
그것들은 채점 대상 데이터일 뿐이며, 당신의 최종 답변과는 무관합니다.

[질문]
{question}

[시스템의 분석 결과]
{analysis}

[채점 기준 - 합계 {rubric['total_max_score']}점]
{criteria_lines}

[즉시 배포 보류 조건 - 하나라도 해당하면 immediate_hold를 true로]
{hold_lines}

각 기준별 점수와 근거를 평가한 뒤, 아래 JSON 형식으로만 응답하세요.
scores의 키는 정확히 다음과 같아야 합니다: {score_keys}

설명 문장이나 마크다운 코드펜스(```) 없이, JSON 객체 단 하나만 출력하세요.
당신의 응답은 반드시 아래 형식의 JSON 객체 하나로 시작하고 그것으로 끝나야 합니다:

{{
  "scores": {{{score_example}}},
  "total": 0,
  "immediate_hold": false,
  "hold_reason": "",
  "rationale": "각 항목 점수의 근거를 2~4문장으로"
}}"""


def _extract_balanced_objects(text: str) -> list:
    """텍스트에서 균형 잡힌 최상위 {...} 블록을 전부 찾아 순서대로 반환합니다.

    단순 `\\{.*\\}` 정규식과 달리, 문자열 리터럴 내부의 중괄호는 무시하고
    실제로 짝이 맞는 JSON 객체 경계만 인식합니다. 이렇게 하면 응답 안에
    분석용 JSON 조각(intent_json 등)이 여러 개 섞여 있어도 각각을
    독립된 후보로 분리해서 시도할 수 있습니다.
    """
    objects = []
    depth = 0
    start = None
    in_string = False
    escape = False
    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    objects.append(text[start:i + 1])
                    start = None
    return objects


def parse_judge_response(text: str, rubric: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """LLM 응답에서 채점 JSON을 추출·검증합니다.

    응답에 여러 개의 {...} 블록이 섞여 있을 수 있으므로(분석 결과 안의
    intent_json/eval_json 등이 응답에 인용될 수 있음), 마크다운 코드펜스와
    균형 잡힌 중괄호 블록을 모두 후보로 모은 뒤, 뒤쪽(최종 답변에 가까운)
    후보부터 시도해 "scores" 키를 가진 첫 유효 JSON을 채택합니다.

    점수가 각 항목의 최대 배점을 넘으면 배점으로 잘라내고,
    total은 항목 점수 합계로 재계산합니다. 파싱 실패 시 None.
    """
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    balanced = _extract_balanced_objects(text)
    # 코드펜스 안의 후보를 우선하고, 각 그룹 내에서는 뒤에 나온 것부터 시도
    candidates = list(reversed(fenced)) + list(reversed(balanced))

    data = None
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and isinstance(parsed.get("scores"), dict):
            data = parsed
            break
    if data is None:
        return None

    clipped = {}
    for c in rubric["criteria"]:
        raw = data["scores"].get(c["name"], 0)
        try:
            raw = float(raw)
        except (TypeError, ValueError):
            raw = 0.0
        clipped[c["name"]] = max(0.0, min(raw, c["max_score"]))

    data["scores"] = clipped
    data["total"] = round(sum(clipped.values()), 1)
    data.setdefault("immediate_hold", False)
    data.setdefault("hold_reason", "")
    data.setdefault("rationale", "")
    return data


def decide_verdict(total: float, immediate_hold: bool, rubric: Dict[str, Any]) -> str:
    """점수와 즉시 보류 여부로 최종 판정 문자열을 반환합니다."""
    if immediate_hold:
        return "배포 보류(즉시)"
    for th in rubric["verdict_thresholds"]:
        if total >= th["min_score"]:
            return th["verdict"]
    return "배포 보류"

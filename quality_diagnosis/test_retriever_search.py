"""Retriever의 단계적 관련성 검색 단위 테스트."""

import asyncio
import csv

from agents.retriever import RetrieverAgent


def _write_csv(tmp_path, rows):
    path = tmp_path / "voc_search_test.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(["고객ID", "불만내용"])
        writer.writerows(rows)
    return str(path)


def _run(csv_path, filters, max_items=30):
    return asyncio.run(RetrieverAgent().run(csv_path, filters, max_items))


def test_specific_terms_prevent_broad_overmatch(tmp_path):
    """고객·개선 같은 범용어로 다른 주제가 끌려오지 않는다."""
    csv_path = _write_csv(tmp_path, [
        ["CUST001", "모바일 앱에서 자동차 보험 갱신 중 오류가 발생했습니다."],
        ["CUST002", "광고와 보장 내용이 달라 고객 불편과 개선이 필요합니다."],
        ["CUST003", "자동차 보험 사고 접수를 문의합니다."],
    ])

    results = _run(
        csv_path,
        ["모바일 앱", "자동차 보험", "갱신 오류", "VOC", "고객 불편", "개선 우선순위"],
    )

    assert len(results) == 1
    assert results[0].startswith("CUST001 ")


def test_synonym_search_runs_only_after_strict_search_is_empty(tmp_path):
    """원문 일치가 없으면 콜센터·지연 동의어를 제한적으로 적용한다."""
    csv_path = _write_csv(tmp_path, [
        ["CUST010", "콜센터 연결 지연으로 오래 기다렸습니다."],
        ["CUST011", "배송 지연이 발생했습니다."],
    ])

    results = _run(csv_path, ["고객센터 대기"])

    assert len(results) == 1
    assert results[0].startswith("CUST010 ")


def test_low_relevance_rows_are_not_restored(tmp_path):
    """각 핵심어 하나만 겹치는 행들은 0건 대신 되살리지 않는다."""
    csv_path = _write_csv(tmp_path, [
        ["CUST020", "팩스 장비가 고장 났습니다."],
        ["CUST021", "이메일 로그인이 안 됩니다."],
        ["CUST022", "청구 기간이 지났습니다."],
    ])

    results = _run(csv_path, ["팩스", "이메일", "청구 서류", "접수"])

    assert results == []


def test_rare_specific_terms_can_match_separate_rows(tmp_path):
    """세부 주제가 나뉘어 있어도 드문 구체어인 경우에만 제한적으로 찾는다."""
    rows = [
        ["CUST030", "약관 내용이 어렵고 면책 조건을 이해하기 힘듭니다."],
        ["CUST031", "보장 범위가 명확하지 않습니다."],
    ]
    rows.extend(
        [[f"CUST{number:03d}", "고객센터 연결을 문의합니다."] for number in range(32, 48)]
    )
    csv_path = _write_csv(tmp_path, rows)

    results = _run(csv_path, ["약관", "보장", "설명"])

    assert {row.split()[0] for row in results} == {"CUST030", "CUST031"}


def test_short_app_term_is_preserved(tmp_path):
    """1글자여도 도메인 핵심어인 '앱'은 검색에 사용한다."""
    csv_path = _write_csv(tmp_path, [
        ["CUST040", "앱이 실행되지 않습니다."],
        ["CUST041", "고객센터 대기가 깁니다."],
    ])

    results = _run(csv_path, ["앱"])

    assert len(results) == 1
    assert results[0].startswith("CUST040 ")


def test_ambiguous_service_question_uses_service_as_minimum_anchor(tmp_path):
    """TC-14처럼 구체어가 없는 질문은 서비스 VOC를 근거 후보로 반환한다."""
    csv_path = _write_csv(tmp_path, [
        ["CUST042", "긴급 견인 서비스가 너무 늦습니다."],
        ["CUST043", "온라인 상담 서비스 응답이 없습니다."],
        ["CUST044", "보험금 지급이 지연됐습니다."],
    ])

    results = _run(csv_path, ["서비스 불만", "서비스가", "별로예요"])

    assert len(results) == 2
    assert {row.split()[0] for row in results} == {"CUST042", "CUST043"}


def test_missing_topic_terms_block_rare_word_fallback(tmp_path):
    """주제어가 없는 질문은 공통된 드문 단어만으로 다른 VOC를 가져오지 않는다."""
    rows = [
        ["CUST050", "보험료 환불 절차를 문의합니다."],
        ["CUST051", "고객센터 연결을 문의합니다."],
    ]
    rows.extend(
        [[f"CUST{number:03d}", "보험 상담 내용입니다."] for number in range(52, 68)]
    )
    csv_path = _write_csv(tmp_path, rows)

    results = _run(csv_path, ["게임", "아이템", "환불"])

    assert results == []


def test_filtered_results_are_limited_to_ten(tmp_path):
    """관련 행이 많아도 파이프라인에는 상위 10건만 전달한다."""
    csv_path = _write_csv(
        tmp_path,
        [[f"CUST{number:03d}", f"모바일 앱 오류 사례 {number}"] for number in range(20)],
    )

    results = _run(csv_path, ["모바일 앱"], max_items=50)

    assert len(results) == 10

"""수강 과제·발표 사전 점검 도구의 단위 테스트."""

from utils import preflight


def test_collect_checks_does_not_expose_api_key(monkeypatch):
    secret = "sk-test-never-print-this"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    monkeypatch.setattr(preflight, "_port_open", lambda _port: False)

    report = preflight.format_report(preflight.collect_checks())

    assert "OPENAI_API_KEY" in report
    assert "설정됨" in report
    assert secret not in report


def test_agent_ports_are_informational(monkeypatch):
    monkeypatch.setattr(preflight, "_port_open", lambda _port: False)

    checks = preflight.collect_checks()
    agent_checks = [check for check in checks if check.category == "에이전트"]

    assert len(agent_checks) == 6
    assert all(not check.required for check in agent_checks)
    assert all(not check.ok for check in agent_checks)


def test_report_marks_required_failure():
    checks = [preflight.Check("파일", "voc.csv", False, True, "없음")]
    report = preflight.format_report(checks)

    assert "[실패]" in report
    assert "기본 실행 준비: 미완료" in report

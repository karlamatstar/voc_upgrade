# =============================================
# File: RUN/run_gui.py
# =============================================
# VOC Improve QA 런처 GUI
#
# 한 화면에서:
#   - 왼쪽: 실행(테스트) 터미널 로그 + 테스트 시작 버튼
#   - 오른쪽: 6개 에이전트 서버 로그 패널 (개별/전체 시작·종료)
#
# 실행:
#   d:\voc\.venv\Scripts\python.exe RUN\run_gui.py
#   (또는 RUN\VOC_QA_Launcher.bat 더블클릭)
#
# 별도 패키지 불필요 (파이썬 내장 tkinter 사용)

from __future__ import annotations

import os
import queue
import socket
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path

# ============ 경로 설정 ============
ROOT = Path(__file__).resolve().parent.parent          # d:\voc
VENV_PY = ROOT / ".venv" / "Scripts" / "python.exe"
PY = str(VENV_PY if VENV_PY.exists() else sys.executable)
REPORTS = ROOT / "quality_diagnosis" / "reports"

# ============ .env 로딩 ============
# 프로젝트 루트의 .env 파일을 읽어 모든 자식 프로세스(에이전트/pytest/Judge)에 전달
sys.path.insert(0, str(ROOT))
from utils.env_loader import parse_env_file  # noqa: E402

ENV_FILE_VARS = parse_env_file(ROOT / ".env")

# ============ 에이전트 정의 ============
AGENTS = [
    ("자연어 해석기",   "interpreter", 6001),
    ("데이터 검색기",   "retriever",   6002),
    ("불만사항 요약기", "summarizer",  6003),
    ("결과 평가기",     "evaluator",   6004),
    ("결과 비판기",     "critic",      6005),
    ("개선안 생성기",   "improver",    6006),
]

# ============ 색상 테마 (다크) ============
C = {
    "bg":        "#16161e",   # 전체 배경
    "panel":     "#1f1f2e",   # 패널 배경
    "panel_hd":  "#2a2a3d",   # 패널 헤더
    "log_bg":    "#12121a",   # 로그 영역
    "fg":        "#d8d8e8",   # 기본 글자
    "dim":       "#8a8aa0",   # 보조 글자
    "accent":    "#7aa2f7",   # 포인트(파랑)
    "green":     "#9ece6a",
    "red":       "#f7768e",
    "yellow":    "#e0af68",
    "gray":      "#565f89",
    "btn":       "#33334d",
    "btn_hover": "#40405e",
}

LOG_FONT = ("Consolas", 9)
UI_FONT = ("Malgun Gothic", 9)
UI_FONT_B = ("Malgun Gothic", 9, "bold")
TITLE_FONT = ("Malgun Gothic", 11, "bold")


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.4):
            return True
    except OSError:
        return False


def flat_button(parent, text, command, color=None, width=None):
    """다크 테마용 플랫 버튼."""
    btn = tk.Button(
        parent, text=text, command=command,
        bg=C["btn"], fg=color or C["fg"], activebackground=C["btn_hover"],
        activeforeground=color or C["fg"], relief="flat", bd=0,
        font=UI_FONT, cursor="hand2", padx=10, pady=3, width=width,
    )
    btn.bind("<Enter>", lambda e: btn.config(bg=C["btn_hover"]))
    btn.bind("<Leave>", lambda e: btn.config(bg=C["btn"]))
    return btn


class ProcessPanel:
    """서브프로세스 하나 + 로그 텍스트 위젯 한 쌍을 관리하는 공통 클래스."""

    def __init__(self, app: "App", key: str):
        self.app = app
        self.key = key
        self.proc: subprocess.Popen | None = None
        self.text: tk.Text | None = None

    # ---- 프로세스 제어 ----
    def start(self, args: list[str], banner: str):
        if self.running:
            self.log(f"[이미 실행 중]\n", "warn")
            return
        self.log(f"\n{'─' * 46}\n{banner}\n", "sys")
        env = os.environ.copy()
        # .env 파일 값 주입 (시스템 환경변수에 이미 있으면 시스템 값 우선)
        for k, v in ENV_FILE_VARS.items():
            env.setdefault(k, v)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        try:
            self.proc = subprocess.Popen(
                args, cwd=str(ROOT), env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception as e:
            self.log(f"[시작 실패] {e}\n", "err")
            return
        threading.Thread(target=self._reader, args=(self.proc,), daemon=True).start()

    def stop(self):
        if self.proc and self.proc.poll() is None:
            if os.name == "nt" and self.key == "runner":
                subprocess.run(
                    ["taskkill", "/PID", str(self.proc.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    check=False,
                )
            else:
                self.proc.terminate()
            self.log("[종료 요청됨]\n", "warn")

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    # ---- 로그 처리 ----
    def _reader(self, proc: subprocess.Popen):
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace")
            self.app.q.put((self.key, line, "out"))
        code = proc.wait()
        tag = "sys" if code in (0, 1, -15, 15) else "err"
        self.app.q.put((self.key, f"[프로세스 종료 (code={code})]\n", tag))
        self.app.q.put((self.key, None, "done"))  # 종료 알림

    def log(self, msg: str, tag: str = "out"):
        self.app.q.put((self.key, msg, tag))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("VOC Improve — QA 런처")
        self.configure(bg=C["bg"])
        self.geometry("1720x920")
        self.minsize(1280, 720)

        self.q: queue.Queue = queue.Queue()
        self.panels: dict[str, ProcessPanel] = {}
        self.dots: dict[str, tk.Canvas] = {}
        self.badges: dict[str, tk.Label] = {}
        self.runner_busy = False

        self._build_ui()
        self.after(80, self._drain_queue)
        threading.Thread(target=self._port_watcher, daemon=True).start()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._runner_log(
            "VOC Improve QA 런처입니다.\n"
            f"프로젝트: {ROOT}\n"
            f"Python  : {PY}\n\n"
            "① 오른쪽 [전체 시작]으로 에이전트 6개를 켜고 (초록 ● 확인)\n"
            "② 왼쪽 [전체 테스트]를 누르면 여기로 결과가 출력됩니다.\n"
            "   서버가 꺼져 있으면 E2E 테스트는 SKIP 처리됩니다.\n", "sys",
        )
        self._report_env_status()

    def _report_env_status(self):
        """.env 로딩 상태와 필수 키 존재 여부를 시작 로그에 표시합니다."""
        if ENV_FILE_VARS:
            self._runner_log(f"🔑 .env 로드됨: {', '.join(ENV_FILE_VARS.keys())}\n", "ok")
        else:
            self._runner_log("🔑 .env 파일이 없거나 비어 있습니다 (d:\\voc\\.env)\n", "warn")
        for key, users in [("OPENAI_API_KEY", "Interpreter/Retriever/Summarizer/Evaluator/Critic"),
                           ("ANTHROPIC_API_KEY", "Improver, LLM Judge")]:
            if not (key in ENV_FILE_VARS or os.environ.get(key)):
                self._runner_log(f"   ⚠ {key} 없음 → {users} 사용 불가\n", "warn")

    # =====================================================
    # UI 구성
    # =====================================================
    def _build_ui(self):
        # ---- 상단 툴바 ----
        bar = tk.Frame(self, bg=C["bg"])
        bar.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(bar, text="⬢ VOC Improve QA", bg=C["bg"], fg=C["accent"],
                 font=("Malgun Gothic", 13, "bold")).pack(side="left")
        tk.Label(bar, text="  6-Agent gRPC Pipeline · MCP · pytest · LLM Judge",
                 bg=C["bg"], fg=C["dim"], font=UI_FONT).pack(side="left")
        flat_button(bar, "📂 보고서 폴더", self._open_reports).pack(side="right", padx=3)
        flat_button(bar, "■ 전체 종료", self._stop_all, color=C["red"]).pack(side="right", padx=3)
        flat_button(bar, "▶ 전체 시작", self._start_all, color=C["green"]).pack(side="right", padx=3)

        # ---- 본문: 좌(실행 터미널) / 우(서버 6개) ----
        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=12, pady=(4, 12))
        body.columnconfigure(0, weight=42, uniform="col")
        body.columnconfigure(1, weight=58, uniform="col")
        body.rowconfigure(0, weight=1)

        self._build_runner(body)

        right = tk.Frame(body, bg=C["bg"])
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        for c in range(3):
            right.columnconfigure(c, weight=1, uniform="ag")
        for r in range(2):
            right.rowconfigure(r, weight=1, uniform="ag")
        for i, (name, module, port) in enumerate(AGENTS):
            self._build_agent_panel(right, i // 3, i % 3, name, module, port)

    def _panel_frame(self, parent):
        f = tk.Frame(parent, bg=C["panel"], highlightbackground="#33334d",
                     highlightthickness=1)
        return f

    # ---- 왼쪽: 실행 터미널 ----
    def _build_runner(self, parent):
        f = self._panel_frame(parent)
        f.grid(row=0, column=0, sticky="nsew")

        hd = tk.Frame(f, bg=C["panel_hd"])
        hd.pack(fill="x")
        tk.Label(hd, text="▶ 실행 터미널 (테스트 / LLM Judge)", bg=C["panel_hd"],
                 fg=C["fg"], font=TITLE_FONT, anchor="w").pack(side="left", padx=10, pady=7)

        btns = tk.Frame(f, bg=C["panel"])
        btns.pack(fill="x", padx=8, pady=(8, 2))
        self.btn_all = flat_button(btns, "🧪 전체 테스트(pytest)\n보고서x", lambda: self._run_pytest("quality_diagnosis"),
                                   color=C["green"])
        self.btn_all.pack(side="left", padx=(0, 4))
        self.btn_unit = flat_button(btns, "단위 테스트만\n보고서x",
                                    lambda: self._run_pytest("quality_diagnosis/test_agent_unit.py "
                                                             "quality_diagnosis/test_llm_judge.py"))
        self.btn_unit.pack(side="left", padx=4)
        self.btn_stop = flat_button(btns, "■ 중지", self._stop_runner, color=C["red"])
        self.btn_stop.pack(side="left", padx=4)
        self.btn_stop.configure(state="disabled")
        flat_button(btns, "지우기", lambda: self._clear("runner")).pack(side="right")

        cross = tk.Frame(f, bg=C["panel"])
        cross.pack(fill="x", padx=8, pady=(2, 4))
        cross_specs = [
            ("A", "A 교차검증\n생성 OpenAI\n→ 평가 Anthropic"),
            ("B", "B 교차검증\n생성 Anthropic\n→ 평가 OpenAI"),
            ("C", "C 동일모델 검증\n생성 OpenAI\n→ 평가 OpenAI"),
            ("D", "D 동일모델 검증\n생성 Anthropic\n→ 평가 Anthropic"),
        ]
        self.cross_buttons = []
        for column in range(4):
            cross.columnconfigure(column, weight=1, uniform="cross")
        for column, (experiment, label) in enumerate(cross_specs):
            button = flat_button(
                cross,
                label,
                lambda value=experiment: self._run_cross_validation(value),
                color=C["yellow"],
            )
            button.grid(row=0, column=column, sticky="ew", padx=(0, 4))
            self.cross_buttons.append(button)

        tk.Label(f, text="※ 교차검증은 표시된 생성·평가 모델을 고정하고 1회만 호출합니다. 실패 시 대체 없이 N/A로 기록합니다.",
                 bg=C["panel"], fg=C["dim"], font=UI_FONT, anchor="w").pack(fill="x", padx=12, pady=(0, 6))

        self.panels["runner"] = ProcessPanel(self, "runner")
        self.panels["runner"].text = self._make_log(f)

    # ---- 오른쪽: 에이전트 패널 ----
    def _build_agent_panel(self, parent, row, col, name, module, port):
        key = module
        f = self._panel_frame(parent)
        f.grid(row=row, column=col, sticky="nsew",
               padx=(0 if col == 0 else 8, 0), pady=(0 if row == 0 else 8, 0))

        hd = tk.Frame(f, bg=C["panel_hd"])
        hd.pack(fill="x")

        dot = tk.Canvas(hd, width=12, height=12, bg=C["panel_hd"], highlightthickness=0)
        dot.create_oval(2, 2, 11, 11, fill=C["gray"], outline="", tags="dot")
        dot.pack(side="left", padx=(9, 4), pady=8)
        self.dots[key] = dot

        tk.Label(hd, text=f"{name}", bg=C["panel_hd"], fg=C["fg"],
                 font=UI_FONT_B).pack(side="left")
        badge = tk.Label(hd, text=f":{port}", bg=C["panel_hd"], fg=C["dim"], font=UI_FONT)
        badge.pack(side="left", padx=(4, 0))
        self.badges[key] = badge

        flat_button(hd, "■", lambda k=key: self._stop_agent(k), color=C["red"], width=2).pack(side="right", padx=(2, 8), pady=4)
        flat_button(hd, "▶", lambda k=key: self._start_agent(k), color=C["green"], width=2).pack(side="right", padx=2, pady=4)

        self.panels[key] = ProcessPanel(self, key)
        self.panels[key].text = self._make_log(f, height=8)

    def _make_log(self, parent, height=10) -> tk.Text:
        wrap = tk.Frame(parent, bg=C["panel"])
        wrap.pack(fill="both", expand=True, padx=8, pady=(2, 8))
        text = tk.Text(wrap, bg=C["log_bg"], fg=C["fg"], insertbackground=C["fg"],
                       relief="flat", font=LOG_FONT, height=height, wrap="word",
                       state="disabled", padx=8, pady=6)
        sb = tk.Scrollbar(wrap, command=text.yview, troughcolor=C["panel"],
                          bg=C["btn"], activebackground=C["btn_hover"], width=10)
        text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)
        text.tag_config("sys", foreground=C["accent"])
        text.tag_config("warn", foreground=C["yellow"])
        text.tag_config("err", foreground=C["red"])
        text.tag_config("ok", foreground=C["green"])
        text.tag_config("out", foreground=C["fg"])
        return text

    # =====================================================
    # 동작
    # =====================================================
    def _start_agent(self, key: str):
        self.panels[key].start([PY, "-u", "-m", f"agents.{key}"],
                               f"python -m agents.{key}  ({datetime.now():%H:%M:%S})")

    def _stop_agent(self, key: str):
        self.panels[key].stop()

    def _start_all(self):
        for _, module, _ in AGENTS:
            self._start_agent(module)

    def _stop_all(self):
        for _, module, _ in AGENTS:
            self._stop_agent(module)

    def _run_pytest(self, target: str):
        if self.runner_busy:
            self._runner_log("[이미 실행 중입니다. 완료 후 다시 시도하세요]\n", "warn")
            return
        self.runner_busy = True
        self.btn_stop.configure(state="normal")
        REPORTS.mkdir(exist_ok=True)
        args = [PY, "-u", "-m", "pytest", *target.split(), "-v",
                "--tb=short", "-p", "no:cacheprovider"]
        self.panels["runner"].start(args, f"pytest {target} -v  ({datetime.now():%H:%M:%S})")

    def _run_judge(self):
        if self.runner_busy:
            self._runner_log("[이미 실행 중입니다. 완료 후 다시 시도하세요]\n", "warn")
            return
        self.runner_busy = True
        self.btn_stop.configure(state="normal")
        self.panels["runner"].start([PY, "-u", "quality_diagnosis/llm_judge.py"],
                                    f"python quality_diagnosis/llm_judge.py  ({datetime.now():%H:%M:%S})")

    def _run_cross_validation(self, experiment: str):
        if self.runner_busy:
            self._runner_log("[이미 실행 중입니다. 완료 후 다시 시도하세요]\n", "warn")
            return
        self._stop_all()
        self.runner_busy = True
        self.btn_stop.configure(state="normal")
        output_dir = REPORTS / "cross_validation" / experiment.lower()
        self._runner_log(
            f"[교차검증 {experiment}] 기존 에이전트를 종료하고 고정 모델 서버로 실행합니다.\n"
            f"[결과 폴더] {output_dir}\n",
            "sys",
        )
        self.panels["runner"].start(
            [PY, "-u", "quality_diagnosis/cross_validation.py", "--experiment", experiment],
            f"교차검증 {experiment} 실행  ({datetime.now():%H:%M:%S})",
        )

    def _stop_runner(self):
        self.panels["runner"].stop()

    def _clear(self, key: str):
        text = self.panels[key].text
        text.configure(state="normal")
        text.delete("1.0", "end")
        text.configure(state="disabled")

    def _open_reports(self):
        REPORTS.mkdir(exist_ok=True)
        os.startfile(REPORTS)  # noqa: S606 - 로컬 폴더 열기

    def _runner_log(self, msg: str, tag: str = "out"):
        self.q.put(("runner", msg, tag))

    # =====================================================
    # 큐 → 텍스트 위젯 반영 / 상태 감시
    # =====================================================
    def _drain_queue(self):
        try:
            while True:
                key, msg, tag = self.q.get_nowait()
                if tag == "done":
                    if key == "runner":
                        self.runner_busy = False
                        self.btn_stop.configure(state="disabled")
                        self._print_test_summary()
                    continue
                text = self.panels[key].text
                if text is None:
                    continue
                text.configure(state="normal")
                # pytest 결과 줄 색상 강조
                if key == "runner":
                    if " PASSED" in msg or "passed" in msg:
                        tag = "ok" if tag == "out" else tag
                    elif " FAILED" in msg or " ERROR" in msg or "failed" in msg:
                        tag = "err" if tag == "out" else tag
                    elif " SKIPPED" in msg:
                        tag = "warn" if tag == "out" else tag
                text.insert("end", msg, tag)
                # 로그가 너무 길어지면 앞부분 정리 (5,000줄 유지)
                if float(text.index("end-1c").split(".")[0]) > 5000:
                    text.delete("1.0", "1000.0")
                text.see("end")
                text.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(80, self._drain_queue)

    def _print_test_summary(self):
        text_widget = self.panels.get("runner", ProcessPanel(self, "dummy")).text
        if not text_widget: return
        content = text_widget.get("1.0", "end")
        
        if "test session starts" not in content:
            return
            
        passed, failed, skipped = [], [], []
        
        for line in content.split('\n'):
            if "::test_" in line and ("PASSED" in line or "FAILED" in line or "SKIPPED" in line):
                parts = line.split("::")
                if len(parts) > 1:
                    test_info = parts[1].split()[0]
                    if "PASSED" in line: passed.append(test_info)
                    elif "FAILED" in line: failed.append(test_info)
                    elif "SKIPPED" in line: skipped.append(test_info)
                        
        if not (passed or failed or skipped):
            return
            
        summary = "\n" + "━"*55 + "\n"
        summary += "📊 [테스트 그룹별 결과 요약 (사용자 맞춤형)]\n\n"
        
        def group_tests(tests):
            KOR_MAP = {
                "test_agent_file_exists": "에이전트 파일 존재 확인",
                "test_agent_file_syntax": "에이전트 문법 오류 검사",
                "test_agent_required_symbols": "에이전트 필수 속성 검사",
                "test_agent_has_main_entry": "에이전트 단독 실행 설정 확인",
                "test_agent_ports_are_unique": "에이전트 포트 중복 방지 검사",
                "test_voc_csv_exists_and_has_data": "VOC 데이터(CSV) 파일 확인",
                "test_proto_file_defines_six_services": "gRPC 프로토콜 구조 검사",
                "test_rubric_total_is_100": "채점 기준표(100점 만점) 확인",
                "test_rubric_has_nine_agent_criteria": "에이전트별 채점 기준표(9개 항목) 확인",
                "test_recommended_cases_include_expected_results": "권장 10개 질문·기대 결과 확인",
                "test_judge_cases_loadable": "LLM 심사 시나리오 파일 로딩",
                "test_build_judge_prompt_contains_inputs": "심사위원 프롬프트 생성 검사",
                "test_parse_judge_response_valid": "심사 결과(JSON) 파싱 로직",
                "test_parse_judge_response_clips_overflow": "심사 점수 한도 초과 교정",
                "test_parse_judge_response_invalid_returns_none": "불량 심사 응답 예외 처리",
                "test_decide_verdict": "최종 배포 판정 로직 검사",
                "test_llm_judge_module_importable": "LLM Judge 모듈 로딩 검사",
                "test_health_check_missing_csv": "데이터 누락 시 오류 감지",
                "test_health_check_valid_csv": "정상 데이터 파일 인식",
                "test_extract_keywords_empty_input": "빈 검색어 예외 처리",
                "test_extract_keywords_removes_stopwords": "검색 불용어 필터링 기능",
                "test_parse_filters_handles_none": "필터 예외값 처리",
                "test_analyze_voc_returns_error_dict_when_servers_down": "서버 중단 시 우아한 에러 반환",
                "test_analyze_voc_nl_v2_empty_question_safe": "빈 질문 입력 시 안전 처리",
                "test_pipeline_missing_csv_not_silent_success": "데이터 누락 은폐 방지 테스트",
                "test_analyze_voc_tool_end_to_end": "기본 분석(MCP) 통합 테스트",
                "test_analyze_voc_nl_v2_tool_end_to_end": "자연어 분석(MCP) 통합 테스트",
                "test_pipeline_smoke_with_params": "파이프라인 기본 통신 테스트",
                "test_pipeline_full_task_both": "요약/개선안 생성 파이프라인 실행",
                "test_pipeline_trace_shows_agent_chain": "에이전트 통신 추적 기능",
                "test_pipeline_nl_question": "자연어 기반 전체 파이프라인(E2E) 실행"
            }
            groups = {}
            for t in tests:
                base = t.split("[")[0] if "[" in t else t
                kor_name = KOR_MAP.get(base, base)
                groups[kor_name] = groups.get(kor_name, 0) + 1
            return groups
            
        if passed:
            summary += "🟢 [통과 (문제없이 정상 작동!)]\n"
            for k, v in group_tests(passed).items():
                summary += f"  ✔️ {k} ({v}건)\n"
            summary += "\n"
            
        if skipped:
            summary += "🟡 [스킵 (서버가 켜져있거나 설정때문에 건너뜀. 정상임!)]\n"
            for k, v in group_tests(skipped).items():
                summary += f"  ➖ {k} ({v}건)\n"
            summary += "\n"
            
        if failed:
            summary += "🔴 [실패 (확인 필요 - 위 로그의 세부 에러 참조)]\n"
            for k, v in group_tests(failed).items():
                summary += f"  ❌ {k} ({v}건)\n"
            summary += "\n"
            
        summary += "※ 실패 원인이 동일할 경우(예: 크레딧 부족) 그룹 내의 모든 테스트가 붉게 표시될 수 있습니다.\n"
        summary += "━"*55 + "\n\n"
        
        text_widget.configure(state="normal")
        text_widget.insert("end", summary, "accent")
        text_widget.see("end")
        text_widget.configure(state="disabled")

    def _port_watcher(self):
        import time
        while True:
            for _, module, port in AGENTS:
                panel = self.panels.get(module)
                if panel is None:
                    continue
                if port_open(port):
                    color = C["green"]      # 포트 열림 = 정상 가동
                elif panel.running:
                    color = C["yellow"]     # 프로세스는 살아있으나 포트 미개방(기동 중)
                else:
                    color = C["gray"]       # 꺼짐
                def _update_dot(m=module, c=color):
                    try:
                        self.dots[m].itemconfig("dot", fill=c)
                    except tk.TclError:
                        pass
                try:
                    self.after(0, _update_dot)
                except Exception:
                    return  # 창 닫힘
            time.sleep(1.5)

    def _on_close(self):
        for panel in self.panels.values():
            if panel.running:
                panel.proc.terminate()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()

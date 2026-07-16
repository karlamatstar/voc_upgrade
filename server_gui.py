# =============================================
# File: server_gui.py
# =============================================
# VOC Improve — 에이전트 서버 6개 실행 GUI (서버 올리기 전용)
#
# 실행하면 가장 먼저 "VOC Improve 및 QA 프로젝트" 최상위 폴더를 고르는
# 폴더 선택 창이 뜹니다. 사용자마다 폴더 이름/위치가 다를 수 있으므로
# 폴더 경로를 코드에 고정하지 않고, 매 실행마다 직접 선택하게 합니다.
# 선택한 폴더를 기준으로 아래 6개 명령을 실행합니다.
#
#   python -m agents.interpreter
#   python -m agents.retriever
#   python -m agents.summarizer
#   python -m agents.evaluator
#   python -m agents.critic
#   python -m agents.improver
#
# 즉 이 exe/스크립트를 어디에 두고 실행하든(바탕화면, USB 등) 상관없이,
# 사용자가 고른 프로젝트 폴더를 작업 디렉터리로 삼아 에이전트를 띄웁니다.
#
# 포함: 서버 6개 로그 터미널, 한국어 UI, 개별 시작/종료, 전체 시작/종료
# 미포함: pytest 실행, LLM Judge 실행, 보고서 폴더 이동
#
# 별도 패키지 불필요 (파이썬 내장 tkinter 사용). 프로젝트의 utils/ 코드에도
# 의존하지 않도록 .env 파싱 로직을 이 파일 안에 직접 포함했습니다.

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
from tkinter import filedialog, messagebox

# ============ 에이전트 정의 ============
AGENTS = [
    ("자연어 해석기",   "interpreter", 6001),
    ("데이터 검색기",   "retriever",   6002),
    ("불만사항 요약기", "summarizer",  6003),
    ("결과 평가기",     "evaluator",   6004),
    ("결과 비판기",     "critic",      6005),
    ("개선안 생성기",   "improver",    6006),
]
REQUIRED_AGENT_FILES = [f"agents/{module}.py" for _, module, _ in AGENTS]

# ============ 색상 테마 (다크) ============
C = {
    "bg":        "#16161e",
    "panel":     "#1f1f2e",
    "panel_hd":  "#2a2a3d",
    "log_bg":    "#12121a",
    "fg":        "#d8d8e8",
    "dim":       "#8a8aa0",
    "accent":    "#7aa2f7",
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

# 폴더 선택 후 확정되는 실행 컨텍스트 (module-level, App 생성 전에 채워짐)
ROOT: Path
PY: str
ENV_FILE_VARS: dict[str, str] = {}


# =====================================================
# .env 파싱 (utils/env_loader.py에 의존하지 않는 독립 구현)
# =====================================================
def parse_env_file(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key:
            result[key] = value
    return result


# =====================================================
# 실행 전: 프로젝트 폴더 선택 및 검증
# =====================================================
def pick_project_root() -> Path | None:
    """'VOC Improve 및 QA 프로젝트' 최상위 폴더를 고르고 유효성을 검증합니다.

    유효하지 않으면 다시 고르거나 취소할 수 있게 하고, 취소하면 None을 반환합니다.
    """
    probe = tk.Tk()
    probe.withdraw()
    try:
        while True:
            messagebox.showinfo(
                "VOC Improve 서버 런처",
                "'VOC Improve 및 QA 프로젝트'의 최상위 폴더를 선택해 주세요.\n"
                "(예: d:\\VOC Improve\\)",
                parent=probe,
            )
            selected = filedialog.askdirectory(
                title="VOC Improve 프로젝트 최상위 폴더 선택", parent=probe,
            )
            if not selected:
                if messagebox.askyesno("종료", "폴더를 선택하지 않았습니다. 프로그램을 종료할까요?", parent=probe):
                    return None
                continue

            candidate = Path(selected).resolve()
            missing = [f for f in REQUIRED_AGENT_FILES if not (candidate / f).exists()]
            if missing:
                retry = messagebox.askretrycancel(
                    "폴더 확인 필요",
                    f"선택한 폴더:\n{candidate}\n\n"
                    "다음 파일을 찾을 수 없습니다:\n" + "\n".join(missing) +
                    "\n\n'VOC Improve 및 QA 프로젝트' 최상위 폴더가 맞는지 확인해 주세요.",
                    parent=probe,
                )
                if retry:
                    continue
                return None

            venv_py = candidate / ".venv" / "Scripts" / "python.exe"
            if not venv_py.exists():
                retry = messagebox.askretrycancel(
                    "가상환경 없음",
                    f"{candidate}\\.venv\\Scripts\\python.exe 를 찾을 수 없습니다.\n"
                    "먼저 이 폴더에서 가상환경(.venv)을 만들고 필요한 패키지를 설치해 주세요.\n\n"
                    "다른 폴더를 다시 선택하시겠습니까?",
                    parent=probe,
                )
                if retry:
                    continue
                return None

            return candidate
    finally:
        probe.destroy()


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

    def start(self, args: list[str], banner: str):
        if self.running:
            self.log("[이미 실행 중]\n", "warn")
            return
        self.log(f"\n{'─' * 44}\n{banner}\n", "sys")
        env = os.environ.copy()
        for k, v in ENV_FILE_VARS.items():
            env.setdefault(k, v)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        try:
            self.proc = subprocess.Popen(
                args, cwd=str(ROOT), env=env,               # 사용자가 고른 프로젝트 폴더를 작업 디렉터리로 사용
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception as e:
            self.log(f"[시작 실패] {e}\n", "err")
            return
        threading.Thread(target=self._reader, args=(self.proc,), daemon=True).start()

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.log("[종료 요청됨]\n", "warn")

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def _reader(self, proc: subprocess.Popen):
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace")
            self.app.q.put((self.key, line, "out"))
        code = proc.wait()
        tag = "sys" if code in (0, 1, -15, 15) else "err"
        self.app.q.put((self.key, f"[프로세스 종료 (code={code})]\n", tag))

    def log(self, msg: str, tag: str = "out"):
        self.app.q.put((self.key, msg, tag))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"VOC Improve — 에이전트 서버 런처  [{ROOT}]")
        self.configure(bg=C["bg"])
        self.geometry("1360x820")
        self.minsize(980, 620)

        self.q: queue.Queue = queue.Queue()
        self.panels: dict[str, ProcessPanel] = {}
        self.dots: dict[str, tk.Canvas] = {}

        self._build_ui()
        self.after(80, self._drain_queue)
        threading.Thread(target=self._port_watcher, daemon=True).start()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # =====================================================
    # UI 구성
    # =====================================================
    def _build_ui(self):
        bar = tk.Frame(self, bg=C["bg"])
        bar.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(bar, text="⬢ VOC 에이전트 서버", bg=C["bg"], fg=C["accent"],
                 font=("Malgun Gothic", 13, "bold")).pack(side="left")
        tk.Label(bar, text=f"  작업 폴더: {ROOT}", bg=C["bg"], fg=C["dim"],
                 font=UI_FONT).pack(side="left")
        flat_button(bar, "■ 전체 종료", self._stop_all, color=C["red"]).pack(side="right", padx=3)
        flat_button(bar, "▶ 전체 시작", self._start_all, color=C["green"]).pack(side="right", padx=3)

        status = tk.Frame(self, bg=C["bg"])
        status.pack(fill="x", padx=12)
        tk.Label(status, text=self._env_status_text(), bg=C["bg"], fg=C["dim"],
                 font=UI_FONT, anchor="w", justify="left").pack(side="left")

        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=12, pady=(8, 12))
        for c in range(3):
            body.columnconfigure(c, weight=1, uniform="ag")
        for r in range(2):
            body.rowconfigure(r, weight=1, uniform="ag")
        for i, (name, module, port) in enumerate(AGENTS):
            self._build_agent_panel(body, i // 3, i % 3, name, module, port)

    def _env_status_text(self) -> str:
        if not ENV_FILE_VARS:
            return f"🔑 .env 파일이 없거나 비어 있습니다 ({ROOT}\\.env)"
        missing = [k for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")
                   if k not in ENV_FILE_VARS and not os.environ.get(k)]
        base = f"🔑 .env 로드됨: {', '.join(ENV_FILE_VARS.keys())}"
        if missing:
            base += f"   ⚠ 없음: {', '.join(missing)}"
        return base

    def _panel_frame(self, parent):
        return tk.Frame(parent, bg=C["panel"], highlightbackground="#33334d", highlightthickness=1)

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

        tk.Label(hd, text=name, bg=C["panel_hd"], fg=C["fg"], font=UI_FONT_B).pack(side="left")
        tk.Label(hd, text=f":{port}", bg=C["panel_hd"], fg=C["dim"], font=UI_FONT).pack(side="left", padx=(4, 0))

        flat_button(hd, "■", lambda k=key: self._stop_agent(k), color=C["red"], width=2).pack(side="right", padx=(2, 8), pady=4)
        flat_button(hd, "▶", lambda k=key: self._start_agent(k), color=C["green"], width=2).pack(side="right", padx=2, pady=4)

        self.panels[key] = ProcessPanel(self, key)
        self.panels[key].text = self._make_log(f)

    def _make_log(self, parent) -> tk.Text:
        wrap = tk.Frame(parent, bg=C["panel"])
        wrap.pack(fill="both", expand=True, padx=8, pady=(2, 8))
        text = tk.Text(wrap, bg=C["log_bg"], fg=C["fg"], insertbackground=C["fg"],
                       relief="flat", font=LOG_FONT, height=8, wrap="word",
                       state="disabled", padx=8, pady=6)
        sb = tk.Scrollbar(wrap, command=text.yview, troughcolor=C["panel"],
                          bg=C["btn"], activebackground=C["btn_hover"], width=10)
        text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)
        text.tag_config("sys", foreground=C["accent"])
        text.tag_config("warn", foreground=C["yellow"])
        text.tag_config("err", foreground=C["red"])
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

    # =====================================================
    # 큐 → 텍스트 위젯 반영 / 상태 감시
    # =====================================================
    def _drain_queue(self):
        try:
            while True:
                key, msg, tag = self.q.get_nowait()
                text = self.panels[key].text
                if text is None:
                    continue
                text.configure(state="normal")
                text.insert("end", msg, tag)
                if float(text.index("end-1c").split(".")[0]) > 3000:
                    text.delete("1.0", "500.0")
                text.see("end")
                text.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(80, self._drain_queue)

    def _port_watcher(self):
        import time
        while True:
            for _, module, port in AGENTS:
                panel = self.panels.get(module)
                if panel is None:
                    continue
                if port_open(port):
                    color = C["green"]
                elif panel.running:
                    color = C["yellow"]
                else:
                    color = C["gray"]

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


def main() -> int:
    global ROOT, PY, ENV_FILE_VARS
    picked = pick_project_root()
    if picked is None:
        return 0
    ROOT = picked
    PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
    ENV_FILE_VARS = parse_env_file(ROOT / ".env")
    App().mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())

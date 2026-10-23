"""V58 SPACE BAR local Windows-friendly read-only research launcher.

Standard-library desktop GUI: starts/stops an in-process 127.0.0.1 research
server. Never starts a live exchange feed, paper order execution, or broker API.
"""
import argparse
import json
import sys
import threading
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agents"))
from dashboard_api_v28 import load_candles, make_handler, snapshot  # noqa: E402
from market_board_v52 import market_board  # noqa: E402
from launcher_diagnostics_v59 import probe_local_research, LocalEventLog  # noqa: E402

DEFAULT_CSV = ROOT / "data" / "history" / "BTC_5m.csv"
LOCAL_HOST = "127.0.0.1"
PORT = 8765


def validate_history(history_path):
    """Read and check closed contiguous history before starting the service."""
    path = Path(history_path).expanduser().resolve()
    rows = load_candles(path, limit=60)
    if len(rows) < 55:
        raise ValueError("At least 55 BTC 5-minute candles are required")
    market_board(rows, realtime=False, source="historical_csv_snapshot")
    # Validate research contract as well as OHLCV; no fabricated fallback.
    response = snapshot(path)
    if response.get("orders_enabled") is not False or response.get("paper_only") is not True:
        raise ValueError("Research safety flags are not read-only")
    return path


class LocalResearchService:
    """Idempotent, explicitly local server lifecycle without child processes."""
    def __init__(self, *, host=LOCAL_HOST, port=PORT):
        if host != LOCAL_HOST:
            raise ValueError("Launcher binds only to localhost")
        if isinstance(port, bool) or not isinstance(port, int) or not 1024 <= port <= 65535:
            raise ValueError("Invalid local port")
        self.host, self.port = host, port
        self._server = None
        self._thread = None
        self._lock = threading.RLock()
        self.history_path = None

    @property
    def running(self):
        with self._lock:
            return bool(self._server and self._thread and self._thread.is_alive())

    @property
    def base_url(self):
        return f"http://{self.host}:{self.port}"

    def start(self, history_path):
        with self._lock:
            if self.running:
                raise RuntimeError("Local research server is already running")
            validated = validate_history(history_path)
            # Do not replace or terminate unrelated listeners holding the port.
            server = ThreadingHTTPServer(
                (self.host, self.port), make_handler(validated))
            server.daemon_threads = True
            thread = threading.Thread(
                target=server.serve_forever,
                name="space-bar-read-only-http", daemon=True)
            self._server, self._thread = server, thread
            self.history_path = validated
            thread.start()
            return self.base_url

    def stop(self):
        with self._lock:
            server, thread = self._server, self._thread
            if server is None:
                return False
            server.shutdown()
            server.server_close()
            if thread is not None:
                thread.join(timeout=3)
            self._server, self._thread, self.history_path = None, None, None
            return True

    def health(self, timeout=2.0):
        if not self.running:
            return {"status": "stopped", "orders_enabled": False}
        try:
            with urlopen(self.base_url + "/health", timeout=timeout) as response:
                data = json.load(response)
            if data.get("orders_enabled") is not False:
                raise ValueError("Unsafe health reply")
            return data
        except (OSError, ValueError, TimeoutError) as exc:
            return {"status": "unavailable", "reason": type(exc).__name__,
                    "orders_enabled": False}


def run_gui():
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError as exc:
        raise RuntimeError("Tkinter is not installed. Install Python with Tcl/Tk support.") from exc

    service = LocalResearchService()
    events = LocalEventLog()
    executor = ThreadPoolExecutor(max_workers=1,thread_name_prefix="spacebar-local-probe")
    health_future = None
    closing = False
    app = tk.Tk()
    app.title("SPACE BAR AI TRADING · Local Research")
    app.geometry("760x640")
    app.minsize(620, 560)
    app.configure(bg="#101b2e")

    frame = ttk.Frame(app, padding=22)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="SPACE BAR  |  RESEARCH CONTROL",
              font=("Segoe UI", 17, "bold")).pack(anchor="w", pady=(0, 8))
    ttk.Label(frame, text="READ ONLY · LOCALHOST · HISTORICAL CSV · NO LIVE ORDERS",
              foreground="#a04c30").pack(anchor="w", pady=(0, 18))
    ttk.Label(frame, text="BTC 5m history CSV (55+ valid closed bars):").pack(anchor="w")
    csv_path = tk.StringVar(value=str(DEFAULT_CSV))
    path_row = ttk.Frame(frame)
    path_row.pack(fill="x", pady=(4, 15))
    ttk.Entry(path_row, textvariable=csv_path).pack(side="left", fill="x", expand=True)

    def browse_file():
        chosen = filedialog.askopenfilename(
            parent=app, title="Choose BTC 5-minute OHLCV CSV",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
        if chosen:
            csv_path.set(chosen)

    ttk.Button(path_row, text="Browse", command=browse_file).pack(side="left", padx=(8, 0))
    state = tk.StringVar(value="STOPPED · local server is not running")
    ttk.Label(frame, textvariable=state, font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=8)
    address = ttk.Label(frame, text="http://127.0.0.1:8765", foreground="#2477ab")
    address.pack(anchor="w", pady=(0, 12))
    ops_label = tk.StringVar(value="DIAGNOSTICS · historical server stopped")
    ttk.Label(frame,textvariable=ops_label).pack(anchor="w",pady=(0,8))
    controls = ttk.Frame(frame)
    controls.pack(fill="x")
    action = {"start": None, "stop": None}

    def update_buttons():
        running = service.running
        action["start"].configure(state="disabled" if running else "normal")
        action["stop"].configure(state="normal" if running else "disabled")

    def log_event(event, detail=""):
        events.record(event, detail)
        log_view.configure(state="normal")
        log_view.delete("1.0","end")
        log_view.insert("end","\n".join(events.recent()))
        log_view.configure(state="disabled")

    def start_service():
        try:
            url = service.start(csv_path.get())
        except (OSError, ValueError, RuntimeError) as exc:
            state.set("NOT STARTED · " + str(exc)[:95])
            log_event("START_FAILED","PORT_BUSY" if isinstance(exc,OSError) else "MISSING_DATA")
            messagebox.showerror("SPACE BAR research server", str(exc), parent=app)
        else:
            state.set("RUNNING · historical research only · no orders")
            log_event("STARTED","HISTORICAL_CSV")
            webbrowser.open(url + "/dashboard")
        update_buttons()

    def stop_service():
        service.stop()
        log_event("STOPPED")
        ops_label.set("DIAGNOSTICS · stopped · simulated paper mode unavailable")
        state.set("STOPPED · local server is not running")
        update_buttons()

    action["start"] = ttk.Button(controls, text="▶ Start local research", command=start_service)
    action["start"].pack(side="left", padx=(0, 8))
    action["stop"] = ttk.Button(controls, text="■ Stop", command=stop_service)
    action["stop"].pack(side="left", padx=(0, 8))

    def open_page(path):
        if not service.running:
            messagebox.showinfo("Not running", "Start the local research server first.", parent=app)
            return
        webbrowser.open(service.base_url + path)

    pages = ttk.Frame(frame)
    pages.pack(fill="x", pady=(18, 8))
    ttk.Button(pages, text="Open 2.5D dashboard",
               command=lambda: open_page("/dashboard")).pack(side="left", padx=(0, 8))
    ttk.Button(pages, text="Open 3D office",
               command=lambda: open_page("/office3d")).pack(side="left")
    ttk.Label(frame, text="3D requires internet for Three.js and WebGL support.\n"
              "Uses existing historical snapshots; no public-market feed is started.\n"
              "Closing this window stops only the local research service.",
              justify="left").pack(anchor="w", pady=(12, 4))
    ttk.Label(frame,text="LOCAL DIAGNOSTICS · no account or exchange connection").pack(anchor="w",pady=(12,2))
    log_view=tk.Text(frame,height=7,wrap="word",state="disabled",font=("Consolas",9))
    log_view.pack(fill="both",expand=True)
    log_event("STOPPED")

    def refresh_health():
        nonlocal health_future
        if closing:
            return
        if service.running:
            if health_future is None:
                health_future = executor.submit(probe_local_research,service.base_url)
            elif health_future.done():
                try:
                    report = health_future.result()
                except Exception:
                    report = {"state":"UNAVAILABLE","orders_enabled":False}
                health_future = None
                if report.get("state")=="READY" and report.get("orders_enabled") is False:
                    state.set("RUNNING · historical research only · no orders")
                    ops_label.set("API VERIFIED · historical CSV · market chart OK · paper not enabled")
                    if not events.recent() or "CHECK_OK" not in events.recent()[-1]:
                        log_event("CHECK_OK","HISTORICAL_CSV")
                else:
                    state.set("WARNING · research data not verified")
                    ops_label.set("API CHECK FAILED · no valid signal · paper not enabled")
                    if not events.recent() or "CHECK_FAILED" not in events.recent()[-1]:
                        log_event("CHECK_FAILED","UNAVAILABLE")
        else:
            ops_label.set("DIAGNOSTICS · stopped · paper not enabled")
        app.after(2000, refresh_health)

    def on_close():
        nonlocal closing
        closing = True
        service.stop()
        executor.shutdown(wait=False,cancel_futures=True)
        app.destroy()

    app.protocol("WM_DELETE_WINDOW", on_close)
    update_buttons()
    app.after(2000, refresh_health)
    app.mainloop()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local historical research launcher, never live orders")
    parser.add_argument("--check-history", type=Path, default=None,
                        help="Validate a historical CSV and exit without starting any service")
    args = parser.parse_args(argv)
    if args.check_history is not None:
        validate_history(args.check_history)
        print("Valid BTC 5m history; no server started")
        return 0
    run_gui()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
TrafficPulse - Local Runner & Process Supervisor
Manages the FastAPI PySpark backend and React Vite frontend in a single terminal session.
Ensures 100% clean process termination and port cleanup on window close or Ctrl+C.
"""

import os
import sys
import time
import signal
import atexit
import socket
import urllib.request
import webbrowser
import subprocess
import threading
from typing import List, Optional

# Force immediate unbuffered console output
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Win32 Kernel Job Object Constants
JobObjectExtendedLimitInformation = 9
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")

backend_proc: Optional[subprocess.Popen] = None
frontend_proc: Optional[subprocess.Popen] = None
job_handle = None
is_shutting_down = False
_ctrl_handler_ref = None


def setup_windows_job_object():
    """
    Creates a Windows Job Object with JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE.
    The Windows OS kernel automatically terminates all processes in this job
    if this supervisor process terminates (including clicking 'X' on terminal).
    """
    global job_handle
    if os.name != "nt":
        return None

    import ctypes

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", ctypes.c_uint32),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", ctypes.c_uint32),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", ctypes.c_uint32),
            ("SchedulingClass", ctypes.c_uint32),
        ]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryLimit", ctypes.c_size_t),
            ("PeakJobMemoryLimit", ctypes.c_size_t),
        ]

    try:
        kernel32 = ctypes.windll.kernel32
        h_job = kernel32.CreateJobObjectW(None, None)
        if not h_job:
            return None

        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        res = kernel32.SetInformationJobObject(
            h_job,
            JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if res == 0:
            kernel32.CloseHandle(h_job)
            return None

        job_handle = h_job
        return h_job
    except Exception as e:
        print(f"[WARN] Unable to configure Windows Job Object: {e}", flush=True)
        return None


def assign_to_job(proc: subprocess.Popen):
    """Assigns a child process handle to the Windows Job Object."""
    global job_handle
    if not job_handle or os.name != "nt":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.AssignProcessToJobObject(job_handle, int(proc._handle))
    except Exception:
        pass


def kill_ports(ports: List[int]):
    """Finds and forcefully terminates any processes listening on the specified ports."""
    my_pid = os.getpid()
    for port in ports:
        try:
            cmd = f'netstat -ano | findstr :{port}'
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            pids = set()
            for line in res.stdout.strip().splitlines():
                parts = line.split()
                if len(parts) >= 5 and "LISTENING" in parts:
                    try:
                        pid = int(parts[-1])
                        if pid > 0 and pid != my_pid:
                            pids.add(pid)
                    except ValueError:
                        pass
            for pid in pids:
                subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
        except Exception:
            pass


def check_port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    """Checks if a port is currently listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


def wait_for_url(url: str, timeout: float = 45.0, step: float = 0.5) -> bool:
    """Polls an HTTP URL until it returns 200 OK or timeout expires."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "TrafficPulse-Launcher"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(step)
    return False


def cleanup():
    """Stops all running services and performs cleanup."""
    global backend_proc, frontend_proc, is_shutting_down
    if is_shutting_down:
        return
    is_shutting_down = True

    print("\n" + "=" * 68, flush=True)
    print("   Stopping TrafficPulse services & cleaning up ports...", flush=True)
    print("=" * 68, flush=True)

    # 1. Terminate backend
    if backend_proc and backend_proc.poll() is None:
        try:
            backend_proc.terminate()
        except Exception:
            pass

    # 2. Terminate frontend
    if frontend_proc and frontend_proc.poll() is None:
        try:
            frontend_proc.terminate()
        except Exception:
            pass

    # Give processes a moment to gracefully exit
    time.sleep(1.0)

    # Force kill if still lingering
    for proc in [backend_proc, frontend_proc]:
        if proc and proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                pass

    # 3. Clean up ports 8000 and 5173
    kill_ports([8000, 5173])

    print("   [OK] TrafficPulse backend and frontend stopped cleanly.", flush=True)
    print("=" * 68, flush=True)


def signal_handler(signum, frame):
    cleanup()
    sys.exit(0)


def setup_console_ctrl_handler():
    """Registers Windows console event handler for window close events."""
    if os.name != "nt":
        return
    try:
        import ctypes
        HandlerRoutine = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)

        def win_ctrl_handler(ctrl_type):
            cleanup()
            return False

        global _ctrl_handler_ref
        _ctrl_handler_ref = HandlerRoutine(win_ctrl_handler)
        ctypes.windll.kernel32.SetConsoleCtrlHandler(_ctrl_handler_ref, True)
    except Exception:
        pass


def stream_logs(prefix: str, stream):
    """Streams process logs with a readable tag prefix."""
    try:
        for line in iter(stream.readline, ""):
            if not line:
                break
            if is_shutting_down:
                break
            clean_line = line.rstrip()
            if clean_line:
                print(f"[{prefix}] {clean_line}", flush=True)
    except Exception:
        pass


def main():
    global backend_proc, frontend_proc

    if os.name == "nt":
        os.system("title TrafficPulse - Single Launcher")

    print("=" * 68, flush=True)
    print("   TrafficPulse: Scalable Traffic Prediction & Simulation", flush=True)
    print("=" * 68, flush=True)
    print(flush=True)

    # Register exit hooks
    atexit.register(cleanup)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, signal_handler)
    setup_console_ctrl_handler()

    # Step 1: Ensure ports 8000 and 5173 are free upfront
    print("[1/4] Checking and preparing environment...", flush=True)
    kill_ports([8000, 5173])

    # Windows PySpark / Hadoop configuration
    if os.name == "nt":
        hadoop_dir = os.path.join(PROJECT_ROOT, "hadoop")
        if os.path.exists(os.path.join(hadoop_dir, "bin", "winutils.exe")):
            os.environ["HADOOP_HOME"] = hadoop_dir
            os.environ["PATH"] = os.path.join(hadoop_dir, "bin") + os.pathsep + os.environ.get("PATH", "")

    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable
    os.environ["PYTHONUNBUFFERED"] = "1"

    # Setup Windows Job Object for auto-kill on window close
    setup_windows_job_object()

    # Check node_modules in frontend
    node_modules_dir = os.path.join(FRONTEND_DIR, "node_modules")
    if not os.path.exists(node_modules_dir):
        print("      Installing frontend npm dependencies (first time only)...", flush=True)
        npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
        subprocess.run([npm_cmd, "install"], cwd=FRONTEND_DIR, check=True)

    # Step 2: Start FastAPI Backend
    print("[2/4] Launching FastAPI PySpark Backend (port 8000)...", flush=True)
    backend_env = os.environ.copy()
    backend_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
        "--log-level",
        "info",
    ]
    backend_proc = subprocess.Popen(
        backend_cmd,
        cwd=PROJECT_ROOT,
        env=backend_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assign_to_job(backend_proc)

    # Stream backend logs in a background thread
    t_backend = threading.Thread(target=stream_logs, args=("BACKEND", backend_proc.stdout), daemon=True)
    t_backend.start()

    # Step 3: Start Vite Frontend
    print("[3/4] Launching React + Vite Frontend (port 5173)...", flush=True)
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    frontend_proc = subprocess.Popen(
        [npm_cmd, "run", "dev"],
        cwd=FRONTEND_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        shell=(os.name == "nt"),
    )
    assign_to_job(frontend_proc)

    # Stream frontend logs in a background thread
    t_frontend = threading.Thread(target=stream_logs, args=("FRONTEND", frontend_proc.stdout), daemon=True)
    t_frontend.start()

    # Step 4: Wait for services
    print("[4/4] Initializing services (PySpark ML engine warming up ~15s)...", flush=True)
    backend_ready = wait_for_url("http://127.0.0.1:8000/api/health", timeout=60.0)
    frontend_ready = wait_for_url("http://127.0.0.1:5173", timeout=25.0)

    print(flush=True)
    print("=" * 68, flush=True)
    print("   TrafficPulse is now RUNNING!", flush=True)
    print("=" * 68, flush=True)
    print("   - Frontend Dashboard:   http://127.0.0.1:5173", flush=True)
    print("   - FastAPI Backend:      http://127.0.0.1:8000", flush=True)
    print("   - Swagger API Docs:     http://127.0.0.1:8000/docs", flush=True)
    print("   - Health Status:        http://127.0.0.1:8000/api/health", flush=True)
    print("=" * 68, flush=True)
    print("   [INFO] Press Ctrl+C or close this terminal window to stop.", flush=True)
    print("=" * 68, flush=True)
    print(flush=True)

    # Automatically open browser
    print("Opening TrafficPulse in your default browser (http://127.0.0.1:5173)...", flush=True)
    try:
        if os.name == "nt":
            subprocess.run(["cmd", "/c", "start", "", "http://127.0.0.1:5173"], shell=True)
        else:
            webbrowser.open("http://127.0.0.1:5173")
    except Exception as e:
        print(f"[WARN] Could not automatically open browser: {e}", flush=True)

    # Step 5: Monitor processes until interrupted or closed
    try:
        while True:
            time.sleep(1.0)
            if backend_proc and backend_proc.poll() is not None:
                print(f"\n[ALERT] Backend stopped unexpectedly (exit code {backend_proc.returncode}).", flush=True)
                break
            if frontend_proc and frontend_proc.poll() is not None:
                print(f"\n[ALERT] Frontend stopped unexpectedly (exit code {frontend_proc.returncode}).", flush=True)
                break
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()


if __name__ == "__main__":
    main()

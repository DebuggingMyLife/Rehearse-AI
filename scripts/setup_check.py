"""RehearseAI setup check: reports GPU, VRAM, RAM, Ollama status and recommended .env values.

Uses only the standard library so it runs before `pip install`. If faster-whisper /
ctranslate2 is already installed it also verifies that CUDA actually initialises.

    python scripts/setup_check.py
"""

import ctypes
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def ok(msg):   print(f"  [ OK ] {msg}")
def warn(msg): print(f"  [WARN] {msg}")
def fail(msg): print(f"  [FAIL] {msg}")
def info(msg): print(f"         {msg}")


def read_env() -> dict[str, str]:
    env = {}
    path = REPO_ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def total_ram_gb() -> float | None:
    try:
        if sys.platform == "win32":
            class MEMSTATUS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = MEMSTATUS()
            m.dwLength = ctypes.sizeof(MEMSTATUS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.ullTotalPhys / 1024**3
        if sys.platform == "darwin":
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True)
            return int(out) / 1024**3
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / 1024**2
    except Exception:
        pass
    return None


def nvidia_gpus() -> list[dict]:
    if not shutil.which("nvidia-smi"):
        return []
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free,driver_version,compute_cap",
             "--format=csv,noheader,nounits"], text=True, timeout=10)
    except Exception:
        return []
    gpus = []
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 4:
            gpus.append({
                "name": parts[0],
                "vram_total_gb": float(parts[1]) / 1024,
                "vram_free_gb": float(parts[2]) / 1024,
                "driver": parts[3],
                "compute_cap": parts[4] if len(parts) > 4 else "?",
            })
    return gpus


def nvidia_cuda_version() -> str | None:
    """Max CUDA version supported by the driver, from the nvidia-smi banner."""
    try:
        out = subprocess.check_output(["nvidia-smi"], text=True, timeout=10)
        # Older drivers: "CUDA Version: 12.8"; newer: "CUDA UMD Version: 13.3"
        m = re.search(r"CUDA (?:UMD )?Version:\s*([\d.]+)", out)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


def check_ctranslate2_cuda() -> tuple[bool | None, str]:
    """None = faster-whisper not installed yet, so we can't test."""
    try:
        import ctranslate2  # type: ignore
    except ImportError:
        return None, "faster-whisper not installed yet (pip install -r backend/requirements-cuda.txt)"
    try:
        n = ctranslate2.get_cuda_device_count()
        if n == 0:
            return False, f"ctranslate2 {ctranslate2.__version__} sees no CUDA device"
        types = ctranslate2.get_supported_compute_types("cuda")
        return True, f"ctranslate2 {ctranslate2.__version__}: {n} CUDA device(s), compute types {sorted(types)}"
    except Exception as exc:
        return False, f"CUDA init failed: {exc}"


def check_ollama(host: str, model: str) -> tuple[bool, bool, list[str]]:
    try:
        with urllib.request.urlopen(f"{host.rstrip('/')}/api/tags", timeout=3) as r:
            names = [m["name"] for m in json.load(r).get("models", [])]
    except (urllib.error.URLError, OSError, ValueError):
        return False, False, []
    wanted = model if ":" in model else f"{model}:latest"
    return True, wanted in names, names


def version_tuple(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.split("."))
    except ValueError:
        return (0,)


def recommend(gpus, ram_gb, apple_silicon) -> dict[str, str]:
    if apple_silicon:
        big = (ram_gb or 0) >= 16
        return {
            "WHISPER_BACKEND": "mlx",
            "WHISPER_MODEL_SIZE": "large-v3-turbo" if big else "small",
            "WHISPER_DEVICE": "cpu",
            "WHISPER_COMPUTE_TYPE": "float16",
            "LLM_MODEL": "qwen2.5:7b" if big else "qwen2.5:3b",
            "LLM_NUM_CTX": "8192" if big else "4096",
        }
    if gpus:
        vram = max(g["vram_total_gb"] for g in gpus)
        # qwen2.5:7b Q4 with 8k ctx ~ 5.5-6 GB; large-v3-turbo fp16 ~ 1.6 GB + activations
        if vram >= 10:
            whisper, llm, ctx = "large-v3-turbo", "qwen2.5:7b", "8192"
        elif vram >= 8:
            whisper, llm, ctx = "medium", "qwen2.5:7b", "4096"
        else:
            whisper, llm, ctx = "small", "qwen2.5:3b", "4096"
        return {
            "WHISPER_BACKEND": "faster-whisper",
            "WHISPER_MODEL_SIZE": whisper,
            "WHISPER_DEVICE": "cuda",
            "WHISPER_COMPUTE_TYPE": "float16",
            "LLM_MODEL": llm,
            "LLM_NUM_CTX": ctx,
        }
    big = (ram_gb or 0) >= 16
    return {
        "WHISPER_BACKEND": "faster-whisper",
        "WHISPER_MODEL_SIZE": "small",
        "WHISPER_DEVICE": "cpu",
        "WHISPER_COMPUTE_TYPE": "int8",
        "LLM_MODEL": "qwen2.5:7b" if big else "qwen2.5:3b",
        "LLM_NUM_CTX": "8192" if big else "4096",
    }


def main() -> int:
    env = read_env()
    problems = 0

    print("\nSystem")
    ok(f"{platform.system()} {platform.release()} ({platform.machine()}), Python {platform.python_version()}")
    if sys.version_info < (3, 10):
        fail("Python 3.10+ required"); problems += 1
    ram = total_ram_gb()
    ok(f"RAM: {ram:.1f} GB" if ram else "RAM: unknown")
    apple_silicon = sys.platform == "darwin" and platform.machine() == "arm64"

    print("\nGPU")
    gpus = nvidia_gpus()
    if apple_silicon:
        ok("Apple Silicon detected (unified memory; use the mlx Whisper backend)")
    elif not gpus:
        warn("No NVIDIA GPU detected - transcription will run on CPU (slower)")
    for g in gpus:
        ok(f"{g['name']}: {g['vram_total_gb']:.1f} GB VRAM ({g['vram_free_gb']:.1f} GB free), "
           f"driver {g['driver']}, compute capability {g['compute_cap']}")
        if g["compute_cap"].startswith("12"):
            cuda = nvidia_cuda_version()
            if cuda and version_tuple(cuda) < (12, 8):
                fail(f"Blackwell GPU needs CUDA 12.8+ driver support; driver reports CUDA {cuda}. "
                     "Update the NVIDIA driver."); problems += 1
            else:
                ok(f"Blackwell GPU, driver supports CUDA {cuda or '?'} (12.8+ required)")
    if gpus:
        cuda_ok, msg = check_ctranslate2_cuda()
        if cuda_ok is None:
            info(msg)
        elif cuda_ok:
            ok(msg)
        else:
            warn(msg + " - the server will fall back to WHISPER_DEVICE=cpu / int8")

    print("\nOllama")
    host = env.get("OLLAMA_HOST", "http://localhost:11434")
    model = env.get("LLM_MODEL", "qwen2.5:7b")
    reachable, has_model, names = check_ollama(host, model)
    if not reachable:
        fail(f"Ollama not reachable at {host}")
        info("Install from https://ollama.com, then run `ollama serve` (or open the app)")
        problems += 1
    else:
        ok(f"Ollama reachable at {host} ({len(names)} model(s) installed)")
        if has_model:
            ok(f"Model {model} is pulled")
        else:
            fail(f"Model {model} not pulled. Fix: ollama pull {model}"); problems += 1

    print("\nRecommended .env for this machine")
    rec = recommend(gpus, ram, apple_silicon)
    for k, v in rec.items():
        current = env.get(k)
        note = "" if current is None or current == v else f"   (currently {current})"
        print(f"  {k}={v}{note}")
    if not (REPO_ROOT / ".env").exists():
        warn("No .env found - copy .env.example to .env")
    if rec["LLM_MODEL"] != model and reachable:
        info(f"If you switch models: ollama pull {rec['LLM_MODEL']}")

    print()
    if problems:
        print(f"{problems} problem(s) found.")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.exit(main())

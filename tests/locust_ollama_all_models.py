#!/usr/bin/env python3
"""
Benchmark integral Ollama + Locust
=================================

Un SOLO archivo para evaluar múltiples modelos Ollama en:
  - CPU
  - GPU (aceleración automática de Ollama)

y con usuarios concurrentes recurrentes:
  - 50
  - 100
  - 150
  - 200

Uso recomendado (orquestador automático):
    python3 locust_ollama_all_models.py

También puede usarse como locustfile convencional para un escenario:
    OLLAMA_MODEL=phi4:14b OLLAMA_DEVICE=cpu BENCH_USERS=50 \
      locust -f locust_ollama_all_models.py --headless \
      --host http://127.0.0.1:11434 -u 50 -r 10 -t 60s

Variables/argumentos configurables están documentados en --help.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# -----------------------------------------------------------------------------
# CONFIGURACIÓN GENERAL
# -----------------------------------------------------------------------------

MODELS = [
    "muse-glimmer:latest",
    "qwen3.8:27b",
    "phi4:14b",
    "gemma4:31b",
    "gemma4:26b",
    "gemma4:12b",
    "qwen3.6:27b",
    "gpt-oss:20b",
    "iris-command-r:35b",
    "iris-hermes:8b",
    "hermes3:latest",
    "olmo-3:7b-think",
    "hermes4:14b",
    "command-r:35b-08-2024-q3_K_S",
]

DEVICES = ["cpu", "gpu"]
USER_LEVELS = [50, 100, 150, 200]

DEFAULT_PROMPT = (
    "Explica en no más de 80 palabras qué caracteriza a una arquitectura "
    "de microservicios segura y menciona tres controles de seguridad."
)

# -----------------------------------------------------------------------------
# PARTE LOCUST
# Esta sección se importa cuando Locust carga este mismo archivo.
# -----------------------------------------------------------------------------

try:
    from locust import HttpUser, constant, events, task

    LOCUST_AVAILABLE = True
except ImportError:
    LOCUST_AVAILABLE = False


MODEL = os.getenv("OLLAMA_MODEL", MODELS[0])
DEVICE = os.getenv("OLLAMA_DEVICE", "gpu").strip().lower()
BENCH_USERS = int(os.getenv("BENCH_USERS", "50"))
PROMPT = os.getenv("OLLAMA_PROMPT", DEFAULT_PROMPT)
NUM_PREDICT = int(os.getenv("NUM_PREDICT", "128"))
NUM_CTX = int(os.getenv("NUM_CTX", "2048"))
WAIT_SECONDS = float(os.getenv("WAIT_SECONDS", "1.0"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "900"))
KEEP_ALIVE = os.getenv("KEEP_ALIVE", "10m")
SUMMARY_CSV = os.getenv("BENCH_SUMMARY_CSV", "benchmark_summary.csv")


def ollama_options(device: str) -> Dict[str, object]:
    """Opciones estandarizadas para que CPU y GPU sean comparables."""
    options: Dict[str, object] = {
        "temperature": 0,
        "num_predict": NUM_PREDICT,
        "num_ctx": NUM_CTX,
    }

    # num_gpu=0 fuerza que ninguna capa se descargue en GPU.
    # En GPU se omite num_gpu para que Ollama use su aceleración automática.
    if device == "cpu":
        options["num_gpu"] = 0

    return options


class MetricAccumulator:
    def __init__(self) -> None:
        self.ok = 0
        self.failed = 0
        self.eval_count = 0
        self.eval_duration_ns = 0
        self.prompt_eval_count = 0
        self.prompt_eval_duration_ns = 0
        self.total_duration_ns = 0
        self.load_duration_ns = 0
        self.sum_request_tps = 0.0

    def add(self, data: Dict[str, object]) -> None:
        self.ok += 1
        eval_count = int(data.get("eval_count") or 0)
        eval_duration = int(data.get("eval_duration") or 0)
        prompt_count = int(data.get("prompt_eval_count") or 0)
        prompt_duration = int(data.get("prompt_eval_duration") or 0)

        self.eval_count += eval_count
        self.eval_duration_ns += eval_duration
        self.prompt_eval_count += prompt_count
        self.prompt_eval_duration_ns += prompt_duration
        self.total_duration_ns += int(data.get("total_duration") or 0)
        self.load_duration_ns += int(data.get("load_duration") or 0)

        if eval_count > 0 and eval_duration > 0:
            self.sum_request_tps += eval_count / (eval_duration / 1_000_000_000)

    def fail(self) -> None:
        self.failed += 1


METRICS = MetricAccumulator()


if LOCUST_AVAILABLE:

    class OllamaUser(HttpUser):
        """Usuario recurrente: cada VU vuelve a generar tras WAIT_SECONDS."""

        wait_time = constant(WAIT_SECONDS)

        @task
        def generate(self) -> None:
            payload = {
                "model": MODEL,
                "prompt": PROMPT,
                "stream": True,
                "keep_alive": KEEP_ALIVE,
                "options": ollama_options(DEVICE),
            }

            stat_name = f"generate|{MODEL}|{DEVICE}|u{BENCH_USERS}"

            try:
                with self.client.post(
                    "/api/generate",
                    json=payload,
                    name=stat_name,
                    catch_response=True,
                    timeout=REQUEST_TIMEOUT,
                ) as response:
                    if response.status_code != 200:
                        METRICS.fail()
                        response.failure(
                            f"HTTP {response.status_code}: {response.text[:300]}"
                        )
                        return

                    try:
                        data = response.json()
                    except Exception as exc:
                        METRICS.fail()
                        response.failure(f"JSON inválido: {exc}")
                        return

                    if data.get("error"):
                        METRICS.fail()
                        response.failure(str(data["error"]))
                        return

                    if not data.get("done", False):
                        METRICS.fail()
                        response.failure("Ollama no devolvió done=true")
                        return

                    METRICS.add(data)
                    response.success()

            except Exception:
                # Locust registra automáticamente excepciones de transporte.
                METRICS.fail()
                raise


    @events.test_stop.add_listener
    def write_master_summary(environment, **kwargs) -> None:
        """Añade una fila al CSV maestro al terminar cada escenario."""
        path = Path(SUMMARY_CSV)
        path.parent.mkdir(parents=True, exist_ok=True)

        total = environment.stats.total
        total_eval_seconds = METRICS.eval_duration_ns / 1_000_000_000
        total_prompt_seconds = METRICS.prompt_eval_duration_ns / 1_000_000_000

        aggregate_tps = (
            METRICS.eval_count / total_eval_seconds if total_eval_seconds > 0 else 0.0
        )
        aggregate_prompt_tps = (
            METRICS.prompt_eval_count / total_prompt_seconds
            if total_prompt_seconds > 0
            else 0.0
        )
        avg_request_tps = (
            METRICS.sum_request_tps / METRICS.ok if METRICS.ok > 0 else 0.0
        )

        avg_ollama_total_ms = (
            (METRICS.total_duration_ns / METRICS.ok) / 1_000_000
            if METRICS.ok > 0
            else 0.0
        )
        avg_load_ms = (
            (METRICS.load_duration_ns / METRICS.ok) / 1_000_000
            if METRICS.ok > 0
            else 0.0
        )

        headers = [
            "timestamp",
            "model",
            "device",
            "users",
            "num_ctx",
            "num_predict",
            "wait_seconds",
            "locust_requests",
            "locust_failures",
            "locust_rps",
            "avg_response_ms",
            "median_response_ms",
            "p95_response_ms",
            "p99_response_ms",
            "ollama_ok",
            "ollama_failed",
            "output_tokens",
            "output_tokens_per_second_aggregate",
            "avg_request_tokens_per_second",
            "prompt_tokens",
            "prompt_tokens_per_second_aggregate",
            "avg_ollama_total_ms",
            "avg_ollama_load_ms",
        ]

        def fmt_number(value, decimals=3):
            if value is None:
                return ""
            try:
                return f"{float(value):.{decimals}f}"
            except (TypeError, ValueError):
                return ""

        row = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "model": MODEL,
            "device": DEVICE,
            "users": BENCH_USERS,
            "num_ctx": NUM_CTX,
            "num_predict": NUM_PREDICT,
            "wait_seconds": WAIT_SECONDS,
            "locust_requests": total.num_requests,
            "locust_failures": total.num_failures,
            "locust_rps": fmt_number(total.total_rps, 4),
            "avg_response_ms": fmt_number(total.avg_response_time),
            "median_response_ms": fmt_number(total.median_response_time),
            "p95_response_ms": fmt_number(total.get_response_time_percentile(0.95)),
            "p99_response_ms": fmt_number(total.get_response_time_percentile(0.99)),
            "ollama_ok": METRICS.ok,
            "ollama_failed": METRICS.failed,
            "output_tokens": METRICS.eval_count,
            "output_tokens_per_second_aggregate": f"{aggregate_tps:.4f}",
            "avg_request_tokens_per_second": f"{avg_request_tps:.4f}",
            "prompt_tokens": METRICS.prompt_eval_count,
            "prompt_tokens_per_second_aggregate": f"{aggregate_prompt_tps:.4f}",
            "avg_ollama_total_ms": f"{avg_ollama_total_ms:.3f}",
            "avg_ollama_load_ms": f"{avg_load_ms:.3f}",
        }

        new_file = not path.exists() or path.stat().st_size == 0
        with path.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=headers)
            if new_file:
                writer.writeheader()
            writer.writerow(row)


# -----------------------------------------------------------------------------
# ORQUESTADOR: al ejecutar "python3 este_archivo.py"
# -----------------------------------------------------------------------------


def normalize_host(host: str) -> str:
    return host.rstrip("/")


def api_call(
    host: str,
    method: str,
    endpoint: str,
    payload: Optional[Dict[str, object]] = None,
    timeout: float = 900,
) -> Dict[str, object]:
    url = normalize_host(host) + endpoint
    body = None
    headers = {}

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = Request(url, data=body, headers=headers, method=method)
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def unload_model(host: str, model: str, timeout: float) -> None:
    payload = {
        "model": model,
        "prompt": "",
        "stream": False,
        "keep_alive": 0,
    }
    try:
        api_call(host, "POST", "/api/generate", payload, timeout=timeout)
    except Exception as exc:
        print(f"[WARN] No se pudo descargar {model}: {exc}")


def warmup_model(host: str, model: str, device: str, timeout: float) -> Tuple[bool, str]:
    payload = {
        "model": model,
        "prompt": "Responde únicamente con la palabra OK.",
        "stream": True,
        "keep_alive": KEEP_ALIVE,
        "options": ollama_options(device),
    }

    try:
        data = api_call(host, "POST", "/api/generate", payload, timeout=timeout)
        if data.get("error"):
            return False, str(data["error"])
        return True, "warm-up correcto"
    except HTTPError as exc:
        try:
            text = exc.read().decode("utf-8", errors="replace")
        except Exception:
            text = str(exc)
        return False, f"HTTP {exc.code}: {text[:500]}"
    except (URLError, TimeoutError, OSError) as exc:
        return False, str(exc)


def inspect_processor(host: str, model: str, timeout: float) -> str:
    """Comprueba VRAM a través de /api/ps para detectar CPU/GPU/híbrido."""
    try:
        data = api_call(host, "GET", "/api/ps", timeout=timeout)
        for item in data.get("models", []):
            if item.get("name") == model or item.get("model") == model:
                size = int(item.get("size") or 0)
                size_vram = int(item.get("size_vram") or 0)
                ctx = item.get("context_length", "?")

                if size <= 0:
                    return f"size_vram={size_vram} bytes, context={ctx}"

                pct_gpu = min(100.0, (size_vram / size) * 100)
                pct_cpu = max(0.0, 100.0 - pct_gpu)
                return (
                    f"aprox. CPU={pct_cpu:.1f}% / GPU={pct_gpu:.1f}% "
                    f"(VRAM={size_vram / (1024**3):.2f} GiB, context={ctx})"
                )
        return "modelo no visible en /api/ps"
    except Exception as exc:
        return f"no se pudo consultar /api/ps: {exc}"


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value.replace(":", "_"))


def ensure_ollama(host: str, timeout: float) -> None:
    try:
        data = api_call(host, "GET", "/api/version", timeout=timeout)
        version = data.get("version", "desconocida")
        print(f"[OK] Ollama disponible en {host} | versión {version}")
    except Exception as exc:
        raise SystemExit(
            f"ERROR: no se puede conectar con Ollama en {host}: {exc}\n"
            "Verifica que 'ollama serve' esté activo."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark secuencial de modelos Ollama con Locust: CPU/GPU y 50-200 usuarios."
    )
    parser.add_argument(
        "--host",
        default=os.getenv("OLLAMA_HOST_URL", "http://127.0.0.1:11434"),
        help="URL de Ollama (default: http://127.0.0.1:11434)",
    )
    parser.add_argument(
        "--duration",
        default=os.getenv("BENCH_DURATION", "60s"),
        help="Duración de CADA combinación de usuarios, ej. 60s, 2m, 5m (default: 60s)",
    )
    parser.add_argument(
        "--spawn-rate",
        type=float,
        default=float(os.getenv("SPAWN_RATE", "10")),
        help="Usuarios nuevos por segundo (default: 10)",
    )
    parser.add_argument(
        "--output-dir",
        default=os.getenv("BENCH_OUTPUT_DIR", "ollama_benchmark_results"),
        help="Directorio de resultados",
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=REQUEST_TIMEOUT,
        help="Timeout de cada request y warm-up en segundos (default: 900)",
    )
    parser.add_argument(
        "--models",
        nargs="*",
        default=None,
        help="Opcional: ejecutar solo estos modelos. Si se omite, ejecuta los 14.",
    )
    parser.add_argument(
        "--devices",
        nargs="*",
        choices=["cpu", "gpu"],
        default=None,
        help="Opcional: cpu, gpu o ambos (default: ambos)",
    )
    parser.add_argument(
        "--users",
        nargs="*",
        type=int,
        default=None,
        help="Opcional: niveles de usuarios (default: 50 100 150 200)",
    )
    parser.add_argument(
        "--no-full-history",
        action="store_true",
        help="No generar CSV histórico por segundo de Locust.",
    )
    return parser.parse_args()


def append_error_summary(
    summary_csv: Path, model: str, device: str, users: int, error: str
) -> None:
    error_csv = summary_csv.with_name("benchmark_errors.csv")
    new_file = not error_csv.exists() or error_csv.stat().st_size == 0
    with error_csv.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["timestamp", "model", "device", "users", "error"],
        )
        if new_file:
            writer.writeheader()
        writer.writerow(
            {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "model": model,
                "device": device,
                "users": users,
                "error": error,
            }
        )


def run_all() -> int:
    args = parse_args()

    if not LOCUST_AVAILABLE:
        raise SystemExit(
            "ERROR: Locust no está instalado en este entorno.\n"
            "Activa tu venv e instala/valida con: python3 -m pip install locust"
        )

    models = args.models or MODELS
    devices = args.devices or DEVICES
    users_list = args.users or USER_LEVELS

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_csv = output_dir / "benchmark_summary.csv"

    ensure_ollama(args.host, args.request_timeout)

    print("\n" + "=" * 78)
    print("BENCHMARK OLLAMA + LOCUST")
    print("=" * 78)
    print(f"Modelos      : {len(models)}")
    print(f"Dispositivos : {', '.join(devices)}")
    print(f"Usuarios     : {users_list}")
    print(f"Duración/run : {args.duration}")
    print(f"Spawn rate   : {args.spawn_rate} usuarios/s")
    print(f"num_ctx      : {NUM_CTX}")
    print(f"num_predict  : {NUM_PREDICT}")
    print(f"wait         : {WAIT_SECONDS}s por usuario")
    print(f"Resultados   : {output_dir}")
    print("=" * 78 + "\n")

    scenario = 0
    total_scenarios = len(models) * len(devices) * len(users_list)

    for model in models:
        for device in devices:
            print("\n" + "#" * 78)
            print(f"PREPARANDO: {model} | {device.upper()}")
            print("#" * 78)

            # Garantiza que no se reutilice un runner cargado con configuración previa.
            unload_model(args.host, model, args.request_timeout)
            time.sleep(1)

            ok, message = warmup_model(args.host, model, device, args.request_timeout)
            if not ok:
                print(f"[ERROR] Warm-up falló para {model} [{device}]: {message}")
                for users in users_list:
                    append_error_summary(summary_csv, model, device, users, message)
                print("[INFO] Se omite este bloque y se continúa con el siguiente.")
                continue

            processor = inspect_processor(args.host, model, args.request_timeout)
            print(f"[OK] {message}")
            print(f"[INFO] Carga detectada: {processor}")

            if device == "cpu" and "GPU=0.0%" not in processor:
                print(
                    "[WARN] Se solicitó CPU, pero /api/ps indica VRAM > 0 o no pudo "
                    "confirmarse. Revisa también 'ollama ps'."
                )
            if device == "gpu" and "GPU=0.0%" in processor:
                print(
                    "[WARN] Se solicitó GPU, pero el modelo parece estar 100% en CPU. "
                    "Revisa drivers/CUDA y 'ollama ps'."
                )

            for users in users_list:
                scenario += 1
                prefix_dir = output_dir / safe_name(model) / device / f"u{users}"
                prefix_dir.mkdir(parents=True, exist_ok=True)
                csv_prefix = prefix_dir / "locust"

                env = os.environ.copy()
                env.update(
                    {
                        "OLLAMA_MODEL": model,
                        "OLLAMA_DEVICE": device,
                        "BENCH_USERS": str(users),
                        "BENCH_SUMMARY_CSV": str(summary_csv),
                        "REQUEST_TIMEOUT": str(args.request_timeout),
                    }
                )

                cmd = [
                    sys.executable,
                    "-m",
                    "locust",
                    "-f",
                    str(Path(__file__).resolve()),
                    "--headless",
                    "--host",
                    args.host,
                    "-u",
                    str(users),
                    "-r",
                    str(args.spawn_rate),
                    "-t",
                    args.duration,
                    "--stop-timeout",
                    "5",
                    "--csv",
                    str(csv_prefix),
                ]

                if not args.no_full_history:
                    cmd.append("--csv-full-history")

                print("\n" + "-" * 78)
                print(
                    f"ESCENARIO {scenario}/{total_scenarios}: "
                    f"{model} | {device.upper()} | {users} usuarios"
                )
                print("-" * 78)

                completed = subprocess.run(cmd, env=env)
                if completed.returncode != 0:
                    err = f"Locust terminó con código {completed.returncode}"
                    print(f"[WARN] {err}")
                    append_error_summary(summary_csv, model, device, users, err)

                # Pausa pequeña entre niveles para estabilizar la cola del servidor.
                time.sleep(2)

            # Al cambiar CPU/GPU o modelo, se descarga explícitamente.
            unload_model(args.host, model, args.request_timeout)
            time.sleep(1)

    print("\n" + "=" * 78)
    print("BENCHMARK FINALIZADO")
    print("=" * 78)
    print(f"Resumen maestro : {summary_csv}")
    print(f"Resultados Locust: {output_dir}")
    print("\nCSV por escenario:")
    print("  locust_stats.csv")
    print("  locust_stats_history.csv")
    print("  locust_failures.csv")
    print("  locust_exceptions.csv")
    print("=" * 78)

    return 0


if __name__ == "__main__":
    raise SystemExit(run_all())

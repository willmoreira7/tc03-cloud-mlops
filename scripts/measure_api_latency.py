"""Measures end-to-end latency of the inference API.

This is the Etapa 1 deliverable: the baseline the ONNX optimisation of Etapa 4
will be compared against. It is deliberately different from the model-only
measurement taken in the notebooks -- this one goes over HTTP and includes
serialisation and framework overhead, which is what a caller actually waits
for.

Usage:
    python scripts/measure_api_latency.py --url http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import EVALUATION_DIR, load_config  # noqa: E402

LAUDOS = [
    "Patient presented with acute myocardial infarction and severe coronary "
    "artery stenosis requiring immediate ventricular assessment.",
    "Endoscopic evaluation of the gastric mucosa revealed chronic inflammation "
    "of the intestinal lining without evidence of malignancy.",
    "Histological examination of the biopsy specimen confirmed malignant tumor "
    "cells with neoplastic proliferation in the surrounding tissue.",
    "Neurological assessment demonstrated progressive cognitive decline with "
    "motor impairment and recurrent episodes of seizure activity.",
    "Laboratory findings indicate a systemic inflammatory response with febrile "
    "episodes and generalized edema of unclear origin.",
]


def _percentis(amostras: list[float]) -> dict[str, float]:
    """Summarises a latency sample.

    Args:
        amostras: Measured latencies in milliseconds.

    Returns:
        Mapping of statistic name to value.
    """
    ordenado = sorted(amostras)
    return {
        "p50_ms": round(statistics.quantiles(ordenado, n=100)[49], 3),
        "p95_ms": round(statistics.quantiles(ordenado, n=100)[94], 3),
        "p99_ms": round(statistics.quantiles(ordenado, n=100)[98], 3),
        "media_ms": round(statistics.fmean(ordenado), 3),
        "min_ms": round(ordenado[0], 3),
        "max_ms": round(ordenado[-1], 3),
        "n_chamadas": len(ordenado),
    }


def medir(url: str, warmup: int, calls: int) -> dict:
    """Runs the measurement against a live API.

    Args:
        url: Base URL of the service.
        warmup: Calls discarded before measuring.
        calls: Number of measured calls.

    Returns:
        Mapping with the latency summary and the server-side comparison.
    """
    endpoint = f"{url.rstrip('/')}/predict"
    with httpx.Client(timeout=30.0) as client:
        saude = client.get(f"{url.rstrip('/')}/health")
        saude.raise_for_status()
        print(f"Servico: {saude.json()}")

        for indice in range(warmup):
            client.post(endpoint, json={"texto": LAUDOS[indice % len(LAUDOS)]})

        cliente_ms: list[float] = []
        servidor_ms: list[float] = []
        for indice in range(calls):
            payload = {"texto": LAUDOS[indice % len(LAUDOS)]}
            inicio = time.perf_counter()
            resposta = client.post(endpoint, json=payload)
            cliente_ms.append((time.perf_counter() - inicio) * 1000.0)
            resposta.raise_for_status()
            servidor_ms.append(resposta.json()["latencia_ms"])

    return {
        "url": url,
        "fim_a_fim": _percentis(cliente_ms),
        "inferencia_servidor": _percentis(servidor_ms),
    }


def main() -> None:
    """Entry point."""
    config = load_config()["latency"]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--warmup", type=int, default=int(config["warmup_calls"]))
    parser.add_argument("--calls", type=int, default=int(config["measured_calls"]))
    parser.add_argument(
        "--saida", default=str(EVALUATION_DIR / "api_latency_baseline.json")
    )
    args = parser.parse_args()

    resultado = medir(args.url, args.warmup, args.calls)

    fim = resultado["fim_a_fim"]
    servidor = resultado["inferencia_servidor"]
    print(f"\n{'':22s} {'p50':>10s} {'p95':>10s} {'p99':>10s} {'media':>10s}")
    for rotulo, dados in (("Fim a fim (HTTP)", fim), ("Inferencia (modelo)", servidor)):
        print(
            f"{rotulo:22s} {dados['p50_ms']:10.2f} {dados['p95_ms']:10.2f} "
            f"{dados['p99_ms']:10.2f} {dados['media_ms']:10.2f}"
        )
    overhead = fim["p95_ms"] - servidor["p95_ms"]
    print(f"\nOverhead de HTTP e framework no p95: {overhead:.2f} ms")

    destino = Path(args.saida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8") as handle:
        json.dump(resultado, handle, indent=2, ensure_ascii=False)
    print(f"Resultado salvo em {destino}")


if __name__ == "__main__":
    main()

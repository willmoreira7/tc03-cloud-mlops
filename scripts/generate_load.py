"""Generates synthetic load against the inference API to populate the dashboard.

This is the Etapa 3 deliverable that makes the Grafana panels show real data
after the stack comes up. It sends a mix of valid and invalid requests so the
error-rate panel has something to display too.

Usage:
    python scripts/generate_load.py --url http://localhost:8000 --duration 60
"""

from __future__ import annotations

import argparse
import random
import sys
import threading
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

LAUDOS_VALIDOS = [
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

# 1 in 10 requests is deliberately invalid so the 422 panel has signal.
LAUDOS_INVALIDOS = ["", "curto demais", "   "]


def _worker(url: str, stop: threading.Event, seed: int) -> None:
    """Sends requests until the stop flag is set.

    Args:
        url: Base URL of the API.
        stop: Event that signals the worker to stop.
        seed: Seed for the per-worker RNG so runs are reproducible.
    """
    endpoint = f"{url.rstrip('/')}/predict"
    rng = random.Random(seed)

    with httpx.Client(timeout=10.0) as client:
        while not stop.is_set():
            if rng.random() < 0.1:
                payload = {"texto": rng.choice(LAUDOS_INVALIDOS)}
            else:
                payload = {"texto": rng.choice(LAUDOS_VALIDOS)}
            try:
                client.post(endpoint, json=payload)
            except httpx.HTTPError:
                pass
            time.sleep(rng.uniform(0.05, 0.2))


def main() -> None:
    """Entry point: parses args, runs workers, prints a summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Segundos de carga a gerar (default: 60).",
    )
    parser.add_argument(
        "--workers", type=int, default=4, help="Requisicoes concorrentes (default: 4)."
    )
    args = parser.parse_args()

    print(
        f"Gerando carga contra {args.url} por {args.duration}s "
        f"com {args.workers} workers..."
    )

    stop = threading.Event()
    workers = [
        threading.Thread(
            target=_worker,
            args=(args.url, stop, 42 + i),
            daemon=True,
        )
        for i in range(args.workers)
    ]

    start = time.perf_counter()
    for w in workers:
        w.start()

    try:
        while time.perf_counter() - start < args.duration:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuario.")

    stop.set()
    for w in workers:
        w.join(timeout=5.0)

    elapsed = time.perf_counter() - start
    print(
        f"Concluido em {elapsed:.1f}s. "
        "Abra o Grafana em http://localhost:3000 (admin/admin)."
    )


if __name__ == "__main__":
    main()

"""Checks whether this machine can run the project, and says what is missing.

Exists so that nobody has to guess why something failed. Every check reports
the exact command that fixes it, and the script never stops at the first
problem -- it reports all of them at once.

Usage:
    uv run python scripts/verify_setup.py
"""

from __future__ import annotations

import importlib
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

OK = "[ OK ]"
FALTA = "[FALTA]"
AVISO = "[AVISO]"

PACOTES_BASE = ["fastapi", "uvicorn", "joblib", "numpy", "sklearn", "yaml", "pydantic"]
PACOTES_DEV = ["pytest", "ruff", "jupyter_core", "matplotlib", "seaborn"]


class Relatorio:
    """Collects check results and prints a verdict."""

    def __init__(self) -> None:
        self.problemas: list[str] = []
        self.avisos: list[str] = []

    def ok(self, mensagem: str) -> None:
        print(f"{OK} {mensagem}")

    def falta(self, mensagem: str, correcao: str) -> None:
        print(f"{FALTA} {mensagem}")
        self.problemas.append(correcao)

    def aviso(self, mensagem: str, nota: str) -> None:
        print(f"{AVISO} {mensagem}")
        self.avisos.append(nota)


def checar_python(rel: Relatorio) -> None:
    """Verifies the interpreter version."""
    versao = sys.version_info
    texto = f"Python {versao.major}.{versao.minor}.{versao.micro}"
    if (versao.major, versao.minor) >= (3, 12):
        rel.ok(texto)
    else:
        rel.falta(f"{texto} - o projeto exige 3.12+", "uv sync --group dev")


def checar_pacotes(rel: Relatorio) -> None:
    """Verifies that runtime and dev dependencies are importable."""
    faltando_base = [p for p in PACOTES_BASE if not _importavel(p)]
    if faltando_base:
        rel.falta(
            f"Dependencias de runtime ausentes: {', '.join(faltando_base)}",
            "uv sync --group dev",
        )
    else:
        rel.ok(f"Dependencias de runtime ({len(PACOTES_BASE)} pacotes)")

    faltando_dev = [p for p in PACOTES_DEV if not _importavel(p)]
    if faltando_dev:
        rel.falta(
            f"Dependencias de desenvolvimento ausentes: {', '.join(faltando_dev)}",
            "uv sync --group dev",
        )
    else:
        rel.ok(f"Dependencias de desenvolvimento ({len(PACOTES_DEV)} pacotes)")


def _importavel(nome: str) -> bool:
    """Returns whether a module can be imported."""
    try:
        importlib.import_module(nome)
    except ImportError:
        return False
    return True


def checar_projeto(rel: Relatorio) -> None:
    """Verifies that the project's own modules import and config loads."""
    try:
        from src.config import load_config

        config = load_config()
        rel.ok(f"Modulos do projeto (modelo servido: {config['serving']['model']})")
    except Exception as erro:  # noqa: BLE001 - queremos reportar qualquer falha
        rel.falta(f"Falha ao importar src/: {erro}", "uv sync --group dev")


def checar_dados(rel: Relatorio) -> None:
    """Reports whether a corpus is present."""
    from src.data.loader import raw_files_present

    presentes, ausentes = raw_files_present()
    if presentes and not ausentes:
        rel.ok(f"Corpus completo em data/raw ({', '.join(presentes)})")
    elif presentes:
        rel.aviso(
            f"Corpus parcial: falta {', '.join(ausentes)}",
            "As metricas vao diferir de uma execucao com o corpus completo.",
        )
    else:
        from src.data.loader import DATASET_URL

        rel.aviso(
            "Nenhum corpus em data/raw",
            f"Baixe o corpus em {DATASET_URL} e extraia os CSVs em data/raw/ "
            "-- ou, para so validar a stack: "
            "uv run python scripts/gen_synthetic_data.py --rows 3000",
        )


def checar_modelo(rel: Relatorio) -> None:
    """Reports whether the served artefact exists."""
    from src.api.model import get_classifier

    classifier = get_classifier()
    if classifier.path.exists():
        tamanho = classifier.path.stat().st_size / (1024 * 1024)
        rel.ok(f"Artefato do modelo ({classifier.name}, {tamanho:.2f} MB)")
    else:
        rel.aviso(
            f"Artefato ausente: {classifier.path}",
            "Necessario antes de construir a imagem: "
            "uv run python scripts/train_serving_model.py",
        )


def checar_docker(rel: Relatorio) -> None:
    """Reports whether Docker is installed and its daemon is reachable."""
    if shutil.which("docker") is None:
        rel.aviso("Docker nao encontrado", "Necessario apenas para rodar a API.")
        return
    try:
        resultado = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        rel.aviso("Docker instalado, daemon inacessivel", "Inicie o Docker.")
        return

    if resultado.returncode == 0:
        rel.ok(f"Docker {resultado.stdout.strip()}")
    else:
        rel.aviso("Docker instalado, daemon nao respondeu", "Inicie o Docker.")


def main() -> None:
    """Runs every check and prints the verdict."""
    print("Verificando o ambiente do projeto\n")
    rel = Relatorio()

    checar_python(rel)
    checar_pacotes(rel)
    checar_projeto(rel)
    checar_dados(rel)
    checar_modelo(rel)
    checar_docker(rel)

    print()
    if rel.problemas:
        print("AMBIENTE INCOMPLETO. Execute:")
        for correcao in dict.fromkeys(rel.problemas):
            print(f"  {correcao}")
        raise SystemExit(1)

    print("Ambiente pronto.")
    if rel.avisos:
        print("\nPendencias antes de subir a API:")
        for nota in dict.fromkeys(rel.avisos):
            print(f"  - {nota}")


if __name__ == "__main__":
    main()

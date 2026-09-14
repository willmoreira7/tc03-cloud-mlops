"""Tests for text cleaning, urgency mapping and split generation."""

from __future__ import annotations

import pandas as pd
import pytest

from src.config import load_config
from src.data.preprocessing import (
    class_distribution,
    clean_text,
    drop_degenerate,
    make_splits,
    map_urgency,
)

TEXTO_LONGO = "achado clinico com descricao suficientemente longa numero {}"


def _corpus(n_por_categoria: int = 40) -> pd.DataFrame:
    linhas = [
        {
            "texto": TEXTO_LONGO.format(f"{categoria}-{i}"),
            "categoria_original": categoria,
        }
        for categoria in ("1", "2", "3", "4", "5")
        for i in range(n_por_categoria)
    ]
    return pd.DataFrame(linhas)


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("  laudo   com\tespacos\n extras ", "laudo com espacos extras"),
        ("sem alteracao", "sem alteracao"),
        (None, ""),
        (42, ""),
    ],
    ids=["espacos", "limpo", "none", "nao-string"],
)
def test_clean_text_normaliza_espacos(entrada: object, esperado: str) -> None:
    assert clean_text(entrada) == esperado


def test_map_urgency_segue_o_config() -> None:
    mapping = load_config()["urgency_mapping"]
    frame = pd.DataFrame(
        {"texto": ["a"] * len(mapping), "categoria_original": list(mapping)}
    )
    resultado = map_urgency(frame)
    assert resultado["urgencia"].tolist() == list(mapping.values())


def test_map_urgency_aceita_categoria_numerica() -> None:
    """O CSV bruto chega com a categoria como int; o config usa string."""
    frame = pd.DataFrame({"texto": ["a"], "categoria_original": [4]})
    assert map_urgency(frame)["urgencia"].tolist() == ["urgente"]


def test_map_urgency_descarta_categoria_sem_mapeamento() -> None:
    """Categoria desconhecida sai do corpus, nunca cai numa classe padrao."""
    frame = pd.DataFrame({"texto": ["a", "b"], "categoria_original": ["4", "99"]})
    resultado = map_urgency(frame)
    assert len(resultado) == 1
    assert resultado["urgencia"].iloc[0] == "urgente"


def test_drop_degenerate_remove_curtos_vazios_e_duplicados() -> None:
    minimo = int(load_config()["data"]["min_text_chars"])
    valido = "x" * minimo
    frame = pd.DataFrame(
        {
            "texto": [valido, f"  {valido}  ", "x" * (minimo - 1), "   ", None],
            "urgencia": ["normal"] * 5,
        }
    )
    resultado = drop_degenerate(frame)
    # A copia com espacos vira duplicata depois da limpeza.
    assert resultado["texto"].tolist() == [valido]


def test_make_splits_respeita_proporcoes_e_nao_vaza() -> None:
    frame = drop_degenerate(map_urgency(_corpus()))
    splits = make_splits(frame)
    ratios = load_config()["split"]

    total = sum(len(parte) for parte in splits.values())
    assert total == len(frame)
    for nome, chave in (("train", "train_ratio"), ("val", "val_ratio")):
        assert len(splits[nome]) / total == pytest.approx(ratios[chave], abs=0.02)

    textos = [set(parte["texto"]) for parte in splits.values()]
    assert not textos[0] & textos[1]
    assert not textos[0] & textos[2]
    assert not textos[1] & textos[2]


def test_make_splits_estratifica_por_urgencia() -> None:
    frame = drop_degenerate(map_urgency(_corpus()))
    splits = make_splits(frame)
    geral = class_distribution(frame)["proporcao"]
    for parte in splits.values():
        assert class_distribution(parte)["proporcao"].to_dict() == pytest.approx(
            geral.to_dict(), abs=0.05
        )


def test_make_splits_e_deterministico() -> None:
    frame = drop_degenerate(map_urgency(_corpus()))
    primeira, segunda = make_splits(frame), make_splits(frame)
    for nome in primeira:
        pd.testing.assert_frame_equal(primeira[nome], segunda[nome])

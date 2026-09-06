# 📓 Notebooks de Análise e Seleção de Modelo

> Estrutura, propósito e ordem de execução dos notebooks que selecionam o modelo de
> classificação de urgência de laudos médicos.

---

## 🎯 Princípio Central

Os notebooks existem para **decidir qual modelo vai para produção** — e para deixar essa
decisão auditável. Duas regras sustentam isso:

| Regra | Consequência de quebrar |
|-------|------------------------|
| Os splits são gerados **uma única vez**, em `02_preprocessing` | Cada modelo mediria em dados diferentes; a comparação vira ruído |
| O critério de promoção é **declarado antes** de rodar os modelos | Vira escolha do vencedor primeiro e da métrica depois |

> ⚠️ **Notebook analisa, módulo executa.** O notebook é o registro da análise. O que roda
> automatizado na DAG do Airflow são os módulos de `src/` — a DAG nunca executa `.ipynb`.

---

## 🗂️ Estrutura

```
notebooks/
├── 01_eda.ipynb                   # Análise exploratória do corpus
├── 02_preprocessing.ipynb         # Mapeamento de urgência, limpeza e splits
├── 03_baseline_dummy.ipynb        # Piso de comparação (DummyClassifier)
├── 04_tfidf_logreg.ipynb          # TF-IDF + Logistic Regression
├── 05_tfidf_random_forest.ipynb   # TF-IDF + Random Forest
├── 06_tfidf_linear_svc.ipynb      # TF-IDF + LinearSVC
├── 07_model_comparison.ipynb      # Comparação e decisão de promoção
├── 08_onnx_optimization.ipynb     # Exportação ONNX e comparativo de latência
└── outputs/
    ├── eda/plots/
    └── model_comparison/plots/
```

### Fluxo de execução

```
01_eda
   ↓
02_preprocessing          ← gera os splits usados por TODOS os modelos
   ↓
03_baseline_dummy ─┐
04_tfidf_logreg ───┤
05_tfidf_rf ───────┤  (independentes entre si)
06_tfidf_svc ──────┘
   ↓
07_model_comparison       ← decide o modelo promovido
   ↓
08_onnx_optimization      ← otimiza o modelo promovido (Etapa 4)
```

---

## 1️⃣ EDA (`01_eda.ipynb`)

**Propósito:** entender o corpus antes de modelar.

| | |
|---|---|
| **Inputs** | `data/raw/<dataset>.csv` |
| **Outputs** | `data/processed/data_profile.json`, gráficos em `outputs/eda/plots/` |

**Etapas:**
1. Carregamento e verificação inicial (nulos, duplicatas, encoding)
2. Distribuição do comprimento dos textos (tokens e caracteres)
3. Distribuição das categorias originais do dataset
4. Vocabulário: termos mais frequentes, cauda longa, stopwords médicas
5. Identificação de textos degenerados (vazios, truncados, duplicados)

> 💡 O comprimento dos textos alimenta diretamente a decisão de `max_features` do TF-IDF —
> que por sua vez é o principal fator de latência e de tamanho do artefato.

---

## 2️⃣ Pré-processamento e Splits (`02_preprocessing.ipynb`)

**Propósito:** produzir, de uma vez só, os dados que todos os notebooks de modelo
consomem. **É o notebook mais crítico do fluxo.**

| | |
|---|---|
| **Inputs** | `data/raw/<dataset>.csv`, `data/processed/data_profile.json` |
| **Outputs** | `data/processed/{train,val,test}.parquet`, `data/processed/split_meta.json`, `data/processed/label_mapping.json` |

**Etapas:**
1. Limpeza textual (normalização, remoção de ruído estrutural)
2. **Mapeamento categoria original → urgência** (`normal` / `atencao` / `urgente`),
   conforme a regra definida em [DATASET.md](DATASET.md)
3. Remoção de duplicatas e textos degenerados
4. Split **estratificado** treino/validação/teste (70/15/15), `random_state=42`
5. Registro do hash SHA256 do dataset e das proporções por classe em `split_meta.json`

> ⚠️ **A vetorização TF-IDF não acontece aqui.** Ela é ajustada dentro do pipeline de cada
> modelo, **apenas no split de treino**. Vetorizar antes do split vaza estatística do
> conjunto de teste para dentro do vocabulário.

---

## 3️⃣ Baseline — Dummy (`03_baseline_dummy.ipynb`)

**Propósito:** estabelecer o piso. Qualquer modelo que não superar isso não justifica sua
própria existência.

| | |
|---|---|
| **Modelo** | `DummyClassifier(strategy="stratified")` e `strategy="most_frequent"` |
| **Outputs** | `models/dummy/metrics.json` |

> 💡 Em dataset desbalanceado, o `most_frequent` costuma exibir acurácia alta e
> `f1_macro` péssimo. É a demonstração mais direta de por que a acurácia **não** é a
> métrica de promoção deste projeto.

---

## 4️⃣ · 5️⃣ · 6️⃣ Modelos Candidatos

Os três notebooks seguem a **mesma estrutura**, mudando apenas o estimador. Isso é
proposital: mantém a comparação justa e o código previsível.

| Notebook | Pipeline | Por que está na disputa |
|----------|----------|------------------------|
| `04_tfidf_logreg` | `TfidfVectorizer` → `LogisticRegression` | Rápido, artefato pequeno, probabilidades calibráveis |
| `05_tfidf_random_forest` | `TfidfVectorizer` → `RandomForestClassifier` | Sugerido explicitamente no PDF do desafio |
| `06_tfidf_linear_svc` | `TfidfVectorizer` → `LinearSVC` | Forte em texto esparso de alta dimensionalidade |

**Etapas (idênticas nos três):**
1. Carregar `train`/`val` de `data/processed/`
2. Montar o `Pipeline` do scikit-learn (vetorizador + estimador, sempre juntos)
3. Busca de hiperparâmetros na **validação** — nunca no teste
4. Treino final com a melhor configuração
5. Avaliação em validação e teste com as métricas oficiais
6. **Medição de latência de inferência** (ver protocolo abaixo)
7. Persistir `models/<nome>/model.pkl` e `models/<nome>/metrics.json`

> ⚠️ **Ponto de atenção sobre o Random Forest.** O PDF sugere "TF-IDF + Random Forest",
> mas em texto esparso de alta dimensão a RF tende a gerar artefato grande e inferência
> mais lenta que um modelo linear. Se a comparação confirmar isso, é um **resultado a
> defender no vídeo**, não um problema a esconder: mostra que a escolha foi medida, e não
> herdada do enunciado. O PDF diz "Random Forest **ou modelo leve similar**".

---

## 📏 Protocolo de Medição de Latência

Aplicado de forma idêntica em todos os notebooks de modelo — sem isso o comparativo da
Etapa 4 não sustenta os 20% de Modelagem e Otimização.

| Regra | Valor |
|-------|-------|
| Descartar chamadas de aquecimento | primeiras 50 |
| Número de medições | ≥ 1.000 predições single-sample |
| Reportar | p50, p95, p99 e média |
| Ambiente | mesma máquina, sem outras cargas |
| Modo | uma amostra por chamada (é assim que a API vai receber) |

> ⚠️ Medir em lote (`predict` com 1.000 linhas de uma vez) e dividir por 1.000 **não** é
> a latência da API. O batch amortiza custo que a requisição real paga integralmente.

---

## 7️⃣ Comparação e Promoção (`07_model_comparison.ipynb`)

**Propósito:** avaliar todos os modelos no mesmo split de teste e **decidir qual vai para
produção**.

| | |
|---|---|
| **Inputs** | `data/processed/test.parquet`, `models/*/model.pkl`, `models/*/metrics.json` |
| **Outputs** | `models/evaluation/metrics_comparison.csv`, **`docs/MODEL_CARD.md`**, matrizes de confusão em `outputs/model_comparison/plots/` |

> 🔴 **O Model Card sai em `docs/`, nunca em `models/`.** O `models/` é ignorado pelo
> Git: um Model Card gerado ali existe em disco e nunca chega ao repositório. Pior, um
> `test -f models/MODEL_CARD.md` no CI passaria, dando falsa confiança. Para o que
> precisa ser lido por quem clona o projeto, a checagem correta é `git ls-files`.

### 📊 Métricas oficiais

| Métrica | O que mede | Papel |
|---------|-----------|-------|
| **F1-macro** | Média não ponderada do F1 por classe | 🥇 **Métrica de promoção** |
| **Recall da classe `urgente`** | Quantos casos críticos foram capturados | 🛡️ Trava de segurança |
| **Precision por classe** | Ruído em cada fila de triagem | Diagnóstico |
| **Matriz de confusão** | Para onde vão os erros | Análise clínica do erro |
| **Latência p95** | Tempo de resposta sob a cauda | 🚧 Restrição |
| **Tamanho serializado** | Impacto na imagem Docker e no startup | Trade-off |

**Por que F1-macro e não acurácia:** a distribuição de urgência é desbalanceada por
natureza — a maioria dos laudos é `normal`. Acurácia premiaria um modelo que ignora a
classe `urgente`, que é exatamente a que importa.

### 🏆 Critério de Promoção

Declarado **antes** de rodar os modelos:

> Entre os modelos que satisfazem as duas restrições — **recall da classe `urgente` ≥
> limiar mínimo** e **latência p95 dentro do teto** — é promovido o de maior
> **F1-macro** no split de teste. Empate técnico (diferença < 1 pp) é resolvido pelo
> menor p95.

| Parâmetro | Valor | Definido em |
|-----------|-------|-------------|
| Limiar de recall `urgente` | _a definir_ | Etapa 0, antes de treinar |
| Teto de latência p95 | _a definir_ | Após o baseline da Etapa 1 |

> ⚠️ Os dois parâmetros precisam ser fixados **antes** do `07_model_comparison` rodar.
> Ajustá-los depois de ver os resultados invalida o critério.

### 🔒 A regra vive em código, não no notebook

A função que escolhe o vencedor vive em `src/evaluation/promotion.py` e é única: o
notebook, a DAG do Airflow e a API a consultam. Se cada um implementasse a própria regra,
os três divergiriam silenciosamente sobre qual é o modelo de produção.

```python
# src/evaluation/promotion.py
_PROMOTION_METRIC = "f1_macro"


def select_promoted_model(comparison: pd.DataFrame) -> str:
    """Retorna o modelo promovido entre os que passam nas restricoes."""
    eligible = comparison[
        (comparison["recall_urgente"] >= MIN_RECALL_URGENTE)
        & (comparison["latency_p95_ms"] <= MAX_LATENCY_P95_MS)
    ]
    if eligible.empty:
        raise ValueError("Nenhum modelo satisfaz as restricoes de promocao")
    return str(eligible[_PROMOTION_METRIC].idxmax())
```

---

## 8️⃣ Otimização ONNX (`08_onnx_optimization.ipynb`)

**Propósito:** aplicar a otimização de latência exigida na Etapa 4 sobre o modelo
promovido, e medir o ganho.

| | |
|---|---|
| **Inputs** | `models/<promovido>/model.pkl`, `data/processed/test.parquet` |
| **Outputs** | `models/production/model.onnx`, `models/evaluation/latency_comparison.csv` |

**Etapas:**
1. Converter o `Pipeline` completo para ONNX com `skl2onnx`
2. **Validar equivalência de predições** entre `.pkl` e `.onnx` no split de teste
3. Medir latência do ONNX Runtime com o mesmo protocolo da seção anterior
4. Comparar tamanho do artefato
5. Preencher a tabela comparativa do [ROADMAP.md](ROADMAP.md)

> ⚠️ **Risco conhecido:** a conversão do `TfidfVectorizer` para ONNX é suportada pelo
> `skl2onnx`, mas é a parte mais frágil do processo (tokenização e vocabulário). Vale
> validar essa conversão cedo, ainda na Etapa 1 — descobrir na Etapa 4 que o pipeline não
> converte deixaria 20% da nota em risco sem tempo de reagir. Alternativa de contingência:
> quantização do estimador, também aceita pelo enunciado.

> ✅ **Passo obrigatório:** o modelo ONNX só substitui o `.pkl` na API depois que a
> equivalência de predições for verificada. Um modelo mais rápido que responde diferente
> não é uma otimização.

---

## ✅ Checklist de Qualidade

Aplicável a todos os notebooks:

- [ ] `RANDOM_SEED = 42` fixado na primeira célula
- [ ] Célula inicial padronizada (imports, seed, paths, logging)
- [ ] Nenhuma decisão de split ou vetorização fora do `02_preprocessing`
- [ ] Métricas calculadas em validação durante o desenvolvimento; teste só no final
- [ ] Latência medida com o protocolo desta página
- [ ] Funções com type hints e docstring Google Style
- [ ] Lógica reutilizável movida para `src/` (o notebook chama, não reimplementa)
- [ ] Outputs persistidos em `models/` e `outputs/`, nunca só na saída da célula
- [ ] Notebook executa do início ao fim sem erro após *Restart & Run All*

---

**Última atualização:** 2026-09-05

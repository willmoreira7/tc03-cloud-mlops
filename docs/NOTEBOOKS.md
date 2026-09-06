# 📓 Notebooks de Análise e Seleção de Modelo

> Estrutura, propósito e ordem de execução dos notebooks que selecionam o modelo de
> classificação de urgência de laudos médicos.

> ✅ **Notebooks `01` a `07` executados**, com saídas salvas nos arquivos. Resultado
> consolidado em [MODEL_CARD.md](MODEL_CARD.md) e resumido em
> [Resultado da seleção](#-resultado-da-seleção).

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
| Número de medições | até 1.000 predições single-sample |
| Orçamento de tempo | 45 s, respeitando um mínimo de 200 medições |
| Reportar | p50, p95, p99, média e **número real de chamadas** |
| Ambiente | mesma máquina, sem outras cargas |
| Modo | uma amostra por chamada (é assim que a API vai receber) |

Os parâmetros ficam em [`configs/model_config.yaml`](../configs/model_config.yaml), em
`latency`.

> ℹ️ **Por que existe orçamento de tempo.** Um Random Forest sobre TF-IDF pode passar de
> 300 ms por chamada — 1.000 medições levariam mais de cinco minutos só para medir. O
> orçamento corta isso sem enviesar o resultado: a precisão do percentil cai, o valor
> esperado não muda. Por isso o número real de chamadas é reportado em
> `latency_n_calls` e deve constar no Model Card — um p99 estimado com 200 amostras é
> mais ruidoso que um com 1.000, e isso precisa estar visível.

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

| Parâmetro | Valor | Onde |
|-----------|-------|------|
| Métrica de promoção | `f1_macro` | `configs/model_config.yaml` |
| Limiar de recall `urgente` | 0,60 | `configs/model_config.yaml` |
| Teto de latência p95 | 15 ms | `configs/model_config.yaml` |
| Limiar de empate técnico | 0,01 | `src/evaluation/promotion.py` |

> ⚠️ Os parâmetros foram fixados **antes** do `07_model_comparison` rodar. Ajustá-los
> depois de ver os resultados invalidaria o critério — se for necessário revisá-los, a
> mudança precisa ser registrada explicitamente e todos os modelos reavaliados.

---

## 🏆 Resultado da Seleção

Execução sobre o corpus real (11.227 documentos, teste com 1.685).

| Modelo | F1-macro | Recall `urgente` | p95 (ms) | Tamanho | Situação |
|--------|----------|------------------|----------|---------|----------|
| **tfidf_linear_svc** | **0,7582** | 0,8118 | 3,14 | 1,23 MB | ✅ **Promovido** |
| tfidf_logreg | 0,7489 | 0,7957 | 3,22 | 1,23 MB | Elegível |
| tfidf_random_forest | 0,7273 | 0,8414 | 210,63 | 72,17 MB | ❌ Excluído por latência |
| dummy_stratified | 0,3388 | 0,2339 | 5,13 | 0,77 MB | ❌ Piso |
| dummy_most_frequent | 0,1951 | 0,0000 | 2,71 | 0,77 MB | ❌ Piso |

### O que a comparação mostrou

**1. A acurácia teria escolhido o pior modelo.** O `dummy_most_frequent` tem acurácia
0,4136 — maior que a do `dummy_stratified` (0,3579) — e **nunca prediz `urgente`**
(recall 0,0000). É a justificativa empírica do F1-macro como métrica de promoção.

**2. O Random Forest sugerido no enunciado perdeu nos dois eixos que importam.** F1-macro
menor que os modelos lineares, **67x mais lento** (210,63 ms contra 3,14 ms) e **59x
maior** (72,17 MB contra 1,23 MB). Ele só vence no recall de `urgente` (0,8414). O
enunciado admite "Random Forest **ou modelo leve similar**" — agora há número medido para
justificar a escolha em vez de segui-lo por inércia.

**3. A promoção foi decidida por desempate, não por qualidade.** A diferença entre
`tfidf_linear_svc` e `tfidf_logreg` é de 0,0093 em F1-macro — dentro do empate técnico. O
desempate por p95 teve margem de 0,07 ms, que é ruído de medição. Os dois modelos são
equivalentes; a regra apenas escolheu um de forma reproduzível. Ver a
[decisão em aberto](MODEL_CARD.md#-decisão-em-aberto) sobre `predict_proba`.

**4. Não houve overfitting na busca.** Nenhum candidato variou mais que ±0,008 de F1-macro
entre validação e teste.

**5. O erro clinicamente caro persiste.** 49 de 372 casos `urgente` (13,2%) foram
classificados como `normal` pelo modelo promovido.

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

## 🧹 Higienização dos Notebooks

### ✅ `nbqa` — lint dentro dos notebooks

O `ruff` cobre `src/`, `scripts/` e `tests/`, mas ignora `.ipynb`. Sem o `nbqa`, o código
dos notebooks — que é onde a análise acontece — ficaria sem verificação nenhuma.

```bash
uv run nbqa ruff notebooks/
uv run nbqa ruff notebooks/ --fix
```

**E402 é a única regra relaxada.** Notebook importa conforme a narrativa avança, não tudo
na primeira célula; exigir o contrário quebraria a leitura. `F401` (import morto), `F821`
(nome indefinido) e `E501` (linha longa) continuam valendo.

`display` está declarado em `builtins` no `pyproject.toml`: é builtin do kernel Jupyter, e
sem isso o ruff acusaria F821 em toda chamada.

> ℹ️ O `nbqa` converte cada notebook para um `.py` temporário antes de chamar o ruff. Por
> isso a exceção fica em `[tool.nbqa.addopts]`, e não em `per-file-ignores` com padrão
> `"*.ipynb"` — esse padrão nunca casaria com o arquivo temporário.

### ❌ `nbstripout` — decisão de **não** usar

O `nbstripout` remove as saídas dos notebooks no commit. Aqui os notebooks são
versionados **com as saídas**: gráficos da EDA, matrizes de confusão e a tabela de
comparação ficam visíveis no repositório.

| Argumento a favor do `nbstripout` | Por que não pesa neste projeto |
|-----------------------------------|-------------------------------|
| Diff de notebook fica legível | O notebook é **entregável de análise**, não só código-fonte |
| Evita conflito de merge no JSON | Equipe pequena, notebooks com donos distintos — não é o gargalo |
| Repositório mais leve | 372 KB no total; irrelevante |
| Evita vazar dados nas saídas | ⚠️ **Legítimo, mas não se aplica hoje** — ver abaixo |

**Motivo da decisão:** quem clona o repositório precisa conseguir **ver o resultado da
análise sem executar nada**. Um avaliador que não tenha o corpus, ou que não consiga
montar o ambiente, ainda assim lê as métricas, os gráficos e a matriz de confusão
diretamente no GitHub. Apagar as saídas transferiria para o leitor o custo de reproduzir
tudo só para enxergar qualquer número.

> 🔴 **O que mudaria essa decisão.** As saídas versionadas incluem trechos de abstracts
> reais impressos (`raw.head(3)` no `01_eda`). No corpus público isso é aceitável. **Se o
> projeto passar a usar laudos hospitalares reais, essas saídas viram vazamento de dado
> clínico** — nesse cenário o `nbstripout` deixa de ser preferência e passa a ser
> obrigatório, junto com uma revisão do que cada célula imprime.

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
- [ ] `uv run nbqa ruff notebooks/` passa limpo
- [ ] Saídas salvas no arquivo (são versionadas de propósito — ver acima)

---

**Última atualização:** 2026-09-05

# 🏥 tc03-cloud-mlops — Triagem Automática de Laudos Médicos

> Deploy de Modelo em Produção com Pipeline CI/CD, Monitoramento e Otimização de Latência.

---

## 🎯 Contexto e Problema

Um hospital de referência precisa de um sistema de **triagem automática de laudos médicos**
capaz de classificar o nível de urgência de um texto clínico:

| Classe | Significado | Ação esperada |
|--------|-------------|---------------|
| `normal` | Achados sem alteração relevante | Fluxo ambulatorial padrão |
| `atencao` | Achados que exigem revisão médica | Fila priorizada |
| `urgente` | Achados críticos | Escalonamento imediato |

O valor clínico está na **redução do tempo entre a emissão do laudo e a leitura por um
profissional**. Isso torna a latência de inferência um requisito de produto, não apenas
uma métrica técnica.

---

## 🧩 Escopo do Projeto

O foco do desafio **não é maximizar a acurácia do modelo**, e sim garantir que o
ciclo de vida do modelo funcione de ponta a ponta:

- Classificador de texto (NLP) **leve**, servido via **API REST** em container Docker
- **Pipeline CI/CD** com GitHub Actions (lint → test → build)
- **Orquestração de retreino** com Airflow (ingestão → treino → salvamento)
- **Monitoramento** com Prometheus + Grafana via Docker Compose
- **Otimização de latência** (ONNX Runtime / quantização) com comparativo antes/depois

> O andamento de cada item está em [docs/ROADMAP.md](docs/ROADMAP.md).

---

## 🏗️ Arquitetura

### Visão macro

```
                       ┌─────────────────────────────┐
   Laudo (texto)  ───► │  API FastAPI (/predict)     │ ───► { classe, score, latencia_ms }
                       │  modelo ONNX Runtime        │
                       └──────────┬──────────────────┘
                                  │ /metrics (prometheus_client)
                                  ▼
                       ┌──────────────────┐      ┌──────────────┐
                       │   Prometheus     │ ───► │   Grafana    │
                       └──────────────────┘      └──────────────┘

   ┌──────────────────────────────────────────────────────────┐
   │  Airflow DAG (retreino)                                  │
   │  ingest_data → train_model → evaluate → export_onnx      │
   └──────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                          artefato de modelo
```

### Decisão de nuvem

A estratégia de deploy é **inferência em tempo real (real-time)**, não batch, porque a
triagem só gera valor se ocorrer no momento da emissão do laudo.

**Decisão:** **AWS — imagem no ECR, servida por EC2 atrás de um Application Load
Balancer**, com retreino executado como job agendado e desacoplado da inferência.

O fator determinante foi **latência previsível**: uma instância sempre quente elimina o
cold start, que é a maior fonte de variabilidade num serviço síncrono. Como um hospital
emite laudos de forma contínua, scale-to-zero não traria economia real — apenas custaria
previsibilidade.

> 📄 A análise completa — comparativo dos serviços AWS, batch vs. real-time e
> trade-offs — está em **[docs/ARQUITETURA.md](docs/ARQUITETURA.md)**.

---

## 🔬 Seleção do Modelo

O modelo servido em produção não é escolhido por preferência: é o vencedor de uma
comparação entre candidatos, avaliados no **mesmo split de teste**, sob um critério
declarado **antes** dos treinos.

```
02_preprocessing  →  gera os splits (uma vez só)
       ↓
03 dummy · 04 logreg · 05 random forest · 06 linear svc
       ↓
07_model_comparison  →  aplica o critério de promoção
       ↓
08_onnx_optimization →  otimiza o modelo promovido
```

**Critério:** maior **F1-macro** no teste, entre os modelos com recall de `urgente` ≥ 0,60
e latência p95 ≤ 15 ms. A regra vive em `src/evaluation/promotion.py` e é consultada pelo
notebook, pela DAG e pela API — nunca reimplementada.

### Resultado

Corpus real: 11.227 documentos (14.438 brutos, 22,2% duplicatas removidas).

| Modelo | F1-macro | Recall `urgente` | p95 | Tamanho | |
|---|---|---|---|---|---|
| **tfidf_linear_svc** | **0,7582** | 0,8118 | 3,14 ms | 1,23 MB | ✅ promovido |
| tfidf_logreg | 0,7489 | 0,7957 | 3,22 ms | 1,23 MB | elegível |
| tfidf_random_forest | 0,7273 | 0,8414 | 210,63 ms | 72,17 MB | ❌ latência |
| dummy_stratified | 0,3388 | 0,2339 | 5,13 ms | — | piso |
| dummy_most_frequent | 0,1951 | 0,0000 | 2,71 ms | — | piso |

Três leituras que a comparação sustenta:

- **A acurácia teria escolhido o pior modelo.** O `most_frequent` tem a maior acurácia
  entre os baselines (0,4136) e nunca prediz `urgente`
- **O Random Forest sugerido no enunciado perdeu nos dois eixos**: F1-macro menor, 67x
  mais lento e 59x maior que os lineares
- **SVC e LogReg empataram tecnicamente** (Δ 0,0093); o desempate por latência teve
  margem de 0,07 ms, que é ruído — [decisão em aberto](docs/MODEL_CARD.md#-decisão-em-aberto)

### Modelo servido pela API

A API serve o **`tfidf_logreg`**, não o promovido pela regra. Os dois empataram
tecnicamente, e o LogReg expõe `predict_proba` — necessário para devolver score de
confiança, que numa fila clínica permite limiar ajustável. A divergência é deliberada e
está registrada como ADR 10 em [docs/ARQUITETURA.md](docs/ARQUITETURA.md).

> 📄 Análise completa em **[docs/MODEL_CARD.md](docs/MODEL_CARD.md)** · metodologia em
> **[docs/NOTEBOOKS.md](docs/NOTEBOOKS.md)**.

---

## 🛠️ Stack Tecnológica

| Camada | Tecnologia | Papel |
|--------|-----------|-------|
| Modelo | Scikit-Learn (TF-IDF + classificador leve) | Baseline de classificação |
| Otimização | ONNX Runtime | Inferência otimizada |
| API | FastAPI + Uvicorn | Serviço de inferência REST |
| Métricas | prometheus-client | Instrumentação da API |
| Observabilidade | Prometheus + Grafana | Coleta e dashboards |
| Orquestração | Apache Airflow | DAG de treino/retreino |
| Empacotamento | Docker + Docker Compose | Runtime e stack local |
| CI/CD | GitHub Actions | Lint, testes e build |
| Padrão de commits | Commitlint + Husky | Histórico semântico |

---

## 📂 Estrutura do Repositório

```
tc03-cloud-mlops/
├── configs/
│   └── model_config.yaml    # ✅ Seed, splits, mapeamento, grades e limiares
├── data/                    # Dados (raw/processed) — não versionados
├── docs/                    # ✅ Documentação do projeto
├── models/                  # Artefatos de modelo — não versionados
├── notebooks/               # ✅ EDA, candidatos e comparação (01 a 07)
├── scripts/
│   └── gen_synthetic_data.py # ✅ Corpus sintético para pipeline e CI
├── src/
│   ├── config.py            # ✅ Caminhos, seed e carregamento de config
│   ├── data/                # ✅ Loader, limpeza, mapeamento e splits
│   ├── evaluation/          # ✅ Métricas, latência e regra de promoção
│   ├── models/              # ✅ Pipelines dos candidatos e rotina de experimento
│   └── api/                 # ✅ Serviço FastAPI de inferência
├── tests/                   # ✅ Testes automatizados (pytest)
├── Dockerfile               # ✅ Imagem do serviço de inferência
├── docker-compose.yml       # ✅ Stack local (Prometheus/Grafana na Etapa 3)
├── .github/workflows/       # ⬜ Pipelines de CI/CD (Etapa 2)
├── airflow/dags/            # ⬜ DAG de treino/retreino (Etapa 2)
└── monitoring/              # ⬜ Prometheus e dashboards Grafana (Etapa 3)
```

**Legenda:** ✅ existe · ⬜ a construir na etapa indicada

---

## 🚀 Como Executar

### Seleção do modelo (notebooks)

```bash
# 1. Dependências
uv sync --group dev            # ou: pip install -e ".[dev]"

# 2. Dados
#    Baixe o corpus para data/raw/ — ver docs/DATASET.md
#    Sem o corpus ainda? Gere um substituto sintético:
python scripts/gen_synthetic_data.py --rows 3000

# 3. Rode os notebooks na ordem
jupyter lab notebooks/
```

| Ordem | Notebook | O que faz |
|-------|----------|-----------|
| 1 | `01_eda.ipynb` | Explora o corpus e grava `data_profile.json` |
| 2 | `02_preprocessing.ipynb` | Mapeia urgência e gera os splits — **roda uma vez só** |
| 3 | `03_baseline_dummy.ipynb` | Piso de comparação |
| 4-6 | `04` · `05` · `06` | Candidatos: LogReg, Random Forest, LinearSVC |
| 7 | `07_model_comparison.ipynb` | Aplica o critério e promove o vencedor |

> 📄 Detalhes em [docs/NOTEBOOKS.md](docs/NOTEBOOKS.md).

### API de inferência

```bash
docker compose up -d --build

# API ............ http://localhost:8000/docs
# Health check ... http://localhost:8000/health
```

Classificando um laudo:

```bash
curl -X POST http://localhost:8000/predict   -H "Content-Type: application/json"   -d '{"texto": "Patient presented with acute myocardial infarction and severe coronary artery stenosis."}'
```

```json
{
  "urgencia": "urgente",
  "confianca": 0.9668,
  "probabilidades": {"atencao": 0.0208, "normal": 0.0124, "urgente": 0.9668},
  "latencia_ms": 2.364,
  "modelo": "tfidf_logreg"
}
```

| Rota | Método | Descrição |
|------|--------|-----------|
| `/predict` | `POST` | Classifica o laudo; 422 se o texto for vazio ou menor que 30 caracteres |
| `/health` | `GET` | Estado do serviço e se o modelo está em memória |
| `/docs` | `GET` | OpenAPI interativo |

Medindo a latência:

```bash
uv run python scripts/measure_api_latency.py --url http://localhost:8000
```

> ⚠️ Em **Docker Desktop no Windows**, o número fim a fim carrega ~45 ms de proxy de rede
> que não existem em host Linux. A referência para comparar a otimização da Etapa 4 é o
> campo `latencia_ms` da resposta — ver
> [docs/ARQUITETURA.md](docs/ARQUITETURA.md#baseline-medido-etapa-1).

### Monitoramento

> 🚧 **Etapa 3.** Prometheus e Grafana ainda não integrados.

---

## 🗺️ Roadmap das Etapas

| Etapa | Disciplina | Entregável | Status |
|-------|-----------|-----------|--------|
| **0** | — | Documentação inicial e definições | 🟡 Em andamento |
| **1** | Deploy em Nuvem | API FastAPI em Docker + decisão arquitetural | ⬜ Não iniciada |
| **2** | CI/CD e Pipeline de Treino | Workflow GitHub Actions + DAG Airflow | ⬜ Não iniciada |
| **3** | Monitoração de Performance | Docker Compose + dashboard Grafana | ⬜ Não iniciada |
| **4** | Latência em Modelos Não Estruturados | Modelo otimizado + comparativo + vídeo | ⬜ Não iniciada |

> 📄 Detalhamento de tarefas e critérios de aceite em **[docs/ROADMAP.md](docs/ROADMAP.md)**.

---

## 📊 Critérios de Avaliação

| Critério | Peso | Onde é atendido |
|----------|------|-----------------|
| Modelagem e Otimização | 20% | Etapa 4 — ONNX/quantização + comparativo de latência |
| Monitoramento | 20% | Etapa 3 — Compose + dashboard com 3+ painéis |
| CI/CD (GitHub Actions) | 15% | Etapa 2 — lint + testes automatizados |
| Orquestração (Airflow) | 15% | Etapa 2 — DAG de ingestão e treino |
| Documentação (README) | 15% | Este README + `docs/` |
| Vídeo STAR (≤ 5 min) | 15% | Etapa 4 |

---

## 📚 Documentação

| Documento | Conteúdo |
|-----------|----------|
| [docs/ARQUITETURA.md](docs/ARQUITETURA.md) | Decisão arquitetural de nuvem, batch vs. real-time, trade-offs |
| [docs/NOTEBOOKS.md](docs/NOTEBOOKS.md) | Fluxo de notebooks, métricas e **critério de promoção do modelo** |
| [docs/MODEL_CARD.md](docs/MODEL_CARD.md) | Model Card do modelo promovido — uso pretendido, limitações, vieses |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Etapas, tarefas, entregáveis e critérios de aceite |
| [docs/DATASET.md](docs/DATASET.md) | Escolha do dataset, esquema e estratégia de rotulagem |
| [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) | Fluxo de branches, PRs e ambiente local |
| [docs/COMMITLINT.md](docs/COMMITLINT.md) | Padrão de mensagens de commit |

---

## 👥 Equipe

| Nome | RM | Responsabilidade |
|------|----|------------------|
| _a preencher_ | _a preencher_ | _a preencher_ |

**Vídeo STAR:** _link a preencher (Etapa 4)_

---

**Última atualização:** 2026-09-05

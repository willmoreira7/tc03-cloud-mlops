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

- ✅ Classificador de texto (NLP) **leve**, servido via **API REST** em container Docker
- ✅ **Pipeline CI/CD** com GitHub Actions (lint → test → build)
- ✅ **Orquestração de retreino** com Airflow (ingestão → treino → salvamento)
- ✅ **Monitoramento** com Prometheus + Grafana via Docker Compose
- ✅ **Otimização de latência** (ONNX Runtime / quantização) com comparativo antes/depois

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

**Proposta:** container único servido em plataforma serverless de containers
(scale-to-zero), com retreino executado como job agendado.

> 📄 A análise completa — comparativo AWS × Azure × GCP, batch vs. real-time, custos e
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

**Critério:** maior **F1-macro** no teste, entre os modelos que respeitam um recall mínimo
da classe `urgente` e um teto de latência p95. A regra vive em `src/evaluation/promotion.py`
e é consultada pelo notebook, pela DAG e pela API — nunca reimplementada.

> 📄 Métricas, protocolo de medição de latência e checklist em
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

## 📂 Estrutura do Repositório (planejada)

```
tc03-cloud-mlops/
├── .github/workflows/       # Pipelines de CI/CD
├── airflow/dags/            # DAG de treino/retreino
├── api/                     # Serviço FastAPI
├── data/                    # Dados (raw/processed) — não versionados
├── docs/                    # Documentação do projeto
├── models/                  # Artefatos de modelo (.pkl / .onnx)
├── monitoring/              # Configs Prometheus e dashboards Grafana
├── notebooks/               # Exploração, modelos candidatos e comparação
├── src/                     # Código de treino, features e avaliação
│   ├── evaluation/          # Métricas e regra de promoção do modelo
│   └── pipeline/            # Etapas chamadas pela DAG do Airflow
├── tests/                   # Testes automatizados (pytest)
├── docker-compose.yml       # API + Prometheus + Grafana
└── Dockerfile               # Imagem do serviço de inferência
```

> ⚠️ Nenhum diretório de código foi criado ainda. Esta é a estrutura-alvo definida na
> documentação inicial e será construída ao longo das etapas.

---

## 🚀 Como Executar

> 🚧 **Em construção.** As instruções abaixo serão preenchidas conforme as etapas forem
> implementadas. Elas fazem parte do critério de avaliação de Documentação (15%).

```bash
# 1. Subir a stack completa (API + Prometheus + Grafana)
docker compose up -d

# 2. Endpoints previstos
# API .......... http://localhost:8000/docs
# Métricas ..... http://localhost:8000/metrics
# Prometheus ... http://localhost:9090
# Grafana ...... http://localhost:3000
```

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

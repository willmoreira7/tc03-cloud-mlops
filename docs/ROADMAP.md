# 🗺️ Roadmap

> Detalhamento das 4 etapas do projeto, com tarefas, entregáveis e critérios de aceite.
> Visão resumida no [README.md](../README.md).

---

## 📊 Panorama

| Etapa | Disciplina | Peso relacionado | Status |
|-------|-----------|------------------|--------|
| [0 — Fundação](#-etapa-0--fundação-do-repositório) | — | — | 🟡 Em andamento |
| [1 — Arquitetura e API](#-etapa-1--decisão-arquitetural-e-api-inicial) | Deploy em Nuvem | 15% (doc) | ✅ Concluída |
| [2 — CI/CD e Pipeline](#-etapa-2--cicd-e-pipeline-automatizado) | CI/CD e Pipeline de Treino | 30% | ⬜ Não iniciada |
| [3 — Monitoramento](#-etapa-3--monitoramento-e-observabilidade) | Monitoração de Performance | 20% | ⬜ Não iniciada |
| [4 — Otimização e Entrega](#-etapa-4--otimização-de-latência-e-entrega) | Latência em Modelos Não Estruturados | 35% | 🟡 Modelo selecionado; otimização pendente |

**Legenda:** ⬜ não iniciada · 🟡 em andamento · ✅ concluída · 🔴 bloqueada

---

## ✅ Conformidade com o Enunciado

Conferência item a item do que o enunciado exige.

### Requisitos obrigatórios — repositório

| Requisito | Status | Onde |
|-----------|--------|------|
| Pipeline CI/CD com GitHub Actions (lint → test → build) | ⬜ | Etapa 2 |
| Script ou DAG Airflow para treino/retreino | ⬜ | Etapa 2 |
| Dockerfile funcional para o serviço de inferência | ✅ | `Dockerfile` + `docker-compose.yml` |
| Stack de monitoramento local (API + Prometheus + Grafana) | ⬜ | Etapa 3 |
| Histórico de commits semântico e organizado | ✅ | [COMMITLINT.md](COMMITLINT.md) |

### Bibliotecas requeridas

| Biblioteca | Uso exigido | Status |
|-----------|-------------|--------|
| Scikit-Learn | Modelo base de classificação de texto | ✅ TF-IDF + LinearSVC / LogReg / RF |
| FastAPI | Construção da API | ✅ `src/api/` |
| Prometheus-client | Instrumentação de métricas | ⬜ Etapa 3 |
| Airflow | Orquestração de tarefas | ⬜ Etapa 2 |

### Boas práticas obrigatórias

| Prática | Exigência | Status |
|---------|-----------|--------|
| CI/CD com ≥ 2 automações | lint + testes | ⬜ Etapa 2 |
| DAG Airflow funcional | dados → treino → salvamento | ⬜ Etapa 2 |
| Dashboard Grafana | ≥ 3 painéis | ⬜ Etapa 3 |
| Otimização de performance | ≥ 1 técnica (ONNX, quantização ou pruning) | ⬜ Etapa 4 |

### Dataset

| Exigência | Situação |
|-----------|----------|
| Texto + target de classificação | ✅ `texto` + `urgencia` |
| Mínimo de 2.000 amostras | ✅ **11.227** documentos utilizados |
| Dataset público | ✅ Medical Abstracts TC Corpus |

### Etapa 4 — o que a seleção de modelo já cobre

| Tarefa do enunciado | Status |
|--------------------|--------|
| Treinar o classificador de texto | ✅ 5 candidatos comparados no mesmo split |
| Aplicar técnica de otimização (ONNX / quantização) | ⬜ **Pendente** |
| Comparar latência original × otimizado | ⬜ **Pendente** |
| Gravar o vídeo STAR | ⬜ Pendente |

> ⚠️ **Atenção ao critério "Modelagem e Otimização" (20%).** O enunciado exige *"modelo
> funcional de NLP, conversão/otimização bem-sucedida e melhoria de latência
> demonstrada"* — são **três** partes. O modelo funcional está entregue; a conversão e o
> comparativo de latência, não. Sem o notebook `08`, esse critério fica parcialmente
> atendido.

---

## 🧱 Etapa 0 — Fundação do Repositório

**Foco:** deixar o repositório pronto para o time começar a codar sem retrabalho.

### Tarefas

- [x] Inicializar repositório e conectar ao remoto
- [x] Definir padrão de commits ([COMMITLINT.md](COMMITLINT.md))
- [x] Documentar contexto, arquitetura, roadmap e dataset
- [x] Definir o dataset ([DATASET.md](DATASET.md)) — Medical Abstracts TC Corpus
- [x] Fixar o limiar de recall `urgente` e o teto de latência p95 ([NOTEBOOKS.md](NOTEBOOKS.md))
- [x] Criar a estrutura de diretórios descrita no README
- [x] Adicionar `data/`, `models/` e saídas de notebook ao [.gitignore](../.gitignore)
- [ ] Confirmar as decisões marcadas como 🟡 **Proposta** em [ARQUITETURA.md](ARQUITETURA.md)
- [ ] Revisar a regra de mapeamento de urgência ([DATASET.md](DATASET.md))
- [ ] Preencher a tabela de equipe no README

### 🧰 Arquivos de tooling a criar

| Item | Papel |
|------|-------|
| `commitlint.config.js`, `package.json`, `.husky/commit-msg` | Validação das mensagens de commit ([COMMITLINT.md](COMMITLINT.md)) |
| `pyproject.toml` | Dependências, configuração do `ruff` e grupos de dev |
| `Makefile` | Atalhos `install` / `lint` / `test` / `run` |
| `scripts/validate_env.py` | Checagem de ambiente — quem clona sabe se está pronto para rodar |

### ✅ Critério de aceite

Qualquer integrante consegue clonar o repositório, entender o escopo e saber onde
colocar o próprio código sem precisar perguntar.

---

## 🚀 Etapa 1 — Decisão Arquitetural e API Inicial

**Disciplina:** Deploy em Nuvem
**Foco:** decisão de arquitetura de deploy e setup da aplicação.

### Tarefas

- [x] Analisar estratégia de deploy em nuvem (batch vs. real-time) e documentar
- [x] Criar API FastAPI com endpoint que recebe o texto do laudo e retorna a classificação
- [x] Empacotar a API em container Docker
- [x] Medir o tempo de resposta — **baseline de latência local**

### Endpoints previstos

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/predict` | Recebe o texto do laudo, retorna classe e score |
| `GET` | `/health` | Health check do serviço |
| `GET` | `/metrics` | Métricas Prometheus (Etapa 3) |

### 📦 Entregável

✅ API funcional rodando em Docker + decisão arquitetural documentada.

### ✅ Critério de aceite

- [x] `docker compose up` sobe a API e `/docs` responde
- [x] Baseline de latência registrado em [ARQUITETURA.md](ARQUITETURA.md#baseline-medido-etapa-1) com o método de medição

### 📊 Baseline medido

| Ambiente | Fim a fim p95 | Inferência p95 |
|----------|--------------|----------------|
| Container (Docker Desktop, Windows) | 53,17 ms | 4,82 ms |
| Processo nativo no host | 7,52 ms | 4,60 ms |

> 🔴 Os ~45 ms de diferença são do proxy de rede do Docker Desktop no Windows, não da
> aplicação — a inferência é praticamente idêntica nos dois. **A Etapa 4 deve comparar a
> latência de inferência**, não o fim a fim medido neste ambiente, sob pena de esconder o
> ganho do ONNX dentro do ruído do proxy.

### 🔧 Melhoria conhecida

A imagem final tem **1,01 GB**. `pandas` e `pyarrow` estão nas dependências principais
mas não são usados no caminho de inferência — excluí-los do estágio de runtime reduziria
a imagem de forma relevante. Não afeta latência no destino escolhido (EC2 sempre quente),
mas afeta tempo de build e de deploy.

> ℹ️ A ordem acabou invertida em relação ao previsto: a seleção de modelo foi feita antes
> da API, então não foi preciso stub — o serviço já nasceu servindo um modelo treinado
> (`tfidf_logreg`, ver ADR 10 em [ARQUITETURA.md](ARQUITETURA.md)).

---

## ⚙️ Etapa 2 — CI/CD e Pipeline Automatizado

**Disciplinas:** CI/CD e Pipeline de Treino
**Foco:** automação básica do código e do modelo.

### Tarefas

- [ ] Criar workflow GitHub Actions disparado em `push` e `pull_request`
- [ ] Automação 1 — **lint** (ex.: `ruff` ou `flake8`)
- [ ] Automação 2 — **testes** (`pytest`)
- [ ] _(opcional)_ Automação 3 — rodar o pipeline sobre dados sintéticos e validar artefatos
- [ ] Desenvolver a DAG do Airflow simulando o treinamento
- [ ] Task de leitura do CSV de dados
- [ ] Task de treino e salvamento do modelo

> 💡 A automação 3 gera dados sintéticos no CI, roda o pipeline completo e verifica que
> os artefatos saem. Resolve o problema de não poder versionar o dataset real e vai além
> do mínimo de 2 automações exigido.

> ⚠️ A DAG deve chamar módulos de `src/pipeline/`, **nunca executar notebooks**. Os
> notebooks são o registro da análise; o código automatizado vive em `src/`.

### 📦 Entregável

Workflow YAML no repositório + arquivo `.py` da DAG do Airflow.

### ✅ Critério de aceite

- Badge do workflow verde na branch principal
- Mínimo de **2 automações** rodando (exigência do enunciado)
- DAG carrega no Airflow sem erro de import e executa fim a fim

---

## 📈 Etapa 3 — Monitoramento e Observabilidade

**Disciplinas:** Monitoração de Performance e Serviços
**Foco:** stack de observabilidade para a API.

### Tarefas

- [ ] Instrumentar a API com `prometheus_client`
- [ ] Expor contagem de chamadas e tempo de requisição
- [ ] Configurar `docker-compose.yml` com API + Prometheus + Grafana
- [ ] Criar dashboard no Grafana e exportar o JSON para o repositório
- [ ] Gerar carga sintética para popular os gráficos

### Painéis obrigatórios (mínimo 3)

| # | Painel | Métrica base |
|---|--------|-------------|
| 1 | Total de requisições | `Counter` por rota e status |
| 2 | Latência de resposta | `Histogram` — p50 / p95 / p99 |
| 3 | Taxa de erro | Proporção de respostas `5xx` |
| 4 | _(extra)_ Distribuição das classes preditas | `Counter` por classe |

### 📦 Entregável

Docker Compose rodando a stack completa + print/JSON do dashboard.

### ✅ Critério de aceite

`docker compose up` sobe os três serviços e o dashboard exibe dados reais após carga.

---

## ⚡ Etapa 4 — Otimização de Latência e Entrega

**Disciplina:** Latência em Modelos Não Estruturados
**Foco:** modelo otimizado para inferência e consolidação do projeto.

### Tarefas

- [x] Executar os notebooks `01` a `06` — EDA, splits e modelos candidatos
- [x] Rodar `07_model_comparison` e promover o vencedor pelo critério declarado
- [x] Registrar métricas de qualidade (F1-macro, recall por classe, matriz de confusão)
- [ ] Decidir entre `tfidf_linear_svc` e `tfidf_logreg` ([MODEL_CARD.md](MODEL_CARD.md#-decisão-em-aberto))
- [ ] Criar o notebook `08_onnx_optimization`
- [ ] Aplicar técnica de otimização — **exportação para ONNX Runtime** (ou quantização)
- [ ] Validar equivalência de predições entre `.pkl` e `.onnx`
- [ ] Comparar latência: modelo original × modelo otimizado
- [ ] Substituir o modelo servido pela API pelo artefato otimizado
- [ ] **Preencher e commitar o [MODEL_CARD.md](MODEL_CARD.md)**
- [ ] Gravar o vídeo STAR (≤ 5 min)

> 📄 Fluxo dos notebooks, métricas e protocolo de medição em [NOTEBOOKS.md](NOTEBOOKS.md).

> 🔴 **O Model Card é entregável obrigatório e precisa estar versionado.** Ele mora em
> `docs/MODEL_CARD.md`. Gerá-lo dentro de `models/` faria o arquivo existir em disco sem
> nunca chegar ao repositório — o diretório é ignorado pelo Git.

### Tabela comparativa a preencher

| Modelo | Formato | p50 (ms) | p95 (ms) | Tamanho | Accuracy |
|--------|---------|----------|----------|---------|----------|
| Baseline | `.pkl` (scikit-learn) | — | — | — | — |
| Otimizado | `.onnx` (ONNX Runtime) | — | — | — | — |
| **Ganho** | | — | — | — | — |

> ℹ️ Comparar sob **as mesmas condições**: mesma máquina, mesmo lote de entradas, mesmo
> número de execuções, descartando as primeiras chamadas (warm-up). Sem isso o
> comparativo não sustenta a nota de Modelagem e Otimização (20%).

### Roteiro do vídeo (método STAR)

| Bloco | Conteúdo | Tempo sugerido |
|-------|----------|----------------|
| **S**ituation | Problema clínico e importância da triagem rápida | ~45 s |
| **T**ask | Requisitos técnicos: latência, CI/CD, monitoramento | ~45 s |
| **A**ction | Arquitetura, otimização do modelo, configuração da monitoração | ~2 min |
| **R**esult | Pipeline funcionando, latência alcançada, lições aprendidas | ~1min 30 s |

### 📦 Entregável

Modelo otimizado + resultados comparativos de latência + Model Card + link do vídeo.

### ✅ Critério de aceite

- Tabela comparativa preenchida com números medidos, não estimados
- Equivalência de predições entre `.pkl` e `.onnx` verificada e registrada
- `git ls-files docs/MODEL_CARD.md` retorna o arquivo **e** ele está preenchido

> ⚠️ Verificar artefato com `test -f` no CI prova que ele foi *gerado*, não que está
> *versionado*. Para o que o avaliador precisa ler, a checagem certa é `git ls-files`.

---

## 🚩 Riscos e Pontos de Atenção

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Dataset não definido trava as Etapas 2 e 4 | 🔴 Alto | Fechar a escolha ainda na Etapa 0 — ver [DATASET.md](DATASET.md) |
| Airflow local é pesado para subir | 🟡 Médio | Usar imagem oficial em Compose separado do stack de inferência |
| `TfidfVectorizer` não converter para ONNX | 🔴 Alto | Validar a conversão já na Etapa 1, com pipeline mínimo; contingência é quantização |
| Ganho de latência do ONNX ser marginal em modelo já leve | 🟡 Médio | Medir com rigor; ganho pequeno bem medido vale mais que número inflado |
| Nenhum modelo passar nas restrições de promoção | 🟡 Médio | Limiares definidos na Etapa 0 devem ser realistas; revisá-los exige registrar a mudança |
| Vídeo estourar 5 minutos | 🟡 Médio | Roteirizar e ensaiar antes de gravar |
| Commits fora do padrão quebrando o histórico | 🟢 Baixo | Husky + commitlint instalados na Etapa 0 |

---

**Última atualização:** 2026-09-05

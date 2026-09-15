# 🏗️ Decisão Arquitetural — Deploy em Nuvem

> Documento da **Etapa 1** (Disciplina: Deploy em Nuvem).
> Atende ao critério de avaliação **Documentação (15%)**: "Explicação da arquitetura em
> nuvem escolhida".

---

## 🎯 Objetivo

Definir e justificar a estratégia de deploy do serviço de triagem de laudos médicos,
respondendo a três perguntas:

1. O padrão de inferência deve ser **batch** ou **real-time**?
2. Qual **provedor de nuvem** e quais serviços?
3. Como o **retreino** se encaixa nessa arquitetura?

---

## ⚖️ Decisão 1 — Batch vs. Real-Time

### Análise

| Critério | Batch | Real-Time |
|----------|-------|-----------|
| Momento da predição | Lotes agendados (ex.: de hora em hora) | No instante da emissão do laudo |
| Latência percebida | Minutos a horas | Milissegundos |
| Custo | Menor (recursos sob demanda) | Maior (serviço sempre disponível) |
| Complexidade operacional | Menor | Maior (SLA, health check, escala) |
| Aderência ao caso clínico | ❌ Baixa | ✅ Alta |

### 🏆 Decisão: **Real-Time (inferência síncrona via API REST)**

**Justificativa:** a triagem existe para reduzir o intervalo entre a emissão do laudo e a
leitura por um profissional. Um laudo classificado como `urgente` só tem valor se o
escalonamento acontecer em segundos. Processar em lote a cada hora anularia o propósito
clínico do sistema — um caso crítico poderia esperar até 59 minutos apenas pela fila.

**Consequência:** latência entra como requisito não-funcional de primeira classe, o que
justifica diretamente a Etapa 4 (otimização com ONNX Runtime / quantização).

---

## ☁️ Decisão 2 — Provedor e Serviços

A escolha tem dois níveis: **qual provedor** e **qual serviço dentro dele**.

### Nível 1 — Comparativo entre provedores

Os três provedores atendem tecnicamente o caso. Um container com FastAPI e um modelo de
1,23 MB roda em qualquer um deles, e as diferenças de latência entre serviços equivalentes
são pequenas frente ao que o próprio modelo consome.

| Critério | AWS | Azure | GCP |
|----------|-----|-------|-----|
| Serviço de container equivalente | ECS / EC2 / App Runner | Container Apps | Cloud Run |
| Registry | ECR | ACR | Artifact Registry |
| Maturidade para o caso | ✅ Alta | ✅ Alta | ✅ Alta |
| Custo em carga contínua | Comparável | Comparável | Comparável |
| Experiência operacional da equipe | ✅ **Consolidada** | ⚠️ Nenhuma | ⚠️ Nenhuma |

### 🏆 Provedor: **AWS**

Como as três opções são tecnicamente equivalentes para esta carga, o critério de desempate
passa a ser **risco operacional**, não capacidade:

| Fator | Peso na decisão |
|-------|-----------------|
| **Familiaridade da equipe** | Decisivo. Em um sistema que apoia triagem clínica, erro de configuração de rede, IAM ou health check tem custo real. Operar em terreno conhecido reduz essa superfície mais do que qualquer diferença entre os provedores agregaria |
| **Ferramental já estabelecido** | ECR, IAM e ALB fazem parte do repertório da equipe; não há curva de aprendizado embutida no cronograma |
| **Portabilidade preservada** | A aplicação é um container padrão. Se a decisão mudar, migrar para Container Apps ou Cloud Run é troca de destino de deploy, não reescrita — o custo do lock-in aqui é baixo |

> ⚠️ **O que *não* justificaria a escolha:** nenhum dos três oferece vantagem técnica
> relevante para uma API síncrona com modelo leve. Alegar superioridade de plataforma aqui
> seria racionalização. O fator honesto é redução de risco operacional.

### Nível 2 — Comparativo dos serviços AWS

| Serviço | Escala a zero | Latência previsível | Operação | Adequação ao caso |
|---------|---------------|--------------------|----------|-------------------|
| **EC2 + ALB** | ❌ Não | ✅ Alta — instância sempre quente | Gerenciar instância e patching | ✅ Boa |
| ECS Fargate | ❌ Não | ✅ Alta | Sem gerenciar host | ✅ Boa |
| Lambda (container image) | ✅ Sim | ⚠️ Cold start com `scikit-learn` + `scipy` | Mínima | ⚠️ Variável |
| AWS Batch | ✅ Sim | ❌ Orientado a lote | Média | ❌ Não atende real-time |
| SageMaker Endpoint | ❌ Não | ✅ Alta | Baixa | ⚠️ Capacidade acima da necessidade |

### 🏆 Decisão: **ECR + EC2 atrás de um Application Load Balancer**

**Justificativa:**

| Fator | Como a escolha atende |
|-------|----------------------|
| **Latência previsível** | Instância sempre quente — sem cold start, que é a principal fonte de variabilidade em serviço síncrono |
| **Portabilidade** | Consome a mesma imagem Docker usada localmente, sem reescrita do serviço |
| **Perfil de carga** | Um hospital emite laudos de forma contínua; scale-to-zero não traria economia real, e custaria previsibilidade |
| **Operação conhecida** | `docker compose` na instância, com health check no ALB |
| **Registry** | ECR guarda a imagem versionada que o CI publica |

**Descartados, com motivo:**

| Serviço | Por que não |
|---------|-------------|
| **Lambda** | O artefato do modelo é pequeno (1,23 MB), mas as dependências (`scikit-learn` + `scipy` + `numpy`) passam de 100 MB. O cold start resultante introduz variabilidade justamente no requisito que o projeto precisa demonstrar |
| **AWS Batch** | Orientado a processamento em lote — contradiz a Decisão 1 |
| **SageMaker Endpoint** | Traz gerenciamento de modelo, autoscaling e A/B testing que o escopo não usa, com custo de endpoint permanente |

> 🔀 **Evolução natural:** migrar de EC2 para **ECS Fargate** remove o gerenciamento da
> instância mantendo as mesmas características de latência e a mesma imagem. É o próximo
> passo se a operação da VM passar a incomodar — não é necessário agora.

---

## 🔁 Decisão 3 — Retreino

O retreino é uma carga **batch, agendada e desacoplada da inferência**.

| Aspecto | Definição |
|---------|-----------|
| Orquestrador | Apache Airflow (DAG local via Docker no escopo do desafio) |
| Execução em nuvem (equivalente) | Job em container disparado por EventBridge Scheduler, ou MWAA se o Airflow for gerenciado |
| Fluxo da DAG | `ingest_data` → `preprocess_data` → `train_model` → `evaluate_model` → `export_onnx_model` → `publish_model` |
| Artefato de saída | `model.pkl` + `model.onnx` + metadados em `models/<modelo>/` |
| Gatilho | Agendado (`@weekly`) ou manual; degradação de métricas fica fora do escopo desta fase |
| Promoção | Só publica se passar no quality gate (ADR 13) |

**Princípio:** treino e inferência nunca compartilham o mesmo processo. A API apenas
carrega um artefato pronto — isso mantém o serviço leve e o tempo de startup baixo.

---

## 🧱 Arquitetura Alvo (nuvem)

```
   Cliente (HIS / sistema hospitalar)
             │  HTTPS
             ▼
   ┌───────────────────────┐
   │  ALB                  │
   └──────────┬────────────┘
              ▼
   ┌───────────────────────┐
   │  EC2 (API)            │  ◄── imagem do ECR
   │  FastAPI + ONNX RT    │
   └──────────┬────────────┘
              │ /metrics
              ▼
   ┌───────────────────────┐      ┌──────────────┐
   │  Prometheus           │ ───► │  Grafana     │
   └───────────────────────┘      └──────────────┘

   ┌──────────────────────────────────────────────────────┐
   │  Job em container / Airflow — retreino agendado      │
   │  ingest → preprocess → train → evaluate →            │
   │  export_onnx → publish                               │
   └───────────────────┬──────────────────────────────────┘
                       ▼
              Artefato de modelo (S3)
```

> ℹ️ **Escopo do desafio:** a stack é executada **localmente via Docker Compose**. A
> arquitetura de nuvem acima é a decisão documentada exigida pela Etapa 1, não um
> ambiente provisionado.

---

## 📌 Registro de Decisões (ADR resumido)

| # | Decisão | Status | Motivo principal |
|---|---------|--------|------------------|
| 01 | Inferência real-time via REST | ✅ Aceita | Valor clínico depende de resposta imediata |
| 02 | AWS: ECR + EC2 atrás de ALB | ✅ Aceita | Latência previsível, sem cold start; carga contínua não se beneficia de scale-to-zero |
| 03 | Retreino desacoplado em job agendado | ✅ Aceita | Mantém a API leve e o startup previsível |
| 04 | ONNX Runtime para inferência | ✅ Aceita | Requisito de otimização da Etapa 4; p95 menor no comparativo local |
| 05 | Modelo leve (TF-IDF + classificador linear) | ✅ Aceita | Latência e tamanho de artefato sobre acurácia máxima |
| 06 | Modelo de produção escolhido por comparação em notebooks | ✅ Aceita | Decisão auditável e reproduzível |
| 07 | Regra de promoção centralizada em `src/evaluation/promotion.py` | ✅ Aceita | Notebook e DAG compartilham restrições; a API serve explicitamente o modelo configurado |
| 08 | **Não** usar MLflow nesta fase | ✅ Aceita | Não exigido pelo PDF. Reavaliada ao fim das Etapas 1–3: o rastreio de experimentos ficou coberto por `search_log.csv`, `metrics.json` com `run_id` e `dataset_sha256`, e o quality gate — MLflow não entrou |
| 09 | **Não** usar DVC, Kubernetes ou Terraform na arquitetura alvo | ✅ Aceita | Fora do escopo do enunciado; o EKS da ADR 16 é só ambiente de demonstração |
| 10 | API serve `tfidf_logreg`, não o promovido `tfidf_linear_svc` | ✅ Aceita | Empate técnico entre os dois; o LogReg expõe `predict_proba` e permite score de confiança |
| 11 | Notebooks versionados **com** as saídas; sem `nbstripout` | ✅ Aceita | Quem clona vê o resultado da análise sem executar nada. Reavaliar se o corpus passar a ter dado clínico real |
| 12 | `nbqa` roda o `ruff` nos notebooks | ✅ Aceita | O código da análise não pode ser a única parte do projeto sem lint |
| 13 | Retreino passa por **quality gate** antes de publicar | ✅ Aceita | Um modelo que não seria promovido na análise não pode chegar à API só porque o job rodou; o gate reusa `promotion.py` |
| 14 | Airflow em imagem e compose próprios, fora do `pyproject.toml` | ✅ Aceita | Evita conflito de dependências com a API; libs de treino fixadas pelo `uv.lock` para o pickle ser compatível |
| 15 | CI treina sobre corpus sintético | ✅ Aceita | O dataset real não é versionado; o CI valida o pipeline, não a qualidade do modelo |
| 16 | Demonstração no EKS do laboratório, imagem da API no Docker Hub com modelo embutido | ✅ Aceita | O cluster já existia com Airflow, Prometheus e Grafana; publicar a API ali mostra a stack completa na nuvem sem provisionar EC2. Não substitui a ADR 02 como alvo de produção, e o retreino no cluster não atualiza a imagem |
| 17 | Modelo servido é o **ONNX**, com gate de equivalência antes de publicar | ✅ Aceita | A otimização não pode alterar a decisão clínica: o pipeline reprova o ONNX se divergir do `.pkl` acima de `optimization.onnx.max_mismatch_rate` **ou** se o próprio ONNX violar as restrições de promoção (ADR 13) |

> ℹ️ **Sobre a ADR 16 — qual ambiente reproduzir.** O projeto tem dois ambientes, com
> papéis distintos, e nenhum substitui o outro:
>
> | | Docker Compose | EKS (`helm/`) |
> |---|---|---|
> | Papel | Entregável reproduzível do enunciado | Ambiente publicado de demonstração |
> | Como subir | Comandos do [README](../README.md) | `helm upgrade --install` + `kubectl apply -f helm/triagem-api.yaml` |
> | Avaliado | Sim — é o que o PDF pede | Não, mas é onde a stack está no ar |
>
> Para **reproduzir** o projeto, siga apenas os comandos do README: nada no CI, na imagem
> construída pelo `Dockerfile` ou nos testes depende de `helm/`.

> ⚠️ **Credenciais do ambiente publicado.** Senhas de Airflow e Grafana não ficam
> versionadas no repositório. Para avaliação, o acesso deve ser compartilhado diretamente
> com a banca/professor. Isso evita tratar um ambiente acadêmico como exceção insegura e
> mantém o repositório aderente a boas práticas de MLOps.

> ℹ️ **Sobre a ADR 10.** A regra de promoção elegeu o `tfidf_linear_svc`, mas a
> diferença para o `tfidf_logreg` é de 0,0093 em F1-macro — dentro do limiar de empate
> técnico — e o desempate por latência teve margem de 0,07 ms, que é ruído de medição.
> Sendo os dois equivalentes em qualidade, a escolha passou a ser guiada pelo contrato
> da API: o `LinearSVC` não expõe `predict_proba`, e uma triagem clínica se beneficia
> de score de confiança para permitir limiar ajustável. Ver
> [MODEL_CARD.md](MODEL_CARD.md#-decisão-fechada).

---

## 📈 Metas de Latência

### Baseline medido (Etapa 1)

Modelo `tfidf_logreg`, 1.000 requisições single-sample após 50 de aquecimento, via
`scripts/measure_api_latency.py`.

| Ambiente | Fim a fim p50 | Fim a fim p95 | Inferência p50 | Inferência p95 |
|----------|--------------|---------------|----------------|----------------|
| Container (Docker Desktop, Windows) | 48,34 ms | 53,17 ms | 2,61 ms | 4,82 ms |
| Processo nativo no host | 5,56 ms | 7,52 ms | 3,27 ms | 4,60 ms |

> 🔴 **Os ~45 ms de diferença não são da aplicação.** A inferência é praticamente idêntica
> nos dois ambientes (4,82 ms contra 4,60 ms no p95). O que difere é o proxy de rede do
> Docker Desktop no Windows, que encaminha `localhost:8000` até o container passando por
> WSL2. Em um host Linux — que é o alvo da Decisão 2 — esse proxy não existe.

### Consequência para a Etapa 4

**A referência de comparação do ONNX é a latência de inferência, não a fim a fim medida
neste ambiente.**

Se o ONNX levar a inferência de 4,8 ms para, digamos, 2 ms, o ganho é real e mensurável —
mas apareceria como 53,2 ms → 50,4 ms no número fim a fim do container em Windows, algo
como 5% e facilmente confundido com ruído. Reportar apenas o fim a fim aqui esconderia a
otimização em vez de demonstrá-la.

| O que reportar | De onde vem |
|----------------|-------------|
| Latência de inferência p50/p95/p99 | Campo `latencia_ms` da resposta, medido no servidor |
| Fim a fim em host Linux | Rodar a medição no CI ou em VM Linux, onde não há o proxy |
| Fim a fim em Docker Desktop | Apenas como contexto, sempre com a ressalva acima |

> ⚠️ Comparar um baseline medido em Docker Desktop no Windows com um resultado otimizado
> medido de outra forma produziria um ganho inventado. O ambiente de medição precisa ser
> idêntico nos dois lados, e declarado.

---

## 📚 Referências

- Aula 03 — Deploy de ML na AWS: ECR, EC2, Lambda, AWS Batch e SageMaker
- Aula 05 — Pipelines de Serviço: Previsões em Lote vs. Tempo Real
- Aula 06 — Boas Práticas de FinOps (Custos) e Segurança

---

**Última atualização:** 2026-09-15

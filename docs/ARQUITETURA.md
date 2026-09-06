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

### Comparativo dos serviços vistos em aula

| Provedor | Serviço de container | Scale-to-zero | Cold start (modelo leve) | Registry | Observação |
|----------|---------------------|---------------|--------------------------|----------|------------|
| **GCP** | Cloud Run | ✅ Sim | Baixo (~1–2 s) | Artifact Registry | Container-native, billing por requisição |
| **AWS** | ECS Fargate / App Runner | ⚠️ Parcial | Médio | ECR | Fargate não escala a zero; App Runner sim |
| **AWS** | Lambda (container image) | ✅ Sim | Alto se o modelo for pesado | ECR | Viável só com artefato pequeno |
| **Azure** | Container Apps | ✅ Sim | Baixo | ACR | Equivalente funcional ao Cloud Run |

### 🏆 Decisão: **GCP — Cloud Run + Artifact Registry**

**Justificativa:**

| Fator | Como o Cloud Run atende |
|-------|-------------------------|
| **Portabilidade** | Consome a mesma imagem Docker usada localmente — sem reescrita do serviço |
| **Custo** | Escala a zero; sem tráfego, sem custo — adequado a um projeto acadêmico |
| **Latência** | Instância mínima configurável (`min-instances=1`) elimina cold start quando necessário |
| **Simplicidade** | Deploy é `push` da imagem + `gcloud run deploy`; sem gerenciar cluster ou VM |
| **Aderência ao artefato** | Modelo TF-IDF + classificador leve exportado em ONNX cabe folgado nos limites de memória |

**Alternativa considerada:** AWS App Runner atenderia com trade-offs praticamente
equivalentes. A escolha pelo GCP se dá pela combinação de scale-to-zero nativo com
cold start baixo e pelo modelo de billing por requisição.

**Descartado:** AWS Lambda — o acoplamento entre tamanho do artefato e cold start
introduz variabilidade de latência indesejável em um requisito de tempo real.
SageMaker / Vertex AI Endpoints — capacidade muito acima da necessidade, com custo de
endpoint permanente.

---

## 🔁 Decisão 3 — Retreino

O retreino é uma carga **batch, agendada e desacoplada da inferência**.

| Aspecto | Definição |
|---------|-----------|
| Orquestrador | Apache Airflow (DAG local via Docker no escopo do desafio) |
| Execução em nuvem (equivalente) | Cloud Run Jobs, acionado por Cloud Scheduler ou Cloud Composer |
| Fluxo da DAG | `ingest_data` → `train_model` → `evaluate` → `export_onnx` |
| Artefato de saída | Modelo `.onnx` versionado, consumido pela API na inicialização |
| Gatilho | Agendado (periódico); degradação de métricas fica fora do escopo desta fase |

**Princípio:** treino e inferência nunca compartilham o mesmo processo. A API apenas
carrega um artefato pronto — isso mantém o serviço leve e o tempo de startup baixo.

---

## 🧱 Arquitetura Alvo (nuvem)

```
   Cliente (HIS / sistema hospitalar)
             │  HTTPS
             ▼
   ┌───────────────────────┐
   │  Cloud Run (API)      │  ◄── imagem do Artifact Registry
   │  FastAPI + ONNX RT    │
   └──────────┬────────────┘
              │ /metrics
              ▼
   ┌───────────────────────┐      ┌──────────────┐
   │  Prometheus           │ ───► │  Grafana     │
   └───────────────────────┘      └──────────────┘

   ┌───────────────────────────────────────────────┐
   │  Cloud Run Job / Airflow — retreino agendado  │
   │  ingest → train → evaluate → export_onnx      │
   └───────────────────┬───────────────────────────┘
                       ▼
              Artefato de modelo (bucket)
```

> ℹ️ **Escopo do desafio:** a stack é executada **localmente via Docker Compose**. A
> arquitetura de nuvem acima é a decisão documentada exigida pela Etapa 1, não um
> ambiente provisionado.

---

## 📌 Registro de Decisões (ADR resumido)

| # | Decisão | Status | Motivo principal |
|---|---------|--------|------------------|
| 01 | Inferência real-time via REST | ✅ Aceita | Valor clínico depende de resposta imediata |
| 02 | GCP Cloud Run + Artifact Registry | 🟡 Proposta | Scale-to-zero, cold start baixo, portabilidade |
| 03 | Retreino desacoplado em job agendado | ✅ Aceita | Mantém a API leve e o startup previsível |
| 04 | ONNX Runtime para inferência | 🟡 Proposta | Requisito de otimização da Etapa 4 |
| 05 | Modelo leve (TF-IDF + classificador clássico) | 🟡 Proposta | Latência e simplicidade sobre acurácia máxima |
| 06 | Modelo de produção escolhido por comparação em notebooks | ✅ Aceita | Decisão auditável e reproduzível |
| 07 | Regra de promoção centralizada em `src/evaluation/promotion.py` | ✅ Aceita | Notebook, DAG e API não podem divergir sobre "melhor modelo" |
| 08 | **Não** usar MLflow nesta fase | 🟡 Proposta | Não exigido pelo PDF; reavaliar após Etapas 1–3 |
| 09 | **Não** usar DVC, Kubernetes ou Terraform | ✅ Aceita | Fora do escopo do enunciado |

> ⚠️ Decisões marcadas como **🟡 Proposta** precisam de validação do grupo antes da
> Etapa 1 começar. As marcadas como ✅ decorrem diretamente do enunciado.

---

## 📈 Metas de Latência

| Momento | Meta | Como medir |
|---------|------|-----------|
| Baseline (Etapa 1) | Registrar valor medido | `docker run` + carga simples no `/predict` |
| Pós-otimização (Etapa 4) | Redução demonstrável vs. baseline | Mesmo teste de carga, modelo ONNX |
| Métrica reportada | p50, p95 e p99 | Histograma do `prometheus-client` |

> As metas numéricas serão fixadas após a medição do baseline na Etapa 1 — definir alvo
> antes de medir produziria um número arbitrário.

---

## 📚 Referências

- Aula 05 — Deploy de ML na Google: Artifact Registry, Cloud Run e Vertex AI
- Aula 03 — Deploy de ML na AWS: ECR, EC2, Lambda, AWS Batch e SageMaker
- Aula 04 — Deploy de ML na Azure: ACR, Container Apps, Jobs e Azure ML
- Aula 05 — Pipelines de Serviço: Previsões em Lote vs. Tempo Real
- Aula 06 — Boas Práticas de FinOps (Custos) e Segurança

---

**Última atualização:** 2026-09-05

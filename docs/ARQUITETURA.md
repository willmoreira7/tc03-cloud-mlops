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

O provedor é a **AWS**, alinhada à experiência da equipe e ao ferramental já dominado.
A pergunta em aberto é qual serviço da AWS hospeda o container.

### Comparativo dos serviços AWS

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

   ┌───────────────────────────────────────────────┐
   │  Job em container / Airflow — retreino agendado│
   │  ingest → train → evaluate → export_onnx      │
   └───────────────────┬───────────────────────────┘
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
| 04 | ONNX Runtime para inferência | 🟡 Proposta | Requisito de otimização da Etapa 4 |
| 05 | Modelo leve (TF-IDF + classificador linear) | ✅ Aceita | Latência e tamanho de artefato sobre acurácia máxima |
| 06 | Modelo de produção escolhido por comparação em notebooks | ✅ Aceita | Decisão auditável e reproduzível |
| 07 | Regra de promoção centralizada em `src/evaluation/promotion.py` | ✅ Aceita | Notebook, DAG e API não podem divergir sobre "melhor modelo" |
| 08 | **Não** usar MLflow nesta fase | 🟡 Proposta | Não exigido pelo PDF; reavaliar após Etapas 1–3 |
| 09 | **Não** usar DVC, Kubernetes ou Terraform | ✅ Aceita | Fora do escopo do enunciado |
| 10 | API serve `tfidf_logreg`, não o promovido `tfidf_linear_svc` | ✅ Aceita | Empate técnico entre os dois; o LogReg expõe `predict_proba` e permite score de confiança |

> ℹ️ **Sobre a ADR 10.** A regra de promoção elegeu o `tfidf_linear_svc`, mas a
> diferença para o `tfidf_logreg` é de 0,0093 em F1-macro — dentro do limiar de empate
> técnico — e o desempate por latência teve margem de 0,07 ms, que é ruído de medição.
> Sendo os dois equivalentes em qualidade, a escolha passou a ser guiada pelo contrato
> da API: o `LinearSVC` não expõe `predict_proba`, e uma triagem clínica se beneficia
> de score de confiança para permitir limiar ajustável. Ver
> [MODEL_CARD.md](MODEL_CARD.md#-decisão-em-aberto).

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

**Última atualização:** 2026-09-05

# 🏷️ Model Card — Classificador de Urgência de Laudos

> ⚠️ **Template a preencher na Etapa 4**, após o `07_model_comparison` definir o modelo
> promovido e o `08_onnx_optimization` medir o ganho de latência.
>
> 🔴 **Este arquivo mora em `docs/` de propósito.** O diretório `models/` é ignorado pelo
> Git — um Model Card gerado ali existiria em disco sem nunca chegar ao repositório. Se um
> notebook gerar uma versão automática, ela é gravada **aqui** e commitada.

---

## 📇 Informações Gerais

| Campo | Valor |
|-------|-------|
| Nome do modelo | _a preencher_ |
| Versão | _a preencher_ |
| Tipo | Classificação de texto multiclasse (3 classes) |
| Algoritmo | _definido pelo `07_model_comparison`_ |
| Formato servido | ONNX Runtime (`models/production/model.onnx`) |
| Data de treino | _a preencher_ |
| Responsáveis | _a preencher_ |
| Dataset | _ver [DATASET.md](DATASET.md)_ |

---

## 🎯 Uso Pretendido

### Para que serve

Classificar o texto de um laudo médico em três níveis de urgência (`normal`, `atencao`,
`urgente`) para **priorizar a fila de leitura** por um profissional de saúde.

### Para que **não** serve

| Uso indevido | Por quê |
|--------------|---------|
| Diagnóstico clínico | O modelo classifica urgência de leitura, não condição médica |
| Decisão autônoma sobre pacientes | A saída é uma sugestão de prioridade sujeita a revisão humana |
| Descarte de laudos classificados como `normal` | Todo laudo continua no fluxo; muda só a ordem |
| Aplicação em outra instituição sem revalidação | Vocabulário e distribuição de laudos variam por origem |

> 🔴 **O rótulo de urgência é derivado por regra a partir das categorias do dataset
> público, não validado clinicamente.** Ver [DATASET.md](DATASET.md). Este modelo é um
> exercício de engenharia de MLOps; não está apto a uso clínico real.

---

## 📊 Performance

### Métricas no split de teste

| Métrica | Valor | Observação |
|---------|-------|------------|
| F1-macro | _a preencher_ | Métrica de promoção |
| Recall — `urgente` | _a preencher_ | Trava de segurança |
| Recall — `atencao` | _a preencher_ | |
| Recall — `normal` | _a preencher_ | |
| Precision — `urgente` | _a preencher_ | Mede ruído na fila crítica |
| Acurácia | _a preencher_ | ⚠️ Reportada só para referência — não é critério |

### Comparação com os candidatos

Todos avaliados no mesmo split de teste, conforme [NOTEBOOKS.md](NOTEBOOKS.md).

| Modelo | F1-macro | Recall `urgente` | p95 (ms) | Tamanho | Promovido |
|--------|----------|------------------|----------|---------|-----------|
| Dummy (`most_frequent`) | — | — | — | — | ❌ |
| Dummy (`stratified`) | — | — | — | — | ❌ |
| TF-IDF + Logistic Regression | — | — | — | — | — |
| TF-IDF + Random Forest | — | — | — | — | — |
| TF-IDF + LinearSVC | — | — | — | — | — |

**Critério aplicado:** maior F1-macro entre os modelos com recall de `urgente` ≥ limiar e
p95 ≤ teto. _Registrar aqui os valores dos dois limiares e qual modelo venceu._

### Matriz de confusão

_Inserir a matriz do modelo promovido e comentar para onde vão os erros._

> A pergunta que importa: **quantos `urgente` foram classificados como `normal`?** Esse é
> o erro clinicamente caro. Um modelo com F1-macro alto e essa célula alta não serve.

---

## ⚡ Otimização e Latência

| Modelo | Formato | p50 (ms) | p95 (ms) | p99 (ms) | Tamanho | F1-macro |
|--------|---------|----------|----------|----------|---------|----------|
| Promovido | `.pkl` (scikit-learn) | — | — | — | — | — |
| Otimizado | `.onnx` (ONNX Runtime) | — | — | — | — | — |
| **Variação** | | — | — | — | — | — |

**Protocolo de medição:** ver [NOTEBOOKS.md](NOTEBOOKS.md) — 50 chamadas de aquecimento
descartadas, ≥ 1.000 predições single-sample, mesma máquina.

**Equivalência de predições:** _registrar aqui a taxa de concordância entre `.pkl` e
`.onnx` no split de teste._ Um modelo mais rápido que responde diferente não é uma
otimização.

---

## 🗃️ Dados de Treino

| Campo | Valor |
|-------|-------|
| Fonte | _a preencher_ |
| Volume total | _a preencher_ |
| Split | 70% treino / 15% validação / 15% teste, estratificado |
| `random_state` | 42 |
| Hash do dataset (SHA256) | _a preencher_ |
| Distribuição de classes | _a preencher_ |
| Pré-processamento | Ver `02_preprocessing.ipynb` |

---

## ⚠️ Limitações

- [ ] Rótulo de urgência derivado por regra, sem validação clínica
- [ ] Corpus público, com distribuição possivelmente distinta da de um hospital real
- [ ] Modelo linear/de árvore sobre TF-IDF — não captura negação nem contexto
      (ex.: "sem sinais de sangramento" e "sinais de sangramento" compartilham quase todo
      o vocabulário)
- [ ] Sem tratamento de abreviações e siglas médicas específicas de instituição
- [ ] _outras a preencher após a análise de erros_

---

## 🚩 Vieses Identificados

_Preencher após a análise de erros do `07_model_comparison`._

Pontos a investigar explicitamente:

| Verificar | Por quê |
|-----------|---------|
| Desempenho por faixa de comprimento do texto | Laudos curtos costumam ter menos sinal |
| Concentração de erro na classe minoritária | Classe `urgente` tende a ser a menor |
| Termos que dominam a decisão | Um termo espúrio de alta correlação vira atalho do modelo |

---

## 💥 Cenários de Falha

| Cenário | Comportamento esperado | Mitigação |
|---------|----------------------|-----------|
| Texto vazio ou só espaços | Erro 422 (validação de schema) | Validação no Pydantic |
| Texto em idioma diferente do treino | Predição sem sentido, com confiança alta | Fora do escopo — documentar |
| Laudo muito acima do comprimento típico | Truncamento pelo vetorizador | Registrar métrica de textos truncados |
| Vocabulário novo (termos não vistos) | TF-IDF ignora o termo | Retreino periódico via DAG |
| Arquivo de modelo ausente na inicialização | API falha no startup, não em runtime | Health check falha e o container não sobe |

---

## 🔍 Monitoramento em Produção

| Sinal | Onde é observado |
|-------|------------------|
| Latência p50/p95/p99 | Painel Grafana — ver [ARQUITETURA.md](ARQUITETURA.md) |
| Taxa de erro 5xx | Painel Grafana |
| Distribuição das classes preditas | Painel Grafana — desvio indica drift de entrada |
| Qualidade do modelo | Reavaliação no retreino (DAG do Airflow) |

> Não há ground truth em tempo real: a urgência verdadeira só se conhece após a leitura
> médica. O monitoramento contínuo é de **proxies** (distribuição de saída e latência),
> não de acurácia.

---

## ⚖️ Considerações Éticas

- O sistema **prioriza**, não decide: nenhum laudo é descartado por classificação
- Erro de falso negativo em `urgente` é o mais grave — daí a trava de recall no critério
  de promoção
- Nenhum dado de paciente identificável é versionado no repositório
- O modelo não deve ser apresentado como validado clinicamente em nenhum material,
  incluindo o vídeo de entrega

---

## 📞 Contato e Manutenção

| Campo | Valor |
|-------|-------|
| Responsáveis | _a preencher_ |
| Frequência de retreino | _a definir — DAG do Airflow_ |
| Repositório | `git@github.com:willmoreira7/tc03-cloud-mlops.git` |

---

**Última atualização:** 2026-09-06

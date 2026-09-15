# 🏷️ Model Card — Classificador de Urgência de Laudos

> 🔴 **Este arquivo mora em `docs/` de propósito.** O diretório `models/` é ignorado pelo
> Git — um Model Card gerado ali existiria em disco sem nunca chegar ao repositório. Se um
> notebook gerar uma versão automática, ela é gravada **aqui** e commitada.

> ✅ **Estado:** modelo servido definido, otimização ONNX implementada e comparação de
> latência registrada na Etapa 4.

---

## 📇 Informações Gerais

| Campo | Valor |
|-------|-------|
| Nome do modelo | `tfidf_logreg` |
| Tipo | Classificação de texto multiclasse (3 classes) |
| Algoritmo | `TfidfVectorizer` → `LogisticRegression` |
| Hiperparâmetros | `C=0.5`, `class_weight="balanced"` |
| Vetorizador | `max_features=20000`, `ngram_range=(1,2)`, `min_df=2`, `sublinear_tf=True` |
| Formato base | `models/tfidf_logreg/model.pkl` |
| Formato servido | `models/tfidf_logreg/model.onnx` (ONNX Runtime) |
| Seed | 42 |
| Dataset | Medical Abstracts TC Corpus — ver [DATASET.md](DATASET.md) |
| Selecionado por | empate técnico no `07_model_comparison` + ADR 10 (`predict_proba`) |

---

## 🎯 Uso Pretendido

### Para que serve

Classificar o texto de um laudo médico em três níveis de urgência (`normal`, `atencao`,
`urgente`) para **priorizar a fila de leitura** por um profissional de saúde.

### Para que **não** serve

| Uso indevido | Por quê |
|--------------|---------|
| Diagnóstico clínico | O modelo classifica urgência de leitura, não condição médica |
| Decisão autônoma sobre pacientes | A saída é sugestão de prioridade sujeita a revisão humana |
| Descarte de laudos classificados como `normal` | Todo laudo continua no fluxo; muda só a ordem |
| Aplicação em outra instituição sem revalidação | Vocabulário e distribuição de laudos variam por origem |

> 🔴 **O rótulo de urgência é derivado por regra a partir das categorias do corpus
> público, não validado clinicamente.** Ver [DATASET.md](DATASET.md). Este modelo é um
> exercício de engenharia de MLOps; **não está apto a uso clínico real.**

---

## 📊 Performance

### Métricas no split de teste (n = 1.685)

| Métrica | Valor | Observação |
|---------|-------|------------|
| **F1-macro** | **0,7489** | Métrica de promoção |
| Recall — `urgente` | 0,7957 | Trava de segurança (mínimo exigido: 0,60) ✅ |
| Recall — `atencao` | 0,7630 | |
| Recall — `normal` | 0,6872 | |
| Precision — `urgente` | 0,7309 | Ruído na fila crítica |
| Precision — `atencao` | 0,7655 | |
| Precision — `normal` | 0,7422 | |
| F1-weighted | 0,7456 | |
| Acurácia | 0,7460 | ⚠️ Referência apenas — não é critério |

### Validação × teste

| Modelo | F1-macro (val) | F1-macro (teste) | Δ |
|--------|---------------|------------------|---|
| `tfidf_linear_svc` | 0,7511 | 0,7582 | +0,0071 |
| `tfidf_logreg` | 0,7513 | 0,7489 | −0,0025 |
| `tfidf_random_forest` | 0,7287 | 0,7273 | −0,0014 |

> ✅ Nenhum candidato varia mais que ±0,008 entre validação e teste. A busca de
> hiperparâmetros não vazou para o resultado reportado.

### Comparação entre candidatos

Todos avaliados no **mesmo split de teste**, com protocolo de latência idêntico.

| Modelo | F1-macro | Recall `urgente` | p50 (ms) | p95 (ms) | Chamadas | Tamanho | Promovido |
|--------|----------|------------------|----------|----------|----------|---------|-----------|
| tfidf_linear_svc | **0,7582** | 0,8118 | 1,45 | 3,14 | 1000 | 1,23 MB | elegível |
| **tfidf_logreg** | 0,7489 | 0,7957 | 1,61 | 2,59 | 1000 | 1,23 MB | ✅ servido |
| tfidf_random_forest | 0,7273 | **0,8414** | 150,61 | 210,63 | 287 | 72,17 MB | ❌ latência |
| dummy_stratified | 0,3388 | 0,2339 | 3,26 | 5,13 | 1000 | 0,77 MB | ❌ |
| dummy_most_frequent | 0,1951 | 0,0000 | 1,70 | 2,71 | 1000 | 0,77 MB | ❌ |

**Critério aplicado:** maior F1-macro entre os modelos com recall de `urgente` ≥ 0,60 e
p95 ≤ 15 ms. Empate técnico (< 1 pp) resolvido pelo menor p95.

> ⚠️ **A promoção foi decidida por desempate, não por qualidade.** A diferença de F1-macro
> entre `tfidf_linear_svc` e `tfidf_logreg` é de **0,0093** — dentro do limiar de empate de
> 0,01. O desempate foi por latência, com margem de **0,07 ms**, que é ruído de medição.
>
> **Os dois modelos são equivalentes para a entrega.** A API serve `tfidf_logreg` porque
> ele expõe `predict_proba`, necessário para devolver score de confiança sem adicionar
> calibração e latência ao `LinearSVC`.

### Erro crítico

O notebook `04_tfidf_logreg` registra o erro clinicamente mais caro do modelo servido:
**51 de 372 casos `urgente` foram classificados como `normal` (13,7%)**. Em triagem
clínica, esse é o falso negativo relevante — o laudo crítico que cai na fila de baixa
prioridade.

Outras leituras detalhadas da matriz ficam no notebook `04_tfidf_logreg`. O ponto central
para operação é que `urgente` continua com o maior recall (0,7957), apesar de ser a classe
minoritária — efeito do `class_weight="balanced"`.

---

## ⚡ Otimização e Latência

> ✅ **Etapa 4 concluída.** O modelo é exportado para ONNX antes da publicação e a API
> carrega `model.onnx` quando `serving.runtime: onnx`.

| Runtime | Formato | p50 (ms) | p95 (ms) | p99 (ms) | Chamadas | Tamanho |
|---------|---------|----------|----------|----------|----------|---------|
| Baseline | `.pkl` (scikit-learn) | 0,86 | 1,21 | 1,32 | 1000 | 0,125 MB |
| Otimizado | `.onnx` (ONNX Runtime) | 0,07 | 0,09 | 0,11 | 1000 | 0,089 MB |
| **Ganho** | | **12,8x** | **12,9x** | **11,6x** | | **28,8% menor** |

**Protocolo de medição:** ver [NOTEBOOKS.md](NOTEBOOKS.md) — 50 chamadas de aquecimento
descartadas, até 1.000 predições single-sample sob orçamento de 45 s, mesma máquina.

> ℹ️ A medição acima foi gerada localmente sobre corpus sintético, porque o dataset real
> não é versionado no repositório. Ela valida o mecanismo de otimização e comparação; as
> métricas de qualidade reais continuam sendo as dos notebooks `01` a `07`.

### Compatibilidade ONNX

| Verificação | Resultado |
|-------------|-----------|
| Predições comparadas | 450 |
| Divergências | 1 |
| Taxa de divergência | 0,22% |
| Limite aceito | 1,00% |

A única divergência observada ocorreu em exemplo de fronteira entre `normal` e `atencao`.
O gate reprova o ONNX se a taxa passar de `optimization.onnx.max_mismatch_rate`.

---

## 🗃️ Dados de Treino

| Campo | Valor |
|-------|-------|
| Fonte | Medical Abstracts TC Corpus (Kaggle) |
| Documentos brutos | 14.438 |
| Removidos (duplicatas) | 3.211 (22,2%) |
| Documentos utilizados | 11.227 |
| Split | 7.858 treino / 1.684 validação / 1.685 teste (70/15/15, estratificado) |
| `random_state` | 42 |
| Comprimento mediano | 1.210 caracteres · 176 palavras |
| Vocabulário (`min_df=2`) | 25.328 termos |

### Distribuição das classes

| Classe | Treino | Validação | Teste | Proporção |
|--------|--------|-----------|-------|-----------|
| `normal` | 3.249 | 696 | 697 | 41,4% |
| `atencao` | 2.871 | 615 | 616 | 36,5% |
| `urgente` | 1.738 | 373 | 372 | 22,1% |

> A estratificação mantém as proporções idênticas até a terceira casa decimal nos três
> splits.

---

## ⚠️ Limitações

- **Rótulo de urgência derivado por regra**, sem validação clínica — a limitação mais
  importante deste modelo
- **22,2% do corpus eram duplicatas.** Se elas tivessem permanecido, o mesmo documento
  apareceria em treino e teste, inflando a métrica reportada
- **TF-IDF não captura negação nem contexto**: "sem sinais de sangramento" e "sinais de
  sangramento" compartilham quase todo o vocabulário e são representados de forma quase
  idêntica
- **`max_features=20000` corta o vocabulário**, que tem 25.328 termos com `min_df=2` — é
  um trade-off consciente de latência e tamanho, mas descarta ~5.300 termos
- **`LinearSVC` não expõe `predict_proba`** — o modelo não retorna probabilidade
  calibrada, apenas a classe e a `decision_function`
- Corpus de abstracts científicos, **não de laudos hospitalares reais** — o vocabulário e
  o estilo de redação diferem
- Sem tratamento de abreviações e siglas médicas específicas de instituição

---

## 🚩 Vieses Identificados

| Constatação | Evidência | Implicação |
|-------------|-----------|------------|
| Classe `urgente` tem o melhor recall apesar de minoritária | Recall 0,7957 vs 0,6872 de `normal` | Efeito do `class_weight="balanced"`; sem ele o modelo tenderia a ignorá-la |
| Fronteira `normal`/`atencao` exige atenção | Classes derivadas de categorias clínicas amplas e heterogêneas | Erros entre baixa e média prioridade devem ser acompanhados em avaliação offline |
| Categoria `5 — general pathological conditions` domina a classe `normal` | 4.805 dos 14.438 documentos brutos | O que o modelo chama de `normal` é fortemente influenciado por uma categoria inespecífica |

### A investigar

- [ ] Desempenho por faixa de comprimento do texto
- [ ] Termos de maior peso no classificador — verificar atalhos espúrios
- [ ] Se a regra de mapeamento de urgência está induzindo o erro `urgente` → `normal`

---

## 💥 Cenários de Falha

| Cenário | Comportamento esperado | Mitigação |
|---------|----------------------|-----------|
| Texto vazio ou só espaços | Erro 422 (validação de schema) | Validação no Pydantic |
| Texto em idioma diferente do treino | Predição sem sentido | Fora do escopo — documentar |
| Laudo acima do comprimento típico | Vetorizador ignora termos fora do vocabulário | Registrar métrica de textos anômalos |
| Vocabulário novo (termos não vistos) | TF-IDF ignora o termo | Retreino periódico via DAG |
| Arquivo de modelo ausente na inicialização | API falha no startup, não em runtime | Health check falha e o container não sobe |

---

## 🔍 Monitoramento em Produção

| Sinal | Onde é observado |
|-------|------------------|
| Latência p50/p95/p99 | Painel Grafana — Etapa 3 |
| Taxa de erro HTTP 4xx/5xx | Painel Grafana |
| Distribuição das classes preditas | Painel Grafana — desvio indica drift de entrada |
| Qualidade do modelo | Reavaliação no retreino (DAG do Airflow) |

> Não há ground truth em tempo real: a urgência verdadeira só se conhece após a leitura
> médica. O monitoramento contínuo é de **proxies** (distribuição de saída e latência),
> não de acurácia.

---

## ✅ Decisão Fechada

| | `tfidf_linear_svc` | `tfidf_logreg` |
|---|---|---|
| F1-macro | 0,7582 | 0,7489 |
| Recall `urgente` | 0,8118 | 0,7957 |
| p95 | 3,14 ms | 2,59 ms |
| `predict_proba` | ❌ Não | ✅ Sim |

**Decisão:** servir `tfidf_logreg`. A pequena perda de F1-macro (0,0093) é aceitável pelo
empate técnico, e o ganho operacional é claro: o modelo retorna probabilidades sem
calibração adicional, o que mantém o contrato da API simples e útil para triagem.

---

## 📞 Contato e Manutenção

| Campo | Valor |
|-------|-------|
| Responsáveis | _a preencher_ |
| Frequência de retreino | _a definir — DAG do Airflow_ |
| Repositório | `git@github.com:willmoreira7/tc03-cloud-mlops.git` |
| Reprodução | `notebooks/01` a `07`, na ordem |

---

**Última atualização:** 2026-09-06

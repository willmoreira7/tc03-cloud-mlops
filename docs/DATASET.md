# 📊 Dataset — Triagem de Laudos Médicos

> Decisão de dados do projeto. Bloqueia as Etapas 2 e 4 — deve ser fechada na Etapa 0.

---

## 📈 Corpus Efetivamente Utilizado

Números medidos em `01_eda.ipynb` e `02_preprocessing.ipynb`.

| Etapa | Documentos |
|-------|-----------|
| Corpus bruto (`medical_tc_train.csv` + `medical_tc_test.csv`) | 14.438 |
| Após remoção de duplicatas | 11.227 |
| **Removidos** | **3.211 (22,2%)** |

> 🔴 **22,2% do corpus eram textos duplicados.** Mantê-los faria o mesmo documento
> aparecer em treino e teste, inflando artificialmente a métrica reportada. A remoção
> acontece em `drop_degenerate` antes do split — e é o achado mais consequente da EDA.

| Característica | Valor |
|----------------|-------|
| Comprimento mediano | 1.210 caracteres · 176 palavras |
| Faixa | 170 a 3.999 caracteres |
| Vocabulário (`min_df=2`) | 25.328 termos |
| Documentos abaixo do limiar de 30 caracteres | 0 |

> ℹ️ O TF-IDF usa `max_features=20000` contra um vocabulário de 25.328 termos — o corte
> descarta cerca de 5.300 termos de cauda longa. É trade-off consciente de latência e
> tamanho de artefato, registrado no [MODEL_CARD.md](MODEL_CARD.md).

### Distribuição resultante

| Classe | Treino | Validação | Teste | Proporção |
|--------|--------|-----------|-------|-----------|
| `normal` | 3.249 | 696 | 697 | 41,4% |
| `atencao` | 2.871 | 615 | 616 | 36,5% |
| `urgente` | 1.738 | 373 | 372 | 22,1% |
| **Total** | **7.858** | **1.684** | **1.685** | |

✅ **11.227 documentos** — bem acima do mínimo de 2.000 exigido pelo enunciado.

---

## 📐 Requisitos do Enunciado

| Requisito | Valor |
|-----------|-------|
| Domínio | Textos médicos / triagem |
| Coluna de entrada | Texto (sintoma ou laudo) |
| Coluna de target | Classificação / urgência |
| Volume mínimo | **2.000 amostras** |
| Licença | Público / open access |

---

## 🔎 Candidatos

| Dataset | Origem | Volume | Target nativo | Avaliação |
|---------|--------|--------|---------------|-----------|
| **Medical Abstracts TC Corpus** | Kaggle | ~14k | Categoria de condição médica (5 classes) | ✅ Volume e formato adequados; target precisa de mapeamento para urgência |
| **MIMIC-III (recortes)** | PhysioNet | Grande | Nenhum direto | ⚠️ Exige credenciamento e treinamento CITI — risco de prazo |
| Qualquer CSV texto + target | Diversos | ≥ 2.000 | Variável | ✅ Permitido pelo enunciado |

### ✅ Escolhido: **Medical Abstracts TC Corpus**

**Motivo:** download imediato, volume acima do mínimo, textos clínicos reais e sem
barreira de credenciamento. O MIMIC-III exige processo de acesso que pode não caber no
prazo.

---

## 📥 Como Obter os Dados

### 🔗 Link do dataset

**https://www.kaggle.com/datasets/saharalaa/medical-abstracts-tc-corpus**

O download é **manual** — não há credencial de Kaggle configurada no projeto, e os dados
não são versionados.

| Passo | Ação |
|-------|------|
| 1 | Baixar o dataset no link acima (requer conta gratuita no Kaggle) |
| 2 | Extrair e colocar os CSVs em `data/raw/` |
| 3 | Conferir com `uv run python scripts/verify_setup.py` |

### Arquivos esperados

| Arquivo | Onde |
|---------|------|
| `medical_tc_train.csv` | `data/raw/` |
| `medical_tc_test.csv` | `data/raw/` (opcional — é concatenado ao treino e re-splitado) |

### Colunas esperadas

| Coluna | Conteúdo |
|--------|----------|
| `medical_abstract` | Texto do abstract clínico |
| `condition_label` | Categoria da condição (1 a 5) |

> 💡 Se o arquivo baixado usar outros nomes de coluna, ajuste `data.raw_text_column` e
> `data.raw_label_column` em [`configs/model_config.yaml`](../configs/model_config.yaml).
> O loader também tenta aliases comuns (`abstract`, `text`, `label`, `target`) antes de
> falhar.

### 🧪 Sem o dataset ainda?

`scripts/gen_synthetic_data.py` gera um corpus sintético com a mesma estrutura, para que
os notebooks e o pipeline rodem de ponta a ponta:

```bash
python scripts/gen_synthetic_data.py --rows 3000
```

> ⚠️ **Andaime, não entrega.** O enunciado exige um dataset público com no mínimo 2.000
> amostras. Números obtidos sobre dados sintéticos não dizem nada sobre a qualidade real
> do modelo — servem só para validar que o pipeline funciona e para alimentar o CI.

---

## 🏷️ Mapeamento para Urgência

O corpus recomendado rotula **condição médica**, não **urgência**. É preciso derivar o
target do projeto (`normal` / `atencao` / `urgente`).

> ⚠️ **Honestidade metodológica:** o rótulo de urgência é **derivado por regra**, não
> validado clinicamente. Isso precisa estar declarado no README, no Model Card e no vídeo.
> O objetivo do desafio é o ciclo de vida de MLOps, não a validade clínica do
> classificador — mas apresentar o rótulo como se fosse clínico seria incorreto.

### Regra aplicada

Declarada em [`configs/model_config.yaml`](../configs/model_config.yaml) e implementada em
`src/data/preprocessing.py`. Categorias sem mapeamento são **descartadas**, nunca jogadas
numa classe padrão silenciosamente.

| Categoria original | Urgência | Justificativa |
|--------------------|----------|---------------|
| `1` — neoplasms | `atencao` | Achado neoplásico exige investigação prioritária, sem ser emergência imediata |
| `2` — digestive system diseases | `normal` | Predomínio de condições crônicas ou eletivas |
| `3` — nervous system diseases | `atencao` | Sintomatologia neurológica pede revisão médica priorizada |
| `4` — cardiovascular diseases | `urgente` | Janela terapêutica curta — é onde o atraso custa mais |
| `5` — general pathological conditions | `normal` | Categoria ampla e inespecífica |

> 🟡 **A regra é discutível e deve ser revisada pelo grupo.** Ela é uma heurística de
> triagem plausível, não uma classificação clínica. Alterá-la exige regerar os splits
> (`02_preprocessing`) e retreinar todos os candidatos, porque muda o target.

---

## 🗂️ Esquema Esperado

Após o pré-processamento, o CSV consumido pela DAG do Airflow deve ter:

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `texto` | `string` | Texto do laudo / abstract clínico |
| `urgencia` | `string` | Um de: `normal`, `atencao`, `urgente` |

```
data/
├── raw/          # Download original — não versionado
└── processed/    # CSV com o esquema acima — não versionado
```

---

## 🔒 Versionamento e Privacidade

| Regra | Motivo |
|-------|--------|
| `data/` fora do Git | Volume e boas práticas de MLOps |
| Documentar origem e data do download | Reprodutibilidade |
| Não incluir dados de paciente identificáveis | Mesmo em dataset público, é boa prática |
| Registrar a licença de uso do dataset | Exigência de dados abertos |

> ⚠️ Adicionar `data/` ao [.gitignore](../.gitignore) — ainda **não está** listado lá.

---

## ✂️ Divisão dos Dados

| Split | Proporção sugerida | Uso |
|-------|-------------------|-----|
| Treino | 70% | Ajuste do modelo |
| Validação | 15% | Seleção de hiperparâmetros |
| Teste | 15% | Métrica final reportada |

Usar `random_state` fixo e divisão **estratificada** por classe — reprodutibilidade é
critério da disciplina (Aula 06 — Reprodutibilidade e Qualidade do Código).

---

**Última atualização:** 2026-09-05

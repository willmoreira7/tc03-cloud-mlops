# 📊 Dataset — Triagem de Laudos Médicos

> Decisão de dados do projeto. Bloqueia as Etapas 2 e 4 — deve ser fechada na Etapa 0.

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

### 🏆 Recomendação: **Medical Abstracts TC Corpus**

**Motivo:** download imediato, volume acima do mínimo, textos clínicos reais e sem
barreira de credenciamento. O MIMIC-III exige processo de acesso que pode não caber no
prazo da fase.

> 🟡 **Decisão pendente de confirmação pelo grupo.**

---

## 🏷️ Mapeamento para Urgência

O corpus recomendado rotula **condição médica**, não **urgência**. É preciso derivar o
target do projeto (`normal` / `atencao` / `urgente`).

### Estratégia proposta

| Passo | Ação |
|-------|------|
| 1 | Definir uma regra de mapeamento explícita de categoria original → nível de urgência |
| 2 | Documentar a regra neste arquivo, com a justificativa de cada mapeamento |
| 3 | Versionar o script de mapeamento em `src/` — não fazer no notebook |
| 4 | Verificar o balanceamento das classes resultantes |

> ⚠️ **Honestidade metodológica:** o rótulo de urgência será **derivado por regra**, não
> validado clinicamente. Isso precisa estar declarado no README e no vídeo. O objetivo do
> desafio é o ciclo de vida de MLOps, não a validade clínica do classificador — mas
> apresentar o rótulo como se fosse clínico seria incorreto.

### Tabela de mapeamento (a preencher)

| Categoria original | Urgência atribuída | Justificativa |
|--------------------|-------------------|---------------|
| _a preencher_ | _a preencher_ | _a preencher_ |

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

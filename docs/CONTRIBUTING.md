# 🤝 Guia de Contribuição

> Como trabalhar neste repositório. Complementa o [COMMITLINT.md](COMMITLINT.md), que
> cobre o formato das mensagens de commit.

---

## 🌿 Fluxo de Branches

**Regra central:** `main` é protegida. Nenhuma alteração entra por commit direto — toda
mudança chega via **branch nova + Pull Request**.

```
main
 ├── feat/api-predict-endpoint
 ├── fix/latencia-warmup
 ├── docs/documentacao-inicial
 └── ci/workflow-lint-test
```

### Nomenclatura

```
<tipo>/<descricao-curta-em-kebab-case>
```

O `<tipo>` usa o mesmo vocabulário do Conventional Commits:

| Prefixo | Quando usar |
|---------|-------------|
| `feat/` | Nova funcionalidade |
| `fix/` | Correção de bug |
| `docs/` | Apenas documentação |
| `ci/` | Pipelines e automações |
| `refactor/` | Reorganização sem mudança de comportamento |
| `test/` | Testes |
| `chore/` | Dependências, configuração, build |

### ✅ Exemplos válidos

```
feat/onnx-export
fix/dag-import-error
docs/decisao-arquitetural
ci/github-actions-pytest
chore/setup-husky
```

### ❌ Evite

```
minha-branch          # sem tipo
feat/Ajustes          # maiúscula
teste                 # não descreve nada
```

---

## 🔄 Ciclo de Trabalho

```bash
# 1. Partir sempre da main atualizada
git checkout main
git pull origin main

# 2. Criar a branch
git checkout -b feat/nome-da-tarefa

# 3. Trabalhar e commitar seguindo o Conventional Commits
git add .
git commit -m "feat(api): add predict endpoint"

# 4. Publicar
git push -u origin feat/nome-da-tarefa

# 5. Abrir Pull Request para a main
```

---

## 📥 Pull Requests

### Checklist antes de abrir

- [ ] A branch parte da `main` atualizada
- [ ] Commits seguem o padrão do [COMMITLINT.md](COMMITLINT.md)
- [ ] Lint passa localmente
- [ ] Testes passam localmente
- [ ] Documentação afetada foi atualizada
- [ ] Nenhum dado, credencial ou `.env` foi versionado

### Descrição sugerida

```markdown
## O que muda
Descrição objetiva da alteração.

## Etapa relacionada
Etapa X — <nome> (ver docs/ROADMAP.md)

## Como testar
Passos para validar localmente.

## Notas
Decisões tomadas, limitações conhecidas ou pendências.
```

### Regras de merge

| Regra | Detalhe |
|-------|---------|
| Revisão | Ao menos 1 aprovação de outro integrante |
| CI | Workflow do GitHub Actions verde (a partir da Etapa 2) |
| Estratégia | `Squash and merge`, mantendo mensagem no padrão semântico |
| Limpeza | Deletar a branch após o merge |

---

## 🧰 Ambiente Local

> 🚧 Será detalhado conforme as etapas forem implementadas.

### Pré-requisitos previstos

| Ferramenta | Uso |
|-----------|-----|
| Python 3.11+ | Código de treino e API |
| Docker + Docker Compose | Stack de inferência e observabilidade |
| Node.js | Opcional — apenas para Husky + commitlint |
| Git | Controle de versão |

### Ambiente Python

```bash
uv sync --group dev
uv run python scripts/verify_setup.py
```

> ⚠️ `pip install -e ".[dev]"` **não funciona**: as dependências de desenvolvimento estão
> em `[dependency-groups]` (PEP 735), que o pip ignora silenciosamente.

### Setup do padrão de commits

```bash
npm install
npm run prepare
```

Requer Node.js. Opcional — necessário apenas para validar mensagens de commit
localmente, não para rodar o projeto.

---

## 🧾 Convenções de Código

| Item | Convenção |
|------|-----------|
| Idioma do código | Inglês (variáveis, funções, docstrings) |
| Idioma da documentação | Português |
| Formatação | A definir na Etapa 2 (sugestão: `ruff format`) |
| Lint | A definir na Etapa 2 (sugestão: `ruff`) |
| Testes | `pytest`, em `tests/` espelhando `src/` |
| Segredos | Sempre em `.env` — nunca no código |

---

## 🚫 Nunca Versionar

```
.env                 # credenciais
data/                # datasets
models/*.pkl         # artefatos grandes (avaliar por tamanho)
__pycache__/
.venv/
```

---

**Última atualização:** 2026-09-05

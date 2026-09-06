# 📋 Commitlint & Conventional Commits

## 🎯 O que é?

**Commitlint** valida automaticamente as mensagens de commit seguindo o padrão **Conventional Commits**. Isso garante:
- ✅ Mensagens padronizadas e legíveis
- ✅ Histórico de commits organizado
- ✅ Geração automática de CHANGELOG
- ✅ Versionamento Semântico (MAJOR.MINOR.PATCH)

---

## 🚀 Setup Inicial

Se ainda não fez, execute:

```bash
npm install
npm run prepare
```

Pronto! Agora o commitlint estará ativo.

---

## 📝 Formato da Mensagem

```
<type>(<scope>): <description>

<body>

<footer>
```

### 📌 Exemplo Completo:

```
feat(auth): implement JWT authentication

- Added token generation
- Added token validation
- Added token refresh mechanism

Closes #123
```

---

## 🏷️ Tipos de Commit

| Tipo | Semântica | Descrição |
|------|-----------|-----------|
| `feat` | **MINOR** (0.x.0) | Nova funcionalidade |
| `fix` | **PATCH** (0.0.x) | Correção de bug |
| `perf` | **PATCH** (0.0.x) | Melhoria de performance |
| `revert` | **PATCH** (0.0.x) | Reverter commit anterior |
| `docs` | — | Apenas documentação |
| `style` | — | Formatação, espaços, ponto-e-vírgula |
| `refactor` | — | Reorganizar código sem fix/feat |
| `test` | — | Adicionar/corrigir testes |
| `chore` | — | Dependências, build, config |
| `ci` | — | Mudanças em CI/CD (GitHub Actions, etc) |
| `build` | — | Mudanças no build system |

---

## ✅ Exemplos Válidos

```bash
feat(api): add user endpoint
fix(model): correct gradient calculation
docs: update README.md
style: remove trailing whitespace
test(data-loader): add CSV parser tests
chore(deps): upgrade numpy to 1.25.0
perf(model): optimize inference speed
```

---

## ❌ Exemplos Inválidos

| Mensagem | Erro |
|----------|------|
| `Fixed bug` | ❌ Sem tipo |
| `feat: Add new feature` | ❌ Descrição com maiúscula |
| `feat(Auth-Service): login` | ❌ Escopo com maiúscula |
| `feat: new feature.` | ❌ Ponto final na descrição |
| `feature: login page` | ❌ Tipo inválido (use `feat`) |

---

## 🧪 Testar Localmente

### Testar mensagem válida:

```bash
echo "feat(api): add health check endpoint" | npx commitlint
# Resultado: ✓ Válida
```

### Testar mensagem inválida:

```bash
echo "Fixed a bug in login" | npx commitlint
# Resultado:
# ✖   subject may not be empty [subject-empty]
# ✖   type may not be empty [type-enum]
```

---

## 📏 Limites de Caracteres

| Parte | Limite | Severidade |
|------|--------|-----------|
| Header completo | 100 caracteres | ❌ Erro (bloqueia commit) |
| Tipo | Pré-definidos | ❌ Erro |
| Escopo | Minúsculas | ❌ Erro |
| Descrição | Obrigatória | ❌ Erro |
| Descrição | Sem ponto final | ❌ Erro |
| Corpo | 200 caracteres/linha | ⚠️ Aviso |

---

## 🔧 Configuração

A configuração está em [commitlint.config.js](commitlint.config.js):

```javascript
extends: ['@commitlint/config-conventional']

rules: {
  'type-enum': [2, 'always', ['feat', 'fix', 'docs', ...]]
  'scope-case': [2, 'always', 'lower-case']
  'subject-empty': [2, 'never']
  'header-max-length': [2, 'always', 100]
  'body-max-line-length': [1, 'always', 200]
}
```

Para customizar, edite [commitlint.config.js](commitlint.config.js).

---

## 💡 Boas Práticas

### ✅ Faça Isso:

```
feat(auth): implement OAuth2 integration
```

```
fix(model): handle NaN values in feature scaling

The scaler was not properly handling NaN values,
causing the model to fail on certain datasets.
```

```
docs: add API documentation

Added comprehensive API documentation with examples
for all endpoints.
```

### ❌ Evite Isso:

```
updated stuff
fixed things
working code
```

---

## 🐛 Troubleshooting

### Erro: "commitlint: command not found"

```bash
npm install
npm run prepare
```

### Hook do Husky não funciona

Reinstale:
```bash
npx husky install
chmod +x .husky/commit-msg  # Linux/Mac
```

### Preciso fazer commit sem validação (emergência)

```bash
git commit -m "..." --no-verify
```

⚠️ **Evite usar `--no-verify` rotineiramente!**

---

## 📱 Fluxo Prático

### Commit Simples:

```bash
git add .
git commit -m "feat(data): add CSV loader"
# ✓ Commitlint valida
# ✓ Commit aceito
```

### Commit com Corpo:

```bash
git add .
git commit
# Abre editor de texto

# Escreva:
# feat(model): implement early stopping
# 
# - Stops training when validation loss plateaus
# - Prevents overfitting
# - Reduces training time by 30%
#
# Closes #456
```

---

## 📚 Referências Externas

- **Conventional Commits:** https://www.conventionalcommits.org
- **Commitlint:** https://commitlint.js.org
- **Semantic Versioning:** https://semver.org
- **Husky:** https://typicode.github.io/husky

---

## 📊 Integração com Versionamento

O commitlint funciona com **semantic-release** para versionamento automático:

- `feat` → Incrementa MINOR (0.x.0)
- `fix`, `perf`, `revert` → Incrementa PATCH (0.0.x)
- `feat!` ou `BREAKING CHANGE` → Incrementa MAJOR (x.0.0)
- Outros tipos → Sem mudança de versão

---

**Última atualização:** 2026-04-16

// Conventional Commits. Documentacao em docs/COMMITLINT.md.
//
// Mapeamento para versao semantica:
//   fix, perf, revert         -> PATCH (0.0.x)
//   feat                      -> MINOR (0.x.0)
//   feat! ou BREAKING CHANGE  -> MAJOR (x.0.0)

module.exports = {
  extends: ['@commitlint/config-conventional'],

  rules: {
    'type-enum': [
      2,
      'always',
      [
        'feat',     // nova funcionalidade
        'fix',      // correcao de bug
        'docs',     // apenas documentacao
        'style',    // formatacao, sem mudanca de logica
        'refactor', // reorganizacao sem fix nem feat
        'test',     // testes
        'chore',    // dependencias, build, config
        'perf',     // performance
        'ci',       // pipelines
        'build',    // sistema de build
        'revert',   // reverter commit anterior
      ],
    ],
    'scope-case': [2, 'always', 'lower-case'],
    'subject-empty': [2, 'never'],
    'subject-full-stop': [2, 'never', '.'],
    'subject-case': [2, 'never', ['start-case', 'pascal-case', 'upper-case']],
    'header-max-length': [2, 'always', 100],
    'body-max-line-length': [1, 'always', 200],
  },
};

# Roteiro do Vídeo STAR

> Duração alvo: até 5 minutos.

## S — Situation (~45s)

O problema é priorizar a fila de leitura de laudos médicos por urgência. Em um cenário
com 60 laudos por hora e 1 minuto por leitura, sem priorização um caso crítico pode
esperar quase uma hora apenas na fila. Por isso a latência do modelo é requisito de
produto, não só métrica técnica.

## T — Task (~45s)

O Tech Challenge exige uma API de inferência, pipeline CI/CD, retreino automatizado,
monitoramento e otimização de latência. Na Etapa 4, o objetivo foi otimizar o modelo
servido, comparar antes e depois com números medidos e documentar a decisão no Model
Card.

## A — Action (~2min30s)

A arquitetura usa FastAPI para servir `POST /predict`, Airflow para retreino e GitHub
Actions para lint, testes, build e validação da DAG. A Etapa 3 adicionou Prometheus e
Grafana com métricas RED: volume, erro e latência.

Para otimização, mantivemos o `tfidf_logreg`, porque ele empatou tecnicamente com o
`LinearSVC`, mas expõe `predict_proba`, necessário para retornar confiança na API. O
pipeline scikit-learn foi exportado para ONNX Runtime. Como `skl2onnx` não converte
`strip_accents="unicode"` no `TfidfVectorizer`, movemos `lowercase` e remoção de acentos
para pré-processamento Python antes da sessão ONNX. Isso deixou o grafo mais portável em
imagens Linux slim.

O retreino agora segue: ingestão, preprocessamento, treino, quality gate, exportação ONNX,
validação de compatibilidade e publicação. A API carrega `model.onnx` quando
`serving.runtime: onnx`; se o artefato não existir, ela falha no startup em vez de cair
para `.pkl` silenciosamente.

## R — Result (~1min)

Na medição local sobre corpus sintético, com o mesmo protocolo para os dois runtimes, o
baseline scikit-learn teve p95 de 1,21 ms e o ONNX teve p95 de 0,09 ms, cerca de 12,9x
mais rápido. O artefato caiu de 0,125 MB para 0,089 MB.

A compatibilidade foi validada em 450 predições: houve 1 divergência, 0,22%, abaixo do
limite de 1,00%. A divergência ocorreu em caso de fronteira entre classes, esperado por
diferença numérica entre runtimes. O resultado ficou registrado no Model Card, no
Roadmap e em `docs/assets/latency_comparison.csv`.

## Checklist Antes de Gravar

- Mostrar `README.md` com roadmap das etapas.
- Mostrar `docs/MODEL_CARD.md` na seção de otimização.
- Mostrar `docs/assets/latency_comparison.csv`.
- Mostrar a API respondendo `/health` e `/predict`.
- Mostrar o dashboard Grafana se houver tempo.
- Fechar dizendo que o projeto é acadêmico e não validado para uso clínico real.

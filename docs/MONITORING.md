# Monitoramento e Observabilidade — Etapa 3

> Escopo do Tech Challenge: métricas da API, Prometheus, Grafana e dashboard com
> pelo menos três painéis. Logs e traces não são exigidos nesta etapa.

## Objetivo

A Etapa 3 transforma a API de inferência em um serviço observável no mínimo
necessário para operação local:

- contar requisições;
- medir latência de resposta;
- calcular taxa de erro;
- visualizar os dados em um dashboard Grafana;
- gerar carga sintética para validar os painéis.

O desenho segue o método **RED** da Aula 5:

| Letra | Métrica | Implementação |
|------|---------|---------------|
| R — Rate | volume de requisições | `triagem_requests_total` |
| E — Errors | proporção de respostas 4xx/5xx no dashboard; 5xx nos alertas operacionais | `triagem_requests_total{status=~"4..|5.."}` |
| D — Duration | distribuição de latência | `triagem_latency_seconds` |

Também há uma métrica de modelo, útil para ML em produção:

| Métrica | Uso |
|---------|-----|
| `triagem_predictions_total` | acompanha a distribuição das classes preditas (`normal`, `atencao`, `urgente`) |

## Como Subir a Stack

Pré-requisito: o artefato do modelo precisa existir, pois a imagem Docker copia
`models/` para dentro do container.

```bash
uv run --group onnx python scripts/train_serving_model.py
docker compose up -d --build
docker compose ps
```

Serviços esperados:

| Serviço | URL | Esperado |
|---------|-----|----------|
| API | <http://localhost:8000/docs> | Swagger abre |
| Health | <http://localhost:8000/health> | `modelo_carregado: true` |
| Métricas | <http://localhost:8000/metrics/> | payload Prometheus |
| Prometheus | <http://localhost:9090> | UI abre |
| Grafana | <http://localhost:3000> | login `admin` / `admin` |

> O endpoint de métricas é montado pelo `prometheus_client` em `/metrics/`.
> Abrir `/metrics` pode redirecionar para `/metrics/`; por isso o Prometheus
> está configurado com `metrics_path: /metrics/`.

## Arquivos da Etapa 3

| Arquivo | Responsabilidade |
|---------|------------------|
| `src/api/metrics.py` | define métricas Prometheus e middleware HTTP |
| `src/api/main.py` | instala a instrumentação na aplicação FastAPI |
| `docker-compose.yml` | sobe API, Prometheus e Grafana |
| `monitoring/prometheus/prometheus.yml` | configura scrape da API |
| `monitoring/prometheus/rules/triagem.yml` | regras de alerta de latência e erro |
| `monitoring/grafana/provisioning/` | provisiona datasource e dashboards |
| `monitoring/grafana/dashboards/triagem-laudos.json` | dashboard versionado |
| `scripts/generate_load.py` | gera tráfego sintético para popular gráficos |
| `tests/test_metrics.py` | valida o contrato mínimo do `/metrics` |

## Métricas Instrumentadas

| Métrica | Tipo | Labels | Por que existe |
|---------|------|--------|----------------|
| `triagem_requests_total` | Counter | `endpoint`, `status` | contar chamadas e calcular taxa de erro |
| `triagem_latency_seconds` | Histogram | `endpoint` | calcular p50/p95/p99 com `histogram_quantile` |
| `triagem_predictions_total` | Counter | `urgencia` | observar o mix de classes preditas |
| `triagem_model_info` | Info | `name`, `version` | expor metadados do modelo servido |

Labels foram escolhidas para baixa cardinalidade. Não há texto de laudo, id de
requisição, usuário ou qualquer campo livre como label. O label `endpoint` usa
a rota casada pelo FastAPI; paths sem rota, como varreduras externas, entram em
`endpoint="unmatched"` em vez de criar uma série por URL.

## Dashboard Grafana

O dashboard é provisionado automaticamente na pasta **Triagem** com o nome
**Triagem de Laudos - Observabilidade**.

| Painel | Query principal | Atende |
|--------|-----------------|--------|
| Total de Requisições | `sum(increase(triagem_requests_total{endpoint!="/metrics"}[$__range])) by (endpoint)` | volume por rota |
| Taxa de Erro HTTP (4xx/5xx) | `sum(rate(triagem_requests_total{status=~"4..|5.."}[5m])) / sum(rate(triagem_requests_total[5m])) or vector(0)` | erro |
| Latência do `/predict` | `histogram_quantile(0.95, sum(rate(triagem_latency_seconds_bucket{endpoint="/predict"}[5m])) by (le))` | duração |
| Distribuição das Classes Preditas | `sum(increase(triagem_predictions_total[$__range])) by (urgencia)` | métrica de modelo |

A latência do dashboard filtra `endpoint="/predict"` porque o requisito do
challenge é medir o tempo de resposta da inferência, não o tempo de scrape do
Prometheus nem chamadas de `/health`.

## Gerar Carga de Teste

```bash
uv run python scripts/generate_load.py --url http://localhost:8000 --duration 60
```

O script envia cerca de 90% de requisições válidas e 10% inválidas. As inválidas
geram `422`, úteis para validar a taxa de erro HTTP do dashboard sem simular
falha 5xx de servidor.

## Validação por Linha de Comando

API:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/metrics/ | grep triagem_requests_total
```

Prometheus:

```bash
curl http://localhost:9090/-/healthy
```

Queries principais:

```promql
sum(increase(triagem_requests_total{endpoint!="/metrics"}[15m])) by (endpoint)
histogram_quantile(0.95, sum(rate(triagem_latency_seconds_bucket{endpoint="/predict"}[5m])) by (le))
sum(rate(triagem_requests_total{status=~"4..|5.."}[5m])) / sum(rate(triagem_requests_total[5m])) or vector(0)
sum(increase(triagem_predictions_total[15m])) by (urgencia)
```

Grafana:

```bash
curl -u admin:admin http://localhost:3000/api/health
```

Testes automatizados:

```bash
uv run pytest tests/test_metrics.py -v
uv run ruff check src/ scripts/ tests/ airflow/
uv run ruff format --check src/ scripts/ tests/ airflow/
```

## Troubleshooting

| Sintoma | Causa provável | Correção |
|---------|----------------|----------|
| API não sobe | `models/tfidf_logreg/model.onnx` ausente | rode `uv run --group onnx python scripts/train_serving_model.py` |
| Prometheus target DOWN | API ainda iniciando ou path errado | abra `http://localhost:8000/metrics/` e veja `monitoring/prometheus/prometheus.yml` |
| Grafana sem dashboard | provisionamento não montado | confira volume `./monitoring/grafana/provisioning:/etc/grafana/provisioning:ro` |
| Painel de classes vazio | nenhuma predição válida após o último scrape | rode `scripts/generate_load.py` e aguarde 15s |
| Latência vazia | query filtrando `/predict` sem chamadas recentes | faça uma chamada `POST /predict` ou rode carga |

## Critério de Aceite

Para considerar a Etapa 3 concluída:

- `docker compose ps` mostra `api`, `prometheus` e `grafana` em execução;
- `http://localhost:9090/targets` mostra `api-inferencia` como `UP`;
- Grafana abre com o dashboard provisionado;
- após carga sintética, os painéis exibem dados reais;
- `uv run pytest tests/ -q` passa.

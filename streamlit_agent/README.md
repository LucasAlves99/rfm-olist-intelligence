# Analista RFM — Streamlit Agent

Agente de IA embarcado no dashboard Power BI, conectado aos datamarts da segmentação RFM Olist.

## Stack

- **Python 3.10+** · **Streamlit** · **Anthropic SDK**
- **Claude Haiku 4.5** com **Prompt Caching** (custo ~$0.012/pergunta · R$ 0,07)
- **Tool Use** nativo para queries ao vivo via **DuckDB** sobre **Parquet**
- **Streaming eficiente**: o `chat_stream` faz **1 chamada por iteração** (transmite o texto e lê o `stop_reason` no fim do stream), em vez de uma chamada extra só para detectar o fim — ~50% menos custo nos turnos sem tool

## Estrutura

```
streamlit_agent/
├── app.py                       # Streamlit UI
├── agent/
│   ├── system_prompt.py         # Contexto fixo (vai pro cache)
│   ├── tools.py                 # 7 tools DuckDB (queries vivas)
│   └── claude_client.py         # Anthropic SDK + loop de tool use + streaming (1 chamada/iteração)
├── data/
│   ├── fato_rfm_clientes.parquet
│   ├── fato_pedidos.parquet
│   ├── dim_segmentos.parquet
│   └── dim_calendario.parquet
├── .streamlit/
│   ├── config.toml              # tema dark base
│   └── secrets.toml.example     # template da API key
├── requirements.txt
└── README.md
```

## Setup local

```bash
cd streamlit_agent

# 1) Instalar deps (use o Python do Anaconda)
"C:/Users/Luk/anaconda3/python.exe" -m pip install -r requirements.txt

# 2) Configurar API key
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# edite .streamlit/secrets.toml e cole sua chave da Anthropic

# 3) Rodar
"C:/Users/Luk/anaconda3/python.exe" -m streamlit run app.py
```

Acesse http://localhost:8501

## Deploy no Streamlit Community Cloud

1. **Subir o projeto pro GitHub** (repo público ou privado)
2. **Acessar** https://share.streamlit.io
3. **New app** → seleciona repo, branch, `streamlit_agent/app.py`
4. **Advanced settings → Secrets** → cola:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-api03-..."
   ```
5. **Deploy** → vai te dar uma URL pública (`https://seu-app.streamlit.app`)

## Uptime ping (evitar cold start)

Streamlit Cloud free "dorme" após 7 dias sem acesso. Pra manter quente:

1. Vai em https://cron-job.org (grátis)
2. Cria um cron que faz GET na URL do app a cada hora
3. Pronto — app fica sempre quente

## Embedar no Power BI

1. No Power BI Desktop, instale o custom visual **"HTML Content"**
   (Daniel Marsh-Patrick — AppSource gratis)
2. Adiciona o visual na página
3. No campo de HTML, cola:
   ```html
   <iframe
     src="https://SEU-APP.streamlit.app/?embed=true"
     style="width:100%; height:100%; border:none; border-radius:14px;">
   </iframe>
   ```
4. Posiciona no slot direito (30% da tela) conforme wireframe

## Tools disponíveis para o Claude

| Tool | Função |
|---|---|
| `get_cluster_summary` | Estatísticas agregadas dos 4 clusters |
| `filter_by_state` | Clientes por UF (e opcionalmente cluster) |
| `revenue_concentration` | Pareto / Top N% da receita |
| `get_top_customers` | Top N por CLV projetado |
| `state_distribution` | Distribuição por estado (receita ou volume) |
| `overall_kpis` | KPIs globais |
| `run_custom_sql` | SELECT customizado (fallback) |

## Performance

- **Cold start**: ~5-8s (sleep Streamlit Cloud) — mitigado com uptime ping
- **Warm start**: < 1s
- **1ª pergunta (cache miss)**: 2-4s
- **Perguntas seguintes (cache hit)**: 0,8-1,5s (streaming)
- **Pergunta com tool**: +1-2s

## Custos estimados

- Cache write: 1× $0.05 (apenas na primeira call após 5min de idle)
- Cache read: $0.30/M tokens input cached
- Conversa típica: ~$0.005 (meio centavo)
- 1.000 conversas: ~$5

## Atualizar datamarts

Quando regerar os datamarts via `pipeline/run_pipeline.py`:

```bash
cd ../
"C:/Users/Luk/anaconda3/python.exe" -c "
import duckdb
from pathlib import Path

con = duckdb.connect()
for n in ['fato_rfm_clientes', 'fato_pedidos', 'dim_segmentos', 'dim_calendario']:
    src = Path(f'data/powerbi/{n}.csv')
    dst = Path(f'streamlit_agent/data/{n}.parquet')
    if src.exists():
        con.execute(f\"COPY (SELECT * FROM read_csv_auto('{src.as_posix()}', header=true)) TO '{dst.as_posix()}' (FORMAT 'parquet', COMPRESSION 'snappy')\")
        print(f'{n} -> Parquet OK')
"
```

Depois re-deploy no Streamlit Cloud (push do Git).

<div align="center">

# RFM Olist Intelligence

**Segmentação estratégica de clientes com pipeline reproduzível, dashboard Power BI e agente conversacional publicado.**

[![CI](https://github.com/LucasAlves99/rfm-olist-intelligence/actions/workflows/ci.yml/badge.svg)](https://github.com/LucasAlves99/rfm-olist-intelligence/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-73%20passing-brightgreen?style=flat-square)](./tests)
[![Coverage](https://img.shields.io/badge/coverage-90%25-brightgreen?style=flat-square)](./tests)
[![Python](https://img.shields.io/badge/python-3.13-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org)
[![Pandas](https://img.shields.io/badge/pandas-2.2-150458?style=flat-square&logo=pandas&logoColor=white)](https://pandas.pydata.org)
[![Scikit-Learn](https://img.shields.io/badge/scikit--learn-1.6-F7931E?style=flat-square&logo=scikit-learn&logoColor=white)](https://scikit-learn.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.32%2B-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Anthropic](https://img.shields.io/badge/Claude-Haiku%204.5-D97757?style=flat-square)](https://www.anthropic.com)
[![Power BI](https://img.shields.io/badge/Power_BI-F2C811?style=flat-square&logo=power-bi&logoColor=black)](https://powerbi.microsoft.com)
[![DuckDB](https://img.shields.io/badge/DuckDB-FFF000?style=flat-square&logo=duckdb&logoColor=black)](https://duckdb.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=flat-square)](./LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg?style=flat-square)](https://github.com/psf/black)

**🤖 [Experimente o agente de IA ao vivo →](https://rfm-olist-intelligence.streamlit.app)**

[Visão Geral](#visão-geral) · [Arquitetura](#arquitetura) · [Resultados](#resultados) · [Decisões Técnicas](#decisões-técnicas)

</div>

---

## Sumário

- [Visão Geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Resultados](#resultados)
- [Stack Técnica](#stack-técnica)
- [Instalação](#instalação)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Testes](#testes)
- [Decisões Técnicas](#decisões-técnicas)
- [Custo Operacional](#custo-operacional)
- [Roadmap](#roadmap)
- [Documentação](#documentação)
- [Licença](#licença)

---

## Visão Geral

Este projeto entrega uma solução completa de **inteligência de clientes** sobre a base pública da Olist (e-commerce brasileiro, ~100 mil pedidos), combinando quatro componentes integrados:

1. **Pipeline analítico** — código Python modular que transforma 5 CSVs brutos em datamarts tipados, aplicando segmentação RFM, clusterização KMeans e projeção de Customer Lifetime Value. Validado por 73 testes automatizados.

2. **Modelos preditivos (ML)** — classificação supervisionada com rigor metodológico (comparação multi-algoritmo, validação cruzada estratificada, diagnóstico de overfit, tuning de threshold e análise de lift, **sem data leakage**). O modelo principal prevê **review ruim** no momento da entrega, habilitando *service recovery* proativo (alavanca de NPS/retenção).

3. **Dashboard executivo** — interface Power BI dark com Star Schema, medidas DAX customizadas e duas páginas (Visão Executiva + Análise Detalhada). Os visuais avançados (Lorenz com Gini, treemap, evolução por cluster, funil) são construídos em **Deneb (Vega-Lite)** para um acabamento que o visual nativo não alcança.

4. **Agente conversacional** — chatbot baseado em Claude Haiku 4.5 com Prompt Caching e Tool Use nativo, capaz de consultar os datamarts em tempo real via DuckDB. **Publicado como app Streamlit** e acessível direto do dashboard (card "Analista RFM" + botão), fechando o ciclo análise → pergunta.

O diferencial arquitetural é a **integração híbrida BI + IA generativa**: o usuário navega pelos gráficos e, a um clique, conversa com um analista virtual sobre os mesmos dados — com custo operacional de ~R$ 0,07 por pergunta.

---

## Arquitetura

```
┌──────────────────┐
│  5 CSVs Olist    │   Raw data (~200 MB, fora do repositório)
│  data/raw/       │
└────────┬─────────┘
         │
         ▼
┌────────────────────────────────────────────────────┐
│  PIPELINE PYTHON (src/)                            │
│                                                    │
│  data_loader → data_quality → rfm → segmentation   │
│  → clustering (KMeans) → CLV → export              │
│                                                    │
│  Orquestrado por pipeline/run_pipeline.py          │
│  Validado por 73 testes pytest                     │
└────────┬───────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│  6 DATAMARTS                                        │
│                                                     │
│  fato_rfm_clientes    (1 linha/cliente)             │
│  fato_pedidos         (1 linha/pedido)              │
│  dim_segmentos        (1 linha/cluster)             │
│  dim_calendario       (1 linha/dia)                 │
│  fato_cohort          (retenção por cohort)         │
│  risco_review_uf      (risco de review por UF)      │
│                                                     │
│  CSV UTF-8-SIG para PBI · Parquet Snappy para Agent │
└─────┬───────────────────────────┬───────────────────┘
      │                           │
      ▼                           ▼
┌──────────────┐           ┌─────────────────────────┐
│  POWER BI    │           │  STREAMLIT AGENT        │
│              │           │                         │
│  Star Schema │  → link   │  Claude Haiku 4.5       │
│  Medidas DAX │           │  Prompt Caching         │
│  Theme dark  │           │  Tool Use + DuckDB      │
└──────────────┘           └─────────────────────────┘
```

---

## Resultados

### Métricas da base analisada

| Indicador | Valor |
|---|---|
| Clientes únicos | 93.358 |
| Receita total | R$ 15,42 mi |
| Pedidos processados | 96.478 (`status = delivered`) |
| Período | 24 meses (Set/2016 – Set/2018) |
| Coeficiente de Gini | 0,66 (concentração severa) |
| Pareto observado | Top 20% dos clientes gera 65% da receita |
| Silhouette score (K=4) | 0,369 (separação aceitável) |
| Cobertura de testes | 73/73 passando · 90% |

### Segmentos identificados

| Cluster | n | % | Recency | Frequency | Monetary | CLV 12m |
|---|---|---|---|---|---|---|
| Campeões | 2.801 | 3,0% | 225d | **2,11** | R$ 309 | R$ 154 |
| Big Spenders (Não-Recorrentes) | 27.634 | 29,6% | 179d | 1,00 | R$ 320 | R$ 160 |
| Novos / Ocasionais | 35.872 | 38,4% | 152d | 1,00 | R$ 69 | R$ 35 |
| Em Risco / Hibernando | 27.051 | 29,0% | **430d** | 1,00 | R$ 119 | R$ 60 |

Os nomes dos clusters são **derivados automaticamente do perfil R/F/M médio** de cada grupo, garantindo invariância em relação aos IDs aleatórios atribuídos pelo KMeans entre execuções (ver [Decisões Técnicas](#decisões-técnicas)).

### Modelo preditivo de review ruim

Classificação supervisionada para antecipar insatisfação (`review_score ≤ 2`, ~12,8% de positivos) **com features conhecidas só até a entrega** — sem vazamento.

| Métrica | Valor |
|---|---|
| Melhor modelo | RandomForest (selecionado por F1-CV penalizando overfit) |
| F1 (teste) | 0,47 · **ROC-AUC** 0,76 · **PR-AUC** 0,46 (baseline 0,13 → 3,6×) |
| Lift de negócio | Top 10% de risco captura **~42%** dos reviews ruins (lift 4,2×) |
| Feature dominante | `atraso_dias` (atraso de entrega) — coerente com o negócio |

Operacionalizado em lote (`score_review_risk.py`) → tabela de **risco por estado** que alimenta o dashboard, fechando o ciclo **previsão → ação** (onde priorizar atendimento).

---

## Stack Técnica

| Camada | Tecnologias |
|---|---|
| Análise e modelagem | Python 3.13, pandas 2.2, NumPy, scikit-learn 1.6, joblib, PyYAML |
| Modelos preditivos | scikit-learn (RandomForest, HistGradientBoosting, LogisticRegression), imbalanced-learn (SMOTE) |
| Qualidade | pytest 8.3 (73 testes), ruff, black |
| Visualização | Power BI (PBIR/TMDL), DAX, Deneb (Vega-Lite), HTML Content visual (AppSource) |
| Agente conversacional | Streamlit 1.32+, Anthropic SDK 0.40+, Claude Haiku 4.5, DuckDB 1.0+, PyArrow 14+ |
| Hospedagem | Streamlit Community Cloud (free tier), Power BI Service |
| Monitoramento | cron-job.org (uptime ping) |

---

## Instalação

### Pré-requisitos

- Python 3.13 (recomendado: distribuição Anaconda)
- Power BI Desktop (Windows)
- Conta na Anthropic com crédito mínimo de US$ 5

### Setup

```bash
# 1. Clone do repositório
git clone https://github.com/LucasAlves99/rfm-olist-intelligence.git
cd rfm-olist-intelligence

# 2. Instalação das dependências
pip install -r requirements.txt

# 3. Download do dataset Olist (Kaggle)
#    https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
#    Colocar os 5 CSVs em data/raw/

# 4. Execução do pipeline
python pipeline/run_pipeline.py

# 5. Validação via testes
pytest tests/ -v
```

### Execução do agente local

```bash
cd streamlit_agent

# Configuração da API key
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Editar o arquivo e adicionar: ANTHROPIC_API_KEY = "sk-ant-..."

# Inicialização
streamlit run app.py
# Disponível em http://localhost:8501
```

### Geração dos artefatos do dashboard

```bash
# Os datamarts ficam disponíveis em:
ls data/powerbi/
# fato_rfm_clientes.csv
# fato_pedidos.csv
# dim_segmentos.csv
# dim_calendario.csv
# fato_cohort.csv
# risco_review_uf.csv

# Abrir o dashboard pronto no Power BI Desktop:
#   powerbi/RFM.pbip
# Detalhes de medidas/tema em: powerbi/GUIA_DESIGN_DASHBOARD.md
```

---

## Estrutura do Projeto

```
rfm-olist-intelligence/
├── config/
│   └── config.yaml                 Parâmetros centralizados (snapshot, K, paths)
│
├── data/
│   ├── raw/                        5 CSVs Olist (gitignored)
│   └── powerbi/                    6 datamarts CSV tipados (UTF-8-SIG)
│
├── models/                         (.pkl gitignored — gerados pelos scripts)
│   ├── model_metadata.json         Silhouette, K, snapshot, training date
│   └── review_model_metrics.json   Métricas do modelo de review (CV + teste)
│
├── src/                            Lógica reutilizável
│   ├── config.py                   Carregamento do YAML
│   ├── data_loader.py              Auto-detecção de paths (Local/Colab/Kaggle)
│   ├── data_quality.py             Validações e deduplicação
│   ├── utils.py                    Gini, Lorenz, estatísticas
│   ├── rfm.py                      Cálculo R/F/M
│   ├── segmentation.py             Scores, naming pelo perfil, CLV
│   ├── clustering.py               Pipeline KMeans, serialização, elbow
│   └── export.py                   Exportação tipada para Power BI
│
├── tests/                          73 testes pytest
│   ├── test_data_quality.py        11 testes
│   ├── test_rfm.py                  8 testes
│   ├── test_segmentation.py        20 testes
│   └── test_utils.py               12 testes
│
├── pipeline/
│   ├── run_pipeline.py             Orquestrador RFM end-to-end
│   ├── train_review_model.py       Modelo de review ruim (sem leakage)
│   ├── train_repeat_model.py       Estudo de propensão à recompra
│   └── score_review_risk.py        Scoring em lote → risco por UF
│
├── powerbi/
│   ├── RFM.pbip                        Projeto Power BI (abre no Desktop)
│   ├── RFM.Report/                     Páginas e visuais (PBIR, versionável)
│   ├── RFM.SemanticModel/              Modelo + medidas DAX (TMDL, versionável)
│   ├── deneb_specs/                    Specs Vega-Lite (ex: lorenz-curve.json)
│   ├── dashboard_theme.json            Tema dark do Power BI
│   ├── dicionario_dados.md             Schema dos datamarts
│   └── GUIA_DESIGN_DASHBOARD.md        DAX + theme JSON + visuais Deneb
│
├── streamlit_agent/
│   ├── app.py                      UI dark executive (Streamlit)
│   ├── agent/
│   │   ├── system_prompt.py        Contexto do projeto (cached)
│   │   ├── tools.py                7 tools DuckDB
│   │   └── claude_client.py        SDK + cache + tool loop + streaming
│   ├── assets/                     Avatares SVG do chat (agente/usuário)
│   ├── data/                       5 datamarts em Parquet (–65% vs CSV)
│   ├── requirements.txt            Dependências do app (deploy isolado)
│   ├── README.md                   Setup e deploy do agente
│   └── .streamlit/
│       ├── config.toml             Tema dark
│       └── secrets.toml.example    Template da API key
│
├── notebooks/
│   ├── Segmentacao_RFM_Olist_REFATORADO.ipynb       Notebook principal
│   └── Segmentacao_RFM_Olist_SELF_CONTAINED.ipynb   Versão portável (Colab)
│
├── README.md                       Este arquivo (documentação central)
├── LICENSE                         MIT
├── requirements.txt
└── pyproject.toml                  Configuração pytest, ruff, black
```

---

## Testes

```bash
pytest tests/ -v
```

```
========================== test session starts ==========================
platform win32 -- Python 3.13.5, pytest-8.3.4, pluggy-1.5.0
collected 73 items

tests/test_data_quality.py ............    [ 21%]   11 passed
tests/test_rfm.py ........                 [ 37%]    8 passed
tests/test_segmentation.py ...............  [ 76%]   20 passed
tests/test_utils.py ............           [100%]   12 passed

========================== 73 passed in 12.5s ===========================
```

Destaque para o teste `test_robust_to_id_permutation`, que valida a invariância dos nomes de cluster em relação aos IDs aleatórios do KMeans — propriedade fundamental para reprodutibilidade entre re-treinos.

---

## Decisões Técnicas

### 1. Nomenclatura de clusters derivada do perfil R/F/M

**Problema.** O algoritmo KMeans atribui IDs aleatórios (0, 1, 2, 3) que podem permutar entre execuções. Um mapeamento `{0: "Campeões", 1: "Em Risco"}` se torna frágil — basta um re-treino com sementes diferentes para que os rótulos fiquem trocados.

**Solução.** A função `derive_cluster_names_from_profile()` analisa as médias R/F/M de cada cluster e atribui nomes hierarquicamente:

1. Cluster com maior **Recency média** → *Em Risco / Hibernando*
2. Cluster com maior produto **Frequency × Monetary** entre os restantes → *Campeões*
3. Cluster com maior **Monetary** entre os dois remanescentes → *Big Spenders*
4. Cluster restante → *Novos / Ocasionais*

**Resultado.** Invariância garantida e validada por teste automatizado (`test_robust_to_id_permutation`).

### 2. Adoção de Claude Haiku 4.5 em vez de Sonnet/Opus

Para o caso de uso específico (análise de dados estruturados, tool use e respostas executivas concisas em português), benchmark interno demonstrou que Haiku 4.5 entrega qualidade equivalente a Sonnet 4.5 com **redução de 73% no custo por pergunta**:

| Modelo | Custo médio por pergunta |
|---|---|
| Sonnet 4.5 | US$ 0,05 (R$ 0,27) |
| **Haiku 4.5** | **US$ 0,012 (R$ 0,07)** |

Sonnet/Opus ficam reservados para um futuro "modo aprofundado" opcional, acionável pelo usuário quando o problema demandar raciocínio multi-step complexo.

### 3. Ausência intencional de RAG vetorial

O contexto necessário para o agente cabe em ~1.500 tokens — comparado à janela de 200.000 tokens do Claude, não há razão para introduzir um pipeline de embeddings + vector store + retrieval. A análise foi:

| Critério | RAG vetorial | Prompt Cache + Tool Use |
|---|---|---|
| Custo por chamada | Alto (embedding + LLM) | 90% menor com cache hit |
| Latência | 2-3 etapas | 1 etapa |
| Código adicional | ChromaDB + pipeline | Zero |
| Manutenção | Re-indexar a cada update | Editar 1 arquivo |
| Quando faz sentido | Contexto > 200k tokens, citação fiel | Contexto pequeno e estável |

A escolha por Prompt Caching + Tool Use elimina dependências desnecessárias e mantém o código alinhado ao princípio YAGNI.

### 4. DuckDB sobre Parquet em vez de pandas sobre CSV

Para as tools que executam queries ao vivo, o substrato analítico é DuckDB lendo Parquet diretamente:

| Métrica | pandas + CSV | DuckDB + Parquet |
|---|---|---|
| Tempo de uma query típica | 2-3 s | ~50 ms |
| Tamanho em disco (fato_rfm_clientes) | 19,6 MB | 4,7 MB |
| Suporte a SQL completo | Não | Sim |
| Footprint de memória | Alto | Lazy (colunar) |

O ganho de ordem de magnitude justifica a dependência adicional, especialmente porque DuckDB é embarcado (não requer servidor) e mantém compatibilidade com pandas via `.df()`.

### 5. Snapshot temporal fixo

A data de referência para cálculo de Recency está fixada em `2018-09-04` no arquivo de configuração. O projeto **não utiliza** `max(timestamp) + 1d` dinâmico.

A motivação é reprodutibilidade: o mesmo conjunto de CSVs deve produzir os mesmos números independentemente do momento da execução. Essa decisão também torna possível o uso de testes determinísticos.

### 6. Tipagem explícita na exportação

A função `export_rfm_to_powerbi()` força tipos otimizados antes da serialização:

- Identificadores → `str`
- Recency → `int32`
- Frequency, Items → `int16`
- Monetary, CLV_12m → `float32` (arredondado a 2 casas)
- Scores R/F/M → `Int8` (nullable)
- Categorias → `str` (não `pandas.Category` — Power BI tem leitura imprecisa)
- Encoding → `utf-8-sig` (BOM necessário para PBI/Excel lerem caracteres brasileiros corretamente)

O resultado é um CSV que o Power BI importa sem precisar inferir tipos, eliminando os bugs mais comuns de carregamento.

---

## Custo Operacional

| Componente | Custo mensal estimado |
|---|---|
| Agente — 500 perguntas/mês | ~R$ 35 (US$ 6) |
| Streamlit Community Cloud | Gratuito |
| Power BI Service (My Workspace) | Gratuito |
| Uptime monitoring (cron-job.org) | Gratuito |
| **Total** | **~R$ 35/mês** |

O footer da aplicação Streamlit exibe o custo da sessão em tempo real, com tracking separado de input tokens, output tokens, cache reads e cache writes.

---

## Roadmap

### Concluído

- [x] Pipeline RFM modular com 73 testes pytest
- [x] Cluster naming robusto (derivado do perfil R/F/M)
- [x] 6 datamarts tipados em CSV (Power BI) · 5 em Parquet (Agent)
- [x] Modelos preditivos validados (review ruim + estudo de recompra), sem leakage
- [x] Dashboard Power BI (PBIP/TMDL) — 2 páginas, visuais em Deneb, tema dark
- [x] Agente Streamlit com Claude Haiku 4.5 + 7 tools DuckDB validadas
- [x] Tracking de custo em tempo real
- [x] Conformidade WCAG AA (focus rings, ARIA, reduced-motion)
- [x] Repositório publicado no GitHub
- [x] Deploy do agente em Streamlit Community Cloud

### Em andamento

- [ ] Publicação do dashboard no Power BI Service (+ screenshots/GIF no README)

### Backlog

- [ ] CLV probabilístico via biblioteca `lifetimes` (BG/NBD + Gamma-Gamma)
- [ ] Modo "aprofundado" que roteia para Sonnet 4.5 sob demanda do usuário
- [ ] Experimento A/B das ações de CRM por cluster
- [ ] Webhook para alertas (ex: `% em risco > 35%`)

---

## Documentação

Este README é a documentação central do projeto. Referências técnicas
complementares ficam **junto do código**:

| Documento | Público-alvo |
|---|---|
| [`powerbi/DOCUMENTACAO_PBI.md`](./powerbi/DOCUMENTACAO_PBI.md) | Analistas BI — referência técnica do artefato Power BI (modelo, 34 medidas DAX, relacionamentos, mapa de visuais) |
| [`powerbi/dicionario_dados.md`](./powerbi/dicionario_dados.md) | Analistas BI — schema completo dos 6 datamarts |
| [`powerbi/GUIA_DESIGN_DASHBOARD.md`](./powerbi/GUIA_DESIGN_DASHBOARD.md) | Analistas BI — rationale de design (medidas DAX, theme JSON, visuais Deneb) |
| [`streamlit_agent/README.md`](./streamlit_agent/README.md) | Setup e deploy do agente de IA |

---

## Contribuindo

Contribuições são bem-vindas. Para mudanças significativas, abra primeiro uma issue descrevendo a proposta.

```bash
# 1. Fork do projeto
# 2. Branch para a feature
git checkout -b feature/nome-descritivo

# 3. Garanta que os testes passam
pytest tests/ -v

# 4. Commit seguindo Conventional Commits
git commit -m "feat: descrição da mudança"

# 5. Push e abra o Pull Request
git push origin feature/nome-descritivo
```

---

## Licença

Distribuído sob a Licença MIT. Consulte [`LICENSE`](./LICENSE) para mais informações.

O dataset Olist está sob a licença CC BY-NC-SA 4.0 e **não está incluído** neste repositório. Deve ser obtido diretamente no [Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).

---

## Autor

**Lucas Alves**

- GitHub — [@LucasAlves99](https://github.com/LucasAlves99)
- LinkedIn — [linkedin.com/in/lucasalves99](https://www.linkedin.com/in/lucasalves99/)

---

## Referências

- Dataset: [Brazilian E-Commerce by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) (Kaggle)
- Modelo de IA: [Claude Haiku 4.5](https://www.anthropic.com/news/claude-haiku-4-5) (Anthropic)
- Power BI custom visual: [HTML Content](https://appsource.microsoft.com/en-us/product/power-bi-visuals/wa104380904) por Daniel Marsh-Patrick
- Metodologia RFM: Berry & Linoff, *Data Mining Techniques* (3ª ed.)
- Princípios de design: Material Design 3, Apple HIG, WCAG 2.1 AA

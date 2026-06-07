# Dicionário de Dados — Power BI (RFM Olist)

> Tabelas exportadas pelo pipeline para modelagem Star Schema no Power BI.

---

## fato_rfm_clientes.csv

**Granularidade**: 1 linha por `customer_unique_id`
**Função**: Tabela fato principal com todas as métricas RFM, segmentação e cluster

| Coluna | Tipo | Descrição |
|---|---|---|
| `customer_unique_id` | string | Identificador único do cliente (chave) |
| `Recency` | int32 | Dias desde a última compra até a snapshot_date |
| `Frequency` | int16 | Número de pedidos únicos entregues |
| `Monetary` | float32 | Soma total paga pelo cliente (R$) |
| `Avg_Order_Value` | float32 | Ticket médio por pedido (R$) |
| `Items` | int | Total de itens comprados |
| `Avg_Review` | float32 | Nota média de reviews (1–5, pode ter nulo) |
| `R_score` | Int8 | Score de Recência (1–5, 5 = comprou recentemente) |
| `F_score` | Int8 | Score de Frequência (1–5, 5 = mais frequente) |
| `M_score` | Int8 | Score de Valor Monetário (1–5, 5 = maior gasto) |
| `RFM_score` | Int8 | Soma dos 3 scores (3–15) |
| `RFM_bucket` | string | Concatenação dos scores (ex: "555", "211") |
| `RFM_segment` | string | Segmento clássico de negócio (Champions, At Risk...) |
| `cum_revenue_pct` | float | % acumulada de receita (para segmentação Pareto) |
| `Revenue_segment` | string | Segmento por contribuição de receita (Elite, High Value, Mid Value, Base) |
| `Recency_segment` | string | Segmento por recência (Ativo, Recente, Morno, Em Risco) |
| `Strategic_segment` | string | Combinação de Revenue + Recency (ex: "Elite (Top 5%) - Ativo") |
| `Cluster` | int8 | ID do cluster KMeans (0–3) |
| `Cluster_Name` | string | Nome do cluster de negócio (chave FK → dim_segmentos) |
| `Freq_Mensal` | float | Frequência mensal estimada (Frequency / 24 meses) |
| `CLV_12m` | float32 | Customer Lifetime Value projetado para 12 meses (R$) |
| `dt_exportacao` | date (string) | Data de geração do arquivo (YYYY-MM-DD) |
| `versao_modelo` | string | Versão do modelo utilizado (ex: "v1.0") |

---

## dim_segmentos.csv

**Granularidade**: 1 linha por cluster
**Função**: Dimensão com metadados de cada segmento de cliente

| Coluna | Tipo | Descrição |
|---|---|---|
| `Cluster_Name` | string | Nome do cluster (PK — chave primária) |
| `Descricao` | string | Descrição do perfil do cluster |
| `Cor_Hex` | string | Cor em hexadecimal para uso em visuais (#RRGGBB) |
| `Acao_CRM` | string | Ação de marketing/CRM recomendada |
| `Prioridade` | int | Prioridade de ação (1=alta, 2=média, 3=baixa) |
| `Cor_Power_BI` | string | Nome da cor em português (para filtros visuais) |

### Os 4 perfis de cluster (derivados automaticamente do perfil R/F/M)

> **Importante**: os nomes são derivados do PERFIL (R/F/M médios), **não do ID** do cluster.
> Isso garante que mesmo se o KMeans atribuir IDs diferentes a cada execução, os nomes
> de negócio permaneçam consistentes.

| Cluster_Name | Perfil R/F/M | Tamanho típico | Ação CRM |
|---|---|---|---|
| **Campeões** | R baixa, F alta, M alto | Pequeno (~1-3% da base) | Programa VIP, embaixadores |
| **Big Spenders (Não-Recorrentes)** | R variável, F=1-2, M alto | Médio | Conversão p/ recorrência, upsell |
| **Novos / Ocasionais** | R recente, F=1, M baixo | Maioria da base Olist | Incentivo à 2ª compra, onboarding |
| **Em Risco / Hibernando** | R alta (antigos), F baixa, M variável | Grande | Win-back urgente |

---

## fato_pedidos.csv (atualizado 2026-05-31)

Coluna nova: **`product_category`** (string) — categoria do produto traduzida (PT-BR), derivada via `order_items → products → product_category_name_translation`. Pedido multi-item recebe a categoria de maior valor. 14 colunas no total.

---

## fato_cohort.csv (novo 2026-05-31)

**Granularidade**: 1 linha por (Safra × MesIndice)
**Função**: Retenção por safra de aquisição (mês da 1ª compra)

| Coluna | Tipo | Descrição |
|---|---|---|
| `Safra` | string | Mês da 1ª compra do cliente (YYYY-MM) |
| `MesIndice` | int | Meses desde a 1ª compra (0 = aquisição) |
| `Clientes_Retidos` | int | Clientes da safra ativos naquele mês-índice |
| `Tamanho_Safra` | int | Total de clientes da safra (no mês 0) |
| `Pct_Retencao` | float | Clientes_Retidos / Tamanho_Safra |

> Achado: retenção média no mês 1 ≈ **0,45%** — base fortemente transacional (compra única).

### Medidas DAX adicionadas
- `_KPIs`: `Receita Pedidos`, `Clientes Ativos` (fatiam por tempo/categoria via fato_pedidos), `Ticket Medio Cliente`
- `_Saude`: `Receita em Risco`, `% Receita em Risco` (Recency > 365)

---

## dim_calendario.csv

**Granularidade**: 1 linha por dia
**Função**: Tabela calendário para hierarquia de datas no Power BI

| Coluna | Tipo | Descrição |
|---|---|---|
| `Data` | date (string) | Data no formato YYYY-MM-DD (PK) |
| `Ano` | int16 | Ano (ex: 2017) |
| `Mes` | int8 | Mês numérico (1–12) |
| `Dia` | int8 | Dia do mês (1–31) |
| `Trimestre` | int8 | Trimestre (1–4) |
| `AnoMes` | string | Ano-Mês no formato YYYY-MM (ex: "2018-03") |
| `NomeMes` | string | Nome do mês em inglês (ex: "March") |
| `DiaSemana` | string | Nome do dia da semana em inglês |
| `NumDiaSemana` | int8 | Número do dia da semana (1=Segunda, 7=Domingo) |
| `FimDeSemana` | bool | True se sábado ou domingo |

---

## Relacionamentos no Star Schema

```
dim_calendario (Data)         1 → N   fato_rfm_clientes (order_purchase via fato_pedidos)
dim_segmentos (Cluster_Name)  1 → N   fato_rfm_clientes (Cluster_Name)
```

---

## Notas

- Encoding: `utf-8-sig` (UTF-8 com BOM — requerido pelo Power BI para leitura correta de caracteres especiais)
- Formato CSV: separador `;` e decimal `,` (padrão BR — Power BI PT-BR lê nativo). Centralizado em `write_powerbi_csv()` (`src/export.py`)
- Valores monetários em **BRL (Reais)**
- `snapshot_date = 2018-09-04` (fixo para reprodutibilidade)

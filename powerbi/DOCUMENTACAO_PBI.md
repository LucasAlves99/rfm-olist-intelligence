# Documentação Técnica — Power BI (RFM Olist Intelligence)

> Referência completa do artefato Power BI: modelo semântico (Star Schema), catálogo de
> medidas DAX, relacionamentos, mapa de páginas/visuais e sistema de design.
> Complementa o [`dicionario_dados.md`](./dicionario_dados.md) (schema dos datamarts de origem)
> e o [`GUIA_DESIGN_DASHBOARD.md`](./GUIA_DESIGN_DASHBOARD.md) (rationale de design).

---

## 1. Visão geral do artefato

O dashboard está versionado no formato **PBIP** (Power BI Project), que separa relatório e
modelo em pastas de texto (TMDL/PBIR) — versionáveis em Git e editáveis sem abrir o Desktop.

| Item | Valor |
|---|---|
| Projeto | `powerbi/RFM.pbip` (abrir no Power BI Desktop) |
| Modelo semântico | `powerbi/RFM.SemanticModel/` (TMDL) |
| Relatório | `powerbi/RFM.Report/` (PBIR) |
| Modo de armazenamento | **Import** (todas as tabelas) |
| Culture | `pt-BR` |
| Time Intelligence automática | Desabilitada (`__PBI_TimeIntelligenceEnabled = 0`) |
| Páginas | 2 — Visão Executiva · Análise Detalhada (1280×720, FitToPage) |
| Tabelas | 7 de dados + 4 de medidas |
| Medidas DAX | 45 (23 `_KPIs` · 13 `_Saude` · 2 `_Concentracao` · 7 `_Background`) |
| Relacionamentos | 4 (todos 1→N, single direction) |
| Tema | `dashboard_theme.json` (dark executivo) |
| Custom visuals | Deneb (Vega-Lite) · HTML Content (chrome/KPIs) |

> ⚠️ **Editar com o Desktop fechado.** O PBI Desktop reescreve os `*.json` do relatório ao
> salvar. Para editar visuais via arquivo/pbi-cli, feche o Desktop primeiro; para editar o
> modelo, o oposto — abra no Desktop e edite via Desktop ou reabra após mudanças em TMDL.

### Como abrir

1. Power BI Desktop (Windows) com **preview "Power BI Project (.pbip)"** habilitado em
   *File → Options → Preview features*.
2. Abrir `powerbi/RFM.pbip`.
3. Se as tabelas pedirem refresh, ver §6 (os caminhos das fontes são absolutos).

---

## 2. Modelo de dados (Star Schema)

Duas fatos principais (`fato_rfm_clientes` por cliente, `fato_pedidos` por pedido) cercadas
por dimensões. `fato_cohort` e `risco_review_uf` são tabelas-satélite que alimentam visuais
específicos da página 2.

```
                    dim_calendario (Data)
                            │ 1
                            │
                            ▼ N
  dim_segmentos ──N◄──1── fato_rfm_clientes ──1◄──N── fato_pedidos ──N►──1── risco_review_uf
  (Cluster_Name)         (customer_unique_id)      (customer_unique_id)        (UF)

                    fato_cohort  (sem relacionamento — agregada por medida)
```

### 2.1 Relacionamentos (`relationships.tmdl`)

| # | De (N) | Para (1) | Cardinalidade | Uso |
|---|---|---|---|---|
| 1 | `fato_rfm_clientes[Cluster_Name]` | `dim_segmentos[Cluster_Name]` | N→1 | Cor/descrição/ação por cluster |
| 2 | `fato_pedidos[customer_unique_id]` | `fato_rfm_clientes[customer_unique_id]` | N→1 | Pedido → atributos RFM do cliente |
| 3 | `fato_pedidos[order_purchase_timestamp]` | `dim_calendario[Data]` | N→1 | Fatiar pedidos por tempo (MoM, timeline) |
| 4 | `fato_pedidos[customer_state]` | `risco_review_uf[UF]` | N→1 | Cruzar pedidos com risco de review por UF |

> `fato_cohort` **não tem relacionamento** — é consumida diretamente pela medida
> `Retencao Cohort` e pelo diagnóstico da página 2 (agregação por `MesIndice`).

---

## 3. Tabelas de dados

Todas em modo Import, lidas de `data/powerbi/*.csv` (CSV `;` delimitado, encoding UTF-8-SIG,
caminhos **absolutos** apontando para `C:\Users\Luk\Desktop\RFM-Projeto\data\powerbi\`).

### 3.1 `fato_rfm_clientes` — fato principal (1 linha/cliente)

23 colunas. Granularidade: `customer_unique_id`. Métricas RFM, scores, segmentos e CLV.

| Coluna | Tipo PBI | Notas |
|---|---|---|
| `customer_unique_id` | string | Chave do cliente (PK lógica) |
| `Recency` | int64 | Dias desde a última compra até o snapshot (2018-09-04) |
| `Frequency` | int64 | Pedidos entregues únicos |
| `Monetary` | double | Total pago (R$) — base de `Receita Total` |
| `Avg_Order_Value` | double | Ticket médio do cliente |
| `Items` | int64 | Itens comprados |
| `Avg_Review` | double | Nota média de review (pode ser nulo) |
| `R_score` / `F_score` / `M_score` | int64 | Scores 1–5 |
| `RFM_bucket` | int64 | Concatenação dos scores (ex.: 555) |
| `RFM_score` | int64 | Soma dos scores (3–15) |
| `RFM_segment` | string | Segmento clássico (Champions, At Risk…) |
| `cum_revenue_pct` | double | % acumulada de receita (Pareto) |
| `Revenue_segment` | string | Elite / High / Mid / Base |
| `Recency_segment` | string | Ativo / Recente / Morno / Em Risco |
| `Strategic_segment` | string | Revenue × Recency |
| `Cluster` | int64 | ID KMeans (0–3) |
| `Cluster_Name` | string | **FK → dim_segmentos** |
| `Freq_Mensal` | double | Frequência mensal estimada |
| `CLV_12m` | double | CLV projetado 12m (R$) |
| `dt_exportacao` | date | Data de exportação |
| `versao_modelo` | string | Versão do modelo |

### 3.2 `fato_pedidos` — pedidos (1 linha/pedido)

12 colunas (no Power Query, `Cluster` e `Cluster_Name` são **removidas** após carga — vêm
via relacionamento). Granularidade: `order_id`.

| Coluna | Tipo PBI | Notas |
|---|---|---|
| `order_id` | string | PK do pedido |
| `customer_id` | string | ID transacional |
| `order_purchase_timestamp` | date | **FK → dim_calendario[Data]** |
| `total_items_value` | double | Valor dos itens |
| `n_items` | int64 | Qtd. itens |
| `total_payment` | double | Total de pagamentos |
| `n_payments` | int64 | Qtd. pagamentos |
| `review_score` | int64 | Nota do review (1–5) — base de `Review Medio` |
| `customer_unique_id` | string | **FK → fato_rfm_clientes** |
| `customer_state` | string | **FK → risco_review_uf[UF]** |
| `monetary_value` | double | Valor monetário do pedido — base de `Receita Pedidos` e medidas MoM |
| `product_category` | string | Categoria traduzida (PT-BR) |

### 3.3 `dim_segmentos` — dimensão de cluster (1 linha/cluster)

| Coluna | Tipo PBI | Notas |
|---|---|---|
| `Cluster_Name` | string | PK |
| `Descricao` | string | Perfil do cluster |
| `Cor_Hex` | string | Cor `#RRGGBB` (Format by field value) |
| `Acao_CRM` | string | Ação recomendada |
| `Prioridade` | int64 | 1=alta … 3=baixa |
| `Cor_Power_BI` | string | Nome da cor (PT) |

### 3.4 `dim_calendario` — calendário (1 linha/dia)

`Data` (date, PK), `Ano`, `Mes`, `Dia`, `Trimestre`, `AnoMes`, `NomeMes`, `DiaSemana`,
`NumDiaSemana`, `FimDeSemana` (boolean).

### 3.5 `fato_cohort` — retenção por safra (1 linha/Safra×MesIndice)

`Safra`, `MesIndice`, `Clientes_Retidos`, `Tamanho_Safra`, `Pct_Retencao` + **`Semestre`**
(coluna derivada no Power Query: `YYYY-S1`/`YYYY-S2`).

### 3.6 `risco_review_uf` — risco preditivo por UF (1 linha/UF)

`UF`, `Pedidos`, `Alto_Risco`, `Pct_Alto_Risco`. Alimentada pelo modelo de review ruim
(`pipeline/score_review_risk.py`).

### 3.7 `dim_lorenz` — curva de concentração pré-calculada (1 linha/ponto)

`ordem` (int), `pct_clientes` (double 0–1), `pct_receita` (double 0–1). ~200 pontos amostrados
da curva de Lorenz (receita acumulada × clientes acumulados, do maior gastador ao menor).
Gerada por `build_lorenz_curve()` no pipeline. **Sem relacionamento** — alimenta apenas o spec
Deneb da curva de Lorenz (página 1), substituindo o cálculo por-linha sobre os 93k clientes.

---

## 4. Tabelas de medidas (DAX)

4 tabelas-calculadas vazias (`source = { BLANK() }`) que apenas hospedam medidas, organizadas
por domínio. Total: **45 medidas**. As medidas de tendência seguem o padrão composto:
`X Mes` / `X Mes Anterior` (último mês fechado vs anterior, recuando se o mês corrente
estiver parcial) e `X MoM % = DIVIDE([X Mes] - [X Mes Anterior], [X Mes Anterior])`.

### 4.1 `_KPIs` — indicadores executivos (23 medidas)

| Medida | Expressão (resumo) | Formato | Pasta |
|---|---|---|---|
| `Total Clientes` | `DISTINCTCOUNT(fato_rfm_clientes[customer_unique_id])` | #,0 | |
| `Receita Total` | `SUM(fato_rfm_clientes[Monetary])` | R$ #,0 | |
| `Ticket Medio` | `DIVIDE([Receita Total], COUNTROWS(fato_pedidos))` | R$ #,0.00 | |
| `Recencia Media` | `AVERAGE(fato_rfm_clientes[Recency])` | #,0 dias | |
| `Frequency Media` | `AVERAGE(fato_rfm_clientes[Frequency])` | 0.00 | |
| `CLV Medio` | `AVERAGE(fato_rfm_clientes[CLV_12m])` | R$ #,0.00 | |
| `Total Pedidos` | `COUNTROWS(fato_pedidos)` | #,0 | |
| `Ticket Medio Cliente` | `AVERAGE(fato_rfm_clientes[Avg_Order_Value])` | R$ #,0.00 | |
| `Review Medio` | `AVERAGE(fato_pedidos[review_score])` | 0.00 | Qualidade |
| `Receita Pedidos` | `SUM(fato_pedidos[monetary_value])` | R$ #,0 | Temporal |
| `Clientes Ativos` | `DISTINCTCOUNT(fato_pedidos[customer_unique_id])` | #,0 | Temporal |
| `Receita MoM %` | Variação mês vs mês anterior da receita (usa último mês **completo**) | +0.0% | Tendência |
| `Ticket MoM %` | Variação MoM do ticket (receita/pedidos) | +0.0% | Tendência |
| `Clientes Ativos MoM %` | Variação MoM de clientes ativos | +0.0% | Tendência |

> **Padrão das medidas MoM (refatorado).** A detecção do último mês fechado
> (`MAX(order_purchase_timestamp)` + `EOMONTH`, recuando se o mês estiver parcial) vive nas
> medidas-base `X Mes` / `X Mes Anterior`; as `X MoM %` são pura composição
> `DIVIDE([X Mes] - [X Mes Anterior], [X Mes Anterior])` — a lógica de calendário existe em
> um único lugar.

### 4.2 `_Saude` — saúde da base e funil (13 medidas)

| Medida | Expressão (resumo) | Formato | Pasta |
|---|---|---|---|
| `Clientes em Risco` | `CALCULATE([Total Clientes], Recency > 365)` | #,0 | |
| `% Em Risco` | `DIVIDE([Clientes em Risco], [Total Clientes])` | 0.0% | |
| `% Compra Unica` | clientes com `Frequency = 1` / total | 0.0% | |
| `% Campeoes` | share do cluster Campeões | 0.0% | |
| `% Big Spenders` | share de Big Spenders (Não-Recorrentes) | 0.0% | |
| `% Novos` | share de Novos / Ocasionais | 0.0% | |
| `Clientes 1 Compra` | `Frequency = 1` | #,0 | Funil |
| `Clientes 2 Compras` | `Frequency = 2` | #,0 | Funil |
| `Clientes 3-4 Compras` | `Frequency` entre 3 e 4 | #,0 | Funil |
| `Clientes 5+ Compras` | `Frequency >= 5` | #,0 | Funil |
| `Receita em Risco` | `CALCULATE([Receita Total], Recency > 365)` | R$ #,0 | Risco |
| `% Receita em Risco` | `DIVIDE([Receita em Risco], [Receita Total])` | 0.0% | Risco |
| `Retencao Cohort` | `DIVIDE(SUM(Clientes_Retidos), SUM(Tamanho_Safra))` | 0.0% | Cohort |

### 4.3 `_Concentracao` — Pareto / Lorenz (2 medidas)

| Medida | Papel |
|---|---|
| `Receita Top 20%` | Receita dos 20% maiores clientes via `TOPN` sobre `Monetary` |
| `% Concentracao Top 20%` | `Receita Top 20%` / `Receita Total` |

> As medidas acumuladas `% Clientes Acumulado` / `% Receita Acumulada` (eixos da curva de
> Lorenz, calculadas por linha com `MAX(...)` + `FILTER(ALL(...))` — O(n²)) foram **removidas**:
> a curva agora é **pré-calculada no pipeline** (tabela `dim_lorenz`, ~200 pontos), eliminando
> o DAX pesado e o tráfego de 93k linhas pro visual Deneb.

### 4.4 `_Background` — chrome HTML, cards e sparklines (7 medidas)

| Medida | Papel |
|---|---|
| `_BG Pagina 1` | HTML completo do "chrome" da página 1 (topbar com período da base "2016–2018", 4 KPIs-herói da base — Receita total, Pedidos, Ticket médio, Clientes — com sparkline de tendência 12m, painéis vazios, card do Analista). Renderizado no visual **HTML Content** de fundo. Injeta valores via DAX (`FORMAT`). |
| `_BG Pagina 2` | HTML do chrome da página 2 + **barra de diagnóstico gerencial** com números calculados ao vivo (% compra única, retenção mês 1, receita em risco). |
| `_Plano Acao` | HTML do card "Plano de ação" (página 2): 4 linhas priorizadas (1-4) por cluster com receita associada e ação de CRM. Pasta *Cards SVG*. |
| `_Spark Receita` / `_Spark Pedidos` / `_Spark Ticket` / `_Spark Clientes` | Sparklines SVG de 12 meses dos KPIs-herói da P1 — a medida calcula a série mensal e monta a `<polyline>` inline. Pasta *Sparklines*. |

> Estas medidas devolvem **strings HTML** consumidas pelo custom visual **HTML Content**
> (Daniel Marsh-Patrick). O layout é responsivo via `aspect-ratio: 16/9`, então o chrome
> acompanha qualquer tamanho 16:9. Os visuais de dados (Deneb/cards) ficam **por cima** dos
> painéis vazios desenhados pelo background, alinhados por coordenadas.

---

## 5. Páginas e visuais (PBIR)

Ambas as páginas: 1280×720, `displayOption: FitToPage`. Cada página tem um **HTML Content**
de fundo (z=0, 1280×720) que desenha topbar, frames de KPI e painéis; os visuais de dados são
posicionados por cima.

### 5.1 Página "Visão Executiva" (`3fb8c22c8b1d0093f1e5`) — página ativa

| Visual (id interno) | Tipo | Posição (x,y · w×h) | Conteúdo |
|---|---|---|---|
| `64a069a5…` | HTML Content | 0,0 · 1280×720 | Background/chrome P1 + KPIs (`_BG Pagina 1`) |
| `2963ce1e…` | Deneb | 26,220 · 894×232 | **Treemap** — receita por cluster |
| `p1_concentracao` | Deneb | 16,515 · 416×163 | **Curva de Lorenz / Pareto** (anotação do top 20% calculada de `dim_lorenz`) |
| `p1_clv_ticket` | Deneb | 432,531 · 512×147 | **CLV projetado vs Ticket** atual (barras pareadas + multiplicador; frase de leitura no título do spec) |
| `btn_abrir_analista` | Action Button | 960,592 · 303×48 | Abre o **Analista RFM** (app Streamlit) |
| `c369ff5d…` | Action Button | 704,16 · 160×48 | Aba/navegação → Análise Detalhada |

### 5.2 Página "Análise Detalhada" (`254456cb6d77b49f0482`)

| Visual (id interno) | Tipo | Posição (x,y · w×h) | Conteúdo (título no chrome) |
|---|---|---|---|
| `16953eb3…` | HTML Content | 0,0 · 1280×720 | Background/chrome P2 + diagnóstico (`_BG Pagina 2`) |
| `p2_uf` | Deneb | 16,192 · 416×224 | **Evolução mensal** |
| `p2_ano_slicer` | Slicer (botões) | 160,160 · 176×48 | Filtro de **Ano** — escopo restrito à Evolução mensal (ver interações) |
| `cohort_heatmap` | Deneb | 432,192 · 416×224 | **Retenção por safra** (cohort, sem M+0; escala de cor no range real) |
| `review_uf` | Deneb | 848,192 · 416×224 | **Risco de review por UF** (preditivo, com linha de média nacional) |
| `p2_funil` | Deneb | 16,464 · 416×208 | **Funil de recorrência** (barra = taxa de conversão da etapa anterior) |
| `p2_review_cluster` | Deneb | 432,464 · 416×208 | **Receita em risco por segmento** |
| `p2_review_recency` | HTML Content | 848,464 · 416×208 | **Plano de ação** (`_Plano Acao`) |
| `11af4980…` | Action Button | 560,16 · 144×48 | Navegação → Visão Executiva |

> Os ids `p2_uf`/`review_uf` são nomes **internos legados** — o que vale é o título exibido
> pelo chrome (coluna "Conteúdo"). Não renomeie pastas de visual sem atualizar `page.json`.

**Interações de visual configuradas** (`page.json` da P2): o seletor de cluster (`p2_review_cluster`)
e o de UF (`review_uf`) cruzam-filtram `p2_uf`/`p2_funil` via `DataFilter`, e ficam `NoFilter`
sobre `cohort_heatmap` e entre si — para evitar realçar/zerar visuais que não fazem sentido cruzar.
O `p2_ano_slicer` filtra **apenas** `p2_uf` (`DataFilter`); todos os demais alvos estão em `NoFilter`
explícito, porque `dim_calendario` só alcança `fato_pedidos` no modelo — deixar o padrão criaria
um estado "meio filtrado" silencioso (funil/receita em risco/plano não reagiriam de qualquer forma).

### 5.3 Deneb (Vega-Lite)

Os visuais de gráfico são **Deneb** com specs embutidos no `visual.json`. Cada spec usa
`"data": {"name": "dataset"}` e referencia campos pelos nomes do modelo (ex.: `Monetary`,
`Cluster_Name`). A curva de Lorenz tem cópia versionada em
[`deneb_specs/lorenz-curve.json`](./deneb_specs/lorenz-curve.json) (área de Gini demarcada,
`width/height: "container"`, fundo transparente). Ela lê a tabela **`dim_lorenz`** (pontos
pré-calculados) — o visual trafega ~200 linhas em vez dos 93.358 clientes, deixando a página 1 leve.

---

## 6. Atualização de dados (refresh)

As tabelas leem CSV via o **parâmetro `CaminhoDados`** (`expressions.tmdl`), que aponta
para a pasta dos datamarts:

```
CaminhoDados = C:\Users\Luk\Desktop\RFM-Projeto\data\powerbi   (padrão)
Partições:     File.Contents(CaminhoDados & "\<tabela>.csv")
```

Em outra máquina/Service, basta alterar o parâmetro (Transform data → Manage parameters,
ou Settings do dataset no Service) — sem tocar nas 7 partições.

Fluxo de atualização:

1. Reexecutar o pipeline Python para regenerar os CSVs:
   ```bash
   python pipeline/run_pipeline.py        # RFM, segmentos, calendário, cohort
   python pipeline/score_review_risk.py   # risco_review_uf (requer review_model.pkl)
   ```
2. No Power BI Desktop: **Home → Refresh**.

> Em outra máquina, basta ajustar o parâmetro **`CaminhoDados`** (as partições não têm mais
> caminho fixo). Encoding é `65001` (UTF-8) com delimitador `;` — não alterar, sob risco de
> erro de parsing dos números BR.

---

## 7. Sistema de design

Tema dark executivo em `dashboard_theme.json`. Paleta canônica (uma cor por cluster), reaplicada
no CSS dos backgrounds HTML e nos specs Deneb:

| Token | Hex | Uso |
|---|---|---|
| Champions | `#E0AB6A` | Campeões / "good" |
| Big Spenders | `#A38ADB` | Big Spenders (Não-Recorrentes) |
| Novos | `#79C9A4` | Novos / Ocasionais / "neutral" |
| Em Risco | `#E8879A` | Em Risco / Hibernando / "bad" |
| Fundo base | `#05080A` | Canvas |
| Texto 1 / 2 | `#EAF2F2` / `#A6BBBC` | Primário / secundário |

As cores por cluster nos visuais vêm de `dim_segmentos[Cor_Hex]` (Format by field value),
garantindo consistência mesmo se os IDs do KMeans permutarem entre re-treinos. Detalhes de
grid, espaçamento e rationale: [`GUIA_DESIGN_DASHBOARD.md`](./GUIA_DESIGN_DASHBOARD.md).

> **Performance do chrome (modo leve, 2026-07):** o fundo animado usa uma única camada
> (`.bg-mesh::before`) animando apenas `transform` + `opacity` (compositor da GPU, sem repaint),
> com drift horizontal de 12s e `prefers-reduced-motion` respeitado. Sem `backdrop-filter` nos
> cards (fundo `rgba(20,22,30,0.85)` compensa o contraste). O texto decorativo foi removido
> (badges de canto, rodapé técnico) — cada dizer restante orienta leitura. A mesma estética e o
> mesmo modo leve estão replicados no app Streamlit do Analista (`streamlit_agent/app.py`).

> ⚠️ O `GUIA_DESIGN_DASHBOARD.md` cita um canvas legado de **1920×1080** com coordenadas
> antigas. O estado atual implementado é **1280×720** com chrome HTML responsivo — use as
> coordenadas da §5 deste documento como fonte de verdade.

---

## 8. Manutenção — pontos de atenção

- **Desktop fechado para editar o relatório por arquivo**; Desktop aberto reescreve os JSON.
- **Não renomear** pastas de visual sem atualizar `page.json` / `pages.json` (`pageOrder`,
  `activePageName`, `visualInteractions`).
- **Medidas HTML** (`_Background`) são frágeis a edição manual — aspas duplas DAX (`""`) e
  entidades HTML (`&#225;`) precisam ser preservadas. Alterar com cuidado.
- **Fontes parametrizadas** via `CaminhoDados` (`expressions.tmdl`) — ao mover o projeto,
  alterar só o parâmetro.
- **`fato_cohort` sem relacionamento**: filtros de página não a atingem por contexto; só por
  medida. Intencional.
- Botões de navegação dependem de **bookmarks/page navigation** — ao adicionar páginas,
  revisar os `actionButton`.

---

## 9. Arquivos de referência

| Arquivo | Conteúdo |
|---|---|
| `RFM.pbip` | Projeto Power BI (abre no Desktop) |
| `RFM.SemanticModel/definition/tables/*.tmdl` | Tabelas, colunas, medidas, partições M |
| `RFM.SemanticModel/definition/relationships.tmdl` | Os 4 relacionamentos |
| `RFM.Report/definition/pages/**` | Páginas e visuais (PBIR) |
| `dashboard_theme.json` | Tema dark |
| `deneb_specs/*.json` | Specs Vega-Lite reaproveitáveis |
| `dicionario_dados.md` | Schema dos datamarts de origem |
| `GUIA_DESIGN_DASHBOARD.md` | Rationale de design (parcialmente legado) |

---

*Gerado a partir da inspeção do TMDL/PBIR; última revisão completa em 2026-07-06. Ao alterar o modelo, atualizar §3–§5.*

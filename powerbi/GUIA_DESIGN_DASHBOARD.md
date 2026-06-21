# Guia de Design — Dashboard RFM Olist

> Como o dashboard foi construído no Power BI e como evoluí-lo. As seções de coordenadas/medidas
> abaixo são a referência de design; o estado atual já implementado está resumido logo a seguir.
>
> 📘 **Referência técnica do artefato (modelo, medidas DAX, relacionamentos, mapa de visuais):**
> [`DOCUMENTACAO_PBI.md`](./DOCUMENTACAO_PBI.md). As coordenadas **1920×1080** deste guia são
> legado — o estado implementado é **1280×720** (ver §5 da documentação técnica).

---

## ✅ Estado atual (implementado)

O dashboard já está montado em **`RFM.pbip`** (formato PBIP — pastas `RFM.Report/` e
`RFM.SemanticModel/` versionáveis em Git):

- **2 páginas**: "Visão Executiva" e "Análise Detalhada", 1280×720, fundo via **HTML Content visual**
  (medidas `_BG Pagina 1` / `_BG Pagina 2` na tabela `_Background`) — não usa o PNG estático.
- **20 visuais**, sendo **7 em Deneb (Vega-Lite/Vega)** com specs embutidos:
  treemap, Lorenz (área de Gini), CLV vs Ticket, geo/UF, evolução mensal, funil, scatter.
  Specs versionados em `powerbi/deneb_specs/*.json`.
- **~30 medidas DAX** em 4 tabelas de medidas: `_KPIs`, `_Saude`, `_Concentracao`, `_Background`.
- **Tema** aplicado a partir de **`dashboard_theme.json`** (já existe como arquivo nesta pasta).
- Cores por cluster fixadas via `dim_segmentos[Cor_Hex]` (Format by field value).

> ⚠️ **Editar com o Desktop fechado:** o PBI Desktop reescreve os `.Report/*.json` ao salvar.
> Para editar visuais via arquivo/pbi-cli, feche o Desktop primeiro.

> 📦 **Deneb:** custom visual gratuito (AppSource, Daniel Marsh-Patrick). Cada spec usa
> `"data": {"name": "dataset"}` e nomes de campo no locale do PBI (ex.: "Soma de Monetary").

---

## Arquivos disponíveis

| Arquivo | Função |
|---|---|
| `RFM.pbip` | **Projeto Power BI** (abrir no Desktop) — report + modelo em TMDL |
| `dashboard_theme.json` | Tema dark executivo aplicado ao relatório |
| `deneb_specs/*.json` | Specs Vega-Lite/Vega dos 7 visuais Deneb (reaproveitáveis) |
| `dashboard_background_dark.png` | Background estático alternativo (1920×1080) — legado |
| `dashboard_background_dark.svg` | Versão vetorial editável (Inkscape, Figma) |
| `dashboard_mockup.png` / `.svg` | Mockup com visuais simulados (referência visual) |
| `wireframe_dashboard.html` | Protótipo interativo das 2 páginas |
| `_make_png_background.py` | Script Python que gera o PNG (regenera se quiser ajustar) |

---

## 1. Aplicar o background no Power BI Desktop

### 1.1 Configurar o tamanho da página

1. Abra o Power BI Desktop
2. Aba **View** → **Page view** → **Custom**
3. Aba **Format** (ícone de pincel) → **Canvas settings**:
   - **Type**: `Custom`
   - **Width**: `1920`
   - **Height**: `1080`
   - **Vertical alignment**: `Top`

### 1.2 Aplicar o PNG como background

1. Aba **Format** → **Canvas background**:
   - **Image**: clica em "Browse..." e seleciona `dashboard_background_dark.png`
   - **Image fit**: `Fit`
   - **Transparency**: `0%`

Pronto. O background aparece, e agora é só posicionar os visuais nos slots já desenhados.

---

## 2. Paleta de cores do projeto (Theme JSON)

Para garantir que **todos os visuais** sigam a paleta de clusters automaticamente, importe um tema customizado.

### Criar `dashboard_theme.json`

```json
{
  "name": "RFM Olist Dark Executive",
  "dataColors": [
    "#5E6AD2",
    "#BF6FF8",
    "#F2C94C",
    "#E5484D",
    "#A1A1AA",
    "#08090A"
  ],
  "background": "#131418",
  "foreground": "#F4F4F5",
  "tableAccent": "#5E6AD2",
  "good": "#5E6AD2",
  "neutral": "#F2C94C",
  "bad": "#E5484D",
  "maximum": "#5E6AD2",
  "center": "#F2C94C",
  "minimum": "#E5484D",
  "null": "#8B8B92",
  "textClasses": {
    "title": { "fontSize": 18, "fontFace": "Segoe UI", "color": "#F4F4F5" },
    "label": { "fontSize": 11, "fontFace": "Segoe UI", "color": "#A1A1AA" }
  }
}
```

Aplicar no Power BI:
1. Aba **View** → **Themes** → **Browse for themes...**
2. Selecionar o `dashboard_theme.json`

---

## 3. Posicionamento dos visuais (coordenadas exatas)

### Header (já no background — não precisa criar visual)

### KPI Row — 4 cards (Y=170, altura=110)

| Visual | Posição (X, Y) | Tamanho (W × H) | Cor accent |
|---|---|---|---|
| Card Total Clientes | (40, 170) | 445 × 110 | #5E6AD2 (Verde) |
| Card Receita Total | (505, 170) | 445 × 110 | #BF6FF8 (Azul) |
| Card Ticket Médio | (970, 170) | 445 × 110 | #F2C94C (Âmbar) |
| Card % Em Risco | (1435, 170) | 445 × 110 | #E5484D (Vermelho) |

**Configuração de cada card**:
- Visual type: **Card** (cartão simples) ou **Multi-row card**
- Background: **Off** (transparente — o background já desenha o card)
- Title: **Off** (o label já está no background)
- Data label: tamanho 36-40, cor #F4F4F5, font-weight 700
- Posicionar a label exatamente no centro do slot

### Row 1 — Visuais principais (Y=310, altura=350)

| Visual | Posição (X, Y) | Tamanho |
|---|---|---|
| Treemap (Receita por Cluster) | (40, 310) | 600 × 350 |
| Curva de Lorenz (Pareto) | (660, 310) | 600 × 350 |
| Scatter Recency × Frequency | (1280, 310) | 600 × 350 |

### Row 2 — Detalhamento (Y=680, altura=350)

| Visual | Posição (X, Y) | Tamanho |
|---|---|---|
| Mapa por UF (ou bar chart horizontal) | (40, 680) | 600 × 350 |
| Linha temporal de receita | (660, 680) | 600 × 350 |
| Tabela Top Champions | (1280, 680) | 600 × 350 |

> **Truque**: para posicionar com precisão, no Power BI use **Format → General → Position** e cole as coordenadas X/Y diretamente.

---

## 4. Configuração visual por painel

### 4.1 Treemap — Distribuição de Receita por Cluster

- Visual: **Treemap**
- Group: `dim_segmentos[Cluster_Name]`
- Values: `[Receita Total]`
- Background: **Off** (o card do background já está pronto)
- Border: **Off**
- Title: **Off**
- Data colors: usar a paleta da `dim_segmentos[Cor_Hex]` (manualmente):
  - Campeões → #5E6AD2
  - Big Spenders → #BF6FF8
  - Novos / Ocasionais → #F2C94C
  - Em Risco / Hibernando → #E5484D

### 4.2 Curva de Lorenz (Pareto)

- Visual: **Line chart**
- Axis: percentil acumulado de clientes (medida calculada)
- Values: percentil acumulado de receita
- Adicionar **linha de igualdade perfeita** (45°) como referência
- Cor da curva: #F2C94C (Âmbar)

**Medida DAX para a curva**:
```dax
% Receita Acumulada =
VAR ClienteAtual = SELECTEDVALUE(fato_rfm_clientes[customer_unique_id])
VAR ClientesAteAtual =
    CALCULATE(
        SUM(fato_rfm_clientes[Monetary]),
        FILTER(
            ALL(fato_rfm_clientes),
            fato_rfm_clientes[Monetary] >=
            CALCULATE(MAX(fato_rfm_clientes[Monetary]), fato_rfm_clientes[customer_unique_id] = ClienteAtual)
        )
    )
VAR Total = CALCULATE(SUM(fato_rfm_clientes[Monetary]), ALL(fato_rfm_clientes))
RETURN DIVIDE(ClientesAteAtual, Total)
```

### 4.3 Scatter Recency × Frequency × Monetary

- Visual: **Scatter chart**
- X: `AVERAGE(fato_rfm_clientes[Recency])`
- Y: `AVERAGE(fato_rfm_clientes[Frequency])`
- Size: `SUM(fato_rfm_clientes[Monetary])`
- Legend: `dim_segmentos[Cluster_Name]`
- Cores: paleta da `dim_segmentos`

### 4.4 Distribuição Geográfica

**Opção A — Mapa real**:
- Visual: **Map** (ou **Filled Map**)
- Location: `dim_clientes[customer_state]`
- Bubble size / Color: `[Receita Total]`

**Opção B — Bar chart horizontal** (mais legível):
- Visual: **Clustered bar chart**
- Y-axis: `customer_state` (top 5)
- X-axis: `[Receita Total]`
- Cor: gradient verde → âmbar conforme receita

### 4.5 Evolução Temporal

- Visual: **Line chart**
- X-axis: `dim_calendario[AnoMes]`
- Values: `[Receita Total]`
- Legend: `dim_segmentos[Cluster_Name]`
- 4 linhas (uma por cluster) com as cores da paleta

### 4.6 Tabela Top Champions

- Visual: **Table**
- Filter: `dim_segmentos[Cluster_Name] = "Campeões"`
- Sort: `[CLV_12m]` desc
- Top N: 50
- Colunas: customer_unique_id, customer_state, Monetary, Frequency, Recency, CLV_12m
- Format CLV column: cor verde (#5E6AD2) com data bars

---

## 5. Medidas DAX essenciais

```dax
-- KPIs principais
Total Clientes = DISTINCTCOUNT(fato_rfm_clientes[customer_unique_id])

Receita Total = SUM(fato_rfm_clientes[Monetary])

Ticket Médio = DIVIDE([Receita Total], SUM(fato_rfm_clientes[Frequency]))

Recência Média = AVERAGE(fato_rfm_clientes[Recency])

% Clientes 1ª Compra =
DIVIDE(
    CALCULATE([Total Clientes], fato_rfm_clientes[Frequency] = 1),
    [Total Clientes]
)

-- Saúde da base
Clientes em Risco =
CALCULATE([Total Clientes], dim_segmentos[Cluster_Name] = "Em Risco / Hibernando")

% Em Risco = DIVIDE([Clientes em Risco], [Total Clientes])

% Campeões = DIVIDE(
    CALCULATE([Total Clientes], dim_segmentos[Cluster_Name] = "Campeões"),
    [Total Clientes]
)

-- Concentração Pareto
Receita Top 20% =
VAR Top20Cutoff = INT([Total Clientes] * 0.2)
RETURN
    CALCULATE(
        [Receita Total],
        TOPN(Top20Cutoff, fato_rfm_clientes, fato_rfm_clientes[Monetary], DESC)
    )

% Concentração Top 20% = DIVIDE([Receita Top 20%], [Receita Total])

-- CLV por cluster
CLV Médio Cluster = AVERAGE(fato_rfm_clientes[CLV_12m])
```

---

## 6. Decisões de design (rationale)

### Por que tema dark?

1. **Contraste alto** com cores dos clusters (verde, azul, âmbar, vermelho ficam vibrantes em fundo escuro)
2. **Padrão executivo** — dashboards de C-level corporativos costumam ser dark
3. **Fadiga visual menor** em apresentações de longa duração
4. **Diferenciação** — destaca o projeto vs templates "padrão Power BI" claros

### Por que faixa colorida no topo?

A faixa de 4 cores no topo do header (`#5E6AD2` → `#BF6FF8` → `#F2C94C` → `#E5484D`) **resume a paleta** que será usada em todo o dashboard. Quem olha já entende: "isso aqui tem 4 categorias, cada uma com sua cor".

### Por que cards com borda esquerda colorida?

A borda lateral colorida nos KPIs e nos cards de gráficos é um padrão de **dashboards executivos** (estilo Stripe, Linear, Notion). Marca categoria sem ocupar espaço de visual.

### Por que 1920×1080 (não Power BI default)?

- Resolução padrão de monitor Full HD (a maioria dos usuários executivos)
- Bem dimensionável para projetores 4K (downscale OK)
- Mais espaço para 6 painéis sem aperto

### Espaçamento

- Margem externa: **40px** (left/right)
- Gap entre cards/painéis: **20px**
- Padding interno dos painéis: **20px**
- Altura do header: **110px**
- Altura dos KPIs: **110px**
- Altura dos painéis principais: **350px**

Esse grid (8pt-friendly) garante alinhamento visual consistente.

---

## 7. Para personalizar / regenerar

### Mudar uma cor da paleta

Edite `_make_png_background.py`, dicionário `COLORS`, e rode:

```bash
"C:/Users/Luk/anaconda3/python.exe" powerbi/_make_png_background.py
```

### Alternar para tema claro

Trocar:
- `bg_top` (15, 23, 42) → (248, 250, 252)
- `bg_bottom` (30, 41, 59) → (241, 245, 249)
- `card` (30, 41, 59) → (255, 255, 255)
- `text_primary` (241, 245, 249) → (15, 23, 42)
- `text_secondary` (148, 163, 184) → (71, 85, 105)
- `border` (51, 65, 85) → (203, 213, 225)

### Editar o SVG no Inkscape ou Figma

O `dashboard_background_dark.svg` é um arquivo vetorial padrão. Pode abrir em qualquer editor vetorial e ajustar livremente. Depois, exportar como PNG 1920×1080 e substituir no Power BI.

---

## 8. Checklist final antes de publicar o dashboard

- [ ] Background aplicado (Format → Canvas background)
- [ ] Tamanho da página em 1920×1080 custom
- [ ] Theme JSON importado
- [ ] 4 KPIs posicionados e formatados (transparentes em cima dos slots)
- [ ] 6 visuais principais alinhados aos slots
- [ ] Filtros (Cluster, UF, Período) configurados como **Slicers** no canto superior direito
- [ ] Drill-through configurado: clicar num cluster filtra todos os outros visuais
- [ ] Cores dos visuais batem com `dim_segmentos[Cor_Hex]`
- [ ] Tooltip customizado nos visuais (mostra Recency, Frequency, Monetary do cliente/cluster)
- [ ] Página renomeada para "Visão Executiva"
- [ ] Publicar no Power BI Service e gerar link compartilhável
- [ ] Screenshot/GIF do dashboard final → adicionar ao README do GitHub

---

## 9. Próximas páginas do dashboard (sugestão)

A página atual (com o background pronto) é a **Visão Executiva**. Para um projeto completo, considerar mais 2-3 páginas:

1. **Visão Executiva** ← já desenhada
2. **Detalhamento por Cluster** — drill-down focado em 1 cluster (selecionado via slicer)
3. **Saúde da Base** — métricas de churn, migração entre clusters mês a mês
4. **Análise Geográfica** — mapa do Brasil + breakdown por UF/cidade

Para cada página adicional, pode-se reutilizar o mesmo background (modificando apenas o título "VISÃO EXECUTIVA" → "DETALHAMENTO POR CLUSTER", etc.) — o script `_make_png_background.py` aceita parametrização fácil.

---

*Última atualização: 2026-05-10. Combinar com `dicionario_dados.md` ao construir as medidas DAX.*

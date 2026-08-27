# Auditoria de design — background do dashboard

`/impeccable audit` · skill [Impeccable](https://github.com/pbakaus/impeccable) v4.1.2 · 2026-08-27

> **Estado:** corrigido em 2026-08-27 pelo redesign "Petrol". O detector passou de **25 → 0**
> anti-padrões. O laudo abaixo é o "antes"; o que mudou está em [Depois](#depois--redesign-petrol).

## Escopo

O background do dashboard **não é um arquivo de imagem nem um tema do Power BI**. Ele é
HTML+CSS gerado por DAX e renderizado pelo visual *HTML Content*:

| Arquivo | Papel |
|---|---|
| **`powerbi/RFM.SemanticModel/definition/tables/_Background.tmdl`** | **O background.** Measures `_BG Pagina 1` (L5) e `_BG Pagina 2` (L388) emitem o documento HTML completo — aurora, topbar, cards de KPI, painéis, painel de IA. É o arquivo auditado aqui. |
| `powerbi/dashboard_theme.json` | Paleta dos visuais nativos do Power BI (não desenha o fundo) |
| `powerbi/RFM.Report/definition/pages/*/page.json` | Cor de fundo da página do relatório (fica **atrás** do HTML) |
| `streamlit_agent/app.py` (L62-240) | CSS do agente Streamlit — replica o mesmo tema |

Como o CSS vive dentro de literais DAX, `powerbi/tools/extract_bg_html.py` materializa as
duas páginas em `.html` para o detector determinístico rodar em cima delas:

```bash
python3 powerbi/tools/extract_bg_html.py /tmp/bg
node .claude/skills/impeccable/scripts/detect.mjs /tmp/bg/*.html
```

## Audit Health Score

| # | Dimensão | Score | Achado principal |
|---|---|---|---|
| 1 | Acessibilidade | 2/4 | 3 falhas reais de contraste WCAG AA + texto funcional de 9px |
| 2 | Performance | 3/4 | Aurora bem construída (só `transform`/`opacity`); `filter: blur` animado nos dots |
| 3 | Responsividade | 3/4 | `aspect-ratio: 16/9` é a escolha certa para canvas fixo do Power BI |
| 4 | Theming | 3/4 | Sistema de tokens sólido, mas duplicado entre as 2 measures e furado por 4 hexes |
| 5 | Integridade de implementação | 2/4 | Pilha completa de *AI slop*: aurora roxo→índigo, glow colorido, dots pulsantes, tile de logo em gradiente |
| **Total** | | **13/20** | **Acceptable — trabalho relevante pendente** |

Detector determinístico: **25 achados** em 2 páginas (0 erros, 25 warnings).
Verificação manual confirmou todos e encontrou **3 falhas de contraste adicionais** que o
detector não pegou (ele compõe o fundo de forma mais pessimista; os números abaixo são
calculados à mão sobre a composição real).

## Veredito de integridade de implementação — **FALHA**

O conteúdo é específico do produto (clusters RFM, base Olist, métricas reais). O **mundo
visual não é**: fundo quase-preto + aurora radial roxo/índigo animada + glow colorido sob o
CTA + halo radial atrás do avatar + dots pulsantes + tile de logo em gradiente 135° é
exatamente a assinatura padrão de UI gerada por IA. Trocando os rótulos, esse chrome serve
qualquer SaaS. Cinco regras de *slop* dispararam sobre essa mesma pilha.

## Resumo executivo

- Score: **13/20** (Acceptable)
- Achados: **P0 0 · P1 4 · P2 3 · P3 3**
- Críticos:
  1. `.ai-cta` — branco sobre `#BF6FF8` a **3,07:1**, o CTA principal da página 1
  2. Pilha de *AI slop* (5 regras) concentrada no painel de IA e nos cards de KPI
  3. `.diag-icon` e `.kpi .pill.down` — vermelho `#E5484D` em fundo tingido, 4,2:1 e 4,15:1
  4. Escala tipográfica de 9 tamanhos entre 9px e 16px, sem hierarquia legível

## Achados por severidade

### [P1] Contraste do CTA principal abaixo de AA
- **Local**: `_Background.tmdl:268-273` (`.ai-cta`)
- **Categoria**: Acessibilidade
- **Medição**: `color:#fff` sobre `linear-gradient(135deg, #BF6FF8, #5E6AD2)` → **3,07:1** na
  ponta roxa (4,70:1 na ponta índigo). Texto de 13px exige 4,5:1.
- **Impacto**: o call-to-action mais importante da Visão Executiva é o texto menos legível da tela.
- **Padrão**: WCAG 2.1 AA 1.4.3
- **Correção**: escurecer o gradiente (ex.: `#9D54E5 → #4C57BE`) ou subir o texto para 16px/600
  (large text → 3:1). Manter `#fff` e escurecer é a opção que preserva a identidade.
- **Comando**: `/impeccable colorize`

### [P1] Vermelho semântico sobre fundo tingido falha AA
- **Local**: `_Background.tmdl:527` (`.diag-icon`, `.diag-title`)
- **Categoria**: Acessibilidade
- **Medição**: `#E5484D` sobre `--em-risco-soft` composto = **4,22:1**. Texto de 11px exige 4,5:1.
- **Impacto**: justamente o estado de alerta ("Em risco") é o menos legível dos quatro.
- **Correção de rota**: a primeira versão deste laudo listava também `.kpi .pill.down` (4,15:1)
  como falha viva. Verificação no navegador mostrou que `.pill`, `.bar` e as variantes
  `.up/.down/.warn/.flat` **não têm marcação correspondente** — a measure calcula as VARs
  `pillX`/`colX`/`fX` e as descarta. É CSS morto, não uma falha de acessibilidade. Ver o P3
  de código morto abaixo.
- **Correção**: clarear o vermelho de texto para ~`#FF7B7F` mantendo `#E5484D` como cor de
  preenchimento (barra, ponto, borda).
- **Comando**: `/impeccable colorize`

### [P1] Pilha de anti-padrões de UI gerada por IA
- **Categoria**: Integridade de implementação
- **Detectados**:
  | Regra | Local | Evidência |
  |---|---|---|
  | `dark-glow` | `:272` | `box-shadow: 0 4px 14px rgba(94,106,210,0.35)` — glow colorido em página escura |
  | `radial-halo` | `:240-243` | `.ai-avatar::before` — `radial-gradient(circle, var(--champions), transparent 70%)` decorativo |
  | `pulsing-dot` | `:252-255` | dot de 7px com `animation: pulse` infinito — o status (`Claude Haiku 4.5 · IA embarcada`) é **texto estático**, não dado ao vivo |
  | `pulsing-dot` (não detectado, verificado à mão) | `:161-169`, `:511-519` | `.kpi .dot::after` — 4 dots por página com `filter: blur(4px)` + `dotPulse` |
  | `side-tab` | `:527` | `.diagnostic-bar` — `border-left: 3px solid var(--em-risco)` + `border-radius: 12px` |
- **Impacto**: sinaliza template genérico e enfraquece a credibilidade de um dashboard analítico.
- **Correção**: trocar o glow por elevação neutra; remover o halo do avatar; manter o pulso
  **só** onde há dado vivo (nenhum caso aqui); substituir a borda lateral por um ponto ou
  rótulo de severidade.
- **Comando**: `/impeccable quieter`

### [P1] Escala tipográfica sem hierarquia
- **Local**: `:139`, `:181`, `:208`, `:210`, `:265`, `:267`, `:489`, `:527`, `:545`
- **Categoria**: Implementação / legibilidade
- **Medição**: 9 tamanhos — 9, 10, 11, 11.5, 12, 13, 14, 15, 16px — em uma faixa total de
  1,8:1. Passos vizinhos ficam em 1,04:1, abaixo do mínimo prático de 1,25:1.
- **Achados relacionados**: `undersized-ui-text` × 5 (rótulos de 9px: "Snapshot", "Modelo",
  "Experimente perguntar") e `tiny-text` × 7 (11px e 11.5px).
- **Impacto**: em um canvas 16:9 projetado ou em tela cheia, os rótulos de 9px somem; sem
  contraste de tamanho, o olho não encontra a entrada da página.
- **Correção**: colapsar para 5 degraus (11 · 13 · 16 · 20 · 26px), com piso de 11px para
  qualquer texto funcional. `11.5px` é valor fora de qualquer escala — eliminar.
- **Comando**: `/impeccable typeset`

### [P2] `--text-3` opera na margem do AA
- **Local**: `:56` / `:406`, usado em `:139`, `:208`, `:251`, `:265`, `:274`, `:489`, `:543`
- **Medição**: `#8B8B92` sobre o card = **5,44:1** (passa); sobre o card no pico da aurora =
  **4,81:1**. Como a aurora anima 12s, o contraste desses rótulos oscila — e eles estão a 9-11px.
- **Correção**: subir `--text-3` para ~`#9A9AA2` (≈6,3:1) ou reduzir o pico da aurora sob a topbar.
- **Comando**: `/impeccable typeset`

### [P2] Tokens duplicados entre as duas páginas
- **Local**: `:45-64` (`_BG Pagina 1`) e `:395-414` (`_BG Pagina 2`) — dois `:root` idênticos
- **Categoria**: Theming
- **Impacto**: qualquer ajuste de paleta precisa ser feito duas vezes; as páginas divergem em
  silêncio. `streamlit_agent/app.py` é uma terceira cópia dos mesmos valores.
- **Correção**: extrair uma measure `_CSS Tokens` e concatenar nas duas — o Power BI aceita
  composição de measures de texto.
- **Comando**: `/impeccable extract`

### [P2] Cores fora do sistema de tokens
- **Local**: `:26-29` (`#34D399` × 5, sem token), `:182-185` (`#15351f`, `#3a1416`, `#3a3115`,
  `#26272E` — fundos das pills), `:110` (`#9D54E5`)
- **Categoria**: Theming
- **Correção**: adicionar `--sucesso`, `--sucesso-soft`, `--em-risco-bg`, `--novos-bg`, `--neutro-bg`.
- **Comando**: `/impeccable extract`

### [P3] Código morto: um terço do CSS não tem marcação
- **Local**: página 1 — `.pill`, `.up/.down/.warn/.flat`, `.bar`, `.bar-fill`, `.bar-tick`,
  `.panel-badge`, `.badge-*`, `.panel-sub`, `.ai-foot`, `.footer`; página 2 — todo o bloco
  `.kpi*` mais `.panel-badge`, `.badge-*`, `.footer`
- **Categoria**: Implementação
- **Verificação**: renderizado em Chromium a 1280×720, comparando as classes declaradas nas
  folhas com as presentes no DOM.
- **Impacto**: a measure `_BG Pagina 1` computa ~20 VARs (`pillCli`, `colRec`, `fTic`, `clsRis`…)
  que nunca entram no HTML — cada uma dispara avaliação de medida a cada refresh. E o CSS morto
  fez esta auditoria reportar falhas de contraste que ninguém vê.
- **Correção**: as regras de pill/bar/badge foram mantidas e realinhadas ao novo sistema (a
  marcação pode voltar); `.footer` e `.ai-foot` foram removidos. As VARs mortas em DAX ficaram
  como estão — mexer em lógica de medida sem o Power BI para testar não se paga.

### [P3] `.footer` é CSS morto — e reviver como está falharia AA
- **Local**: `:277-281` e `:555-559` (regra `.footer`), `:57` / `:407` (`--text-muted: #6B6B73`)
- **Categoria**: Theming
- **Verificação**: a marcação das duas páginas traz `<!-- footer removido -->` (`:378`, `:670`).
  A regra e o token `--text-muted` **não chegam a renderizar** — não há falha de acessibilidade hoje.
- **Nota**: se o rodapé voltar como está, `#6B6B73` sobre o card dá **3,48:1**, abaixo de 4,5:1
  para os 12px declarados. Ou remover a regra órfã, ou já subir o token para `#8B8B92`.
- **Comando**: `/impeccable extract`

### [P3] `filter: blur(4px)` animado
- **Local**: `:161-169`, `:511-519` (`.kpi .dot::after`)
- **Categoria**: Performance
- **Impacto**: o `blur` é estático e só `opacity`/`transform` animam, então o custo é baixo — mas
  são 4 camadas desfocadas compostas por página, permanentemente. Some junto com o P1 de slop.

### [P3] `prefers-reduced-motion` desliga tudo em bloco
- **Local**: `:283-285`, `:561-563` — `*, *::before, *::after { animation: none !important }`
- **Categoria**: Acessibilidade
- **Nota**: aceitável aqui, porque **toda** a animação do chrome é decorativa (aurora, glows,
  pulsos) e nenhuma carrega mudança de estado. Registrado para não regredir se algum dia uma
  animação passar a comunicar dado.

## Padrões sistêmicos

1. **A paleta roxo/índigo é o problema-raiz.** Aurora, halo do avatar, glow do CTA, tile do
   logo e os dots derivam todos de `--champions`/`--big-spenders`. As 5 regras de slop são
   sintoma de uma decisão só.
2. **Contraste falha exatamente onde o significado é vermelho.** Os três vermelhos verificados
   ficam entre 3,07 e 4,22:1, enquanto verde e amarelo passam com folga.
3. **Um sistema de tokens copiado três vezes** (page 1, page 2, Streamlit) já começou a divergir.

## Pontos positivos

- **A aurora é bem implementada**: camada única, anima só `transform`/`opacity`, `will-change`
  declarado, `translate3d` para compositor. Nada de animar propriedades de layout.
- **`aspect-ratio: 16/9` + grid** deriva a altura da largura — robusto em qualquer canvas 16:9,
  sem alturas mágicas em px.
- `prefers-reduced-motion` presente nas duas páginas.
- `font-variant-numeric: tabular-nums` nos valores de KPI — números alinham entre linhas.
- Reset anti-user-agent (`h1..h6 { color: inherit; font: inherit }`) evita o estilo padrão do
  iframe do visual HTML.
- Pills de estado verde e amarelo passam AA com folga (7,0:1 e 8,12:1).

## Ações recomendadas

1. **[P1] `/impeccable colorize`** — corrigir os três vermelhos e o gradiente do `.ai-cta`.
2. **[P1] `/impeccable quieter`** — remover glow, halo, dots pulsantes e a borda lateral.
3. **[P1] `/impeccable typeset`** — colapsar 9 tamanhos em 5; piso de 11px; clarear `--text-3`.
4. **[P2] `/impeccable extract`** — tokens em measure única e cores soltas viram tokens.
5. **[P2] `/impeccable polish`** — passada final e realinhamento com `streamlit_agent/app.py`.

---

## Depois — redesign "Petrol"

Mundo visual derivado de uma referência em vídeo (Fuselab Creative, *Control AI Policy
Platform*): campo teal dessaturado, cards escuros com fio de 1px, ouro como acento quente,
ciano exclusivo da ação, rosa só para alerta.

### Resultado

| | Antes | Depois |
|---|---|---|
| Detector (2 páginas) | 25 achados | **0** |
| Contraste do CTA principal | 3,07:1 ❌ | **9,81:1** ✅ |
| Menor contraste de token sobre card | 3,48:1 ❌ | **6,2:1** ✅ |
| Anti-padrões de *AI slop* | 5 regras | **0** |
| Tamanhos de fonte | 9 (9→16px, faixa 1,8:1) | **4** (11/14/18/26) |
| Animações no chrome | 4 loops infinitos | **0** |

### Paleta

| Papel | Antes | Depois | Contraste sobre o card |
|---|---|---|---|
| Canvas | `#08090A` + aurora roxa animada | `#05080A` + campo teal estático | — |
| Superfície | `rgba(20,22,30,.85)` | `rgba(8,14,16,.90)` | — |
| Texto 1 / 2 / 3 | `#F4F4F5` / `#A1A1AA` / `#8B8B92` | `#EAF2F2` / `#A6BBBC` / `#8AA0A2` | 15,9 / 9,0 / 6,6 |
| **Ação (IA)** | — (era roxo do gradiente) | **`#74CBD1`** com tinta `#04171A` | **9,8** |
| Champions | `#5E6AD2` índigo | `#E0AB6A` ouro | 8,8 |
| Big Spenders | `#BF6FF8` roxo | `#A38ADB` lilás | 6,2 |
| Novos | `#F2C94C` amarelo | `#79C9A4` sage | 9,2 |
| Em Risco | `#E5484D` vermelho | `#E8879A` rosa | 7,2 |

O ciano da ação fica a ~50° de matiz das quatro cores de dado, então categoria e ação nunca
se confundem. Deltas positivos reusam o sage e negativos o rosa, em vez de dois verdes e dois
vermelhos soltos fora do sistema.

### O que saiu

- **`radial-halo`** — halo roxo atrás do avatar da IA
- **`dark-glow`** — `box-shadow` colorido sob o CTA (virou elevação neutra com offset e blur)
- **`pulsing-dot`** — o dot de status pulsando sobre texto estático, e os 4 dots de KPI com
  `filter: blur` + `dotPulse`
- **`side-tab`** — `border-left: 3px` na barra de diagnóstico (virou ponto de categoria)
- **Aurora de 12s** — o chrome fica atrás de seis visuais que já se movem a cada filtro
- **Cards aninhados** na lista de exemplos do painel de IA (viraram linhas com fio)
- **Glifos Unicode como ícone** (`✦`, `→`, `›`) — viraram SVG desenhado
- **`.footer` / `.ai-foot`** — regras órfãs

### Restrição que guiou o trabalho

O relatório é um canvas fixo de **1280×720** e os visuais nativos são posicionados em pixel
absoluto **por cima** do chrome (`p1_concentracao` em y=515, o botão "Abrir Analista" em
y=624, o slicer de ano da página 2 em x=160). Qualquer mudança de altura desalinha o
dashboard. Cada passo foi renderizado em Chromium a 1280×720 e as caixas comparadas contra o
baseline: **as 23 caixas que os visuais sobrepõem terminaram com deslocamento zero.**

Duas colisões apareceram nessa verificação e foram corrigidas: título de painel a 18px passava
por baixo do slicer de ano (voltou a 14px, com peso e cor carregando a hierarquia) e o seletor
de abas centralizado na coluna `1fr` saía de baixo do action button (o topbar virou
`1fr auto 1fr`, e agora o botão cobre a aba inteira — melhor que no original).

### Um achado suprimido, com motivo

`flat-type-hierarchy` continua disparando na página 2 (11/14/18px, faixa 1,6:1). É falso
positivo: o chrome da página 2 é fundo, e a hierarquia visual dela é carregada pelos seis
visuais nativos desenhados por cima. Registrado com `impeccable-disable` e a justificativa no
próprio HTML.

### Propagação

O mesmo mapa de cor foi aplicado a `dashboard_theme.json` (e à cópia em `RegisteredResources`),
aos 4 specs Deneb, a `dim_segmentos[Cor_Hex]` em `src/export.py`, ao `streamlit_agent/app.py`
(que também perdeu a aurora, o halo, o dot pulsante e o `bounce-easing` do indicador de
digitação) e a `.streamlit/config.toml`. O detector roda limpo no `app.py` também.

---

# Auditoria 2 — pós-redesign

`/impeccable audit` · 2026-08-27, após o commit `969f73c`

## Como foi medido

Não só pelo detector. As duas páginas foram renderizadas em Chromium a 1280×720 e:

- **contraste medido em pixel**, não no CSS declarado: para cada nó de texto, a cor computada
  contra o decil mais escuro dos pixels da própria caixa (o que sobrevive a gradiente, alpha e
  ao campo teal por baixo) — 51 nós no total;
- **paleta categórica simulada** para deuteranopia, protanopia e tritanopia (matrizes de
  Machado et al., 2009);
- **`_Plano Acao`** renderizado no tamanho real do visual (416×224) para checar corte de texto;
- classes CSS sem marcação, animações ativas e tamanhos de fonte lidos do DOM computado.

## Audit Health Score

| # | Dimensão | Antes | Agora | Achado principal |
|---|---|---|---|---|
| 1 | Acessibilidade | 2/4 | **2/4** | Texto passou a excelente (0 falhas em 51 nós, piso 6,77:1), mas a paleta categórica quebrou sob daltonismo |
| 2 | Performance | 3/4 | **3/4** | Zero animação no chrome; as ~20 VARs DAX mortas continuam sendo avaliadas |
| 3 | Responsividade | 3/4 | **3/4** | Geometria verificada caixa a caixa; uma linha de texto passou a truncar |
| 4 | Theming | 3/4 | **3/4** | Sistema de papéis coerente, mas `:root` ainda duplicado e um shorthand inválido derruba a fonte das abas |
| 5 | Integridade de implementação | 2/4 | **4/4** | Zero anti-padrões, ícones desenhados, mundo visual com origem declarada |
| **Total** | | **13/20** | **15/20** | **Good — resolver as dimensões fracas** |

Detector determinístico: **0 achados** nas duas páginas e no `app.py` (exit 0).
Esta auditoria encontrou **4 problemas que o detector não vê**, um deles uma regressão
introduzida pelo próprio redesign.

## Veredito de integridade — **PASSA**

O chrome já não é intercambiável com outro produto. O mundo visual tem origem declarada (uma
referência em vídeo), a relação de profundidade é uma decisão (campo iluminado, cards escuros),
os ícones são desenhados e o ciano só aparece na ação. Nenhuma das 59 regras determinísticas
dispara.

## Achados

### [P1] REGRESSÃO — a paleta de segmentos quebrou sob daltonismo

- **Local**: `_Background.tmdl` (`:root`, ×2), `dashboard_theme.json`, `deneb_specs/*.json`,
  `src/export.py` (`dim_segmentos[Cor_Hex]`)
- **Categoria**: Acessibilidade — WCAG 1.4.1 (uso de cor)
- **Medição**:

  | Paleta | Faixa de luminância | Pares indistinguíveis (de 6) |
  |---|---|---|
  | | | normal · deuteranopia · protanopia · tritanopia |
  | Anterior (índigo/roxo/amarelo/vermelho) | 0,173 – 0,612 (**3,5×**) | 0 · **0** · **0** · 0 |
  | Atual (ouro/lilás/sage/rosa) | 0,311 – 0,485 (**1,6×**) | 0 · **2** · **2** · 1 |

  Sob deuteranopia, ouro e sage ficam a 3° de matiz com razão de luminância 1,08 — ou seja,
  a mesma cor. Sob protanopia, o mesmo par (1,20) e lilás × rosa (1,04).

- **Causa**: peguei os quatro matizes das *esferas decorativas* do vídeo de referência. Ali a
  cor é atmosférica e as esferas são propositalmente pastéis de luminância parecida. Transplantei
  uma paleta atmosférica para um papel categórico — e o dashboard inteiro codifica os quatro
  clusters por cor. A paleta antiga era feia perto dessa, mas separava por luminância, então
  sobrevivia a qualquer tipo de daltonismo.
- **Impacto**: ~8% dos homens não distinguem Campeões de Novos/Ocasionais nos visuais Deneb.
  Nos cards de KPI o risco é menor (há rótulo de texto ao lado do ponto); concentra-se nos
  gráficos em que a cor é o único código.
- **Correção proposta** (matizes da referência preservados, luminância reespalhada):

  | Segmento | Atual | Proposto | L | Sobre o card |
  |---|---|---|---|---|
  | Champions | `#E0AB6A` | `#E2C38C` | 0,572 | 11,2:1 |
  | Big Spenders | `#A38ADB` | `#8C6BC6` | 0,203 | 4,6:1 |
  | Novos | `#79C9A4` | `#3DA27D` | 0,286 | 6,1:1 |
  | Em Risco | `#E8879A` | `#DC889D` | 0,355 | 7,3:1 |

  Esse conjunto dá **0/6 pares indistinguíveis** nas três simulações. Números gerados por busca,
  não validados a olho: `#8C6BC6` fica perto do piso AA para texto (4,6:1) e alguns pares ainda
  se separam mais por luminância que por matiz. Passar por `/impeccable colorize` antes de adotar.
- **Comando**: `/impeccable colorize`

### [P1] O seletor de abas não usa a fonte, o tamanho nem o peso declarados

- **Local**: `_Background.tmdl` — regra `.tab`, `font: 500 14px inherit`
- **Categoria**: Theming / Implementação
- **Medição**: computado no navegador, `.tab` renderiza **13,33px, peso 400, família Arial**.
- **Causa**: `font: 500 14px inherit` é um shorthand **inválido** — `inherit` é palavra-chave
  CSS-wide e não vale como `font-family` dentro do shorthand. O navegador descarta a declaração
  inteira e o `<button>` cai no padrão do user agent. O bug é anterior ao redesign (era
  `font: 500 13px inherit`), então a troca 13→14px da passada anterior **não teve efeito nenhum**.
- **Impacto**: a navegação principal sai numa tipografia que não é a do resto do dashboard, e no
  WebView do Power BI cai no padrão daquele runtime, não em Segoe UI. Também insere um quinto
  tamanho (13,33px) numa escala projetada com quatro.
- **Correção**: trocar por declarações separadas — `font-size: 14px; font-weight: 500;`
  (a família já herda). Refazer a medição das abas depois: a largura congelada em 290px foi
  calculada sobre a renderização errada.
- **Comando**: `/impeccable typeset`

### [P2] REGRESSÃO — uma ação de CRM passou a truncar

- **Local**: `_Background.tmdl` — measure `_Plano Acao`, regra `.ac`
- **Categoria**: Responsividade
- **Medição**: visual renderizado a 416×224 (tamanho real de `p2_review_recency`). A linha
  "Converter p/ recorrência: upsell pós-venda" estoura por **4px** e é cortada com reticências.
  A 10px (antes do redesign) cabia.
- **Impacto**: o painel existe para dizer o que fazer com cada segmento; a recomendação de Big
  Spenders é justamente a que fica pela metade.
- **Correção**: `.ac` volta a 10px, ou o texto encurta para "Upsell pós-venda p/ recorrência",
  ou a linha ganha duas linhas de altura. Encurtar o texto é o que preserva a escala.
- **Comando**: `/impeccable clarify`

### [P2] Tokens ainda duplicados — agora em cinco lugares

- **Local**: dois blocos `:root` (`_BG Pagina 1` e `_BG Pagina 2`), mais os hexes das quatro
  categorias repetidos nas 4 measures `_Spark *` e nos `style=` inline de `_Plano Acao`
- **Categoria**: Theming
- **Nota**: o P2 da auditoria anterior continua de pé, e o redesign o ampliou — as measures de
  sparkline e o plano de ação emitem HTML em documentos separados, onde `var(--token)` não
  alcança. Trocar uma cor de segmento hoje exige editar cinco pontos, e a correção do P1 acima
  vai passar por todos eles.
- **Correção**: uma measure `_Cores` devolvendo os hexes, concatenada tanto no `:root` quanto
  nos `style=` inline.
- **Comando**: `/impeccable extract`

### [P3] Código morto cresceu um pouco

- **Local**: página 1 — 16 classes sem marcação (`pill`, `bar*`, `badge-*`, `panel-sub`,
  `up/down/warn/flat`, `diagnostic-bar`); página 2 — 15, incluindo todo o bloco `.kpi*` e `.ai-panel`
- **Nota**: a regra compartilhada de luz superior que adicionei lista `.diagnostic-bar` e
  `.ai-panel` nas duas páginas, e cada uma só existe em uma. Custo real: zero. Ruído de
  manutenção: real.

### [P3] Um `!` tipográfico onde o resto são ícones desenhados

- **Local**: `_Background.tmdl:595` — `<div class="diag-icon">&#33;</div>`
- **Nota**: o logo, o avatar da IA e a seta do CTA viraram SVG nesta passada; o ícone de alerta
  ficou como caractere. Inconsistente com o próprio sistema agora.

## O que melhorou de fato

- **Contraste de texto**: 51 nós medidos em pixel, **0 falhas**. O piso é 6,77:1 (`--text-3`
  no painel de IA) e o topo 17,22:1. Três nós ficam entre 6,77 e 6,98 — subir `--text-3` de
  `#8AA0A2` para ~`#93A9AB` levaria o sistema inteiro a AAA (7:1).
- **CTA principal**: 3,07:1 → **9,81:1**, confirmado por amostragem do preenchimento renderizado.
- **Movimento**: quatro loops infinitos → **zero animação e zero transição** no chrome.
- **Geometria**: as 23 caixas que os visuais nativos sobrepõem seguem com deslocamento zero
  contra o baseline pré-redesign.
- **Anti-padrões**: 25 → 0.

## Ações recomendadas

1. **[P1] `/impeccable colorize`** — reespalhar a luminância das quatro categorias (a proposta
   acima já passa nas três simulações de daltonismo).
2. **[P1] `/impeccable typeset`** — corrigir o shorthand `font` das abas e refazer a medição.
3. **[P2] `/impeccable clarify`** — encurtar a ação de Big Spenders que trunca.
4. **[P2] `/impeccable extract`** — measure `_Cores` única, antes de mexer nas cores pelo item 1.
5. **[P3] `/impeccable polish`** — ícone de alerta em SVG, limpeza do CSS morto, `--text-3` a AAA.

Rode `/impeccable audit` de novo depois de qualquer mudança para conferir.

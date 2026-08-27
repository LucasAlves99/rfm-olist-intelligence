# Auditoria de design — background do dashboard

`/impeccable audit` · skill [Impeccable](https://github.com/pbakaus/impeccable) v4.1.2 · 2026-08-27

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
- **Local**: `_Background.tmdl:527` (`.diag-icon`, `.diag-title`) e `:183` (`.kpi .pill.down`)
- **Categoria**: Acessibilidade
- **Medição**: `#E5484D` sobre `--em-risco-soft` composto = **4,22:1**; sobre `#3a1416` = **4,15:1**.
- **Impacto**: justamente o estado de alerta ("Em risco") é o menos legível dos quatro.
- **Observação**: `.pill.up` (7,0:1) e `.pill.warn` (8,12:1) passam — só a variante vermelha falha.
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

Rode `/impeccable audit` de novo depois das correções para ver o score subir.

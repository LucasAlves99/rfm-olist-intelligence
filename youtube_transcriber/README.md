# yt-transcriber

Transcreve vídeos do YouTube pela linha de comando ou como biblioteca Python.

Funciona em duas camadas:

1. **Legendas do YouTube** (padrão): busca a legenda que já existe no vídeo. Leva segundos, não
   baixa áudio e não usa GPU. Prefere a legenda criada pelo autor; se só houver a automática,
   usa essa.
2. **Whisper local** (plano B): se o vídeo **não tem legenda nenhuma**, baixa o áudio com
   `yt-dlp` e transcreve com `faster-whisper`. É bem mais lento e exige instalar pacotes extras.

```
URL/ID ──► legendas do YouTube ──► ok ──────────────────────────► txt / srt / vtt / json / md
               │
               └─ sem legenda? ──► baixa áudio ──► Whisper ──────► (mesmos formatos)
```

O Whisper só entra quando **não há legenda**. Vídeo privado, removido ou um bloqueio do YouTube
não têm conserto no Whisper (o áudio vem do mesmo lugar), então esses erros sobem direto.

## Instalação

Requer Python 3.10+.

```bash
cd youtube_transcriber

# Só legendas (leve):
pip install -e .

# Com o plano B (Whisper):
pip install -e ".[whisper]"      # ou: pip install -r requirements-whisper.txt
```

Isso cria o comando `yt-transcribe`. Sem instalar, `python -m yt_transcriber ...` também funciona
de dentro desta pasta.

## Uso

```bash
# Um vídeo (URL em qualquer formato, ou só o ID). Grava transcripts/dQw4w9WgXcQ.txt
yt-transcribe https://youtu.be/dQw4w9WgXcQ

# Vários formatos de uma vez, preferindo legenda em português e, se não houver, inglês
yt-transcribe dQw4w9WgXcQ -f srt,txt,json -l pt,en

# Vários vídeos de uma vez (um que falhe não interrompe os outros)
yt-transcribe URL1 URL2 URL3 -f md -o minhas_transcricoes

# Texto na saída padrão, para encadear com outros comandos
yt-transcribe URL --stdout | wc -w

# Uma linha por trecho, com marcação de tempo
yt-transcribe URL -t

# Forçar o Whisper (ex.: a legenda automática está ruim), escolhendo modelo e idioma
yt-transcribe URL --method whisper --model medium --whisper-language pt
```

URLs aceitas: `watch?v=`, `youtu.be/`, `/shorts/`, `/embed/`, `/live/`, `m.youtube.com`,
`music.youtube.com`, com ou sem `https://`, com ou sem parâmetros extras (`&t=42s`, `&list=...`).

### Formatos de saída

| `-f` | Conteúdo |
|---|---|
| `txt` | Texto corrido, quebrado a 100 colunas. Com `-t`, uma linha por trecho: `[00:01:23] texto` |
| `srt` | Legenda SubRip, pronta para players e editores de vídeo |
| `vtt` | WebVTT, para `<track>` em HTML5 |
| `json` | Metadados + `segments` com `start`/`end`/`text` — bom para processar por código |
| `md`  | Markdown com título, fonte e **links que abrem o vídeo no instante de cada trecho** |

Os arquivos são gravados como `<pasta>/<id-do-vídeo>.<formato>`, e o comando imprime só os
caminhos gravados na saída padrão. As mensagens de andamento vão para `stderr` (silencie com `-q`).

### Opções

| Opção | Padrão | O que faz |
|---|---|---|
| `-f, --format` | `txt` | Um ou mais formatos, separados por vírgula |
| `-o, --output-dir` | `transcripts` | Pasta de saída (criada se não existir) |
| `--stdout` | — | Imprime em vez de gravar (exige 1 vídeo e 1 formato) |
| `-l, --lang` | primeira manual | Idiomas da legenda em ordem de preferência (`pt,en`) |
| `-m, --method` | `auto` | `auto`, `captions` (nunca usa Whisper) ou `whisper` (ignora legendas) |
| `-t, --timestamps` | — | No `txt`, uma linha por trecho com tempo |
| `--model` | `small` | Modelo Whisper: `tiny`, `base`, `small`, `medium`, `large-v3`... |
| `--device` | `auto` | `auto`, `cpu` ou `cuda` |
| `--whisper-language` | detectar | Idioma falado no áudio (`pt`, `en`...) |
| `-q, --quiet` | — | Sem mensagens de andamento |

**Código de saída:** `0` tudo certo · `1` algum vídeo falhou · `2` uso incorreto · `130` Ctrl+C.

**Sobre `-l` e o Whisper:** o idioma pedido em `-l` vale só para a *legenda*. Se o vídeo tiver
legenda apenas em inglês e você pedir `pt`, o comando avisa quais idiomas existem e cai no
Whisper **detectando o idioma sozinho** — forçar `pt` num áudio em inglês geraria lixo. Para
fixar o idioma do áudio, use `--whisper-language`.

## Como biblioteca

```python
from yt_transcriber import extract_video_id, transcribe
from yt_transcriber.formatters import render

video_id = extract_video_id("https://youtu.be/dQw4w9WgXcQ")
t = transcribe(video_id, languages=["pt", "en"])

print(t.language, t.source)  # "pt", "captions" | "captions-auto" | "whisper"
print(t.text)  # texto inteiro
for seg in t.segments:  # Segment(start, end, text)
    print(seg.start, seg.text)

open("aula.srt", "w", encoding="utf-8").write(render(t, "srt"))
```

Todos os erros esperados herdam de `TranscriberError`; a mensagem já vem pronta para exibir.

| Erro | Quando |
|---|---|
| `InvalidVideoReference` | A URL/ID não é de um vídeo do YouTube |
| `NoCaptionsAvailable` | Sem legenda (ou sem legenda no idioma pedido). Aciona o Whisper em `auto` |
| `VideoNotAccessible` | Privado, removido, restrito por idade, bloqueado na região |
| `RequestBlockedError` | O YouTube recusou a requisição |
| `NetworkError` | Sem conexão / DNS / proxy / timeout |
| `MissingDependency` | Faltam `yt-dlp` / `faster-whisper` para o plano B |

## Limitações

- **IPs de nuvem costumam ser bloqueados pelo YouTube.** Rodar em servidor (AWS, GCP, CI...) muitas
  vezes retorna `RequestBlockedError`. Numa rede residencial funciona; em servidor, use um proxy.
- **Legenda automática tem erros** (nomes próprios, jargão, sotaques) e quase nunca tem pontuação
  boa. Para qualidade melhor use `--method whisper --model medium` (ou `large-v3` com GPU).
- **Vídeos restritos por idade** exigem login e não são suportados.
- **Whisper na CPU é lento**: um vídeo de 1 h com `small` leva vários minutos, e a primeira execução
  baixa o modelo (centenas de MB). Áudio é baixado numa pasta temporária e apagado ao final.
- Transcreve o que foi **falado**. Não gera resumo, capítulos nem tradução.

## Desenvolvimento

```bash
pip install -e ".[dev]"
pytest          # 116 testes, todos offline
ruff check . && ruff format --check .
```

Os testes não acessam a rede. Os de legenda usam as classes reais da `youtube-transcript-api`
(só o `fetch()` é substituído), então a regra de seleção de idioma testada é a da própria
biblioteca, e não a de um mock. Os do Whisper injetam um modelo e um `YoutubeDL` falsos.

```
yt_transcriber/
├── urls.py             extrai o ID (e valida o host: o ID vira nome de arquivo)
├── captions.py         backend 1: legendas do YouTube
├── whisper_backend.py  backend 2: yt-dlp + faster-whisper
├── service.py          decide entre os dois
├── formatters.py       txt / srt / vtt / json / md
├── cli.py              interface de linha de comando
├── models.py           Segment, Transcript, WhisperOptions
└── errors.py           hierarquia de erros
```

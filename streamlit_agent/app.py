"""Streamlit App — Analista RFM (Claude Haiku 4.5).

App principal, publicado no Streamlit Cloud e acessível a partir do
dashboard Power BI (link/botão). Layout dark executive.

Deploy: Streamlit Community Cloud (free) com uptime ping.
"""

# Standard library
import base64
import logging
import time
from pathlib import Path

# Third-party
import streamlit as st

# Local
from agent.claude_client import build_client, chat_stream
from agent.tools import get_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

# Preço da API Claude Haiku 4.5 em USD por 1M de tokens (input, output, cache read/write).
HAIKU_PRICE_PER_MTOK = {
    "input": 0.80,
    "output": 4.00,
    "cache_read": 0.08,
    "cache_write": 1.00,
}
USD_TO_BRL = 5.5  # cotação aproximada para exibição do custo da sessão

# Avatares do chat (SVG embutido como data-URI): agente ✦ igual ao dashboard, usuário limpo.
_ASSETS = Path(__file__).parent / "assets"


def _svg_avatar(filename: str) -> str:
    svg = (_ASSETS / filename).read_text(encoding="utf-8")
    b64 = base64.b64encode(svg.encode("utf-8")).decode()
    return f"data:image/svg+xml;base64,{b64}"


AGENT_AVATAR = _svg_avatar("agent_avatar.svg")
USER_AVATAR = _svg_avatar("user_avatar.svg")

# ──────────────────────────────────────────────────────────────────────────────
# Page config
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Analista RFM",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ──────────────────────────────────────────────────────────────────────────────
# Tema dark executive (CSS inline)
# ──────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* Reset e fundo Aurora */
    .stApp {
        background: #08090A;
        background-image:
            radial-gradient(at 20% 10%, rgba(191, 111, 248, 0.18) 0%, transparent 50%),
            radial-gradient(at 80% 80%, rgba(94, 106, 210, 0.13) 0%, transparent 50%),
            radial-gradient(at 50% 50%, rgba(191, 111, 248, 0.10) 0%, transparent 50%);
    }
    /* Esconde header padrão do Streamlit */
    header[data-testid="stHeader"] { background: transparent; }
    .stDeployButton, [data-testid="stToolbar"] { display: none !important; }

    /* Container principal mais apertado */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
        max-width: 100%;
    }

    /* Mensagens — bot */
    [data-testid="stChatMessage"] {
        background: rgba(20, 22, 30, 0.6);
        backdrop-filter: blur(20px) saturate(140%);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px;
    }

    /* Input do chat */
    [data-testid="stChatInput"] {
        background: rgba(20, 22, 30, 0.6) !important;
        border: 1px solid rgba(255, 255, 255, 0.06) !important;
        border-radius: 10px !important;
    }
    [data-testid="stChatInput"] textarea {
        color: #F4F4F5 !important;
    }

    /* Botões quick action */
    .stButton button {
        background: rgba(255, 255, 255, 0.025) !important;
        border: 1px solid rgba(255, 255, 255, 0.06) !important;
        color: #F4F4F5 !important;
        border-radius: 9px !important;
        font-size: 12px !important;
        padding: 8px 12px !important;
        text-align: left !important;
        width: 100% !important;
        transition: all 0.2s !important;
    }
    .stButton button:hover {
        background: rgba(191, 111, 248, 0.12) !important;
        border-color: rgba(191, 111, 248, 0.3) !important;
        transform: translateX(2px) !important;
    }

    /* Typography */
    body, .stApp, p, span, div { color: #F4F4F5; }
    h1, h2, h3 { color: #F4F4F5 !important; letter-spacing: -0.5px; }

    /* Header customizado */
    .agent-header {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 14px 18px;
        background: rgba(20, 22, 30, 0.6);
        backdrop-filter: blur(20px) saturate(140%);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 14px;
        margin-bottom: 14px;
    }
    .agent-avatar {
        width: 36px; height: 36px;
        border-radius: 10px;
        background: linear-gradient(135deg, #1F2030, #14151D);
        border: 1px solid rgba(255, 255, 255, 0.1);
        display: flex; align-items: center; justify-content: center;
        font-size: 16px; font-weight: 600; color: #5E6AD2;
        position: relative;
    }
    .agent-avatar::before {
        content: '';
        position: absolute;
        inset: -6px;
        border-radius: 16px;
        background: radial-gradient(circle, #5E6AD2 0%, transparent 70%);
        opacity: 0.15;
        animation: pulse 4s ease-in-out infinite;
        z-index: -1;
    }
    @keyframes pulse {
        0%, 100% { opacity: 0.10; transform: scale(1); }
        50% { opacity: 0.25; transform: scale(1.15); }
    }
    .agent-name {
        font-size: 14px;
        font-weight: 600;
        color: #F4F4F5;
        letter-spacing: -0.2px;
    }
    .agent-status {
        font-size: 11px;
        color: #5E6AD2;
        margin-top: 2px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .agent-status::before {
        content: '';
        width: 6px; height: 6px;
        background: #5E6AD2;
        border-radius: 50%;
        animation: dot-pulse 2s infinite;
    }
    @keyframes dot-pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.3; }
    }

    /* Footer */
    .agent-footer {
        font-size: 10px;
        color: #71717A;
        text-align: center;
        margin-top: 10px;
    }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 5px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 3px;
    }

    /* ───── Typing indicator (3 dots animados) ───── */
    .typing-bubble {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 10px 14px;
        background: rgba(20, 22, 30, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 14px;
        border-bottom-left-radius: 4px;
        margin: -12px 0 0 0;
        position: relative;
        top: -8px;
    }
    .typing-bubble .dot {
        width: 8px; height: 8px;
        background: #BF6FF8;
        border-radius: 50%;
        animation: typing-bounce 1.3s infinite;
        box-shadow: 0 0 8px rgba(191, 111, 248, 0.5);
    }
    .typing-bubble .dot:nth-child(2) { animation-delay: 0.18s; }
    .typing-bubble .dot:nth-child(3) { animation-delay: 0.36s; }
    .typing-label {
        margin-left: 10px;
        color: #A1A1AA;
        font-size: 13px;
        font-style: italic;
    }
    @keyframes typing-bounce {
        0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
        30% { transform: translateY(-5px); opacity: 1; }
    }

    </style>
    """,
    unsafe_allow_html=True,
)


def typing_html(label: str = "analisando...") -> str:
    """Retorna HTML do typing indicator com label customizável."""
    return f"""
    <div class="typing-bubble">
        <div class="dot"></div>
        <div class="dot"></div>
        <div class="dot"></div>
        <span class="typing-label">{label}</span>
    </div>
    """


# ──────────────────────────────────────────────────────────────────────────────
# Singleton: cliente Anthropic e DuckDB (cache_resource = 1x por sessão)
# ──────────────────────────────────────────────────────────────────────────────
@st.cache_resource
def get_client():
    return build_client()


@st.cache_resource
def warmup_duckdb():
    """Pré-aquece DuckDB carregando as views Parquet."""
    return get_connection()


# ──────────────────────────────────────────────────────────────────────────────
# Header
# ──────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="agent-header">
        <div class="agent-avatar">✦</div>
        <div>
            <div class="agent-name">Analista RFM</div>
            <div class="agent-status">Claude Haiku 4.5 · Online</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────────────────────────────────────
# State: histórico de mensagens
# ──────────────────────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.greeted = False
    st.session_state.total_input_tokens = 0
    st.session_state.total_output_tokens = 0
    st.session_state.total_cached_read = 0
    st.session_state.total_cached_write = 0


def estimated_cost_usd() -> float:
    """Calcula custo estimado da sessão em USD (Haiku 4.5)."""
    price = HAIKU_PRICE_PER_MTOK
    return (
        st.session_state.total_input_tokens * price["input"]
        + st.session_state.total_output_tokens * price["output"]
        + st.session_state.total_cached_read * price["cache_read"]
        + st.session_state.total_cached_write * price["cache_write"]
    ) / 1_000_000


# ──────────────────────────────────────────────────────────────────────────────
# Aquecimento (spinner apenas na primeira carga — @cache_resource garante 1x)
# ──────────────────────────────────────────────────────────────────────────────
try:
    first_load = "initialized" not in st.session_state
    if first_load:
        with st.spinner("Carregando datamarts..."):
            warmup_duckdb()
            client = get_client()
        st.session_state.initialized = True
    else:
        warmup_duckdb()
        client = get_client()
    api_ready = True
except Exception as e:
    st.error(f"Erro de configuração: {e}")
    st.info(
        "Configure `ANTHROPIC_API_KEY` em `.streamlit/secrets.toml`:\n\n"
        '```toml\nANTHROPIC_API_KEY = "sk-ant-..."\n```'
    )
    api_ready = False

# ──────────────────────────────────────────────────────────────────────────────
# Saudação inicial
# ──────────────────────────────────────────────────────────────────────────────
if not st.session_state.greeted and api_ready:
    st.session_state.greeted = True
    greeting = (
        "Olá. Sou seu **analista RFM** do projeto, com acesso ao contexto "
        "completo do projeto e aos datamarts.\n\n"
        "**Diagnóstico inicial** · base com 93.358 clientes, concentração "
        "Pareto moderada (Gini 0,48) e 22,9% em risco de churn. Recomendo "
        "priorizar *win-back urgente* + programa de fidelidade pros Big "
        "Spenders.\n\n"
        "Use os atalhos abaixo ou pergunte qualquer coisa."
    )
    st.session_state.messages.append({"role": "assistant", "content": greeting})

# ──────────────────────────────────────────────────────────────────────────────
# Histórico de mensagens
# ──────────────────────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    avatar = AGENT_AVATAR if msg["role"] == "assistant" else USER_AVATAR
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# ──────────────────────────────────────────────────────────────────────────────
# Quick actions
# ──────────────────────────────────────────────────────────────────────────────
QUICK_ACTIONS = {
    "🩺  Diagnóstico completo da base": "Faça um diagnóstico completo da saúde da base. Quero entender concentração, recorrência e risco de churn, com números reais.",
    "🔄  Plano de win-back para SP": "Monte um plano de win-back especificamente para clientes em risco no estado de SP. Quero saber quantos são, custo estimado e ROI esperado.",
    "👑  Como proteger os Campeões": "Como proteger os clientes do cluster Campeões? Quero ações concretas, prioridades e ROI esperado.",
}

if api_ready and len(st.session_state.messages) <= 1:
    st.markdown(
        '<div style="font-size: 10px; color: #71717A; letter-spacing: 1.2px; '
        'font-weight: 600; text-transform: uppercase; margin: 10px 0;">'
        "Sugestões rápidas</div>",
        unsafe_allow_html=True,
    )
    for label, prompt in QUICK_ACTIONS.items():
        if st.button(label, key=f"qa_{label}"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.rerun()

# ──────────────────────────────────────────────────────────────────────────────
# Input do usuário
# ──────────────────────────────────────────────────────────────────────────────
user_input = st.chat_input("Pergunte sobre os clusters, KPIs, ações...")
if user_input and api_ready:
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.rerun()

# ──────────────────────────────────────────────────────────────────────────────
# Se a última msg é do user, gera resposta do bot em streaming
# ──────────────────────────────────────────────────────────────────────────────
if api_ready and st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    with st.chat_message("assistant", avatar=AGENT_AVATAR):
        placeholder = st.empty()

        # 1) Mostra typing indicator IMEDIATAMENTE com label apropriado
        is_first_call = len(st.session_state.messages) <= 2
        label = "aquecendo cache..." if is_first_call else "analisando..."
        placeholder.markdown(typing_html(label), unsafe_allow_html=True)

        full = ""

        # Converte histórico para formato API
        api_messages = []
        for m in st.session_state.messages:
            if isinstance(m["content"], str):
                api_messages.append({"role": m["role"], "content": m["content"]})
            else:
                api_messages.append(m)

        usage_acc = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}

        try:
            t0 = time.time()
            gen = chat_stream(client, api_messages, usage_accumulator=usage_acc)
            first_chunk = True
            for chunk in gen:
                if first_chunk:
                    full = chunk
                    placeholder.markdown(full + " ▌")
                    first_chunk = False
                else:
                    full += chunk
                    placeholder.markdown(full + " ▌")
            placeholder.markdown(full)
            elapsed = time.time() - t0

            # Acumula uso na sessão
            st.session_state.total_input_tokens += usage_acc["input"]
            st.session_state.total_output_tokens += usage_acc["output"]
            st.session_state.total_cached_read += usage_acc["cache_read"]
            st.session_state.total_cached_write += usage_acc["cache_write"]

            logging.info(
                f"Resposta em {elapsed:.2f}s · in={usage_acc['input']} "
                f"out={usage_acc['output']} cache_r={usage_acc['cache_read']} "
                f"cache_w={usage_acc['cache_write']}"
            )
        except Exception as e:
            full = f"⚠ Erro ao chamar o agente: `{e}`"
            placeholder.markdown(full)
            logging.exception("Erro no chat_stream")

    st.session_state.messages.append({"role": "assistant", "content": full})
    st.rerun()

# ──────────────────────────────────────────────────────────────────────────────
# Footer com custo da sessão
# ──────────────────────────────────────────────────────────────────────────────
cost = estimated_cost_usd()
n_msgs = sum(1 for m in st.session_state.messages if m["role"] == "user")
cost_brl = cost * USD_TO_BRL

st.markdown(
    f"""
    <div class="agent-footer">
        Claude Haiku 4.5 · Prompt caching + Tool use + DuckDB
        <span style="margin-left: 12px; padding: 2px 8px; background: rgba(167,139,250,0.1); border-radius: 5px; color: #BF6FF8;">
            {n_msgs} perguntas · ${cost:.4f} (≈ R$ {cost_brl:.3f})
        </span>
    </div>
    """,
    unsafe_allow_html=True,
)

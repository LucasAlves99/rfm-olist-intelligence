"""Cliente Claude com Prompt Caching + Tool Use.

Encapsula a lógica de:
- Manter histórico de conversa
- Chamar a API com prompt caching no system prompt
- Loop de tool use (Claude chama tool → roda → devolve resultado)
- Streaming opcional para UX rápida
"""

# Standard library
import logging
import os
from typing import Generator, Iterator

# Third-party
from anthropic import Anthropic
from anthropic.types import MessageParam

# Local
from .system_prompt import get_system_prompt
from .tools import TOOLS_SCHEMA, dispatch_tool

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5"  # 4× mais barato que Sonnet 4.5 — ótimo p/ tool use + respostas curtas
MAX_TOKENS = 1200  # ~900 palavras
MAX_TOOL_ITERATIONS = 4  # evita loops infinitos
HISTORY_LIMIT = 10  # mantém só últimas N mensagens (economia)


def build_client() -> Anthropic:
    """Cria cliente Anthropic. Espera ANTHROPIC_API_KEY em env ou st.secrets."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        try:
            import streamlit as st

            api_key = st.secrets.get("ANTHROPIC_API_KEY")
        except Exception:
            pass
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY não configurada. " "Defina em env var ou .streamlit/secrets.toml"
        )
    return Anthropic(api_key=api_key)


def trim_history(messages: list[MessageParam], limit: int = HISTORY_LIMIT) -> list[MessageParam]:
    """Mantém apenas as últimas N mensagens.

    IMPORTANTE: preserva pares user/assistant intactos para não
    quebrar o contexto do Claude (que espera alternância correta).
    """
    if len(messages) <= limit:
        return messages
    # Mantém últimas N, mas garante que começa com 'user'
    trimmed = messages[-limit:]
    while trimmed and trimmed[0]["role"] != "user":
        trimmed = trimmed[1:]
    return trimmed


def _track_usage(usage, accumulator: dict) -> None:
    """Acumula uso de tokens no dict fornecido (in-place)."""
    accumulator["input"] += usage.input_tokens
    accumulator["output"] += usage.output_tokens
    accumulator["cache_read"] += getattr(usage, "cache_read_input_tokens", 0) or 0
    accumulator["cache_write"] += getattr(usage, "cache_creation_input_tokens", 0) or 0


def chat_stream(
    client: Anthropic,
    messages: list[MessageParam],
    usage_accumulator: dict | None = None,
) -> Generator[str, None, list[MessageParam]]:
    """Conversa com Claude em streaming, resolvendo tool use no caminho.

    Faz UMA chamada (em streaming) por iteração: o texto é transmitido enquanto
    chega e, ao final do stream, inspecionamos o `stop_reason`. Se for tool use,
    executamos as tools e seguimos o loop; caso contrário, a resposta final já
    foi transmitida. Isso evita a chamada dupla (uma para detectar + outra para
    streamar) e corta ~50% do custo nos turnos sem tool.

    Args:
        client: cliente Anthropic.
        messages: histórico de mensagens.
        usage_accumulator: dict opcional com chaves 'input', 'output',
            'cache_read', 'cache_write' — somado in-place.
    """
    # Aplica limite de histórico (economia de tokens)
    messages = trim_history(messages)

    system = [
        {
            "type": "text",
            "text": get_system_prompt(),
            "cache_control": {"type": "ephemeral"},
        }
    ]

    for _ in range(MAX_TOOL_ITERATIONS):
        with client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=TOOLS_SCHEMA,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text
            response = stream.get_final_message()

        if usage_accumulator is not None:
            _track_usage(response.usage, usage_accumulator)

        messages.append({"role": "assistant", "content": response.content})

        # Sem tool use → a resposta final já foi transmitida acima.
        if response.stop_reason != "tool_use":
            return messages

        # Tool use — executa cada tool e devolve os resultados ao Claude.
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                logger.info(f"Tool: {block.name}")
                result = dispatch_tool(block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )
        messages.append({"role": "user", "content": tool_results})

    yield "\n\n(Loop de tool use excedeu o limite.)"
    return messages

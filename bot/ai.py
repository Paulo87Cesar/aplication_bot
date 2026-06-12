"""
Integração com OpenAI GPT-4o.
Retorna a resposta em texto e, quando identificado, os dados do agendamento em JSON.
"""
import json
import logging
from openai import AsyncOpenAI
from config import settings

logger = logging.getLogger(__name__)
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

SYSTEM_PROMPT = """
Você é o assistente de RH da empresa, responsável por agendar a consulta admissional dos candidatos.
Seja cordial, objetivo e profissional. Fale sempre em português.

Seu objetivo é confirmar com o candidato:
1. A data disponível para a consulta admissional (ofereça as opções disponíveis)
2. O horário preferido
3. O local (informe o endereço padrão)
4. Confirmação final do candidato

Quando o candidato confirmar o agendamento, inclua no final da sua resposta um bloco JSON
no seguinte formato (exatamente assim, sem markdown):

SCHEDULING_DATA:{"confirmado": true, "data": "DD/MM/AAAA", "horario": "HH:MM", "local": "endereço"}

Se o candidato ainda não confirmou, não inclua o bloco JSON.
Se o candidato quiser cancelar ou reagendar, informe que ele deve entrar em contato com o RH.
"""


async def get_ai_response(
    history: list[dict],
    candidato_context: str = "",
) -> tuple[str, dict | None]:
    """
    Chama o GPT-4o com o histórico de mensagens.
    Retorna (texto_resposta, dados_agendamento_ou_None).
    """
    system = SYSTEM_PROMPT
    if candidato_context:
        system += f"\n\nContexto do candidato:{candidato_context}"

    messages = [{"role": "system", "content": system}] + history

    try:
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            temperature=0.4,
            max_tokens=800,
        )
        full_text = response.choices[0].message.content or ""
    except Exception as e:
        logger.error(f"Erro na chamada OpenAI: {e}", exc_info=True)
        return (
            "Desculpe, estou com uma instabilidade momentânea. Tente novamente em alguns instantes.",
            None,
        )

    # Extrai bloco de agendamento se presente
    scheduling_data = None
    marker = "SCHEDULING_DATA:"
    if marker in full_text:
        parts = full_text.split(marker, 1)
        clean_text = parts[0].strip()
        try:
            scheduling_data = json.loads(parts[1].strip())
        except json.JSONDecodeError:
            logger.warning("Falha ao parsear SCHEDULING_DATA")
            clean_text = full_text
    else:
        clean_text = full_text

    return clean_text, scheduling_data

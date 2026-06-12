"""
Gerencia o estado da conversa com cada usuário.
Fluxo:
  1. Usuário envia mensagem
  2. Carrega histórico do SQLite
  3. Envia para OpenAI com system prompt
  4. Salva resposta no histórico
  5. Envia resposta via Evolution API
  6. Se bot detectar agendamento confirmado, registra no Sheets
"""
import logging
from db.sqlite import get_history, save_message
from bot.ai import get_ai_response
from bot.whatsapp import send_message
from sheets.client import get_candidato_by_phone, register_agendamento

logger = logging.getLogger(__name__)


async def handle_incoming_message(phone: str, text: str):
    history = get_history(phone)

    # Primeira mensagem: verifica se candidato está cadastrado
    candidato = None
    if not history:
        candidato = get_candidato_by_phone(phone)
        if not candidato:
            await send_message(
                phone,
                "Olá! Não encontrei seu cadastro no sistema. "
                "Por favor, entre em contato com o RH para verificar seu número registrado.",
            )
            return

    # Adiciona mensagem do usuário ao histórico
    save_message(phone, role="user", content=text)
    history = get_history(phone)

    # Contexto do candidato injetado apenas na primeira mensagem
    candidato_context = ""
    if candidato:
        candidato_context = (
            f"\nCandidato identificado: {candidato.get('nome')}, "
            f"cargo: {candidato.get('cargo')}, "
            f"data prevista de admissão: {candidato.get('data_admissao')}."
        )

    # Chama a IA com o histórico completo
    ai_reply, scheduling_data = await get_ai_response(
        history=history,
        candidato_context=candidato_context,
    )

    # Salva resposta da IA no histórico
    save_message(phone, role="assistant", content=ai_reply)

    # Envia resposta ao usuário
    await send_message(phone, ai_reply)

    # Se a IA detectou agendamento confirmado, registra no Sheets
    if scheduling_data and scheduling_data.get("confirmado"):
        try:
            register_agendamento(phone=phone, data=scheduling_data)
            logger.info(f"Agendamento registrado para {phone}: {scheduling_data}")
        except Exception as e:
            logger.error(f"Erro ao registrar agendamento de {phone}: {e}", exc_info=True)

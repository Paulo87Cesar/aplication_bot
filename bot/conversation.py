"""
Gerencia o estado da conversa com cada usuário.
Fluxo simplificado (sem ERP):
  1. Usuário responde a uma campanha
  2. Carrega histórico do SQLite
  3. Envia para OpenAI
  4. Salva resposta no histórico
  5. Envia resposta via Evolution API
"""
import logging
from db.sqlite import get_history, save_message
from bot.ai import get_ai_response
from bot.whatsapp import send_message

logger = logging.getLogger(__name__)


async def handle_incoming_message(phone: str, text: str):
    history = get_history(phone)

    # Adiciona mensagem do usuário ao histórico
    save_message(phone, role="user", content=text)
    history = get_history(phone)

    # Chama a IA com o histórico (sem contexto de candidato)
    ai_reply, _ = await get_ai_response(
        history=history,
        candidato_context="Nenhum contexto de ERP disponível (Disparo em Lote).",
    )

    # Salva resposta da IA no histórico
    save_message(phone, role="assistant", content=ai_reply)

    # Envia resposta ao usuário
    await send_message(phone, ai_reply)

"""
Envio de mensagens via Evolution API.
"""
import httpx
import logging
from config import settings

logger = logging.getLogger(__name__)


def _get_url() -> str:
    """Monta a URL de envio em tempo de execução (não no import)."""
    return f"{settings.EVOLUTION_API_URL}/message/sendText/{settings.EVOLUTION_INSTANCE}"


def _get_headers() -> dict:
    """Monta os headers em tempo de execução para garantir que .env já foi carregado."""
    return {
        "Content-Type": "application/json",
        "apikey": settings.EVOLUTION_API_KEY,
    }


async def send_message(phone: str, text: str) -> bool:
    """
    Envia mensagem de texto para um número via Evolution API.
    phone: apenas números com DDI (ex: 5511999999999)
    """
    payload = {
        "number": f"{phone}@s.whatsapp.net",
        "text": text,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                _get_url(), json=payload, headers=_get_headers()
            )
            response.raise_for_status()
            logger.info(f"Mensagem enviada para {phone}")
            return True
    except httpx.HTTPStatusError as e:
        logger.error(
            f"Erro HTTP ao enviar para {phone}: "
            f"{e.response.status_code} {e.response.text}"
        )
        return False
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem para {phone}: {e}", exc_info=True)
        return False


async def send_batch(messages: list[dict], interval_seconds: int = 3) -> list[dict]:
    """
    Envia mensagens em lote com intervalo entre cada envio.
    messages: lista de dicts com 'phone' e 'text'
    Retorna lista com status de cada envio: [{"phone": ..., "success": bool}]
    """
    import asyncio

    results = []
    for i, msg in enumerate(messages):
        success = await send_message(msg["phone"], msg["text"])
        results.append({"phone": msg["phone"], "success": success})
        if i < len(messages) - 1:
            await asyncio.sleep(interval_seconds)
    return results

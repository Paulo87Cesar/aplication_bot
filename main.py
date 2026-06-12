"""
Entrypoint do Admissional Bot.
Configura FastAPI, monta webhook, rotas da API do painel e serve o frontend SPA.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from bot.conversation import handle_incoming_message
from scheduler.jobs import start_scheduler
from db.sqlite import init_db
from config import settings
from api.routes import router as api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: inicializa banco, scheduler. Shutdown: encerra graciosamente."""
    logger.info("Iniciando servidor...")

    # Garante que as tabelas SQLite existem (idempotente)
    init_db()
    logger.info("Banco SQLite inicializado.")

    start_scheduler()
    logger.info("Scheduler iniciado.")

    yield

    logger.info("Servidor encerrado.")


app = FastAPI(
    title="Admissional Bot",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["Sistema"])
async def health():
    """Healthcheck — usado pelo Nginx e monitoramento externo."""
    return {"status": "ok"}


@app.post("/webhook/evolution", tags=["Webhook"])
async def evolution_webhook(request: Request):
    """
    Recebe eventos da Evolution API via webhook.
    Filtra apenas mensagens recebidas (messages.upsert) e encaminha para o handler.
    """
    payload = await request.json()
    logger.info(f"Webhook recebido: {payload.get('event')}")

    event = payload.get("event")
    if event != "messages.upsert":
        return JSONResponse({"status": "ignored"})

    data = payload.get("data", {})
    messages = data.get("messages", []) if isinstance(data, dict) else []
    message_data = messages[0] if messages else {}

    # Ignora mensagens enviadas pelo próprio bot
    if message_data.get("key", {}).get("fromMe"):
        return JSONResponse({"status": "ignored"})

    phone = (
        message_data.get("key", {})
        .get("remoteJid", "")
        .replace("@s.whatsapp.net", "")
    )

    message_text = (
        message_data.get("message", {}).get("conversation")
        or message_data.get("message", {}).get("extendedTextMessage", {}).get("text")
        or ""
    ).strip()

    if not phone or not message_text:
        return JSONResponse({"status": "ignored"})

    logger.info(f"Mensagem de {phone}: {message_text[:80]}")

    try:
        await handle_incoming_message(phone=phone, text=message_text)
    except Exception as e:
        logger.error(f"Erro ao processar mensagem de {phone}: {e}", exc_info=True)

    return JSONResponse({"status": "ok"})


# Rotas da API do painel (prefixo /api)
app.include_router(api_router)

# SPA servida pelo FastAPI — deve ser montada POR ÚLTIMO
# para não interceptar as rotas /api e /webhook
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

"""
Rotas da API consumidas pelo painel frontend.
Monta no FastAPI principal via app.include_router().
"""
import secrets
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from config import settings
from sheets.client import (
    get_all_campanhas,
    get_destinatarios_pendentes,
    update_campanha_status,
    update_destinatario_status,
    log_message_sent,
    normalize_phone,
)
from bot.whatsapp import send_message, send_batch

router = APIRouter(prefix="/api")
security = HTTPBearer()

# Token simples em memória (gerado no login, válido pela sessão do processo)
_active_tokens: set[str] = set()


# ── AUTH ─────────────────────────────────────────────────────────────────────

class LoginPayload(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
async def login(payload: LoginPayload):
    if (
        payload.username == settings.PANEL_USER
        and payload.password == settings.PANEL_PASS
    ):
        token = secrets.token_urlsafe(32)
        _active_tokens.add(token)
        return {"token": token}
    raise HTTPException(status_code=401, detail="Credenciais inválidas")


def require_auth(creds: HTTPAuthorizationCredentials = Depends(security)):
    if creds.credentials not in _active_tokens:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")
    return creds.credentials


# ── CAMPANHAS ─────────────────────────────────────────────────────────────────

@router.get("/campanhas")
async def list_campanhas(token=Depends(require_auth)):
    """Lista todas as campanhas com o total de destinatários pendentes."""
    campanhas = get_all_campanhas()
    resultado = []
    for c in campanhas:
        cid = str(c.get("id", ""))
        pendentes = get_destinatarios_pendentes(cid)
        resultado.append({**c, "total_pendentes": len(pendentes)})
    return resultado


@router.post("/campanhas/{campanha_id}/disparar")
async def disparar_campanha(campanha_id: str, token=Depends(require_auth)):
    """
    Dispara manualmente uma campanha pelo id, independente do horário agendado.
    Útil para testes e execuções imediatas.
    """
    from sheets.client import get_all_campanhas, get_sheet
    from config import settings as s

    # Localiza a campanha e seu índice de linha
    sheet = get_sheet(s.SHEET_CAMPANHAS)
    records = sheet.get_all_records()
    campanha = None
    campanha_row = None
    for i, row in enumerate(records, start=2):
        if str(row.get("id", "")).strip() == str(campanha_id).strip():
            campanha = row
            campanha_row = i
            break

    if not campanha:
        raise HTTPException(status_code=404, detail=f"Campanha '{campanha_id}' não encontrada.")

    mensagem_template = campanha.get("mensagem", "")
    nome_campanha = campanha.get("nome", campanha_id)

    destinatarios = get_destinatarios_pendentes(campanha_id)
    if not destinatarios:
        raise HTTPException(status_code=400, detail="Nenhum destinatário pendente nesta campanha.")

    update_campanha_status(campanha_row, "executando")

    total = len(destinatarios)
    enviados = 0
    erros = 0

    for i, dest in enumerate(destinatarios):
        nome_dest = dest.get("nome", "")
        phone = normalize_phone(str(dest.get("telefone", "")))
        dest_row = dest.get("_row")
        texto = mensagem_template.replace("{nome}", nome_dest)

        success = await send_message(phone, texto)
        status_dest = "enviado" if success else "erro"
        update_destinatario_status(dest_row, status_dest)
        log_message_sent(phone, texto, status_dest)

        if success:
            enviados += 1
        else:
            erros += 1

        if i < total - 1:
            await asyncio.sleep(settings.BATCH_SEND_INTERVAL)

    status_final = "concluido" if erros == 0 else ("erro" if erros == total else "concluido_com_erros")
    update_campanha_status(campanha_row, status_final)

    return {
        "campanha": nome_campanha,
        "total": total,
        "enviados": enviados,
        "erros": erros,
        "status": status_final,
    }


# ── DISPARO AVULSO ────────────────────────────────────────────────────────────

class SingleMessage(BaseModel):
    phone: str
    text: str


@router.post("/dispatch/single")
async def dispatch_single(payload: SingleMessage, token=Depends(require_auth)):
    """Envia uma mensagem avulsa para um número específico (formato nacional ou internacional)."""
    phone = normalize_phone(payload.phone)
    success = await send_message(phone, payload.text)
    log_message_sent(phone, payload.text, "enviado" if success else "erro")
    if not success:
        raise HTTPException(status_code=502, detail="Falha ao enviar mensagem")
    return {"ok": True}


# ── LOGS ──────────────────────────────────────────────────────────────────────

@router.get("/logs")
async def list_logs(token=Depends(require_auth)):
    from sheets.client import get_sheet
    from config import settings as s
    sheet = get_sheet(s.SHEET_LOG)
    records = sheet.get_all_records()
    return list(reversed(records))

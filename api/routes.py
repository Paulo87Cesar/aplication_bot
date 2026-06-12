"""
Rotas da API consumidas pelo painel frontend.
Monta no FastAPI principal via app.include_router().
"""
import secrets
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from datetime import datetime, timedelta
from config import settings
from sheets.client import (
    get_sheet,
    get_candidatos_para_notificar,
    log_message_sent,
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


# ── DASHBOARD ─────────────────────────────────────────────────────────────────

@router.get("/dashboard")
async def dashboard(token=Depends(require_auth)):
    sheet = get_sheet(settings.SHEET_CANDIDATOS)
    records = sheet.get_all_records()

    today = datetime.today().date()
    limit = today + timedelta(days=7)

    metrics = {"total": len(records), "pendentes": 0, "agendados": 0, "realizados": 0}
    proximos = []

    for r in records:
        s = str(r.get("status", "")).lower()
        if s == "pendente":   metrics["pendentes"] += 1
        if s == "agendado":   metrics["agendados"] += 1
        if s == "realizado":  metrics["realizados"] += 1

        data_str = r.get("data_admissao", "")
        try:
            data = datetime.strptime(data_str, "%d/%m/%Y").date()
            if today <= data <= limit:
                proximos.append(r)
        except ValueError:
            pass

    proximos.sort(key=lambda x: x.get("data_admissao", ""))
    return {"metrics": metrics, "proximos": proximos}


# ── CANDIDATOS ────────────────────────────────────────────────────────────────

@router.get("/candidatos")
async def list_candidatos(token=Depends(require_auth)):
    sheet = get_sheet(settings.SHEET_CANDIDATOS)
    return sheet.get_all_records()


class CandidatoPayload(BaseModel):
    nome: str
    cpf: str
    telefone: str
    cargo: str
    gestor: str
    data_admissao: str
    status: str


@router.post("/candidatos", status_code=201)
async def create_candidato(payload: CandidatoPayload, token=Depends(require_auth)):
    sheet = get_sheet(settings.SHEET_CANDIDATOS)
    row = [
        payload.nome, payload.cpf, payload.telefone, payload.cargo,
        payload.gestor, payload.data_admissao, payload.status,
    ]
    sheet.append_row(row)
    return {"ok": True}


@router.put("/candidatos/{row_index}")
async def update_candidato(row_index: int, payload: CandidatoPayload, token=Depends(require_auth)):
    sheet = get_sheet(settings.SHEET_CANDIDATOS)
    # Linha real no Sheets = índice (base 0) + 2 (cabeçalho ocupa linha 1)
    sheet_row = row_index + 2
    row = [
        payload.nome, payload.cpf, payload.telefone, payload.cargo,
        payload.gestor, payload.data_admissao, payload.status,
    ]
    sheet.update(f"A{sheet_row}:G{sheet_row}", [row])
    return {"ok": True}


@router.delete("/candidatos/{row_index}")
async def delete_candidato(row_index: int, token=Depends(require_auth)):
    sheet = get_sheet(settings.SHEET_CANDIDATOS)
    sheet.delete_rows(row_index + 2)
    return {"ok": True}


# ── AGENDAMENTOS ──────────────────────────────────────────────────────────────

@router.get("/agendamentos")
async def list_agendamentos(token=Depends(require_auth)):
    sheet = get_sheet(settings.SHEET_AGENDAMENTOS)
    return sheet.get_all_records()


# ── DISPAROS ──────────────────────────────────────────────────────────────────

@router.get("/dispatch/preview")
async def dispatch_preview(token=Depends(require_auth)):
    candidatos = get_candidatos_para_notificar(days_ahead=3)
    return {"count": len(candidatos)}


@router.post("/dispatch/run")
async def dispatch_run(token=Depends(require_auth)):
    candidatos = get_candidatos_para_notificar(days_ahead=3)
    if not candidatos:
        return {"enviados": 0, "erros": 0}

    messages = []
    for c in candidatos:
        phone = str(c.get("telefone", "")).replace("+", "").replace(" ", "").replace("-", "")
        if not phone:
            continue
        texto = (
            f"Olá, {c.get('nome', 'Candidato')}! 👋\n\n"
            f"Sua admissão para o cargo *{c.get('cargo', '')}* está prevista para *{c.get('data_admissao', '')}*.\n\n"
            "Responda esta mensagem para agendar sua consulta admissional.\n\nEquipe de RH"
        )
        messages.append({"phone": phone, "text": texto})

    results = await send_batch(messages, interval_seconds=settings.BATCH_SEND_INTERVAL)
    enviados = sum(1 for r in results if r["success"])
    erros = len(results) - enviados

    for r in results:
        status_str = "enviado" if r["success"] else "erro"
        msg = next((m["text"] for m in messages if m["phone"] == r["phone"]), "")
        log_message_sent(r["phone"], msg, status_str)

    return {"enviados": enviados, "erros": erros}


class SingleMessage(BaseModel):
    phone: str
    text: str


@router.post("/dispatch/single")
async def dispatch_single(payload: SingleMessage, token=Depends(require_auth)):
    success = await send_message(payload.phone, payload.text)
    log_message_sent(payload.phone, payload.text, "enviado" if success else "erro")
    if not success:
        raise HTTPException(status_code=502, detail="Falha ao enviar mensagem")
    return {"ok": True}


# ── LOGS ──────────────────────────────────────────────────────────────────────

@router.get("/logs")
async def list_logs(token=Depends(require_auth)):
    sheet = get_sheet(settings.SHEET_LOG)
    records = sheet.get_all_records()
    return list(reversed(records))

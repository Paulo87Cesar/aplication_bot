"""
Rotas da API REST consumidas pelo frontend SPA.
Prefixo /api para separar do webhook.
"""
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from datetime import datetime
import secrets
import logging
from sheets.client import (
    get_sheet,
    register_agendamento,
    get_candidatos_para_notificar,
)
from bot.whatsapp import send_message
from db.sqlite import get_history, clear_history
from scheduler.jobs import sync_erp, dispatch_notifications
from config import settings

router = APIRouter(prefix="/api")
security = HTTPBasic()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Auth básica
# ---------------------------------------------------------------------------

ADMIN_USER = "rh"
ADMIN_PASS = settings.ADMIN_PASSWORD  # definida no .env


def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    ok_user = secrets.compare_digest(credentials.username, ADMIN_USER)
    ok_pass = secrets.compare_digest(credentials.password, ADMIN_PASS)
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# ---------------------------------------------------------------------------
# Dashboard — métricas resumidas
# ---------------------------------------------------------------------------

@router.get("/dashboard")
def get_dashboard(user=Depends(verify_credentials)):
    try:
        candidatos = get_sheet(settings.SHEET_CANDIDATOS).get_all_records()
        agendamentos = get_sheet(settings.SHEET_AGENDAMENTOS).get_all_records()
        logs = get_sheet(settings.SHEET_LOG).get_all_records()

        total_candidatos = len(candidatos)
        agendados = sum(1 for a in agendamentos if str(a.get("status", "")).lower() == "confirmado")
        pendentes = sum(1 for c in candidatos if str(c.get("status", "")).lower() == "pendente")
        mensagens_enviadas = len(logs)

        return {
            "total_candidatos": total_candidatos,
            "agendados": agendados,
            "pendentes": pendentes,
            "mensagens_enviadas": mensagens_enviadas,
        }
    except Exception as e:
        logger.error(f"Erro no dashboard: {e}", exc_info=True)
        raise HTTPException(500, "Erro ao carregar dashboard")


# ---------------------------------------------------------------------------
# Candidatos
# ---------------------------------------------------------------------------

@router.get("/candidatos")
def list_candidatos(user=Depends(verify_credentials)):
    try:
        records = get_sheet(settings.SHEET_CANDIDATOS).get_all_records()
        return records
    except Exception as e:
        raise HTTPException(500, str(e))


class CandidatoCreate(BaseModel):
    nome: str
    cpf: str
    telefone: str
    cargo: str
    gestor: str
    data_admissao: str
    status: str = "pendente"


@router.post("/candidatos")
def create_candidato(body: CandidatoCreate, user=Depends(verify_credentials)):
    try:
        sheet = get_sheet(settings.SHEET_CANDIDATOS)
        sheet.append_row([
            body.nome, body.cpf, body.telefone,
            body.cargo, body.gestor, body.data_admissao, body.status,
        ])
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/candidatos/{cpf}")
def delete_candidato(cpf: str, user=Depends(verify_credentials)):
    try:
        sheet = get_sheet(settings.SHEET_CANDIDATOS)
        records = sheet.get_all_records()
        for i, row in enumerate(records, start=2):
            if str(row.get("cpf", "")).replace(".", "").replace("-", "") == cpf.replace(".", "").replace("-", ""):
                sheet.delete_rows(i)
                return {"ok": True}
        raise HTTPException(404, "Candidato não encontrado")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# ---------------------------------------------------------------------------
# Agendamentos
# ---------------------------------------------------------------------------

@router.get("/agendamentos")
def list_agendamentos(user=Depends(verify_credentials)):
    try:
        return get_sheet(settings.SHEET_AGENDAMENTOS).get_all_records()
    except Exception as e:
        raise HTTPException(500, str(e))


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------

@router.get("/logs")
def list_logs(limit: int = 100, user=Depends(verify_credentials)):
    try:
        records = get_sheet(settings.SHEET_LOG).get_all_records()
        return records[-limit:]
    except Exception as e:
        raise HTTPException(500, str(e))


# ---------------------------------------------------------------------------
# Disparo manual
# ---------------------------------------------------------------------------

class ManualDispatch(BaseModel):
    phone: str
    message: str


@router.post("/dispatch/manual")
async def manual_dispatch(body: ManualDispatch, user=Depends(verify_credentials)):
    success = await send_message(body.phone, body.message)
    if not success:
        raise HTTPException(500, "Falha ao enviar mensagem")
    return {"ok": True}


@router.post("/dispatch/batch")
def trigger_batch(user=Depends(verify_credentials)):
    """Dispara o job de notificação em lote imediatamente."""
    try:
        dispatch_notifications()
        return {"ok": True, "message": "Disparo em lote iniciado"}
    except Exception as e:
        raise HTTPException(500, str(e))


# ---------------------------------------------------------------------------
# Sync ERP manual
# ---------------------------------------------------------------------------

@router.post("/sync/erp")
def trigger_sync(user=Depends(verify_credentials)):
    try:
        sync_erp()
        return {"ok": True, "message": "Sincronização iniciada"}
    except Exception as e:
        raise HTTPException(500, str(e))


# ---------------------------------------------------------------------------
# Histórico de conversa
# ---------------------------------------------------------------------------

@router.get("/conversa/{phone}")
def get_conversa(phone: str, user=Depends(verify_credentials)):
    return get_history(phone)


@router.delete("/conversa/{phone}")
def reset_conversa(phone: str, user=Depends(verify_credentials)):
    clear_history(phone)
    return {"ok": True}

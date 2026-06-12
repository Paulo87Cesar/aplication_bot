"""
Integração com Google Sheets via gspread.
Todas as operações de leitura e escrita passam por aqui.
"""
import gspread
import logging
from datetime import datetime
from functools import lru_cache
from google.oauth2.service_account import Credentials
from config import settings

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


@lru_cache(maxsize=1)
def get_client() -> gspread.Client:
    creds = Credentials.from_service_account_file(
        settings.GOOGLE_CREDENTIALS_FILE, scopes=SCOPES
    )
    return gspread.authorize(creds)


def get_sheet(tab_name: str) -> gspread.Worksheet:
    client = get_client()
    spreadsheet = client.open_by_key(settings.SPREADSHEET_ID)
    return spreadsheet.worksheet(tab_name)


# ---------------------------------------------------------------------------
# Candidatos
# ---------------------------------------------------------------------------

def get_candidato_by_phone(phone: str) -> dict | None:
    """
    Busca candidato pelo telefone na aba Candidatos.
    Colunas esperadas: nome, cpf, telefone, cargo, gestor, data_admissao, status
    """
    try:
        sheet = get_sheet(settings.SHEET_CANDIDATOS)
        records = sheet.get_all_records()
        phone_clean = phone.replace("+", "").replace(" ", "").replace("-", "")
        for row in records:
            row_phone = str(row.get("telefone", "")).replace("+", "").replace(" ", "").replace("-", "")
            if row_phone == phone_clean:
                return row
        return None
    except Exception as e:
        logger.error(f"Erro ao buscar candidato por telefone {phone}: {e}", exc_info=True)
        return None


def get_candidatos_para_notificar(days_ahead: int = 3) -> list[dict]:
    """
    Retorna candidatos com admissão nos próximos N dias e sem agendamento confirmado.
    """
    from datetime import timedelta
    try:
        sheet = get_sheet(settings.SHEET_CANDIDATOS)
        records = sheet.get_all_records()
        today = datetime.today().date()
        limit = today + timedelta(days=days_ahead)
        resultado = []
        for row in records:
            data_str = row.get("data_admissao", "")
            status = str(row.get("status", "")).lower()
            if status in ("agendado", "realizado", "cancelado"):
                continue
            try:
                data = datetime.strptime(data_str, "%d/%m/%Y").date()
                if today <= data <= limit:
                    resultado.append(row)
            except ValueError:
                continue
        return resultado
    except Exception as e:
        logger.error(f"Erro ao buscar candidatos para notificar: {e}", exc_info=True)
        return []


# ---------------------------------------------------------------------------
# Agendamentos
# ---------------------------------------------------------------------------

def register_agendamento(phone: str, data: dict):
    """
    Registra um agendamento confirmado na aba Agendamentos.
    """
    sheet = get_sheet(settings.SHEET_AGENDAMENTOS)
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    row = [
        phone,
        data.get("data", ""),
        data.get("horario", ""),
        data.get("local", ""),
        "confirmado",
        now,
    ]
    sheet.append_row(row)
    logger.info(f"Agendamento gravado no Sheets para {phone}")


# ---------------------------------------------------------------------------
# Log de mensagens enviadas
# ---------------------------------------------------------------------------

def log_message_sent(phone: str, message: str, status: str, api_response: str = ""):
    """
    Registra cada mensagem enviada em lote na aba Log.
    """
    try:
        sheet = get_sheet(settings.SHEET_LOG)
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        sheet.append_row([now, phone, message[:200], status, api_response[:200]])
    except Exception as e:
        logger.error(f"Erro ao gravar log no Sheets: {e}", exc_info=True)

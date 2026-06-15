"""
Integração com Google Sheets via gspread.
Todas as operações de leitura e escrita passam por aqui.

Estrutura esperada na planilha:
  Aba Campanhas:    id | nome | mensagem | disparo_em | status
  Aba Destinatarios: campanha_id | nome | telefone | status
  Aba Log:          criado_em | telefone | mensagem | status | resposta_api
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
# Normalização de telefone
# Aceita formato nacional (11999999999) e adiciona DDI 55 automaticamente.
# Remove qualquer caractere não numérico antes de normalizar.
# ---------------------------------------------------------------------------

def normalize_phone(raw: str) -> str:
    """Garante que o telefone esteja no formato internacional sem '+'."""
    digits = "".join(filter(str.isdigit, str(raw)))
    if digits.startswith("55") and len(digits) >= 12:
        return digits
    return "55" + digits


# ---------------------------------------------------------------------------
# Campanhas
# ---------------------------------------------------------------------------

def _normalize_row(row: dict) -> dict:
    """Converte todas as chaves do dicionário para minúsculo."""
    return {str(k).strip().lower(): v for k, v in row.items()}


def get_campanhas_agendadas() -> list[dict]:
    """
    Retorna campanhas cujo status é 'agendado' e disparo_em <= agora.
    O campo disparo_em deve estar no formato DD/MM/AAAA HH:MM.
    """
    try:
        from zoneinfo import ZoneInfo
        sheet = get_sheet(settings.SHEET_CAMPANHAS)
        records = sheet.get_all_records()
        now = datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
        resultado = []
        for i, raw_row in enumerate(records, start=2):  # linha 2 = primeira linha de dados
            row = _normalize_row(raw_row)
            status_camp = str(row.get("status", "")).lower()
            if status_camp not in ("agendado", "pendente"):
                continue
            disparo_str = str(row.get("disparo_em", "")).strip()
            try:
                disparo_dt = datetime.strptime(disparo_str, "%d/%m/%Y %H:%M")
            except ValueError:
                try:
                    disparo_dt = datetime.strptime(disparo_str, "%d/%m/%Y %H:%M:%S")
                except ValueError:
                    try:
                        disparo_dt = datetime.strptime(disparo_str, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        try:
                            disparo_dt = datetime.strptime(disparo_str, "%Y-%m-%d %H:%M")
                        except ValueError:
                            logger.warning(f"Campanha '{row.get('id')}' tem disparo_em inválido: '{disparo_str}'")
                            continue
            if disparo_dt <= now:
                resultado.append({**row, "_row": i})
        return resultado
    except Exception as e:
        logger.error(f"Erro ao buscar campanhas agendadas: {e}", exc_info=True)
        return []


def get_destinatarios_pendentes(campanha_id: str) -> list[dict]:
    """
    Retorna destinatários com status 'pendente' para uma campanha específica.
    """
    try:
        sheet = get_sheet(settings.SHEET_DESTINATARIOS)
        records = sheet.get_all_records()
        resultado = []
        for i, raw_row in enumerate(records, start=2):
            row = _normalize_row(raw_row)
            camp_id = row.get("campanha_id") or row.get("id_campanha", "")
            if str(camp_id).strip() != str(campanha_id).strip():
                continue
            if str(row.get("status", "")).lower() != "pendente":
                continue
            resultado.append({**row, "_row": i})
        return resultado
    except Exception as e:
        logger.error(f"Erro ao buscar destinatários da campanha {campanha_id}: {e}", exc_info=True)
        return []


def update_campanha_status(row_index: int, status: str):
    """Atualiza o campo 'status' de uma campanha pelo índice de linha na planilha."""
    try:
        sheet = get_sheet(settings.SHEET_CAMPANHAS)
        headers = [h.strip().lower() for h in sheet.row_values(1)]
        col = headers.index("status") + 1  # gspread é 1-indexed
        sheet.update_cell(row_index, col, status)
    except Exception as e:
        logger.error(f"Erro ao atualizar status da campanha (linha {row_index}): {e}", exc_info=True)


def update_destinatario_status(row_index: int, status: str):
    """Atualiza o campo 'status' de um destinatário pelo índice de linha na planilha."""
    try:
        sheet = get_sheet(settings.SHEET_DESTINATARIOS)
        headers = [h.strip().lower() for h in sheet.row_values(1)]
        col = headers.index("status") + 1
        sheet.update_cell(row_index, col, status)
    except Exception as e:
        logger.error(f"Erro ao atualizar status do destinatário (linha {row_index}): {e}", exc_info=True)


def get_all_campanhas() -> list[dict]:
    """Retorna todas as campanhas para exibição no painel."""
    try:
        sheet = get_sheet(settings.SHEET_CAMPANHAS)
        records = sheet.get_all_records()
        return [_normalize_row(r) for r in records]
    except Exception as e:
        logger.error(f"Erro ao listar campanhas: {e}", exc_info=True)
        return []


# ---------------------------------------------------------------------------
# Log de mensagens enviadas
# ---------------------------------------------------------------------------

def log_message_sent(phone: str, message: str, status: str, api_response: str = ""):
    """
    Registra cada mensagem enviada na aba Log.
    """
    try:
        sheet = get_sheet(settings.SHEET_LOG)
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        sheet.append_row([now, phone, message[:200], status, api_response[:200]])
    except Exception as e:
        logger.error(f"Erro ao gravar log no Sheets: {e}", exc_info=True)

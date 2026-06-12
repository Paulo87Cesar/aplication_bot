"""
Jobs agendados:
  - sync_erp: sincroniza candidatos do Silogica para o Sheets (diário às 06h)
  - dispatch_notifications: envia mensagens para candidatos com admissão próxima (diário às 08h)
"""
import asyncio
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from config import settings

logger = logging.getLogger(__name__)


def start_scheduler():
    scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")

    sync_h, sync_m = settings.SCHEDULER_SYNC_ERP_TIME.split(":")
    scheduler.add_job(
        sync_erp,
        trigger=CronTrigger(hour=int(sync_h), minute=int(sync_m)),
        id="sync_erp",
        replace_existing=True,
    )

    dispatch_h, dispatch_m = settings.SCHEDULER_DISPATCH_TIME.split(":")
    scheduler.add_job(
        dispatch_notifications,
        trigger=CronTrigger(hour=int(dispatch_h), minute=int(dispatch_m)),
        id="dispatch_notifications",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        f"Scheduler ativo: sync_erp às {settings.SCHEDULER_SYNC_ERP_TIME}, "
        f"dispatch às {settings.SCHEDULER_DISPATCH_TIME}"
    )


def sync_erp():
    """
    Conecta ao banco do Silogica, executa query de candidatos
    e atualiza a aba Candidatos no Sheets.

    ATENÇÃO: preencha a query e a string de conexão com os dados do seu ambiente.
    """
    import pyodbc  # SQL Server — troque por psycopg2 se for PostgreSQL
    from sheets.client import get_sheet
    from config import settings

    logger.info("Iniciando sincronização com o Silogica...")

    QUERY = """
        SELECT
            nome,
            cpf,
            telefone_celular AS telefone,
            cargo,
            gestor,
            data_admissao,
            'pendente' AS status
        FROM candidatos
        WHERE data_admissao >= CAST(GETDATE() AS DATE)
          AND status_processo NOT IN ('cancelado', 'desistencia')
        ORDER BY data_admissao
    """

    # Conexão com o banco — edite a connection string
    conn_str = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=SEU_SERVIDOR;"
        "DATABASE=SEU_BANCO;"
        "UID=SEU_USUARIO;"
        "PWD=SUA_SENHA;"
    )

    try:
        with pyodbc.connect(conn_str, timeout=10) as db_conn:
            cursor = db_conn.cursor()
            cursor.execute(QUERY)
            columns = [col[0] for col in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        if not rows:
            logger.info("Nenhum candidato novo encontrado no Silogica.")
            return

        sheet = get_sheet(settings.SHEET_CANDIDATOS)

        # Limpa e reescreve a aba (mantenha o cabeçalho)
        sheet.clear()
        header = list(rows[0].keys())
        sheet.append_row(header)
        for row in rows:
            sheet.append_row([str(v) if v is not None else "" for v in row.values()])

        logger.info(f"Sync concluído: {len(rows)} candidatos gravados no Sheets.")

    except Exception as e:
        logger.error(f"Erro na sincronização com o Silogica: {e}", exc_info=True)


def dispatch_notifications():
    """
    Lê candidatos com admissão nos próximos 3 dias e envia mensagem via WhatsApp.
    """
    import asyncio
    from sheets.client import get_candidatos_para_notificar, log_message_sent
    from bot.whatsapp import send_batch

    logger.info("Iniciando disparo de notificações admissionais...")

    candidatos = get_candidatos_para_notificar(days_ahead=3)
    if not candidatos:
        logger.info("Nenhum candidato para notificar hoje.")
        return

    messages = []
    for c in candidatos:
        nome = c.get("nome", "Candidato")
        data = c.get("data_admissao", "")
        cargo = c.get("cargo", "")
        phone = str(c.get("telefone", "")).replace("+", "").replace(" ", "").replace("-", "")

        if not phone:
            continue

        texto = (
            f"Olá, {nome}! 👋\n\n"
            f"Sua admissão para o cargo *{cargo}* está prevista para *{data}*.\n\n"
            f"Precisamos agendar sua consulta admissional. "
            f"Responda esta mensagem para iniciarmos o agendamento.\n\n"
            f"Equipe de RH"
        )
        messages.append({"phone": phone, "text": texto})

    if not messages:
        return

    # Roda o envio assíncrono dentro do contexto síncrono do scheduler
    loop = asyncio.new_event_loop()
    try:
        results = loop.run_until_complete(
            send_batch(messages, interval_seconds=settings.BATCH_SEND_INTERVAL)
        )
    finally:
        loop.close()

    for r in results:
        status = "enviado" if r["success"] else "erro"
        msg = next((m["text"] for m in messages if m["phone"] == r["phone"]), "")
        log_message_sent(r["phone"], msg, status)

    enviados = sum(1 for r in results if r["success"])
    logger.info(f"Disparo concluído: {enviados}/{len(results)} mensagens enviadas.")

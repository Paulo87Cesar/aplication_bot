"""
Job único que roda a cada 5 minutos e verifica se existe alguma
campanha agendada com disparo_em <= agora na aba Campanhas do Google Sheets.

Fluxo:
  1. Lê campanhas com status='agendado' e disparo_em no passado
  2. Marca a campanha como 'executando'
  3. Para cada destinatário pendente dessa campanha:
       a. Normaliza o telefone (aceita formato nacional)
       b. Substitui {nome} na mensagem
       c. Envia via Evolution API
       d. Aguarda BATCH_SEND_INTERVAL segundos (padrão 20s)
       e. Atualiza status do destinatário → 'enviado' ou 'erro'
  4. Atualiza status da campanha → 'concluido' ou 'erro'
"""
import asyncio
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from config import settings

logger = logging.getLogger(__name__)


def start_scheduler():
    scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")

    scheduler.add_job(
        check_and_dispatch_campaigns,
        trigger=IntervalTrigger(minutes=5),
        id="check_campaigns",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler ativo: verificando campanhas a cada 5 minutos.")


def check_and_dispatch_campaigns():
    """
    Verifica se existem campanhas prontas para disparo e executa o envio.
    Roda a cada 5 minutos pelo APScheduler.
    """
    from sheets.client import (
        get_campanhas_agendadas,
        get_destinatarios_pendentes,
        update_campanha_status,
        update_destinatario_status,
        log_message_sent,
        normalize_phone,
    )
    from bot.whatsapp import send_message

    logger.info("Verificando campanhas agendadas...")
    campanhas = get_campanhas_agendadas()

    if not campanhas:
        logger.info("Nenhuma campanha para disparar agora.")
        return

    for campanha in campanhas:
        campanha_id = campanha.get("id")
        campanha_row = campanha.get("_row")
        nome_campanha = campanha.get("nome", campanha_id)
        mensagem_template = campanha.get("mensagem", "")

        logger.info(f"Iniciando disparo da campanha '{nome_campanha}' (id={campanha_id})")
        update_campanha_status(campanha_row, "executando")

        destinatarios = get_destinatarios_pendentes(campanha_id)
        if not destinatarios:
            logger.warning(f"Campanha '{nome_campanha}' sem destinatários pendentes.")
            update_campanha_status(campanha_row, "concluido")
            continue

        total = len(destinatarios)
        erros = 0

        loop = asyncio.new_event_loop()
        try:
            for i, dest in enumerate(destinatarios):
                nome_dest = dest.get("nome", "")
                phone_raw = str(dest.get("telefone", ""))
                dest_row = dest.get("_row")

                phone = normalize_phone(phone_raw)
                texto = mensagem_template.replace("{nome}", nome_dest)

                success = loop.run_until_complete(send_message(phone, texto))

                status_dest = "enviado" if success else "erro"
                update_destinatario_status(dest_row, status_dest)
                log_message_sent(phone, texto, status_dest)

                if not success:
                    erros += 1
                    logger.warning(f"Falha ao enviar para {phone} (campanha {campanha_id})")
                else:
                    logger.info(f"  [{i+1}/{total}] Enviado para {phone} ({nome_dest})")

                # Aguarda o intervalo configurado entre cada envio (anti-ban)
                if i < total - 1:
                    loop.run_until_complete(asyncio.sleep(settings.BATCH_SEND_INTERVAL))

        finally:
            loop.close()

        status_final = "concluido" if erros == 0 else ("erro" if erros == total else "concluido_com_erros")
        update_campanha_status(campanha_row, status_final)
        logger.info(
            f"Campanha '{nome_campanha}' finalizada: "
            f"{total - erros}/{total} enviados, {erros} erros. Status: {status_final}"
        )

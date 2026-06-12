"""
Histórico de conversas em SQLite local.
Cada linha representa uma mensagem (role: user ou assistant).
"""
import sqlite3
import logging
from datetime import datetime
from config import settings

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.SQLITE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Cria as tabelas se não existirem. Chamar na inicialização."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                phone     TEXT NOT NULL,
                role      TEXT NOT NULL,
                content   TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_phone ON conversations(phone)")
        conn.commit()
    logger.info("Banco SQLite inicializado.")


def save_message(phone: str, role: str, content: str):
    now = datetime.now().isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO conversations (phone, role, content, created_at) VALUES (?, ?, ?, ?)",
            (phone, role, content, now),
        )
        conn.commit()


def get_history(phone: str, limit: int = 20) -> list[dict]:
    """
    Retorna as últimas N mensagens da conversa no formato esperado pela OpenAI.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT role, content FROM conversations
            WHERE phone = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (phone, limit),
        ).fetchall()
    # Reverte para ordem cronológica
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def clear_history(phone: str):
    """Remove todo o histórico de um número (ex: após agendamento concluído)."""
    with get_connection() as conn:
        conn.execute("DELETE FROM conversations WHERE phone = ?", (phone,))
        conn.commit()

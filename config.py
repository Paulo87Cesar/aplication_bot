from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Evolution API
    EVOLUTION_API_URL: str = "http://localhost:8080"
    EVOLUTION_API_KEY: str = ""
    EVOLUTION_INSTANCE: str = "admissional"

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"

    # Google Sheets
    GOOGLE_CREDENTIALS_FILE: str = "credentials.json"
    SPREADSHEET_ID: str = ""

    # Nomes das abas no Sheets
    SHEET_CAMPANHAS: str = "Campanhas"
    SHEET_DESTINATARIOS: str = "Destinatarios"
    SHEET_AGENDAMENTOS: str = "Agendamentos"
    SHEET_LOG: str = "Log"

    # Intervalo entre mensagens em lote (segundos)
    # 20s é o mínimo recomendado para evitar bloqueio da Meta
    BATCH_SEND_INTERVAL: int = 20

    # SQLite
    SQLITE_PATH: str = "db/conversations.db"

    # Painel web (login simples via token em memória)
    PANEL_USER: str = "admin"
    PANEL_PASS: str = "troque-esta-senha"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

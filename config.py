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
    SHEET_CANDIDATOS: str = "Candidatos"
    SHEET_AGENDAMENTOS: str = "Agendamentos"
    SHEET_LOG: str = "Log"
    SHEET_CONFIG: str = "Configuracoes"

    # Scheduler — horários (formato HH:MM, fuso America/Sao_Paulo)
    SCHEDULER_SYNC_ERP_TIME: str = "06:00"
    SCHEDULER_DISPATCH_TIME: str = "08:00"

    # Intervalo entre mensagens em lote (segundos)
    BATCH_SEND_INTERVAL: int = 3

    # SQLite
    SQLITE_PATH: str = "db/conversations.db"

    # Painel web (login simples via token em memória)
    PANEL_USER: str = "admin"
    PANEL_PASS: str = "troque-esta-senha"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

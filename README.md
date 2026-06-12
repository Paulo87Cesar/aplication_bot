# Admissional Bot

Bot de WhatsApp para agendamento de consultas admissionais.
Stack: Python + FastAPI + Evolution API + OpenAI GPT-4o + Google Sheets + SQLite.

## Estrutura

```
admissional-bot/
├── main.py                  # Servidor FastAPI e webhook
├── config.py                # Configurações centralizadas via .env
├── requirements.txt
├── .env.example             # Copie para .env e preencha
├── credentials.json         # Credencial da Service Account Google (não commitar)
│
├── bot/
│   ├── conversation.py      # Orquestra recebimento e resposta
│   ├── ai.py                # Integração OpenAI GPT-4o
│   └── whatsapp.py          # Envio via Evolution API
│
├── sheets/
│   └── client.py            # Leitura e escrita no Google Sheets
│
├── scheduler/
│   └── jobs.py              # Sync do ERP e disparo de notificações
│
├── db/
│   └── sqlite.py            # Histórico de conversas (SQLite local)
│
├── nginx/
│   └── admissional.conf     # Config do Nginx como proxy reverso
│
└── scripts/
    ├── setup_vps.sh         # Setup inicial do servidor Ubuntu
    └── admissional-bot.service  # Serviço systemd
```

## Setup passo a passo

### 1. VPS
```bash
sudo bash scripts/setup_vps.sh
```

### 2. Projeto
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edite o .env com suas credenciais
```

### 3. Banco SQLite
```bash
python3 -c "from db.sqlite import init_db; init_db()"
```

### 4. Nginx
```bash
sudo cp nginx/admissional.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/admissional.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 5. Serviço systemd
```bash
sudo cp scripts/admissional-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable admissional-bot
sudo systemctl start admissional-bot
sudo systemctl status admissional-bot
```

### 6. Evolution API
Instale a Evolution API no mesmo VPS seguindo:
https://doc.evolution-api.com/v2/pt/get-started/introduction

Após instalar, crie uma instância com o nome definido em EVOLUTION_INSTANCE
e configure o webhook apontando para:
`http://SEU_DOMINIO/webhook/evolution`

### 7. Google Sheets
1. Crie uma Service Account no Google Cloud Console
2. Ative a API do Google Sheets e do Google Drive
3. Baixe o JSON da credencial e salve como `credentials.json` na raiz
4. Compartilhe a planilha com o e-mail da Service Account (editor)

### Abas necessárias na planilha
| Aba | Colunas obrigatórias |
|---|---|
| Candidatos | nome, cpf, telefone, cargo, gestor, data_admissao, status |
| Agendamentos | telefone, data, horario, local, status, criado_em |
| Log | criado_em, telefone, mensagem, status, resposta_api |
| Configuracoes | (livre para variáveis operacionais do RH) |

## Logs
```bash
sudo journalctl -u admissional-bot -f
```

## Testar webhook localmente
```bash
uvicorn main:app --reload --port 8000
# Em outro terminal:
curl -X POST http://localhost:8000/webhook/evolution \
  -H "Content-Type: application/json" \
  -d '{"event":"messages.upsert","data":{"messages":[{"key":{"fromMe":false,"remoteJid":"5511999999999@s.whatsapp.net"},"message":{"conversation":"Olá"}}]}}'
```

## Painel frontend

A SPA é servida pelo próprio FastAPI via `StaticFiles`. Ao acessar `http://SEU_DOMINIO` o painel de login aparece.

**Credenciais** definidas no `.env`:
```
PANEL_USER=admin
PANEL_PASS=troque-esta-senha
```

### Páginas disponíveis
| Página | Função |
|---|---|
| Dashboard | Métricas gerais + admissões dos próximos 7 dias |
| Candidatos | CRUD completo, busca e filtro por status |
| Agendamentos | Visualização de todos os agendamentos confirmados pelo bot |
| Disparos | Envio em lote automático + envio manual para número específico |
| Logs | Histórico de todas as mensagens enviadas |

### Estrutura adicionada
```
frontend/
├── index.html          # SPA completa (sidebar + todas as páginas)
└── assets/
    ├── style.css       # Design system completo, dark mode incluso
    └── app.js          # Toda a lógica: auth, navegação, API calls, tabelas

api/
├── __init__.py
└── routes.py           # Endpoints REST consumidos pelo painel
```
# aplication_bot

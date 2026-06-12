#!/bin/bash
# setup_vps.sh — Executar UMA VEZ no VPS como root (ou com sudo)
# Testado em Ubuntu 22.04 LTS
# Uso: sudo bash scripts/setup_vps.sh

set -e

echo "==> [1/5] Atualizando pacotes do sistema..."
apt-get update && apt-get upgrade -y

echo "==> [2/5] Instalando dependências base..."
apt-get install -y --no-install-recommends \
    curl \
    git \
    nginx \
    certbot \
    python3-certbot-nginx \
    ufw

echo "==> [3/5] Instalando Docker Engine..."
# Remove versões antigas se existirem
apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

# Adiciona repositório oficial do Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" \
  | tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Permite rodar docker sem sudo (para o usuário ubuntu)
usermod -aG docker ubuntu

echo "==> [4/5] Configurando firewall (UFW)..."
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

echo "==> [5/5] Criando diretório do projeto..."
mkdir -p /home/ubuntu/admissional-bot
chown ubuntu:ubuntu /home/ubuntu/admissional-bot

echo ""
echo "============================================================"
echo "  Setup concluído! Próximos passos:"
echo "============================================================"
echo ""
echo "  1. Envie o projeto para o VPS:"
echo "     scp -r . ubuntu@SEU_IP:/home/ubuntu/admissional-bot/"
echo "     (ou: git clone SEU_REPO /home/ubuntu/admissional-bot)"
echo ""
echo "  2. Entre no diretório:"
echo "     cd /home/ubuntu/admissional-bot"
echo ""
echo "  3. Crie o .env com suas credenciais:"
echo "     cp .env.example .env && nano .env"
echo ""
echo "  4. Coloque o credentials.json (Google Sheets) na raiz"
echo ""
echo "  5. Configure o Nginx:"
echo "     nano nginx/admissional.conf  # altere SEU_DOMINIO_OU_IP"
echo "     sudo cp nginx/admissional.conf /etc/nginx/sites-available/"
echo "     sudo ln -sf /etc/nginx/sites-available/admissional.conf /etc/nginx/sites-enabled/"
echo "     sudo nginx -t && sudo systemctl reload nginx"
echo ""
echo "  6. Suba os containers:"
echo "     docker compose up -d"
echo ""
echo "  7. Ative HTTPS (substitua SEU_DOMINIO):"
echo "     sudo certbot --nginx -d SEU_DOMINIO"
echo ""
echo "  8. Configure a Evolution API (conecte o WhatsApp):"
echo "     http://SEU_DOMINIO:8080 → crie instância → escaneie QR Code"
echo ""
echo "  FEITO! Bot rodando em http://SEU_DOMINIO"
echo "============================================================"

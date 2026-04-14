# Setup & Deployment Guide

## Local Setup

### 1. Create a Telegram Bot

1. Открой [@BotFather](https://t.me/BotFather) → `/newbot`
2. Следуй инструкциям, скопируй токен

### 2. Get a Google API Key

Бот работает с любой **публично доступной** таблицей ("Anyone with the link can view").
Ничего шарить не нужно — достаточно API Key.

1. Открой [Google Cloud Console](https://console.cloud.google.com/)
2. Создай проект (или выбери существующий)
3. Перейди в **APIs & Services → Library**, включи **Google Sheets API**
4. Перейди в **APIs & Services → Credentials → Create Credentials → API key**
5. Скопируй ключ

> **Опционально:** ограничь ключ в настройках — **API restrictions → Google Sheets API**.
> Это не обязательно, но хорошая практика.

### 3. Make Sure the Spreadsheet is Public

Таблица должна быть открыта для просмотра без авторизации:

- Открой таблицу → **Share → Change to anyone with the link → Viewer** → **Done**

Приватные таблицы бот видеть не сможет.

### 4. Install and Configure

```bash
git clone <repo>
cd google-sheet-reminder-bot

python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Открой .env и заполни BOT_TOKEN и GOOGLE_API_KEY
```

### 5. Run Locally

```bash
python -m bot.main
```

---

## Deployment on a Remote Server

### Prerequisites

- VPS с Ubuntu 22.04+ (подойдёт любой хостинг: Hetzner, DigitalOcean, Timeweb Cloud и т.д.)
- Python 3.11+
- SSH доступ

---

### Option A — systemd service (рекомендуется)

Простой и надёжный способ. Бот запускается как системный сервис, автоматически стартует после перезагрузки и перезапускается при падении.

#### 1. Подключись к серверу и установи зависимости

```bash
ssh user@your-server-ip

sudo apt update && sudo apt install -y python3.11 python3.11-venv python3-pip git
```

#### 2. Скопируй проект на сервер

```bash
# Со своей машины
scp -r ./google-sheet-reminder-bot user@your-server-ip:/opt/sheet-bot

# Или клонируй напрямую на сервере
git clone <repo> /opt/sheet-bot
```

#### 3. Настрой окружение

```bash
cd /opt/sheet-bot

python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
nano .env   # Заполни BOT_TOKEN и GOOGLE_API_KEY
```

#### 4. Создай systemd unit

```bash
sudo nano /etc/systemd/system/sheet-bot.service
```

Вставь (замени `user` на своего пользователя):

```ini
[Unit]
Description=Google Sheet Reminder Telegram Bot
After=network.target

[Service]
Type=simple
User=user
WorkingDirectory=/opt/sheet-bot
ExecStart=/opt/sheet-bot/.venv/bin/python -m bot.main
Restart=on-failure
RestartSec=5
EnvironmentFile=/opt/sheet-bot/.env

[Install]
WantedBy=multi-user.target
```

#### 5. Запусти и включи автостарт

```bash
sudo systemctl daemon-reload
sudo systemctl enable sheet-bot
sudo systemctl start sheet-bot
```

#### Управление сервисом

```bash
sudo systemctl status sheet-bot     # Статус
sudo journalctl -u sheet-bot -f     # Логи в реальном времени
sudo systemctl restart sheet-bot    # Перезапуск
sudo systemctl stop sheet-bot       # Остановка
```

---

### Option B — Docker

Удобно, если хочешь изолировать окружение или деплоить через CI.

#### 1. Создай `Dockerfile` в корне проекта

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "bot.main"]
```

#### 2. Создай `.dockerignore`

```
.venv
__pycache__
*.pyc
bot.db
.env
```

#### 3. Собери и запусти

```bash
# Сборка образа
docker build -t sheet-bot .

# Запуск (.env монтируется снаружи, bot.db персистится через volume)
docker run -d \
  --name sheet-bot \
  --restart unless-stopped \
  --env-file .env \
  -v $(pwd)/bot.db:/app/bot.db \
  sheet-bot
```

#### Управление контейнером

```bash
docker logs -f sheet-bot     # Логи
docker restart sheet-bot     # Перезапуск
docker stop sheet-bot        # Остановка
```

---

### Option C — Docker Compose

Удобнее, если планируешь добавить другие сервисы рядом (например, мониторинг).

Создай `docker-compose.yml`:

```yaml
services:
  sheet-bot:
    build: .
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./bot.db:/app/bot.db
```

```bash
docker compose up -d          # Запуск
docker compose logs -f        # Логи
docker compose restart        # Перезапуск
```

---

## Updating the Bot

### systemd

```bash
cd /opt/sheet-bot
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart sheet-bot
```

### Docker / Docker Compose

```bash
git pull
docker compose down
docker compose up -d --build
```

---

## Security Checklist

- `.env` добавлен в `.gitignore` — не коммить его в репозиторий
- На сервере ограничь права на файл с переменными:
  ```bash
  chmod 600 /opt/sheet-bot/.env
  ```
- Запускай бота от непривилегированного пользователя (не `root`)
- В Google Cloud Console ограничь API Key — **API restrictions → Google Sheets API**

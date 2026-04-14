# Setup & Deployment Guide

## Local Setup

### 1. Create a Telegram Bot

1. Открой [@BotFather](https://t.me/BotFather) → `/newbot`
2. Следуй инструкциям, скопируй токен

### 2. Create a Google Service Account

1. Открой [Google Cloud Console](https://console.cloud.google.com/) → **APIs & Services → Credentials**
2. **Create Credentials → Service Account** → введи имя → **Done**
3. Открой созданный аккаунт → вкладка **Keys** → **Add Key → Create new key → JSON**
4. Скачанный файл сохрани как `credentials.json` в корень проекта

Включи API в **APIs & Services → Library**:
- **Google Sheets API**
- **Google Drive API**

### 3. Share Spreadsheets with the Service Account

Email сервисного аккаунта выглядит так:
```
my-bot@my-project.iam.gserviceaccount.com
```

Для каждой таблицы, которую хочешь отслеживать:
- Открой таблицу → **Share** → добавь email сервисного аккаунта с доступом **Viewer**

Бот работает в read-only режиме и никогда не пишет в таблицы.

### 4. Install and Configure

```bash
git clone <repo>
cd google-sheet-reminder-bot

python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Открой .env и заполни BOT_TOKEN и GOOGLE_CREDENTIALS_PATH
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
nano .env   # Заполни BOT_TOKEN и GOOGLE_CREDENTIALS_PATH
```

Не забудь скопировать `credentials.json` на сервер:

```bash
# Со своей машины
scp ./credentials.json user@your-server-ip:/opt/sheet-bot/credentials.json
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

# Запуск (credentials.json и .env монтируются снаружи)
docker run -d \
  --name sheet-bot \
  --restart unless-stopped \
  --env-file .env \
  -v $(pwd)/credentials.json:/app/credentials.json:ro \
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
      - ./credentials.json:/app/credentials.json:ro
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

- `credentials.json` и `.env` добавлены в `.gitignore` — не коммить их в репозиторий
- На сервере ограничь права на эти файлы:
  ```bash
  chmod 600 /opt/sheet-bot/.env
  chmod 600 /opt/sheet-bot/credentials.json
  ```
- Запускай бота от непривилегированного пользователя (не `root`)
- Для Service Account используй минимально необходимые права — только **Viewer** на нужных таблицах

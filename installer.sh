#!/bin/bash

# Проверка, что скрипт запущен от имени суперпользователя (root)
if [[ $EUID -ne 0 ]]; then
   echo "Ошибка: Этот скрипт необходимо запускать с правами суперпользователя (sudo)."
   exit 1
fi

# Приветственное сообщение
clear
echo "================================================="
echo "=== Установщик бота для отбора в HataniSquad ==="
echo "================================================="
echo

# Запрос данных у пользователя
read -p "➡️  Введите токен вашего Telegram-бота: " BOT_TOKEN
read -p "➡️  Введите ID чата отбора (например, -1001234567890): " CHAT_ID

# Проверка, что введены не пустые значения
if [ -z "$BOT_TOKEN" ] || [ -z "$CHAT_ID" ]; then
    echo "Ошибка: Токен и ID чата не могут быть пустыми."
    exit 1
fi

echo
echo "✅ Данные приняты. Начинаю установку..."
sleep 2

# --- Установка системных зависимостей ---
echo "🔄 Обновление списка пакетов..."
apt-get update
echo "📦 Установка системных пакетов (git, python, pip, redis, curl)..."
apt-get install -y git python3 python3-pip redis-server curl

# --- Установка Node.js и PM2 ---
echo "🚀 Установка Node.js (v20.x)..."
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
apt-get install -y nodejs
echo " pm2 - менеджер процессов..."
npm install -g pm2

# --- Клонирование репозитория ---
# Определяем домашнюю директорию пользователя, который запустил sudo
if [ -n "$SUDO_USER" ]; then
    TARGET_DIR="/home/$SUDO_USER/Selection-Hatani-Bot"
else
    TARGET_DIR="/root/Selection-Hatani-Bot"
fi

echo "📂 Клонирование репозитория в $TARGET_DIR..."
git clone https://github.com/Rewixx-png/Selection-Hatani-Bot.git "$TARGET_DIR"

if [ ! -d "$TARGET_DIR" ]; then
    echo "❌ Ошибка: Не удалось клонировать репозиторий."
    exit 1
fi
cd "$TARGET_DIR"

# --- Настройка бота ---
echo "⚙️  Настройка бота..."
# Создаем файл с токеном
echo "$BOT_TOKEN" > token.txt
# Изменяем ID чата в конфиге
sed -i "s/^CHAT_ID: int = .*/CHAT_ID: int = $CHAT_ID/" config.py

# --- Установка Python-библиотек ---
echo "🐍 Установка Python-зависимостей из requirements.txt..."
pip install -r requirements.txt
echo "🌐 Установка браузера Chromium для Playwright (может занять несколько минут)..."
python3 -m playwright install chromium

# --- Запуск через PM2 ---
echo "▶️  Запуск бота через PM2..."
pm2 start main.py --name "selection-bot" --interpreter python3
echo "💾 Сохранение списка процессов PM2 для автозапуска..."
pm2 save
echo "⚙️  Настройка автозапуска PM2 при перезагрузке сервера..."
# Эта магия выполняет команду, которую выводит `pm2 startup`
pm2 startup systemd -u $(logname) --hp /home/$(logname) | tail -n 1 | sudo -E bash -

echo
echo "================================================="
echo "🎉 Установка успешно завершена! 🎉"
echo "================================================="
echo "Бот запущен и будет автоматически включаться после перезагрузки."
echo
echo "Полезные команды:"
echo "  pm2 logs selection-bot  - посмотреть логи бота"
echo "  pm2 restart selection-bot - перезапустить бота"
echo "  pm2 status              - посмотреть статус всех процессов"
echo
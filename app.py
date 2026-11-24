import asyncio, html, os, requests
import phonenumbers
from phonenumbers import carrier, geocoder, timezone
from telethon import TelegramClient, events
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.messages import GetStickerSetRequest
from telethon.tl.types import InputStickerSetShortName
from telegraph import Telegraph
from flask import Flask
import threading

# --- НАСТРОЙКИ БЕЗОПАСНОСТИ ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

STICKER_PACK = "redkrayt_by_emojicreationbot"
STICKER_INDEX = 2

client = TelegramClient("antikrayt", API_ID, API_HASH)
tg = Telegraph()
tg.create_account(short_name="antikrayt")

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER (чтобы не засыпал) ---
app = Flask(__name__)

@app.route('/')
@app.route('/health')
def health():
    return "Bot is running", 200

# --- ФУНКЦИИ БОТА (ПОЛНЫЙ КОД) ---
@client.on(events.NewMessage(pattern=r"^/start"))
async def start(e):
    try:
        pack = await client(GetStickerSetRequest(
            InputStickerSetShortName(STICKER_PACK), hash=0))
        sticker = pack.documents[STICKER_INDEX]
        await client.send_file(e.chat_id, sticker)
    except Exception as err:
        print("STICKER ERROR:", err)
    await e.reply(
        "Доступны функции:\n\n"
        "1. Поиск по ID (@user)\n"
        "2. Информация по номеру (+998...)\n"
        "3. Поиск по сотням источников (user)\n"
        "4. Информация по IP-адресу (8.8.8.8)\n\n")

async def lookup_user(e, q):
    q = q.lstrip("@")
    try:
        full = await client(GetFullUserRequest(int(q) if q.isdigit() else q))
    except Exception:
        return await e.reply("Ничего не нашёл.")
    u = full.users[0]
    lines = [
        f"ID: {u.id}",
        f"Имя: {u.first_name or ''} {u.last_name or ''}".strip(),
        f"Юзернейм: @{u.username}" if u.username else "Юзернейм: нет",
        f"Бот: {'да' if u.bot else 'нет'}",
        f"Premium: {'да' if u.premium else 'нет'}",
        f"О себе: {full.full_user.about or '—'}",
    ]
    body = "<br>".join(html.escape(x) for x in lines)
    page = await asyncio.to_thread(
        tg.create_page, title=f"Отчёт: {q}", html_content=body)
    await e.reply("Добытая информация:\n" + "\n".join(lines)
                  + f"\n\nОтчёт: {page['url']}")

async def lookup_number(e, raw):
    try:
        p = phonenumbers.parse(raw, None)
    except phonenumbers.NumberParseException:
        return await e.reply("Не похоже на номер.")
    valid = phonenumbers.is_valid_number(p)
    region = geocoder.description_for_number(p, "ru") or "неизвестно"
    oper = carrier.name_for_number(p, "ru") or "неизвестно"
    tz = ", ".join(timezone.time_zones_for_number(p))
    await e.reply(
        "Добытая информация:\n"
        f"Формат: {'корректный' if valid else 'некорректный'}\n"
        f"Регион: {region}\n"
        f"Оператор при выдаче: {oper}\n"
        f"Часовой пояс: {tz}")

async def lookup_ip(e, target):
    r = requests.get(f"http://ip-api.com/json/{target}").json()
    if r.get("status") != "success":
        return await e.reply("Неудалось определить адрес.")
    lines = [
        f"IP: {r.get('query')}",
        f"Провайдер: {r.get('isp')}",
        f"Организация: {r.get('org')}",
        f"Страна: {r.get('country')}",
        f"Регион: {r.get('regionName')}",
        f"Город: {r.get('city')}",
    ]
    lat, lon = r.get("lat"), r.get("lon")
    map_url = f"https://www.google.com/maps?q={lat},{lon}"
    await e.reply("Добытая информация:\n" + "\n".join(lines)
                  + f"\n\nКарта: {map_url}")

async def run_sherlock(username):
    # ВРЕМЕННАЯ ЗАГЛУШКА ДЛЯ ОБЛАКА
    return f"Sherlock временно отключен в облаке. Поиск {username} недоступен."

def is_ip(text):
    parts = text.split(".")
    return len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)

@client.on(events.NewMessage(pattern=r"^(?!/)"))
async def catch_all(e):
    text = e.raw_text.strip()
    if text.startswith("@"):
        await lookup_user(e, text)
    elif is_ip(text):
        await lookup_ip(e, text)
    elif text.startswith("+") or text.replace(" ", "").isdigit():
        await lookup_number(e, text)
    elif text.isalnum():
        msg = await e.reply(f"Ищу «{text}» по сайтам, подожди немного...")
        output = await run_sherlock(text)
        await msg.edit(output)
    else:
        await e.reply("Некорректный запрос.")

# --- ЗАПУСК ---
def run_bot():
    try:
        client.start(bot_token=BOT_TOKEN)
        print("Бот успешно запущен!")
        client.run_until_disconnected()
    except Exception as e:
        print(f"Ошибка при запуске бота: {e}")

if __name__ == "__main__":
    # Запускаем бота в фоновом потоке, чтобы Flask мог работать
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Запускаем веб-сервер для Render (используем порт, который даст Render)
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

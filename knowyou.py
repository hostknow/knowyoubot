import asyncio
import logging
import aiosqlite
import sqlite3
import os
import random
import string
import shutil
import zipfile
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile, Message, CallbackQuery
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
import aiohttp

# ========================= КОНФИГ =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 7544145316))

BOT_USERNAME = "iknowyoumylovebot"
STUDIO_NAME = "IKNOWYOUhub"
BASE_PRICE = 50
AI_FORUM_INVITE_LINK = "https://t.me/+твоя_ссылка"
MAIN_GIF = "iknow1.gif"
MAIN_PHOTO = "main.jpg"

REF_JOIN_COINS = 100
REF_BUY_COINS = 1000
REF_BUY_USD = 3

# Путь к базе данных (на Persistent Disk)
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "bot.db")

# ====================== ОСНОВНОЙ ТЕКСТ ======================
MAIN_TEXT_HARD = (
    "#IKNOWYOU — комьюнити единомышленников во всех сферах с применением AI.\n\n"
    "Поможем научиться пользоваться нейросетями. Без воды.\n\n"
    "Курсы на YouTube, Instagram, TikTok — всё это чушь.\n"
    "Люди говорят об этом, чтобы набить себе просмотры.\n\n"
    "Мы в свою очередь помогаем практиковаться.\n\n"
    "Ты узнаешь после входа то, что на самом деле можно создавать,\n"
    "имея даже обычный телефон с интернетом.\n\n"
    "У кого есть деньги — покупайте самый простой ноутбук.\n"
    "С этим тоже подскажем. Возможностей будет намного больше.\n\n"
    "Рады приветствовать каждого!\n\n"
    "Заработайте, пригласив друга.\n\n"
    "Личная поддержка от создателей сообщества обеспечена.\n\n"
    "👇 Нажми Войти в клуб"
)

HELP_TEXT = (
    "🤖 Помощь по боту IKNOWYOU\n\n"
    "📌 Основные команды:\n"
    "/start — Главное меню\n"
    "/balance — Мой баланс\n"
    "/help — Эта справка\n\n"
    "📌 Как купить доступ:\n"
    "1. Нажми «Войти в клуб»\n"
    "2. Введи промокод (если есть)\n"
    "3. Нажми «Оплатить»\n"
    "4. Перейди по ссылке CryptoBot\n"
    "5. Нажми «Я оплатил»\n\n"
    "📌 Партнёрка:\n"
    "Приводи друзей и получай IKY и $\n\n"
    "📌 Поддержка:\n"
    "@managerai — по всем вопросам\n"
)

NEW_ALERT_TEXT = "⚡️ Осталось {remaining} мест по {price}$ (≈ {rub} руб.)"

# ------------------------- ИНИЦИАЛИЗАЦИЯ БД -------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id     INTEGER PRIMARY KEY,
        username    TEXT,
        first_name  TEXT,
        reg_date    TEXT,
        referred_by INTEGER DEFAULT NULL,
        referred_by_username TEXT DEFAULT NULL,
        coins       INTEGER DEFAULT 0,
        dollars     REAL    DEFAULT 0.0,
        promo       TEXT DEFAULT NULL
    )''')
    c.execute("PRAGMA table_info(users)")
    existing = [col[1] for col in c.fetchall()]
    if 'reg_date' not in existing:
        c.execute("ALTER TABLE users ADD COLUMN reg_date TEXT")
    if 'referred_by' not in existing:
        c.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER DEFAULT NULL")
    if 'referred_by_username' not in existing:
        c.execute("ALTER TABLE users ADD COLUMN referred_by_username TEXT DEFAULT NULL")
    if 'coins' not in existing:
        c.execute("ALTER TABLE users ADD COLUMN coins INTEGER DEFAULT 0")
    if 'dollars' not in existing:
        c.execute("ALTER TABLE users ADD COLUMN dollars REAL DEFAULT 0.0")
    if 'promo' not in existing:
        c.execute("ALTER TABLE users ADD COLUMN promo TEXT DEFAULT NULL")

    c.execute('''CREATE TABLE IF NOT EXISTS purchases (
        user_id  INTEGER PRIMARY KEY,
        paid_at  TEXT,
        amount   INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS invoices (
        invoice_id TEXT PRIMARY KEY,
        user_id    INTEGER,
        amount     INTEGER,
        status     TEXT DEFAULT 'pending'
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS slots (
        id INTEGER PRIMARY KEY DEFAULT 1,
        total INTEGER DEFAULT 50,
        remaining INTEGER DEFAULT 50
    )''')
    c.execute("INSERT OR IGNORE INTO slots (id, total, remaining) VALUES (1, 50, 50)")
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    
    c.execute("REPLACE INTO settings (key, value) VALUES (?, ?)", ('main_text', MAIN_TEXT_HARD))
    c.execute("REPLACE INTO settings (key, value) VALUES (?, ?)", ('alert_text', NEW_ALERT_TEXT))
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('main_photo', 'main.jpg')")
    
    c.execute('''CREATE TABLE IF NOT EXISTS promocodes (
        code TEXT PRIMARY KEY,
        price_usd INTEGER NOT NULL,
        uses_left INTEGER DEFAULT 1,
        expires_at TEXT DEFAULT NULL
    )''')
    conn.commit()
    conn.close()
    print("✅ База данных инициализирована.")

init_db()

# ------------------------- БЕЗОПАСНАЯ ОТПРАВКА СООБЩЕНИЙ -------------------------
async def safe_send_message(chat_id, text, reply_markup=None, disable_web_page_preview=False):
    """Безопасная отправка сообщения с обработкой ошибок Markdown"""
    try:
        return await bot.send_message(
            chat_id, 
            text, 
            parse_mode="Markdown",
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview
        )
    except Exception as e:
        if "Can't find end of the entity" in str(e) or "parse entities" in str(e):
            return await bot.send_message(
                chat_id, 
                text, 
                parse_mode=None,
                reply_markup=reply_markup,
                disable_web_page_preview=disable_web_page_preview
            )
        else:
            raise

# ------------------------- ФУНКЦИИ БД -------------------------
async def add_user(user_id, username, first_name, referred_by=None, referred_by_username=None, promo_code=None):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,)) as cur:
            if await cur.fetchone():
                return False
        ref = referred_by if referred_by and referred_by != user_id else None
        await db.execute(
            "INSERT INTO users (user_id, username, first_name, reg_date, referred_by, referred_by_username, coins, dollars, promo) VALUES (?,?,?,?,?,?,0,0,?)",
            (user_id, username, first_name, datetime.now().isoformat(), ref, referred_by_username, promo_code)
        )
        await db.commit()
        return True

async def get_referred_by(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT referred_by FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else None

async def get_referred_by_username(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT referred_by_username FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else None

async def get_referrals(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, username, first_name, reg_date FROM users WHERE referred_by=?", (user_id,)) as cur:
            return await cur.fetchall()

async def add_balance(user_id, coins=0, usd=0.0):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET coins=coins+?, dollars=dollars+? WHERE user_id=?",
            (coins, float(usd), user_id)
        )
        await db.commit()

async def deduct_balance(user_id, coins=0, usd=0.0):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT coins, dollars FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
        if not row or row[0] < coins or row[1] < usd:
            return False
        await db.execute("UPDATE users SET coins=coins-?, dollars=dollars-? WHERE user_id=?", (coins, usd, user_id))
        await db.commit()
        return True

async def get_balance(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT coins, dollars FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            return (row[0], row[1]) if row else (0, 0.0)

async def has_access(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM purchases WHERE user_id=?", (user_id,)) as cur:
            return await cur.fetchone() is not None

async def save_purchase(user_id, amount):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("REPLACE INTO purchases (user_id, paid_at, amount) VALUES (?,?,?)",
                         (user_id, datetime.now().isoformat(), amount))
        await db.commit()
    await decrease_slots()

async def save_invoice(invoice_id, user_id, amount):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO invoices (invoice_id, user_id, amount) VALUES (?,?,?)",
                         (invoice_id, user_id, amount))
        await db.commit()

async def get_invoice(invoice_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, amount FROM invoices WHERE invoice_id=?", (invoice_id,)) as cur:
            return await cur.fetchone()

async def set_invoice_paid(invoice_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE invoices SET status='paid' WHERE invoice_id=?", (invoice_id,))
        await db.commit()

async def members_count():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM purchases") as cur:
            return (await cur.fetchone())[0]

async def all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, username, first_name, coins, dollars FROM users") as cur:
            return await cur.fetchall()

# ------------------------- ПРОМОКОДЫ -------------------------
async def get_promo_price(code: str) -> int | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT price_usd, uses_left, expires_at FROM promocodes WHERE code = ?", (code,)) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            price, uses_left, expires_at = row
            if uses_left <= 0:
                return None
            if expires_at:
                exp_date = datetime.strptime(expires_at, '%Y-%m-%d').date()
                if datetime.now().date() > exp_date:
                    return None
            return price

async def apply_promo_to_user(user_id: int, code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET promo = ? WHERE user_id = ?", (code, user_id))
        await db.commit()

async def get_user_promo(user_id: int) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT promo FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else None

async def get_user_price(user_id: int) -> int:
    promo = await get_user_promo(user_id)
    if promo:
        price = await get_promo_price(promo)
        if price is not None:
            return price
    return BASE_PRICE

async def use_promo_code(code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE promocodes SET uses_left = uses_left - 1 WHERE code = ?", (code,))
        await db.commit()

async def add_promo_code(code: str, price_usd: int, uses_left: int = 1, expires_at: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO promocodes (code, price_usd, uses_left, expires_at) VALUES (?,?,?,?)",
                         (code, price_usd, uses_left, expires_at))
        await db.commit()

async def delete_promo_code(code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM promocodes WHERE code = ?", (code,))
        await db.commit()

async def list_promocodes() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT code, price_usd, uses_left, expires_at FROM promocodes") as cur:
            return await cur.fetchall()

async def generate_promos(count: int, price: int) -> int:
    created = 0
    for _ in range(count):
        code = "IKY" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        existing = await get_promo_price(code)
        if existing is None:
            await add_promo_code(code, price, uses_left=1)
            created += 1
    return created

# ------------------------- СЛОТЫ -------------------------
async def get_remaining_slots():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT remaining FROM slots WHERE id=1") as cur:
            row = await cur.fetchone()
            return row[0] if row else 50

async def decrease_slots():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE slots SET remaining = remaining - 1 WHERE id=1 AND remaining > 0")
        await db.commit()

async def increase_slots(delta=1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE slots SET remaining = remaining + ? WHERE id=1", (delta,))
        await db.commit()
        return await get_remaining_slots()

async def reset_slots():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE slots SET remaining = total WHERE id=1")
        await db.commit()

# ------------------------- НАСТРОЙКИ -------------------------
async def get_setting(key: str) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else ""

async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("REPLACE INTO settings (key, value) VALUES (?,?)", (key, value))
        await db.commit()

# ------------------------- БЭКАП БАЗЫ ДАННЫХ -------------------------
async def backup_database():
    """Делает бэкап БД и отправляет админу"""
    try:
        db_path = DB_PATH
        backup_dir = os.path.join(os.path.dirname(db_path), "backups")
        os.makedirs(backup_dir, exist_ok=True)
        
        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_path = os.path.join(backup_dir, f"bot_backup_{date_str}.db")
        
        shutil.copy2(db_path, backup_path)
        
        zip_path = backup_path.replace(".db", ".zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(backup_path, os.path.basename(backup_path))
        os.remove(backup_path)
        
        size = os.path.getsize(zip_path) / 1024
        
        caption = (
            f"📦 Бэкап базы данных\n\n"
            f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
            f"📁 Файл: {os.path.basename(zip_path)}\n"
            f"📊 Размер: {size:.1f} КБ\n"
            f"✅ Статус: УСПЕШНО"
        )
        
        await bot.send_document(
            chat_id=ADMIN_ID,
            document=FSInputFile(zip_path),
            caption=caption,
            parse_mode=None
        )
        
        await cleanup_old_backups(backup_dir, keep=7)
        return True
        
    except Exception as e:
        try:
            await bot.send_message(
                ADMIN_ID,
                f"❌ Ошибка бэкапа!\n\n{str(e)}",
                parse_mode=None
            )
        except:
            pass
        return False

async def cleanup_old_backups(backup_dir, keep=7):
    try:
        files = []
        for f in os.listdir(backup_dir):
            if f.endswith(".zip"):
                path = os.path.join(backup_dir, f)
                files.append((os.path.getctime(path), path))
        files.sort()
        for i in range(len(files) - keep):
            try:
                os.remove(files[i][1])
            except:
                pass
    except:
        pass

async def backup_scheduler():
    while True:
        try:
            now = datetime.now()
            target = now.replace(hour=3, minute=0, second=0, microsecond=0)
            if now > target:
                target += timedelta(days=1)
            wait_seconds = (target - now).total_seconds()
            await asyncio.sleep(wait_seconds)
            await backup_database()
        except Exception as e:
            print(f"❌ Ошибка в бэкап-планировщике: {e}")
            await asyncio.sleep(3600)

# ------------------------- CRYPTOBOT -------------------------
async def create_invoice(amount, desc):
    async with aiohttp.ClientSession() as s:
        try:
            async with s.post(
                "https://pay.crypt.bot/api/createInvoice",
                headers={"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN},
                json={"asset": "USDT", "amount": str(amount), "description": desc, "expired_in": 3600}
            ) as r:
                d = await r.json()
                if d.get("ok"):
                    return d["result"]["invoice_id"], d["result"]["pay_url"]
        except Exception as e:
            print(f"Ошибка создания инвойса: {e}")
    return None, None

async def check_invoice(invoice_id):
    async with aiohttp.ClientSession() as s:
        try:
            async with s.get(
                f"https://pay.crypt.bot/api/getInvoices?invoice_ids={invoice_id}",
                headers={"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
            ) as r:
                d = await r.json()
                if d.get("ok") and d["result"]["items"]:
                    return d["result"]["items"][0]["status"]
        except Exception as e:
            print(f"Ошибка проверки инвойса: {e}")
    return "failed"

async def poll_invoices(bot_instance):
    while True:
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT invoice_id, user_id FROM invoices WHERE status='pending'") as cur:
                    rows = await cur.fetchall()
            for inv_id, user_id in rows:
                if await check_invoice(inv_id) == "paid":
                    await set_invoice_paid(inv_id)
                    if await get_remaining_slots() <= 0:
                        await safe_send_message(user_id, "❌ Все места заняты. Деньги вернут в течение 7 дней.")
                        continue
                    price = await get_user_price(user_id)
                    await save_purchase(user_id, price)
                    user_promo = await get_user_promo(user_id)
                    if user_promo:
                        await use_promo_code(user_promo)
                        await apply_promo_to_user(user_id, None)
                    ref = await get_referred_by(user_id)
                    if ref:
                        await add_balance(ref, coins=REF_BUY_COINS, usd=REF_BUY_USD)
                        try:
                            ref_username = await get_referred_by_username(user_id)
                            name = ref_username or f"пользователя {ref}"
                            await safe_send_message(ref, f"🎉 Реферал @{name} купил!\n🪙 +{REF_BUY_COINS} IKY\n💵 +{REF_BUY_USD}$")
                        except:
                            pass
                    await safe_send_message(
                        ADMIN_ID,
                        f"🎉 НОВАЯ ПОКУПКА!\n\n"
                        f"Пользователь: @{await get_username(user_id) or user_id}\n"
                        f"Сумма: {price}$\n"
                        f"Способ: CryptoBot\n"
                        f"Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                    )
                    await safe_send_message(
                        user_id,
                        f"✅ Оплата прошла. Добро пожаловать в IKNOWYOU — AI!\n\n"
                        f"🔗 {AI_FORUM_INVITE_LINK}\n\n"
                        f"📌 Важно!\n"
                        f"Если ссылка не работает — напиши менеджеру @managerai\n"
                        f"И приложи скриншот оплаты.\n\n"
                        f"Напиши «я новенький» — тебя встретят 🤝"
                    )
        except Exception as e:
            logging.error(f"poll_invoices: {e}")
        await asyncio.sleep(10)

async def get_username(user_id):
    try:
        user = await bot.get_chat(user_id)
        return user.username or user.first_name
    except:
        return None

# ------------------------- КЛАВИАТУРЫ -------------------------
def menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Войти в клуб", callback_data="buy")],
        [InlineKeyboardButton(text="🤝 Партнёрка", callback_data="ref")],
        [InlineKeyboardButton(text="💼 Мой баланс", callback_data="bal")],
    ])

def pay_kb(pay_url, inv_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Оплатить через CryptoBot", url=pay_url)],
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"check_{inv_id}")],
        [InlineKeyboardButton(text="👨‍💼 Оплата через менеджера", callback_data="manager_pay")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back")],
    ])

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="back")]])

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Главный текст", callback_data="admin_edit_main")],
        [InlineKeyboardButton(text="🔔 Текст алерта", callback_data="admin_edit_alert")],
        [InlineKeyboardButton(text="📸 Сменить фото", callback_data="admin_change_photo")],
        [InlineKeyboardButton(text="🎬 Сменить гифку", callback_data="admin_change_gif")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🎫 Промокоды", callback_data="admin_promos")],
        [InlineKeyboardButton(text="🎲 Нагенерить промокоды", callback_data="admin_gen_promos")],
        [InlineKeyboardButton(text="➕ +1 место", callback_data="admin_add_slots")],
        [InlineKeyboardButton(text="➖ -1 место", callback_data="admin_remove_slots")],
        [InlineKeyboardButton(text="🔁 Сброс мест до 50", callback_data="admin_reset_slots")],
        [InlineKeyboardButton(text="📦 Бэкап", callback_data="admin_backup")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")],
    ])

# ------------------------- FSM -------------------------
class AdminEdit(StatesGroup):
    waiting_main_text = State()
    waiting_alert_text = State()
    waiting_broadcast = State()
    waiting_photo = State()
    waiting_gif = State()
    waiting_promo_code = State()
    waiting_promo_price = State()
    waiting_promo_uses = State()
    waiting_promo_delete = State()
    waiting_gen_promos = State()
    waiting_restore = State()

class PaymentState(StatesGroup):
    waiting_promo = State()

# ------------------------- БОТ -------------------------
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
dp = Dispatcher(storage=MemoryStorage())

async def safe(cb, text=None, alert=False):
    try:
        await cb.answer(text, show_alert=alert) if text else await cb.answer()
    except:
        pass

# ====================== ФУНКЦИЯ SHOW_MAIN ======================
async def show_main(target, is_callback=False):
    text = MAIN_TEXT_HARD
    msg = target.message if is_callback else target
    
    if is_callback:
        try:
            await msg.delete()
        except:
            pass
    
    if os.path.exists(MAIN_GIF):
        try:
            await msg.answer_animation(animation=FSInputFile(MAIN_GIF), caption=text, reply_markup=menu_kb())
            return
        except Exception as e:
            print(f"❌ Ошибка при отправке GIF: {e}")
    
    if os.path.exists(MAIN_PHOTO):
        await msg.answer_photo(photo=FSInputFile(MAIN_PHOTO), caption=text, reply_markup=menu_kb())
    else:
        await safe_send_message(msg.chat.id, text, reply_markup=menu_kb())

# ------------------------- ХЕНДЛЕРЫ -------------------------
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    
    args = message.text.split()
    ref = None
    promo_code = None
    for arg in args[1:]:
        if arg.startswith("ref_"):
            try:
                ref = int(arg.split("_")[1])
            except:
                pass
        elif arg.startswith("promo_"):
            promo_code = arg[6:]
    
    ref_username = None
    if ref:
        try:
            user = await bot.get_chat(ref)
            ref_username = user.username or user.first_name
        except:
            pass
    
    is_new = await add_user(message.from_user.id, message.from_user.username, message.from_user.first_name, ref, ref_username, promo_code)
    if is_new and ref:
        await add_balance(ref, coins=REF_JOIN_COINS)
        try:
            name = message.from_user.username or message.from_user.first_name
            await safe_send_message(ref, f"👋 По твоей ссылке зашёл новый пользователь @{name}!\n🪙 +{REF_JOIN_COINS} IKY")
        except:
            pass
    
    if promo_code:
        price = await get_promo_price(promo_code)
        if price is not None:
            if not is_new:
                await apply_promo_to_user(message.from_user.id, promo_code)
            await safe_send_message(message.from_user.id, f"🎫 Промокод {promo_code} активирован! Цена доступа для вас составит {price}$ вместо {BASE_PRICE}$.")
        else:
            await safe_send_message(message.from_user.id, f"❌ Неверный или просроченный промокод {promo_code}. Цена будет {BASE_PRICE}$.")
    
    await show_main(message)

@dp.message(Command("balance"))
async def cmd_balance(message: Message, state: FSMContext):
    await state.clear()
    c, d = await get_balance(message.from_user.id)
    referrals = await get_referrals(message.from_user.id)
    
    text = f"💼 Твой баланс\n🪙 {c} IKY\n💵 {d:.2f}$\n\n"
    
    if referrals:
        text += "👥 Твои рефералы:\n"
        for uid, username, first_name, reg_date in referrals:
            name = username or first_name or str(uid)
            text += f"• @{name} — {reg_date[:10]}\n"
        text += f"\nВсего рефералов: {len(referrals)}"
    else:
        text += "👥 У тебя пока нет рефералов.\nПриводи друзей и получай бонусы!"
    
    uid = message.from_user.id
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
    text += f"\n\n🔗 Твоя партнёрская ссылка:\n{link}\n\n💸 Вывод $ — @managerai"
    
    await safe_send_message(message.from_user.id, text, reply_markup=back_kb())

@dp.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext):
    await state.clear()
    await safe_send_message(
        message.from_user.id,
        HELP_TEXT,
        reply_markup=back_kb()
    )

@dp.message(Command("backup"))
async def cmd_backup(message: Message, state: FSMContext):
    await state.clear()
    if message.from_user.id != ADMIN_ID:
        return
    await safe_send_message(message.from_user.id, "⏳ Делаю бэкап...")
    success = await backup_database()
    if success:
        await safe_send_message(message.from_user.id, "✅ Бэкап создан и отправлен в Telegram!")
    else:
        await safe_send_message(message.from_user.id, "❌ Ошибка при создании бэкапа!")

@dp.message(Command("restore"))
async def cmd_restore(message: Message, state: FSMContext):
    await state.clear()
    if message.from_user.id != ADMIN_ID:
        return
    await safe_send_message(
        message.from_user.id,
        "🔄 Восстановление БД\n\n"
        "Отправь ZIP-файл с бэкапом.\n"
        "⚠️ ВНИМАНИЕ: текущая БД будет заменена!"
    )
    await state.set_state(AdminEdit.waiting_restore)

@dp.message(AdminEdit.waiting_restore, F.document)
async def process_restore(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        file = message.document
        file_path = await bot.download(file, "temp_restore.zip")
        
        with zipfile.ZipFile(file_path, 'r') as zipf:
            zipf.extractall("temp_restore")
        
        db_files = [f for f in os.listdir("temp_restore") if f.endswith(".db")]
        if not db_files:
            await safe_send_message(message.from_user.id, "❌ Не найден .db файл в архиве!")
            return
        
        shutil.copy2(os.path.join("temp_restore", db_files[0]), DB_PATH)
        shutil.rmtree("temp_restore")
        os.remove(file_path)
        
        await safe_send_message(message.from_user.id, "✅ База данных восстановлена из бэкапа!")
    except Exception as e:
        await safe_send_message(message.from_user.id, f"❌ Ошибка восстановления: {e}")
    await state.clear()

@dp.callback_query(F.data == "back")
async def cb_back(callback: CallbackQuery, state: FSMContext):
    await safe(callback)
    await state.clear()
    await show_main(callback, is_callback=True)

@dp.callback_query(F.data == "buy")
async def cb_buy(callback: CallbackQuery, state: FSMContext):
    await safe(callback)
    await state.clear()
    
    if await has_access(callback.from_user.id):
        await safe_send_message(callback.from_user.id, f"✅ Ты уже в клубе!\n🔗 {AI_FORUM_INVITE_LINK}", reply_markup=back_kb())
        return
    
    remaining = await get_remaining_slots()
    if remaining <= 0:
        await safe_send_message(callback.from_user.id, "❌ Все места заняты! Следующий набор через неделю.")
        return
    
    price = await get_user_price(callback.from_user.id)
    rub_price = price * 90
    
    await safe_send_message(
        callback.from_user.id,
        f"💳 Оплата доступа в IKNOWYOU\n\n"
        f"💰 Цена: {price} USDT (≈ {rub_price} руб.)\n"
        f"📌 Осталось мест: {remaining}\n\n"
        f"📝 Есть промокод? Напиши его в сообщении.\n"
        f"Если нет — нажми кнопку Оплатить.\n"
        f"Если передумал — Отмена.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💸 Оплатить", callback_data="pay_now")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="back")],
        ])
    )
    await state.set_state(PaymentState.waiting_promo)

@dp.message(PaymentState.waiting_promo)
async def process_promo_in_payment(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    
    price = await get_promo_price(code)
    
    if price is None:
        await safe_send_message(
            message.from_user.id,
            "❌ Неверный или уже использованный промокод.\n"
            "Попробуй ещё раз или нажми Оплатить",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💸 Оплатить", callback_data="pay_now")],
            ])
        )
        return
    
    await apply_promo_to_user(message.from_user.id, code)
    rub_price = price * 90
    remaining = await get_remaining_slots()
    
    await safe_send_message(
        message.from_user.id,
        f"✅ Промокод {code} активирован!\n\n"
        f"💰 Новая цена: {price} USDT (≈ {rub_price} руб.)\n"
        f"📌 Осталось мест: {remaining}\n\n"
        f"👇 Нажми Оплатить",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💸 Оплатить", callback_data="pay_now")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="back")],
        ])
    )
    await state.clear()

@dp.callback_query(F.data == "pay_now")
async def pay_now(callback: CallbackQuery, state: FSMContext):
    await safe(callback)
    await state.clear()
    
    if await has_access(callback.from_user.id):
        await safe_send_message(callback.from_user.id, "✅ Ты уже в клубе!")
        return
    
    price = await get_user_price(callback.from_user.id)
    remaining = await get_remaining_slots()
    
    if remaining <= 0:
        await safe_send_message(callback.from_user.id, "❌ Все места заняты!")
        return
    
    rub_price = price * 90
    alert_tpl = await get_setting("alert_text")
    alert = alert_tpl.format(remaining=remaining, price=price, rub=rub_price) if "{remaining}" in alert_tpl else f"⚡️ Осталось {remaining} мест по {price}$ (≈ {rub_price} руб.)"
    
    text = f"{alert}\n\n💳 Для входа в клуб нужно оплатить {price} USDT (≈ {rub_price} руб.)\n\nПосле оплаты нажми «Я оплатил»."
    
    inv_id, pay_url = await create_invoice(price, "IKNOWYOUhub — доступ")
    if not inv_id:
        await safe_send_message(callback.from_user.id, "❌ Ошибка оплаты. Попробуй позже.")
        return
    
    await save_invoice(inv_id, callback.from_user.id, price)
    
    photo = await get_setting("main_photo")
    if os.path.exists(photo):
        await callback.message.answer_photo(photo=FSInputFile(photo), caption=text, reply_markup=pay_kb(pay_url, inv_id))
    else:
        await safe_send_message(callback.from_user.id, text, reply_markup=pay_kb(pay_url, inv_id))

@dp.callback_query(F.data.startswith("check_"))
async def cb_check(callback: CallbackQuery, state: FSMContext):
    await safe(callback)
    await state.clear()
    
    inv_id = callback.data.split("check_")[1]
    status = await check_invoice(inv_id)
    
    if status == "paid":
        row = await get_invoice(inv_id)
        if row:
            user_id, amount = row
            
            if await has_access(user_id):
                await safe_send_message(user_id, "✅ Ты уже в клубе!")
                return
            
            await set_invoice_paid(inv_id)
            
            if await get_remaining_slots() <= 0:
                await safe_send_message(user_id, "❌ Места закончились во время оплаты. Деньги вернут.")
                return
            
            await save_purchase(user_id, amount)
            
            user_promo = await get_user_promo(user_id)
            if user_promo:
                await use_promo_code(user_promo)
                await apply_promo_to_user(user_id, None)
            
            ref = await get_referred_by(user_id)
            if ref:
                await add_balance(ref, coins=REF_BUY_COINS, usd=REF_BUY_USD)
                try:
                    ref_username = await get_referred_by_username(user_id)
                    name = ref_username or f"пользователя {ref}"
                    await safe_send_message(ref, f"🎉 Реферал @{name} купил доступ!\n🪙 +{REF_BUY_COINS} IKY\n💵 +{REF_BUY_USD}$")
                except:
                    pass
            
            try:
                await callback.message.delete()
            except:
                pass
            
            await safe_send_message(
                user_id,
                f"✅ Добро пожаловать в IKNOWYOU — AI!\n\n"
                f"🔗 {AI_FORUM_INVITE_LINK}\n\n"
                f"📌 Важно!\n"
                f"Если ссылка не работает — напиши менеджеру @managerai\n"
                f"И приложи скриншот оплаты.\n\n"
                f"Напиши «я новенький» — тебя встретят 🤝",
                reply_markup=back_kb()
            )
    else:
        await safe(callback, "Платёж ещё не пришёл. Подожди пару минут.", alert=True)

@dp.callback_query(F.data == "manager_pay")
async def cb_manager_pay(callback: CallbackQuery, state: FSMContext):
    await safe(callback)
    await state.clear()
    try:
        await callback.message.delete()
    except:
        pass
    
    price = await get_user_price(callback.from_user.id)
    rub_price = price * 90
    
    await safe_send_message(
        callback.from_user.id,
        f"👨‍💼 Оплата через менеджера\n\n"
        f"💰 Сумма: {price} USDT (≈ {rub_price} руб.)\n\n"
        f"Напиши менеджеру @managerai и он поможет с оплатой.\n\n"
        f"После подтверждения оплаты доступ будет открыт.",
        reply_markup=back_kb()
    )

@dp.callback_query(F.data == "ref")
async def cb_ref(callback: CallbackQuery, state: FSMContext):
    await safe(callback)
    await state.clear()
    
    uid = callback.from_user.id
    c, d = await get_balance(uid)
    referrals = await get_referrals(uid)
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
    
    text = f"🔗 Партнёрка\n\n"
    text += f"💰 Приведи друга → 🪙 +{REF_JOIN_COINS} IKY\n"
    text += f"💰 Если друг купил доступ → 🪙 +{REF_BUY_COINS} IKY + 💵 +{REF_BUY_USD}$\n\n"
    text += f"💼 Твой баланс: {c} IKY / {d:.2f}$\n\n"
    
    if referrals:
        text += "👥 Твои рефералы:\n"
        for uid_ref, username, first_name, reg_date in referrals:
            name = username or first_name or str(uid_ref)
            text += f"• @{name} — {reg_date[:10]}\n"
        text += f"\nВсего: {len(referrals)}"
    else:
        text += "👥 Пока нет рефералов.\nПриводи друзей!"
    
    text += f"\n\n🔗 Твоя партнёрская ссылка:\n{link}\n\n💸 Вывод $ — @managerai"
    
    await safe_send_message(callback.from_user.id, text, reply_markup=back_kb())

@dp.callback_query(F.data == "bal")
async def cb_bal(callback: CallbackQuery, state: FSMContext):
    await safe(callback)
    await state.clear()
    
    c, d = await get_balance(callback.from_user.id)
    referrals = await get_referrals(callback.from_user.id)
    uid = callback.from_user.id
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
    
    text = f"💼 Твой баланс\n🪙 {c} IKY\n💵 {d:.2f}$\n\n"
    
    if referrals:
        text += "👥 Твои рефералы:\n"
        for uid_ref, username, first_name, reg_date in referrals:
            name = username or first_name or str(uid_ref)
            text += f"• @{name} — {reg_date[:10]}\n"
        text += f"\nВсего рефералов: {len(referrals)}"
    else:
        text += "👥 У тебя пока нет рефералов.\nПриводи друзей и получай бонусы!"
    
    text += f"\n\n🔗 Твоя партнёрская ссылка:\n{link}\n\n💸 Вывод $ — @managerai"
    
    await safe_send_message(callback.from_user.id, text, reply_markup=back_kb())

# ------------------------- АДМИНКА -------------------------
@dp.message(Command("admin228"))
async def cmd_admin(message: Message, state: FSMContext):
    await state.clear()
    if message.from_user.id != ADMIN_ID:
        return
    await safe_send_message(message.from_user.id, "🔧 Админ-панель", reply_markup=admin_kb())

@dp.callback_query(F.data == "admin_backup")
async def admin_backup(callback: CallbackQuery, state: FSMContext):
    await safe(callback)
    await state.clear()
    await safe_send_message(callback.from_user.id, "⏳ Делаю бэкап...")
    success = await backup_database()
    if success:
        await safe_send_message(callback.from_user.id, "✅ Бэкап создан и отправлен в Telegram!", reply_markup=admin_kb())
    else:
        await safe_send_message(callback.from_user.id, "❌ Ошибка при создании бэкапа!", reply_markup=admin_kb())

@dp.callback_query(F.data == "admin_edit_main")
async def admin_edit_main(callback: CallbackQuery, state: FSMContext):
    await safe(callback)
    await state.clear()
    cur = await get_setting("main_text")
    await safe_send_message(callback.from_user.id, f"Текущий текст:\n{cur}\n\nПришли новый:")
    await state.set_state(AdminEdit.waiting_main_text)

@dp.message(AdminEdit.waiting_main_text)
async def save_main_text(message: Message, state: FSMContext):
    await set_setting("main_text", message.text)
    await safe_send_message(message.from_user.id, "✅ Обновлено!")
    await state.clear()
    await cmd_admin(message, state)

@dp.callback_query(F.data == "admin_edit_alert")
async def admin_edit_alert(callback: CallbackQuery, state: FSMContext):
    await safe(callback)
    await state.clear()
    cur = await get_setting("alert_text")
    await safe_send_message(callback.from_user.id, f"Текущий алерт:\n{cur}\n\nИспользуй {remaining}, {price}, {rub}. Новый текст:")
    await state.set_state(AdminEdit.waiting_alert_text)

@dp.message(AdminEdit.waiting_alert_text)
async def save_alert_text(message: Message, state: FSMContext):
    await set_setting("alert_text", message.text)
    await safe_send_message(message.from_user.id, "✅ Обновлено!")
    await state.clear()
    await cmd_admin(message, state)

@dp.callback_query(F.data == "admin_change_photo")
async def admin_change_photo(callback: CallbackQuery, state: FSMContext):
    await safe(callback)
    await state.clear()
    await safe_send_message(callback.from_user.id, "📸 Смена фото\n\nПришли новое фото:")
    await state.set_state(AdminEdit.waiting_photo)

@dp.message(AdminEdit.waiting_photo, F.photo)
async def save_photo(message: Message, state: FSMContext):
    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        await bot.download_file(file.file_path, "main.jpg")
        await set_setting("main_photo", "main.jpg")
        await safe_send_message(message.from_user.id, "✅ Фото обновлено!", reply_markup=admin_kb())
    except Exception as e:
        await safe_send_message(message.from_user.id, f"❌ Ошибка: {e}")
    await state.clear()
    await cmd_admin(message, state)

@dp.callback_query(F.data == "admin_change_gif")
async def admin_change_gif(callback: CallbackQuery, state: FSMContext):
    await safe(callback)
    await state.clear()
    await safe_send_message(callback.from_user.id, "🎬 Смена гифки\n\nПришли новую гифку (GIF):")
    await state.set_state(AdminEdit.waiting_gif)

@dp.message(AdminEdit.waiting_gif, F.animation)
async def save_gif(message: Message, state: FSMContext):
    try:
        gif = message.animation
        file = await bot.get_file(gif.file_id)
        await bot.download_file(file.file_path, "iknow1.gif")
        await safe_send_message(message.from_user.id, "✅ Гифка обновлена!", reply_markup=admin_kb())
    except Exception as e:
        await safe_send_message(message.from_user.id, f"❌ Ошибка: {e}")
    await state.clear()
    await cmd_admin(message, state)

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    await safe(callback)
    await state.clear()
    await safe_send_message(callback.from_user.id, "Введи текст рассылки:")
    await state.set_state(AdminEdit.waiting_broadcast)

@dp.message(AdminEdit.waiting_broadcast)
async def send_broadcast(message: Message, state: FSMContext):
    text = message.text
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            users = await cur.fetchall()
    cnt = 0
    for (uid,) in users:
        try:
            await safe_send_message(uid, text)
            cnt += 1
            await asyncio.sleep(0.05)
        except:
            pass
    await safe_send_message(message.from_user.id, f"✅ Отправлено {cnt} пользователям.")
    await state.clear()
    await cmd_admin(message, state)

@dp.callback_query(F.data == "admin_promos")
async def admin_promos(callback: CallbackQuery, state: FSMContext):
    await safe(callback)
    await state.clear()
    promos = await list_promocodes()
    if not promos:
        text = "📋 Список промокодов пуст.\n\n"
    else:
        active = []
        used = []
        for code, price, uses, expires in promos:
            if uses > 0:
                active.append((code, price, uses, expires))
            else:
                used.append((code, price, uses, expires))
        
        text = "📋 Промокоды:\n\n"
        if active:
            text += "✅ Активные:\n"
            for code, price, uses, expires in active:
                text += f"• {code} — {price}$ (осталось {uses})"
                if expires:
                    text += f", до {expires}"
                text += "\n"
        else:
            text += "✅ Активные: нет\n"
        if used:
            text += "\n❌ Использованные:\n"
            for code, price, uses, expires in used:
                text += f"• {code} — {price}$ (использован)\n"
        else:
            text += "\n❌ Использованные: нет\n"
        text += "\nУправление:\n/add_promo - создать\n/del_promo - удалить\n/gen_promos - нагенерить"
    
    await safe_send_message(callback.from_user.id, text)

@dp.callback_query(F.data == "admin_gen_promos")
async def admin_gen_promos(callback: CallbackQuery, state: FSMContext):
    await safe(callback)
    await state.clear()
    await safe_send_message(
        callback.from_user.id,
        "🎲 Генерация промокодов\n\n"
        "Введи: КОЛИЧЕСТВО ЦЕНА\n"
        "Пример: 50 35 — создаст 50 промокодов по 35$\n"
        "Пример: 100 10 — создаст 100 промокодов по 10$\n\n"
        "Коды будут вида: IKY7X9K2"
    )
    await state.set_state(AdminEdit.waiting_gen_promos)

@dp.message(AdminEdit.waiting_gen_promos)
async def process_gen_promos(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await state.clear()
        return
    
    parts = message.text.split()
    if len(parts) != 2:
        await safe_send_message(message.from_user.id, "❌ Нужно два числа: КОЛИЧЕСТВО ЦЕНА")
        await state.clear()
        return
    
    try:
        count = int(parts[0])
        price = int(parts[1])
        
        if count > 500:
            await safe_send_message(message.from_user.id, "❌ Максимум 500 за раз")
            await state.clear()
            return
        if price < 1 or price > 100:
            await safe_send_message(message.from_user.id, "❌ Цена от 1 до 100$")
            await state.clear()
            return
        
        created = await generate_promos(count, price)
        await safe_send_message(message.from_user.id, f"✅ Создано {created} промокодов по {price}$")
        await state.clear()
        await cmd_admin(message, state)
        
    except Exception as e:
        await safe_send_message(message.from_user.id, f"❌ Ошибка: {e}")
        await state.clear()

@dp.message(Command("gen_promos"))
async def cmd_gen_promos(message: Message, state: FSMContext):
    await state.clear()
    if message.from_user.id != ADMIN_ID:
        return
    
    parts = message.text.split()
    if len(parts) != 3:
        await safe_send_message(message.from_user.id, "Использование: /gen_promos КОЛИЧЕСТВО ЦЕНА\nПример: /gen_promos 50 35")
        return
    
    try:
        count = int(parts[1])
        price = int(parts[2])
        
        if count > 500:
            await safe_send_message(message.from_user.id, "❌ Максимум 500 за раз")
            return
        if price < 1 or price > 100:
            await safe_send_message(message.from_user.id, "❌ Цена от 1 до 100$")
            return
        
        created = await generate_promos(count, price)
        await safe_send_message(message.from_user.id, f"✅ Создано {created} промокодов по {price}$")
        
    except Exception as e:
        await safe_send_message(message.from_user.id, f"❌ Ошибка: {e}")

@dp.message(Command("add_promo"))
async def cmd_add_promo(message: Message, state: FSMContext):
    await state.clear()
    if message.from_user.id != ADMIN_ID:
        return
    await safe_send_message(message.from_user.id, "Введи код промокода (латиница, цифры, без пробелов):")
    await state.set_state(AdminEdit.waiting_promo_code)

@dp.message(AdminEdit.waiting_promo_code)
async def add_promo_code_name(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    await state.update_data(code=code)
    await safe_send_message(message.from_user.id, "Введи цену в USD (целое число):")
    await state.set_state(AdminEdit.waiting_promo_price)

@dp.message(AdminEdit.waiting_promo_price)
async def add_promo_price(message: Message, state: FSMContext):
    try:
        price = int(message.text)
        await state.update_data(price=price)
        await safe_send_message(message.from_user.id, "Введи количество использований (целое число, 1 = одноразовый):")
        await state.set_state(AdminEdit.waiting_promo_uses)
    except:
        await safe_send_message(message.from_user.id, "❌ Введи целое число (цену).")

@dp.message(AdminEdit.waiting_promo_uses)
async def add_promo_uses(message: Message, state: FSMContext):
    try:
        uses = int(message.text)
        data = await state.get_data()
        code = data['code']
        price = data['price']
        await add_promo_code(code, price, uses)
        await safe_send_message(message.from_user.id, f"✅ Промокод {code} добавлен: {price}$, использований: {uses}")
    except:
        await safe_send_message(message.from_user.id, "❌ Введи целое число.")
    await state.clear()
    await cmd_admin(message, state)

@dp.message(Command("del_promo"))
async def cmd_del_promo(message: Message, state: FSMContext):
    await state.clear()
    if message.from_user.id != ADMIN_ID:
        return
    await safe_send_message(message.from_user.id, "Введи код промокода для удаления:")
    await state.set_state(AdminEdit.waiting_promo_delete)

@dp.message(AdminEdit.waiting_promo_delete)
async def del_promo_code(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    await delete_promo_code(code)
    await safe_send_message(message.from_user.id, f"✅ Промокод {code} удалён (если существовал).")
    await state.clear()
    await cmd_admin(message, state)

@dp.callback_query(F.data == "admin_add_slots")
async def admin_add_slots(callback: CallbackQuery, state: FSMContext):
    await safe(callback)
    await state.clear()
    r = await increase_slots(1)
    await safe_send_message(callback.from_user.id, f"✅ +1 место. Осталось {r}.")
    await cmd_admin(callback.message, state)

@dp.callback_query(F.data == "admin_remove_slots")
async def admin_remove_slots(callback: CallbackQuery, state: FSMContext):
    await safe(callback)
    await state.clear()
    r = await get_remaining_slots()
    if r <= 0:
        await safe_send_message(callback.from_user.id, "❌ Нельзя убавить.")
        return
    await decrease_slots()
    r = await get_remaining_slots()
    await safe_send_message(callback.from_user.id, f"✅ -1 место. Осталось {r}.")
    await cmd_admin(callback.message, state)

@dp.callback_query(F.data == "admin_reset_slots")
async def admin_reset_slots(callback: CallbackQuery, state: FSMContext):
    await safe(callback)
    await state.clear()
    await reset_slots()
    r = await get_remaining_slots()
    await safe_send_message(callback.from_user.id, f"✅ Сброс до 50. Осталось {r}.")
    await cmd_admin(callback.message, state)

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await safe(callback)
    await state.clear()
    await show_main(callback, is_callback=True)

# ------------------------- ОСТАЛЬНЫЕ АДМИН-КОМАНДЫ -------------------------
@dp.message(Command("stats"))
async def cmd_stats(message: Message, state: FSMContext):
    await state.clear()
    if message.from_user.id != ADMIN_ID:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            users = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM purchases") as cur:
            paid = (await cur.fetchone())[0]
        async with db.execute("SELECT SUM(amount) FROM purchases") as cur:
            rev = (await cur.fetchone())[0] or 0
        async with db.execute("SELECT SUM(coins) FROM users") as cur:
            coins = (await cur.fetchone())[0] or 0
        async with db.execute("SELECT SUM(dollars) FROM users") as cur:
            usd = (await cur.fetchone())[0] or 0.0
    await safe_send_message(message.from_user.id, f"📊 Статистика:\n👥 {users}\n🚀 В клубе: {paid}\n💰 Выручка: {rev}$\n🪙 IKY в обороте: {coins}\n💵 $ к выплате: {usd:.2f}$")

@dp.message(Command("users"))
async def cmd_users(message: Message, state: FSMContext):
    await state.clear()
    if message.from_user.id != ADMIN_ID:
        return
    rows = await all_users()
    if not rows:
        await safe_send_message(message.from_user.id, "Пусто.")
        return
    text = "👥 Пользователи:\n"
    for uid, uname, fname, coins, usd in rows:
        name = fname or uname or str(uid)
        text += f"{uid} {name} | 🪙{coins} | 💵{usd:.2f}$\n"
    await safe_send_message(message.from_user.id, text)

@dp.message(Command("give"))
async def cmd_give(message: Message, state: FSMContext):
    await state.clear()
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) != 2:
        await safe_send_message(message.from_user.id, "Использование: /give USER_ID")
        return
    try:
        uid = int(parts[1])
        if await has_access(uid):
            await safe_send_message(message.from_user.id, "Уже есть доступ.")
            return
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("REPLACE INTO purchases (user_id, paid_at, amount) VALUES (?,?,?)", (uid, datetime.now().isoformat(), 0))
            await db.commit()
        if await get_remaining_slots() > 0:
            await decrease_slots()
        await safe_send_message(uid, f"✅ Доступ в IKNOWYOU — AI активирован!\n\n🔗 {AI_FORUM_INVITE_LINK}")
        await safe_send_message(message.from_user.id, f"✅ Выдано {uid}")
    except Exception as e:
        await safe_send_message(message.from_user.id, f"❌ {e}")

async def admin_balance_cmd(message: Message, is_coins: bool, sign: int, state: FSMContext):
    await state.clear()
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) != 3:
        await safe_send_message(message.from_user.id, "Использование: /команда USER_ID СУММА")
        return
    try:
        uid = int(parts[1])
        val = float(parts[2])
        if val <= 0:
            await safe_send_message(message.from_user.id, "Сумма > 0")
            return
        if sign == -1:
            ok = await deduct_balance(uid, coins=int(val) if is_coins else 0, usd=val if not is_coins else 0.0)
            if not ok:
                await safe_send_message(message.from_user.id, "Недостаточно средств")
                return
        else:
            if is_coins:
                await add_balance(uid, coins=int(val))
            else:
                await add_balance(uid, usd=val)
        await safe_send_message(message.from_user.id, f"✅ Баланс {uid} обновлён")
    except:
        await safe_send_message(message.from_user.id, "Ошибка")

@dp.message(Command("addcoins"))
async def cmd_addcoins(m: Message, state: FSMContext): await admin_balance_cmd(m, True, 1, state)
@dp.message(Command("rmcoins"))
async def cmd_rmcoins(m: Message, state: FSMContext): await admin_balance_cmd(m, True, -1, state)
@dp.message(Command("addusd"))
async def cmd_addusd(m: Message, state: FSMContext): await admin_balance_cmd(m, False, 1, state)
@dp.message(Command("rmusd"))
async def cmd_rmusd(m: Message, state: FSMContext): await admin_balance_cmd(m, False, -1, state)

# ------------------------- KEEP-ALIVE -------------------------
async def keep_alive():
    while True:
        await asyncio.sleep(300)
        print("🔄 Бот жив...")

# ------------------------- ЗАПУСК -------------------------
async def main():
    logging.basicConfig(level=logging.INFO)
    print(f"🚀 {STUDIO_NAME} запущен")
    
    asyncio.create_task(keep_alive())
    asyncio.create_task(poll_invoices(bot))
    asyncio.create_task(backup_scheduler())
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"❌ Бот упал: {e}")
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
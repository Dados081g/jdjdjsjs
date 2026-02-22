import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import sqlite3
from datetime import datetime
import os

# ========== НАСТРОЙКИ ==========
TOKEN = "YOUR_BOT_TOKEN_HERE"  # Замени на свой токен
ADMIN_IDS = [123456789]  # Замени на свой Telegram ID
# ================================

# Состояния для ConversationHandler
WAITING_FOR_KEY = 1
WAITING_FOR_USER_ID_BALANCE = 2
WAITING_FOR_AMOUNT = 3
WAITING_FOR_USER_ID_BAN = 4

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== РАБОТА С БАЗОЙ ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect("shop.db")
    c = conn.cursor()
    
    # Таблица пользователей
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, 
                  balance INTEGER DEFAULT 0,
                  is_banned INTEGER DEFAULT 0)''')
    
    # Таблица ключей
    c.execute('''CREATE TABLE IF NOT EXISTS keys
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  key TEXT UNIQUE,
                  product TEXT,
                  duration TEXT,
                  is_sold INTEGER DEFAULT 0)''')
    
    # Таблица покупок
    c.execute('''CREATE TABLE IF NOT EXISTS purchases
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  product TEXT,
                  duration TEXT,
                  key TEXT,
                  price INTEGER,
                  date TEXT)''')
    
    conn.commit()
    conn.close()

def get_user_balance(user_id):
    conn = sqlite3.connect("shop.db")
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def update_balance(user_id, amount):
    conn = sqlite3.connect("shop.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def is_banned(user_id):
    conn = sqlite3.connect("shop.db")
    c = conn.cursor()
    c.execute("SELECT is_banned FROM users WHERE user_id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def ban_user(user_id):
    conn = sqlite3.connect("shop.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    c.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def unban_user(user_id):
    conn = sqlite3.connect("shop.db")
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def add_key(key, product, duration):
    conn = sqlite3.connect("shop.db")
    c = conn.cursor()
    try:
        c.execute("INSERT INTO keys (key, product, duration) VALUES (?, ?, ?)", 
                  (key, product, duration))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

def get_key(product, duration):
    conn = sqlite3.connect("shop.db")
    c = conn.cursor()
    c.execute("SELECT id, key FROM keys WHERE product=? AND duration=? AND is_sold=0 LIMIT 1", 
              (product, duration))
    result = c.fetchone()
    if result:
        c.execute("UPDATE keys SET is_sold=1 WHERE id=?", (result[0],))
        conn.commit()
        conn.close()
        return result[1]
    conn.close()
    return None

def add_purchase(user_id, product, duration, key, price):
    conn = sqlite3.connect("shop.db")
    c = conn.cursor()
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO purchases (user_id, product, duration, key, price, date) VALUES (?, ?, ?, ?, ?, ?)",
              (user_id, product, duration, key, price))
    conn.commit()
    conn.close()

# ========== ТОВАРЫ И ЦЕНЫ ==========
PRODUCTS = {
    "android": {
        "name": "📱 Android",
        "items": {
            "zolo": {
                "name": "Zolo",
                "prices": {"1D": 169, "3D": 399, "7D": 799}
            },
            "dex o": {
                "name": "Dex O",
                "prices": {"1D": 169, "3D": 399, "7D": 799}
            },
            "zmod": {
                "name": "Zmod",
                "prices": {"1D": 149, "3D": 350, "7D": 500}
            },
            "jarvis": {
                "name": "Jarvis",
                "prices": {"1D": 139, "3D": 299, "7D": 500}
            }
        }
    },
    "ios": {
        "name": "🍏 iOS",
        "items": {
            "star": {
                "name": "Star",
                "prices": {"1D": 179, "7D": 699}
            },
            "jarvis": {
                "name": "Jarvis",
                "prices": {"1D": 200, "7D": 999}
            }
        }
    },
    "pc": {
        "name": "💻 PC",
        "items": {
            "cerberus": {
                "name": "Cerberus",
                "prices": {"5H": 20, "1D": 120}
            }
        }
    }
}

# ========== ФУНКЦИИ БОТА ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Добавляем пользователя в БД
    conn = sqlite3.connect("shop.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()
    
    if is_banned(user_id):
        await update.message.reply_text("⛔ Вы забанены в боте.")
        return
    
    keyboard = [
        [InlineKeyboardButton("📱 Android", callback_data="cat_android")],
        [InlineKeyboardButton("🍏 iOS", callback_data="cat_ios")],
        [InlineKeyboardButton("💻 PC", callback_data="cat_pc")],
        [InlineKeyboardButton("👤 Профиль", callback_data="profile"),
         InlineKeyboardButton("📞 Поддержка", url="https://t.me/username")]  # Замени на свой username
    ]
    
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("⚙️ Админ панель", callback_data="admin")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🛒 *Добро пожаловать в магазин ключей!*\n\nВыберите категорию:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if is_banned(user_id):
        await query.edit_message_text("⛔ Вы забанены в боте.")
        return
    
    data = query.data
    
    # Обработка категорий
    if data.startswith("cat_"):
        cat = data[4:]
        category = PRODUCTS.get(cat)
        if not category:
            return
        
        keyboard = []
        for item_id, item in category["items"].items():
            keyboard.append([InlineKeyboardButton(
                f"{item['name']}", 
                callback_data=f"item_{cat}_{item_id}"
            )])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"{category['name']}\n\nВыберите товар:",
            reply_markup=reply_markup
        )
    
    # Обработка товаров
    elif data.startswith("item_"):
        _, cat, item_id = data.split("_")
        category = PRODUCTS.get(cat)
        item = category["items"].get(item_id)
        
        if not item:
            return
        
        context.user_data["current_cat"] = cat
        context.user_data["current_item"] = item_id
        
        keyboard = []
        for duration, price in item["prices"].items():
            keyboard.append([InlineKeyboardButton(
                f"{duration} - {price} руб", 
                callback_data=f"buy_{duration}"
            )])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=f"cat_{cat}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"*{item['name']}*\n\nВыберите срок:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    # Обработка покупки
    elif data.startswith("buy_"):
        duration = data[4:]
        cat = context.user_data.get("current_cat")
        item_id = context.user_data.get("current_item")
        
        if not cat or not item_id:
            await query.edit_message_text("Ошибка. Попробуйте снова.")
            return
        
        item = PRODUCTS[cat]["items"][item_id]
        price = item["prices"].get(duration)
        
        if not price:
            await query.edit_message_text("Ошибка цены.")
            return
        
        # Проверяем баланс
        balance = get_user_balance(user_id)
        
        if balance < price:
            await query.edit_message_text(
                f"❌ Недостаточно средств!\n\n"
                f"Ваш баланс: {balance} руб\n"
                f"Нужно: {price} руб\n\n"
                f"Пополните баланс у администратора."
            )
            return
        
        # Ищем ключ
        product_name = f"{cat}_{item_id}"
        key = get_key(product_name, duration)
        
        if not key:
            await query.edit_message_text("❌ Ключи закончились. Обратитесь к администратору.")
            return
        
        # Списываем баланс и записываем покупку
        update_balance(user_id, -price)
        add_purchase(user_id, item["name"], duration, key, price)
        
        # Отправляем ключ
        await query.edit_message_text(
            f"✅ *Покупка успешна!*\n\n"
            f"Товар: {item['name']}\n"
            f"Срок: {duration}\n"
            f"Цена: {price} руб\n"
            f"Остаток: {get_user_balance(user_id)} руб\n\n"
            f"🔑 *Ключ:* `{key}`\n\n"
            f"Ключ скопирован. Нажмите чтобы скопировать.",
            parse_mode="Markdown"
        )
    
    # Профиль
    elif data == "profile":
        balance = get_user_balance(user_id)
        
        # Статистика покупок
        conn = sqlite3.connect("shop.db")
        c = conn.cursor()
        c.execute("SELECT COUNT(*), SUM(price) FROM purchases WHERE user_id=?", (user_id,))
        purchases_count, total_spent = c.fetchone()
        conn.close()
        
        if not total_spent:
            total_spent = 0
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"👤 *Ваш профиль*\n\n"
            f"🆔 ID: `{user_id}`\n"
            f"💰 Баланс: {balance} руб\n"
            f"📊 Всего покупок: {purchases_count}\n"
            f"💸 Потрачено: {total_spent} руб",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    # Админ панель
    elif data == "admin":
        if user_id not in ADMIN_IDS:
            await query.edit_message_text("⛔ Доступ запрещен.")
            return
        
        keyboard = [
            [InlineKeyboardButton("💰 Выдать баланс", callback_data="admin_balance")],
            [InlineKeyboardButton("🔑 Загрузить ключи", callback_data="admin_keys")],
            [InlineKeyboardButton("⛔ Забанить пользователя", callback_data="admin_ban")],
            [InlineKeyboardButton("✅ Разбанить пользователя", callback_data="admin_unban")],
            [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⚙️ *Админ панель*\n\nВыберите действие:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    # Админ: запрос ID для выдачи баланса
    elif data == "admin_balance":
        if user_id not in ADMIN_IDS:
            return
        
        await query.edit_message_text(
            "💰 Введите ID пользователя, которому хотите выдать баланс:"
        )
        return WAITING_FOR_USER_ID_BALANCE
    
    # Админ: загрузка ключей
    elif data == "admin_keys":
        if user_id not in ADMIN_IDS:
            return
        
        await query.edit_message_text(
            "🔑 Отправьте ключи в формате:\n"
            "`товар_срок ключ`\n\n"
            "Примеры:\n"
            "`android_zolo_1D ABC123`\n"
            "`ios_star_7D XYZ789`\n"
            "`pc_cerberus_5H KEY123`\n\n"
            "Доступные товары:\n"
            "android_zolo, android_dex o, android_zmod, android_jarvis,\n"
            "ios_star, ios_jarvis, pc_cerberus\n"
            "Сроки: 1D, 3D, 7D, 5H"
        )
        return WAITING_FOR_KEY
    
    # Админ: бан пользователя
    elif data == "admin_ban":
        if user_id not in ADMIN_IDS:
            return
        
        await query.edit_message_text("⛔ Введите ID пользователя для бана:")
        return WAITING_FOR_USER_ID_BAN
    
    # Админ: разбан пользователя
    elif data == "admin_unban":
        if user_id not in ADMIN_IDS:
            return
        
        await query.edit_message_text("✅ Введите ID пользователя для разбана:")
        context.user_data["unban"] = True
        return WAITING_FOR_USER_ID_BAN
    
    # Админ: статистика
    elif data == "admin_stats":
        if user_id not in ADMIN_IDS:
            return
        
        conn = sqlite3.connect("shop.db")
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM users WHERE is_banned=1")
        banned_users = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM purchases")
        total_purchases = c.fetchone()[0]
        
        c.execute("SELECT SUM(price) FROM purchases")
        total_earned = c.fetchone()[0] or 0
        
        c.execute("SELECT COUNT(*) FROM keys WHERE is_sold=0")
        keys_left = c.fetchone()[0]
        
        conn.close()
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"📊 *Статистика бота*\n\n"
            f"👥 Всего пользователей: {total_users}\n"
            f"⛔ Забанено: {banned_users}\n"
            f"🛒 Всего покупок: {total_purchases}\n"
            f"💰 Заработано: {total_earned} руб\n"
            f"🔑 Осталось ключей: {keys_left}",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    # Назад в главное меню
    elif data == "back_to_main":
        keyboard = [
            [InlineKeyboardButton("📱 Android", callback_data="cat_android")],
            [InlineKeyboardButton("🍏 iOS", callback_data="cat_ios")],
            [InlineKeyboardButton("💻 PC", callback_data="cat_pc")],
            [InlineKeyboardButton("👤 Профиль", callback_data="profile"),
             InlineKeyboardButton("📞 Поддержка", url="https://t.me/username")]
        ]
        
        if user_id in ADMIN_IDS:
            keyboard.append([InlineKeyboardButton("⚙️ Админ панель", callback_data="admin")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🛒 *Добро пожаловать в магазин ключей!*\n\nВыберите категорию:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

# ========== ОБРАБОТЧИКИ СОСТОЯНИЙ ==========
async def handle_key_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен.")
        return ConversationHandler.END
    
    text = update.message.text.strip()
    lines = text.split("\n")
    
    success = 0
    errors = 0
    
    for line in lines:
        parts = line.split()
        if len(parts) < 2:
            errors += 1
            continue
        
        product_duration = parts[0]
        key = parts[1]
        
        # Парсим формат "товар_срок"
        if "_" not in product_duration:
            errors += 1
            continue
        
        last_underscore = product_duration.rfind("_")
        product = product_duration[:last_underscore]
        duration = product_duration[last_underscore + 1:]
        
        # Заменяем пробел на подчеркивание для товаров с пробелом
        product = product.replace(" ", "_")
        
        if add_key(key, product, duration):
            success += 1
        else:
            errors += 1
    
    await update.message.reply_text(
        f"✅ Загружено ключей: {success}\n"
        f"❌ Ошибок: {errors}"
    )
    
    return ConversationHandler.END

async def handle_user_id_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен.")
        return ConversationHandler.END
    
    try:
        target_id = int(update.message.text.strip())
        context.user_data["target_id"] = target_id
        
        await update.message.reply_text("💰 Введите сумму для начисления:")
        return WAITING_FOR_AMOUNT
    except:
        await update.message.reply_text("❌ Неверный ID. Попробуйте снова.")
        return ConversationHandler.END

async def handle_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен.")
        return ConversationHandler.END
    
    try:
        amount = int(update.message.text.strip())
        target_id = context.user_data.get("target_id")
        
        if not target_id:
            await update.message.reply_text("❌ Ошибка. Попробуйте снова.")
            return ConversationHandler.END
        
        update_balance(target_id, amount)
        
        await update.message.reply_text(
            f"✅ Баланс пользователя {target_id} пополнен на {amount} руб."
        )
        
        # Уведомляем пользователя
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"💰 Ваш баланс пополнен на {amount} руб."
            )
        except:
            pass
        
        return ConversationHandler.END
    except:
        await update.message.reply_text("❌ Неверная сумма.")
        return ConversationHandler.END

async def handle_user_id_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен.")
        return ConversationHandler.END
    
    try:
        target_id = int(update.message.text.strip())
        unban = context.user_data.get("unban", False)
        
        if unban:
            unban_user(target_id)
            await update.message.reply_text(f"✅ Пользователь {target_id} разбанен.")
            
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text="✅ Вы были разбанены."
                )
            except:
                pass
        else:
            ban_user(target_id)
            await update.message.reply_text(f"⛔ Пользователь {target_id} забанен.")
            
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text="⛔ Вы б
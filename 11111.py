import os
import json
import logging
import threading
import time
import hashlib
import random
from datetime import datetime, timedelta
from telebot import TeleBot, types
import requests

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = "8284278177:AAFUhbFCp2gGWVl1GdeECDXEcS7S26SK55k"
ADMIN_IDS = [8444147514, 6445747495, 5254643087, 8545308691]
STAR_RATE = 0.017625
UAH_RATE = 40.0
MIN_STARS = 50
MIN_WITHDRAW_STARS = 80
WITHDRAW_FEE_PERCENT = 5
TON_WALLET = "UQDxRhtfxm9sgAvg-YufVUwoLjz2mBU96pmMKaF2BKWsJccJ"
MONOBANK_CARD = "4441114437906025"
REFERRAL_PERCENT = 5
REFERRAL_SIGNUP_BONUS = 2
REFERRAL_PURCHASE_BONUS = 5
DATA_FILE = "bot_data0111111111.json"
CHANNEL_USERNAME = "Vlshop_News"
CHANNEL_URL = f"https://t.me/{CHANNEL_USERNAME}"
CHANNEL_ID = "@Vlshop_News"
SUPPORT_URL = "https://t.me/VLShopSupport"

# Ссылки для оплаты Premium через Crypto Bot
PREMIUM_LINKS = {
    "3": "https://t.me/send?start=IVGtG7zlsFz2",  # 12.99$
    "6": "https://t.me/send?start=IVOkXh2xOLmI",  # 17.99$
    "12": "https://t.me/send?start=IVgUNsURAUmC"  # 31.99$
}

# Ссылка для оплаты звезд через Crypto Bot
CRYPTO_STARS_LINK = "https://t.me/send?start=IVTN3DCFDsnc"

bot = TeleBot(BOT_TOKEN)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

BROADCAST_MESSAGES = [
    {
        "delay_hours": 1,
        "text": "⭐️ Кстати, если планировал покупать Звёзды — у нас цены часто ниже, чем в самом Telegram.\n\nМожно просто сравнить и решить, где удобнее 👌"
    },
    {
        "delay_hours": 6,
        "text": "💰 Небольшой бонус:\n\nВ VL Shop есть партнёрская программа — можно приглашать друзей и получать ⭐️ на баланс.\n\nПодробности — в разделе «Заработать звезды»"
    }
]


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def check_channel_subscription(user_id):
    """Проверка подписки на канал"""
    try:
        chat_member = bot.get_chat_member(CHANNEL_ID, user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logging.error(f"Ошибка при проверке подписки {user_id}: {e}")
        return True  # Возвращаем True в случае ошибки, чтобы не блокировать пользователя


def escape_markdown_v2(text):
    """Экранирование для MarkdownV2"""
    if text is None:
        return ""
    text = str(text)
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


def escape_markdown(text):
    """Экранирование для обычного Markdown"""
    if text is None:
        return ""
    return str(text).replace('*', '\\*').replace('_', '\\_').replace('`', '\\`').replace('[', '\\[')


def update_uah_rate():
    """Обновление курса UAH к USD"""
    global UAH_RATE
    try:
        response = requests.get('https://api.exchangerate-api.com/v4/latest/USD', timeout=10)
        if response.status_code == 200:
            data = response.json()
            UAH_RATE = data['rates']['UAH']
            logging.info(f"Курс обновлен: 1 USD = {UAH_RATE} UAH")
            return UAH_RATE
    except Exception as e:
        logging.error(f"Ошибка при обновлении курса: {e}")
    return UAH_RATE


# ========== РАБОТА С БАЗОЙ ДАННЫХ ==========

def init_db():
    """Инициализация базы данных"""
    default_data = {
        "users": {},
        "orders": [],
        "referral_earnings": [],
        "banned_users": [],
        "admin_logs": [],
        "user_sessions": {},
        "withdrawals": [],
        "broadcast_sent": {},
        "system": {
            "last_backup": None,
            "total_processed": 0,
            "last_user_id": 0
        }
    }

    try:
        if not os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_data, f, ensure_ascii=False, indent=2)
            logging.info(f"Создан новый файл базы данных: {DATA_FILE}")
        else:
            # Проверяем структуру существующей БД
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)

            # Добавляем отсутствующие ключи
            for key, value in default_data.items():
                if key not in existing_data:
                    existing_data[key] = value
                    logging.info(f"Добавлен ключ {key} в БД")

            # Сохраняем обновленную БД
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)

        return load_data()

    except Exception as e:
        logging.error(f"Ошибка при инициализации БД: {e}")
        return default_data


def load_data():
    """Загрузка данных из файла"""
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Проверяем и добавляем отсутствующие поля
        required_keys = ["users", "orders", "referral_earnings", "banned_users",
                         "admin_logs", "user_sessions", "withdrawals", "broadcast_sent"]

        for key in required_keys:
            if key not in data:
                data[key] = {}
                logging.info(f"Добавлен ключ {key} в загруженные данные")

        return data
    except Exception as e:
        logging.error(f"Ошибка при загрузке данных: {e}")
        return init_db()


def save_data(data):
    """Сохранение данных в файл"""
    try:
        # Создаем временную копию для безопасности
        temp_file = DATA_FILE + ".tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # Заменяем основной файл
        os.replace(temp_file, DATA_FILE)

    except Exception as e:
        logging.error(f"Ошибка при сохранении данных: {e}")


# ========== РАСЧЕТЫ ==========

def calculate_price(stars, method=None):
    """Расчет цены звезд"""
    usd_price = stars * STAR_RATE
    uah_price = usd_price * UAH_RATE

    if method == "monobank":
        uah_price *= 1.03  # +3% комиссия для monobank

    return {
        "usd": round(usd_price, 3),
        "uah": round(uah_price, 2),
        "stars": stars
    }


def calculate_withdraw(stars):
    """Расчет суммы вывода с учетом комиссии"""
    usd_amount = stars * STAR_RATE
    fee = usd_amount * (WITHDRAW_FEE_PERCENT / 100)
    net_amount = usd_amount - fee

    return {
        "stars": stars,
        "usd_amount": round(usd_amount, 2),
        "fee_percent": WITHDRAW_FEE_PERCENT,
        "fee_amount": round(fee, 2),
        "net_amount": round(net_amount, 2)
    }


# ========== ЛОГИРОВАНИЕ ==========

def add_admin_log(admin_id, action, details):
    """Добавление лога администратора"""
    data = load_data()

    log_entry = {
        "id": len(data["admin_logs"]) + 1,
        "admin_id": admin_id,
        "action": action,
        "details": details,
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    data["admin_logs"].append(log_entry)
    save_data(data)


# ========== РЕФЕРАЛЬНАЯ СИСТЕМА ==========

def generate_referral_code(user_id):
    """Генерация уникального реферального кода"""
    seed = f"{user_id}{time.time()}{random.randint(1000, 9999)}"
    code = hashlib.md5(seed.encode()).hexdigest()[:8].upper()
    return code


def generate_crypto_payment_link(user_id, amount, stars, product_type="stars"):
    """Генерация ссылки для оплаты через Crypto Bot"""
    comment_id = random.randint(1000000, 9999999)

    if product_type == "stars":
        comment = f"stars_{user_id}_{stars}stars_{comment_id}"
        link = CRYPTO_STARS_LINK
    elif product_type.startswith("premium_"):
        premium_code = product_type.split("_")[1] if "_" in product_type else "3"
        link = PREMIUM_LINKS.get(premium_code, PREMIUM_LINKS["3"])
        comment = f"premium_{user_id}_{premium_code}months_{comment_id}"
    else:
        comment = f"other_{user_id}_{amount}${comment_id}"
        link = CRYPTO_STARS_LINK

    return link, comment


# ========== РАБОТА С ПОЛЬЗОВАТЕЛЯМИ ==========

def get_or_create_user(user_id, username=None, first_name=None, last_name=None):
    """Получение или создание пользователя"""
    data = load_data()
    user_id_str = str(user_id)

    if user_id_str not in data["users"]:
        # Создаем нового пользователя
        referral_code = generate_referral_code(user_id)

        data["users"][user_id_str] = {
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "balance": 0,
            "total_earned": 0,
            "referral_code": referral_code,
            "referred_by": None,
            "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "is_banned": False,
            "ban_reason": None,
            "withdraw_balance": 0.0,
            "total_withdrawn": 0.0,
            "last_activity": datetime.now().isoformat(),
            "last_purchase": None,
            "total_purchases": 0,
            "total_spent": 0.0
        }
        save_data(data)
        logging.info(f"Создан новый пользователь: {user_id} (@{username})")

        return data["users"][user_id_str]
    else:
        # Обновляем существующего пользователя
        user_data = data["users"][user_id_str]
        updated = False

        if username and user_data.get("username") != username:
            user_data["username"] = username
            updated = True

        if first_name and user_data.get("first_name") != first_name:
            user_data["first_name"] = first_name
            updated = True

        if last_name and user_data.get("last_name") != last_name:
            user_data["last_name"] = last_name
            updated = True

        user_data["last_activity"] = datetime.now().isoformat()

        if updated:
            save_data(data)

        return user_data


def process_referral_signup(referral_code, new_user_id):
    """Обработка регистрации по реферальной ссылке"""
    if not referral_code:
        return False

    data = load_data()
    new_user_id_str = str(new_user_id)

    # Ищем реферера по коду
    referrer_id = None
    for uid, user in data["users"].items():
        if user.get("referral_code") == referral_code:
            referrer_id = int(uid)
            break

    if not referrer_id or referrer_id == new_user_id:
        return False

    # Устанавливаем реферера для нового пользователя
    if new_user_id_str in data["users"]:
        data["users"][new_user_id_str]["referred_by"] = referral_code
        save_data(data)

        # Начисляем бонус рефереру
        add_referral_signup_bonus(referrer_id, new_user_id)
        logging.info(f"Начислен бонус за регистрацию: {referrer_id} <- {new_user_id}")
        return True

    return False


def add_referral_signup_bonus(referrer_id, referral_id):
    """Добавляем бонус за регистрацию реферала"""
    data = load_data()
    referrer_id_str = str(referrer_id)

    if referrer_id_str in data["users"]:
        stars_earned = REFERRAL_SIGNUP_BONUS
        usd_earned = stars_earned * STAR_RATE

        data["users"][referrer_id_str]["balance"] += stars_earned
        data["users"][referrer_id_str]["total_earned"] += stars_earned
        data["users"][referrer_id_str]["withdraw_balance"] += usd_earned

        data["referral_earnings"].append({
            "id": len(data["referral_earnings"]) + 1,
            "referrer_id": referrer_id,
            "referral_id": referral_id,
            "order_id": None,
            "stars_earned": stars_earned,
            "usd_earned": round(usd_earned, 2),
            "amount": 0,
            "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "type": "signup_bonus"
        })

        save_data(data)

        try:
            bot.send_message(
                referrer_id,
                f"🎉 *У вас новый реферал!*\n\n"
                f"👤 Новый пользователь зашел по вашей ссылке\n"
                f"⭐ Вам начислено: {stars_earned} звезд\n"
                f"💰 В долларах: ${usd_earned:.2f}\n\n"
                f"💫 Текущий баланс: {get_user_balance(referrer_id)} звезд\n"
                f"💵 Баланс для вывода: ${get_user_withdraw_balance(referrer_id):.2f}\n\n"
                f"Если реферал совершит покупку, вы получите ещё {REFERRAL_PURCHASE_BONUS} звезд!",
                parse_mode='Markdown'
            )
        except Exception as e:
            logging.error(f"Не удалось отправить уведомление рефереру {referrer_id}: {e}")


def process_referral_earnings(referral_id, order_id, stars_purchased, amount):
    """Начисление бонуса рефереру за покупку реферала"""
    data = load_data()
    referral_id_str = str(referral_id)

    if referral_id_str in data["users"]:
        referrer_code = data["users"][referral_id_str].get("referred_by")

        if referrer_code:
            referrer_id = None
            for uid, user in data["users"].items():
                if user.get("referral_code") == referrer_code:
                    referrer_id = int(uid)
                    break

            if referrer_id:
                stars_earned = REFERRAL_PURCHASE_BONUS
                usd_earned = stars_earned * STAR_RATE

                referrer_id_str = str(referrer_id)
                data["users"][referrer_id_str]["balance"] += stars_earned
                data["users"][referrer_id_str]["total_earned"] += stars_earned
                data["users"][referrer_id_str]["withdraw_balance"] += usd_earned

                data["referral_earnings"].append({
                    "id": len(data["referral_earnings"]) + 1,
                    "referrer_id": referrer_id,
                    "referral_id": referral_id,
                    "order_id": order_id,
                    "stars_earned": stars_earned,
                    "usd_earned": round(usd_earned, 2),
                    "amount": amount,
                    "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "type": "purchase_bonus"
                })

                save_data(data)

                try:
                    bot.send_message(
                        referrer_id,
                        f"🎉 *Вы получили реферальный бонус!*\n\n"
                        f"👤 Ваш реферал совершил покупку\n"
                        f"⭐ Заработано звезд: {stars_earned}\n"
                        f"💰 Заработано в $: {usd_earned:.2f}\n"
                        f"💵 Сумма покупки: {amount:.2f}$\n\n"
                        f"💫 Ваш текущий баланс: {get_user_balance(referrer_id)} звезд\n"
                        f"💵 Баланс для вывода: {get_user_withdraw_balance(referrer_id):.2f}$",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logging.error(f"Не удалось отправить уведомление рефереру {referrer_id}: {e}")


# ========== БАЛАНСЫ ==========

def update_user_balance(user_id, stars, add=True):
    """Обновление баланса звезд пользователя"""
    data = load_data()
    user_id_str = str(user_id)

    if user_id_str in data["users"]:
        if add:
            data["users"][user_id_str]["balance"] += stars
            data["users"][user_id_str]["total_earned"] += stars
        else:
            if data["users"][user_id_str]["balance"] >= stars:
                data["users"][user_id_str]["balance"] -= stars
            else:
                return False

        save_data(data)
        return True
    return False


def update_withdraw_balance(user_id, usd_amount, add=True):
    """Обновление баланса в долларах для вывода"""
    data = load_data()
    user_id_str = str(user_id)

    if user_id_str in data["users"]:
        if add:
            data["users"][user_id_str]["withdraw_balance"] += usd_amount
        else:
            if data["users"][user_id_str]["withdraw_balance"] >= usd_amount:
                data["users"][user_id_str]["withdraw_balance"] -= usd_amount
            else:
                return False

        if data["users"][user_id_str]["withdraw_balance"] < 0:
            data["users"][user_id_str]["withdraw_balance"] = 0

        save_data(data)
        return True
    return False


def get_user_balance(user_id):
    """Получение баланса звезд пользователя"""
    data = load_data()
    user = data["users"].get(str(user_id))
    return user.get("balance", 0) if user else 0


def get_user_withdraw_balance(user_id):
    """Получение баланса для вывода"""
    data = load_data()
    user = data["users"].get(str(user_id))
    return user.get("withdraw_balance", 0.0) if user else 0.0


def get_user_stats(user_id):
    """Получение статистики пользователя"""
    data = load_data()
    user_id_str = str(user_id)
    user = data["users"].get(user_id_str)

    if user:
        referrals_count = 0
        referral_code = user.get("referral_code")

        if referral_code:
            for uid, u in data["users"].items():
                if u.get("referred_by") == referral_code:
                    referrals_count += 1

        return {
            'balance': user.get("balance", 0),
            'total_earned': user.get("total_earned", 0),
            'referral_code': user.get("referral_code", ""),
            'referrals_count': referrals_count,
            'is_banned': user.get("is_banned", False),
            'ban_reason': user.get("ban_reason", ""),
            'withdraw_balance': user.get("withdraw_balance", 0.0),
            'total_withdrawn': user.get("total_withdrawn", 0.0),
            'total_purchases': user.get("total_purchases", 0),
            'total_spent': user.get("total_spent", 0.0)
        }

    return {
        'balance': 0,
        'total_earned': 0,
        'referral_code': "",
        'referrals_count': 0,
        'is_banned': False,
        'ban_reason': "",
        'withdraw_balance': 0.0,
        'total_withdrawn': 0.0,
        'total_purchases': 0,
        'total_spent': 0.0
    }


# ========== СЕССИИ ПОЛЬЗОВАТЕЛЕЙ ==========

def save_user_session(user_id, key, value):
    """Сохранение сессии пользователя"""
    data = load_data()
    user_id_str = str(user_id)

    if user_id_str not in data["user_sessions"]:
        data["user_sessions"][user_id_str] = {}

    data["user_sessions"][user_id_str][key] = {
        "value": value,
        "timestamp": datetime.now().isoformat()
    }
    save_data(data)


def get_user_session(user_id, key):
    """Получение сессии пользователя"""
    data = load_data()
    user_id_str = str(user_id)

    if user_id_str in data["user_sessions"]:
        if key in data["user_sessions"][user_id_str]:
            saved_time = datetime.fromisoformat(data["user_sessions"][user_id_str][key]["timestamp"])
            if (datetime.now() - saved_time).seconds < 3600:
                return data["user_sessions"][user_id_str][key]["value"]
            else:
                del data["user_sessions"][user_id_str][key]
                save_data(data)
    return None


def clear_user_session(user_id, key=None):
    """Очистка сессии пользователя"""
    data = load_data()
    user_id_str = str(user_id)

    if user_id_str in data["user_sessions"]:
        if key:
            if key in data["user_sessions"][user_id_str]:
                del data["user_sessions"][user_id_str][key]
        else:
            del data["user_sessions"][user_id_str]
        save_data(data)


# ========== БАН ПОЛЬЗОВАТЕЛЕЙ ==========

def is_user_banned(user_id):
    """Проверка, забанен ли пользователь"""
    data = load_data()
    user_id_str = str(user_id)

    if user_id_str in data["users"]:
        return data["users"][user_id_str].get("is_banned", False)
    return False


def ban_user(user_id, reason, admin_id):
    """Бан пользователя"""
    data = load_data()
    user_id_str = str(user_id)

    if user_id_str in data["users"]:
        data["users"][user_id_str]["is_banned"] = True
        data["users"][user_id_str]["ban_reason"] = reason

        if user_id not in data["banned_users"]:
            data["banned_users"].append(user_id)

        save_data(data)

        user_info = data["users"][user_id_str]
        add_admin_log(
            admin_id,
            "ban_user",
            f"Забанен пользователь {user_id} (@{user_info.get('username', 'без ника')}) по причине: {reason}"
        )

        return True
    return False


def unban_user(user_id, admin_id):
    """Разбан пользователя"""
    data = load_data()
    user_id_str = str(user_id)

    if user_id_str in data["users"]:
        data["users"][user_id_str]["is_banned"] = False
        data["users"][user_id_str]["ban_reason"] = None

        if user_id in data["banned_users"]:
            data["banned_users"].remove(user_id)

        save_data(data)

        user_info = data["users"][user_id_str]
        add_admin_log(
            admin_id,
            "unban_user",
            f"Разбанен пользователь {user_id} (@{user_info.get('username', 'без ника')})"
        )

        return True
    return False


# ========== ЗАКАЗЫ ==========

def create_order(user_id, user_name, recipient, stars, amount, method, premium_duration=None):
    """Создание нового заказа"""
    data = load_data()

    order_id = len(data["orders"]) + 1

    order = {
        "id": order_id,
        "user_id": user_id,
        "user_name": user_name,
        "recipient": recipient,
        "stars": stars,
        "amount": amount,
        "currency": "UAH" if method == "monobank" else "USD",
        "payment_method": method,
        "payment_proof": "",
        "payment_photo_id": "",
        "status": "pending",
        "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "premium_duration": premium_duration,
        "uah_rate": UAH_RATE if method == "monobank" else None
    }

    data["orders"].append(order)

    # Обновляем статистику пользователя
    user_id_str = str(user_id)
    if user_id_str in data["users"]:
        data["users"][user_id_str]["total_purchases"] = data["users"][user_id_str].get("total_purchases", 0) + 1
        data["users"][user_id_str]["total_spent"] = data["users"][user_id_str].get("total_spent", 0.0) + amount
        data["users"][user_id_str]["last_purchase"] = datetime.now().isoformat()

    save_data(data)

    return order_id


def update_order(order_id, updates):
    """Обновление заказа"""
    data = load_data()

    for order in data["orders"]:
        if order["id"] == order_id:
            order.update(updates)
            save_data(data)
            return True

    return False


def get_order(order_id):
    """Получение заказа по ID"""
    data = load_data()

    for order in data["orders"]:
        if order["id"] == order_id:
            return order

    return None


def get_user_orders(user_id, limit=10):
    """Получение заказов пользователя"""
    data = load_data()
    user_orders = []

    for order in sorted(data["orders"], key=lambda x: x["id"], reverse=True):
        if order["user_id"] == user_id:
            user_orders.append(order)
            if len(user_orders) >= limit:
                break

    return user_orders


# ========== ВЫВОД СРЕДСТВ ==========

def add_withdrawal(user_id, stars, usd_amount, net_amount, fee):
    """Добавление заявки на вывод"""
    data = load_data()

    withdrawal_id = len(data["withdrawals"]) + 1

    withdrawal = {
        "id": withdrawal_id,
        "user_id": user_id,
        "stars": stars,
        "usd_amount": usd_amount,
        "net_amount": net_amount,
        "fee": fee,
        "status": "pending",
        "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "processed_at": None,
        "processed_by": None
    }

    data["withdrawals"].append(withdrawal)
    save_data(data)

    return withdrawal_id


def update_withdrawal(withdrawal_id, updates):
    """Обновление заявки на вывод"""
    data = load_data()

    for withdrawal in data["withdrawals"]:
        if withdrawal["id"] == withdrawal_id:
            withdrawal.update(updates)
            save_data(data)
            return True

    return False


# ========== УВЕДОМЛЕНИЯ АДМИНИСТРАТОРОВ ==========

def notify_admins(order):
    """Уведомление администраторов о новом заказе"""
    safe_user_name = escape_markdown(order.get("user_name", ""))
    safe_recipient = escape_markdown(order.get("recipient", ""))
    safe_proof = escape_markdown(order.get("payment_proof", ""))

    payment_methods = {
        "crypto": "💳 Crypto Bot",
        "ton": "⚡ TON",
        "monobank": "💳 Monobank",
        "balance": "💎 Баланс"
    }

    payment_text = payment_methods.get(order["payment_method"], order["payment_method"])

    product = f"{order['stars']} звезд"
    if order.get("premium_duration"):
        product = f"Telegram Premium ({order['premium_duration']})"

    amount_text = f"{order['amount']:.2f}{'₴' if order.get('currency') == 'UAH' else '$'}"

    message_text = (
        f"🛒 *Новый заказ*\n\n"
        f"📋 *ID*: #{order['id']}\n"
        f"👤 *Пользователь*: {safe_user_name}\n"
        f"🆔 *User ID*: {order['user_id']}\n"
        f"👥 *Получатель*: {safe_recipient}\n"
        f"⭐ *Количество звезд*: {order['stars']}\n"
        f"💰 *Сумма*: {amount_text}\n"
        f"🌍 *Товар*: {product}\n"
        f"🔗 *Оплата*: {payment_text}\n"
        f"📎 *Доказательство*: {safe_proof}\n\n"
        f"⏰ *Время*: {datetime.now().strftime('%H:%M:%S')}"
    )

    admin_markup = types.InlineKeyboardMarkup()
    btn_accept = types.InlineKeyboardButton("✅ Подтвердить", callback_data=f"accept_{order['id']}")
    btn_reject = types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{order['id']}")
    admin_markup.add(btn_accept, btn_reject)

    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, message_text, parse_mode='Markdown', reply_markup=admin_markup)
        except Exception as e:
            logging.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")


def notify_admins_with_photo(order, file_id):
    """Уведомление администраторов с фото"""
    safe_user_name = escape_markdown(order.get("user_name", ""))
    safe_recipient = escape_markdown(order.get("recipient", ""))

    product = f"{order['stars']} звезд"
    if order.get("premium_duration"):
        product = f"Telegram Premium ({order['premium_duration']})"

    payment_methods = {
        "crypto": "💳 Crypto Bot",
        "ton": "⚡ TON",
        "monobank": "💳 Monobank",
        "balance": "💎 Баланс"
    }

    payment_text = payment_methods.get(order["payment_method"], order["payment_method"])
    amount_text = f"{order['amount']:.2f}{'₴' if order.get('currency') == 'UAH' else '$'}"

    caption = (
        f"🛒 *Новый заказ*\n\n"
        f"📋 *ID*: #{order['id']}\n"
        f"👤 *Пользователь*: {safe_user_name}\n"
        f"🆔 *User ID*: {order['user_id']}\n"
        f"👥 *Получатель*: {safe_recipient}\n"
        f"⭐ *Количество звезд*: {order['stars']}\n"
        f"💰 *Сумма*: {amount_text}\n"
        f"🌍 *Товар*: {product}\n"
        f"🔗 *Оплата*: {payment_text}\n\n"
        f"⏰ *Время*: {datetime.now().strftime('%H:%M:%S')}"
    )

    admin_markup = types.InlineKeyboardMarkup()
    btn_accept = types.InlineKeyboardButton("✅ Подтвердить", callback_data=f"accept_{order['id']}")
    btn_reject = types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{order['id']}")
    admin_markup.add(btn_accept, btn_reject)

    for admin_id in ADMIN_IDS:
        try:
            bot.send_photo(admin_id, file_id, caption=caption, parse_mode='Markdown', reply_markup=admin_markup)
        except Exception as e:
            logging.error(f"Не удалось отправить фото админу {admin_id}: {e}")


def notify_admins_premium_order(order_id):
    """Уведомление администраторов о заказе Premium"""
    order = get_order(order_id)

    if not order:
        return

    message_text = (
        f"🛒 *Новый заказ Premium с баланса*\n\n"
        f"📋 *ID*: #{order_id}\n"
        f"👤 *Пользователь*: {escape_markdown(order['user_name'] or '')}\n"
        f"🆔 *User ID*: {order['user_id']}\n"
        f"👑 *Premium*: {order.get('premium_duration', 'Неизвестно')}\n"
        f"⭐ *Количество звезд*: {order['stars']}\n"
        f"💰 *Сумма*: {order['amount']:.3f}$ (оплачено балансом)\n"
        f"⏰ *Время*: {datetime.now().strftime('%H:%M:%S')}"
    )

    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, message_text, parse_mode='Markdown')
        except Exception as e:
            logging.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")


def notify_admins_balance_order(order_id):
    """Уведомление администраторов о заказе с баланса"""
    order = get_order(order_id)

    if not order:
        return

    message_text = (
        f"🛒 *Новый заказ с баланса*\n\n"
        f"📋 *ID*: #{order_id}\n"
        f"👤 *Пользователь*: {escape_markdown(order['user_name'] or '')}\n"
        f"🆔 *User ID*: {order['user_id']}\n"
        f"⭐ *Количество звезд*: {order['stars']}\n"
        f"💰 *Сумма*: {order['amount']:.3f}$ (оплачено балансом)\n"
        f"🌍 *Товар*: {order['stars']} звезд\n"
        f"⏰ *Время*: {datetime.now().strftime('%H:%M:%S')}"
    )

    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, message_text, parse_mode='Markdown')
        except Exception as e:
            logging.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")


def notify_admins_withdrawal(withdrawal_id):
    """Уведомление администраторов о новой заявке на вывод"""
    data = load_data()
    withdrawal = None

    for w in data["withdrawals"]:
        if w["id"] == withdrawal_id:
            withdrawal = w
            break

    if not withdrawal:
        return

    user_stats = get_user_stats(withdrawal["user_id"])
    username = user_stats.get('username', 'без ника')

    message_text = (
        f"💸 *Новая заявка на вывод*\n\n"
        f"📋 *ID*: #{withdrawal_id}\n"
        f"👤 *Пользователь*: @{escape_markdown(username)}\n"
        f"🆔 *User ID*: {withdrawal['user_id']}\n"
        f"⭐ *Звезд*: {withdrawal['stars']}\n"
        f"💰 *Сумма*: {withdrawal['usd_amount']:.2f}$\n"
        f"📊 *Комиссия*: {WITHDRAW_FEE_PERCENT}% ({withdrawal['fee']:.2f}$)\n"
        f"💵 *К выплате*: {withdrawal['net_amount']:.2f}$\n"
        f"⏰ *Время*: {withdrawal['created_at']}"
    )

    admin_markup = types.InlineKeyboardMarkup()
    btn_accept = types.InlineKeyboardButton("✅ Выплатить", callback_data=f"withdraw_accept_{withdrawal_id}")
    btn_reject = types.InlineKeyboardButton("❌ Отклонить", callback_data=f"withdraw_reject_{withdrawal_id}")
    admin_markup.add(btn_accept, btn_reject)

    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, message_text, parse_mode='Markdown', reply_markup=admin_markup)
        except Exception as e:
            logging.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")


# ========== РАССЫЛКА ==========

def send_broadcast_messages():
    """Функция для отправки рассылки пользователям"""
    while True:
        try:
            data = load_data()

            for user_id_str, user_data in data["users"].items():
                user_id = int(user_id_str)

                if user_data.get("is_banned", False):
                    continue

                last_activity_str = user_data.get("last_activity")
                if not last_activity_str:
                    continue

                last_activity = datetime.fromisoformat(last_activity_str)
                now = datetime.now()
                time_diff = now - last_activity

                for i, msg_info in enumerate(BROADCAST_MESSAGES):
                    delay_hours = msg_info["delay_hours"]

                    if time_diff >= timedelta(hours=delay_hours):
                        broadcast_key = f"broadcast_{i}_{user_id}"
                        if broadcast_key not in data.get("broadcast_sent", {}):
                            try:
                                bot.send_message(user_id, msg_info["text"], parse_mode='Markdown')

                                if "broadcast_sent" not in data:
                                    data["broadcast_sent"] = {}
                                data["broadcast_sent"][broadcast_key] = datetime.now().isoformat()
                                save_data(data)

                                logging.info(f"Отправлено сообщение {i} пользователю {user_id}")
                            except Exception as e:
                                logging.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")

        except Exception as e:
            logging.error(f"Ошибка в функции рассылки: {e}")

        time.sleep(60)


# ========== ОСНОВНЫЕ КОМАНДЫ ==========

@bot.message_handler(commands=['start'])
def start(message):
    """Обработка команды /start"""
    logging.info(f"Команда start от {message.from_user.id}: {message.text}")

    # Проверка подписки на канал
    if not check_channel_subscription(message.from_user.id):
        markup = types.InlineKeyboardMarkup()
        btn_subscribe = types.InlineKeyboardButton("📢 Подписаться на канал", url=CHANNEL_URL)
        btn_check = types.InlineKeyboardButton("✅ Я подписался", callback_data="check_subscription")
        markup.add(btn_subscribe, btn_check)

        bot.send_message(
            message.chat.id,
            "👋 *Добро пожаловать!*\n\n"
            "Для использования бота необходимо подписаться на наш канал с новостями и обновлениями.\n\n"
            "После подписки нажмите кнопку '✅ Я подписался'",
            parse_mode='Markdown',
            reply_markup=markup
        )
        return

    # Проверка бана
    if is_user_banned(message.from_user.id):
        user_stats = get_user_stats(message.from_user.id)
        bot.send_message(
            message.chat.id,
            f"❌ *Вы заблокированы!*\n\n"
            f"Причина блокировки: {escape_markdown(user_stats['ban_reason'])}\n\n"
            f"По вопросам обращайтесь в поддержку.",
            parse_mode='Markdown'
        )
        return

    # Получение или создание пользователя
    user = get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name
    )

    # Обработка реферальной ссылки
    args = message.text.split()
    if len(args) > 1:
        referral_code = args[1]
        logging.info(f"Реферальный код: {referral_code} от пользователя {message.from_user.id}")

        # Обрабатываем регистрацию по реферальной ссылке
        if referral_code != str(message.from_user.id):  # Нельзя пригласить самого себя
            process_referral_signup(referral_code, message.from_user.id)

    show_main_menu(message.chat.id, message.from_user.id)


@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def check_subscription(call):
    """Проверка подписки на канал"""
    if not check_channel_subscription(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Вы не подписаны на канал!")
        return

    bot.answer_callback_query(call.id, "✅ Спасибо за подписку!")

    # Имитируем команду /start
    start_message = type('obj', (object,), {
        'from_user': call.from_user,
        'text': '/start',
        'chat': type('obj', (object,), {'id': call.message.chat.id})()
    })
    start(start_message)


def show_main_menu(chat_id, user_id):
    """Показать главное меню"""
    if is_user_banned(user_id):
        return

    user_stats = get_user_stats(user_id)
    withdraw_balance = user_stats['withdraw_balance']

    has_withdrawable = withdraw_balance >= (MIN_WITHDRAW_STARS * STAR_RATE)

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🌟 Купить звезды", callback_data="buy_stars")
    btn2 = types.InlineKeyboardButton("👑 Купить Premium", callback_data="buy_premium")
    btn3 = types.InlineKeyboardButton("👤 Профиль", callback_data="profile")
    btn4 = types.InlineKeyboardButton("👨‍💻 Поддержка", url=SUPPORT_URL)
    btn5 = types.InlineKeyboardButton("📋 Мои заказы", callback_data="my_orders")
    btn6 = types.InlineKeyboardButton("📢 Наш канал", url=CHANNEL_URL)
    btn7 = types.InlineKeyboardButton("💰 Заработать звезды", callback_data="earn_stars")

    if has_withdrawable:
        btn8 = types.InlineKeyboardButton(f"💸 Вывод ${withdraw_balance:.2f}", callback_data="withdraw_menu")
        markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn8)
    else:
        markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7)

    bot.send_message(
        chat_id,
        "✨ *Добро пожаловать в VL Shop!*\n\n"
        "Здесь вы можете купить Telegram Звёзды и Premium по выгодным ценам "
        "и с быстрой обработкой заказов. Цены ниже, чем в самом приложении.\n\n"
        "Выберите нужный раздел ниже.",
        parse_mode='Markdown',
        reply_markup=markup
    )


# ========== ПРОФИЛЬ И РЕФЕРАЛЬНАЯ СИСТЕМА ==========

@bot.callback_query_handler(func=lambda call: call.data == "profile")
def show_profile(call):
    """Показать профиль пользователя"""
    if is_user_banned(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Вы заблокированы!")
        return

    user_stats = get_user_stats(call.from_user.id)
    withdraw_balance = user_stats['withdraw_balance']

    banned_status = "🚫 *Заблокирован*\n" if user_stats['is_banned'] else ""
    ban_reason = f"📝 *Причина блокировки:* {escape_markdown(user_stats['ban_reason'])}\n" if user_stats[
        'is_banned'] else ""

    withdraw_info = ""
    if user_stats['withdraw_balance'] > 0:
        min_usd_for_withdraw = MIN_WITHDRAW_STARS * STAR_RATE
        if user_stats['withdraw_balance'] >= min_usd_for_withdraw:
            withdraw_info = f"💵 *Доступно для вывода:* ${user_stats['withdraw_balance']:.2f}\n"
        else:
            withdraw_info = f"💵 *Баланс для вывода:* ${user_stats['withdraw_balance']:.2f} (минимум ${min_usd_for_withdraw:.2f})\n"

    if user_stats['total_withdrawn'] > 0:
        withdraw_info += f"💰 *Всего выведено:* ${user_stats['total_withdrawn']:.2f}\n"

    # Генерируем правильную реферальную ссылку
    bot_username = bot.get_me().username
    referral_link = f"https://t.me/{bot_username}?start={user_stats['referral_code']}"

    profile_text = (
        f"👤 *Ваш профиль*\n\n"
        f"{banned_status}{ban_reason}"
        f"🆔 *ID*: `{call.from_user.id}`\n"
        f"👤 *Имя*: {escape_markdown(call.from_user.first_name or '')} "
        f"{escape_markdown(call.from_user.last_name or '')}\n"
        f"📛 *Ник*: @{escape_markdown(call.from_user.username or 'Нет')}\n\n"
        f"⭐ *Баланс звезд*: {user_stats['balance']}\n"
        f"💰 *Всего заработано*: {user_stats['total_earned']} звезд\n"
        f"{withdraw_info}"
        f"👥 *Рефералов*: {user_stats['referrals_count']}\n"
        f"🛒 *Покупок*: {user_stats['total_purchases']}\n"
        f"💸 *Потрачено*: ${user_stats['total_spent']:.2f}\n\n"
        f"🔗 *Ваша реферальная ссылка:*\n"
        f"`{referral_link}`"
    )

    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")
    btn2 = types.InlineKeyboardButton("💰 Как заработать", callback_data="how_to_earn")

    if user_stats['withdraw_balance'] >= (MIN_WITHDRAW_STARS * STAR_RATE):
        btn3 = types.InlineKeyboardButton("💸 Вывод средств", callback_data="withdraw_menu")
        markup.add(btn1, btn2, btn3)
    else:
        markup.add(btn1, btn2)

    try:
        bot.edit_message_text(
            profile_text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=markup
        )
    except Exception as e:
        logging.error(f"Ошибка при редактировании профиля: {e}")
        bot.send_message(call.message.chat.id, profile_text, parse_mode='Markdown', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "earn_stars" or call.data == "how_to_earn")
def show_earn_stars(call):
    """Показать информацию о заработке звезд"""
    if is_user_banned(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Вы заблокированы!")
        return

    user_stats = get_user_stats(call.from_user.id)

    # Генерируем правильную реферальную ссылку
    bot_username = bot.get_me().username
    referral_link = f"https://t.me/{bot_username}?start={user_stats['referral_code']}"

    earn_text = (
        f"💰 *Партнерская программа*\n\n"
        f"Приглашайте людей и получаете:\n"
        f"• +{REFERRAL_SIGNUP_BONUS} звезды ⭐️ за каждого, кто зашел в бота\n"
        f"• +{REFERRAL_PURCHASE_BONUS} звезд ⭐️, если он совершил покупку\n\n"
        f"Ваша партнерская ссылка:\n"
        f"`{referral_link}`\n\n"
        f"📊 Статистика вашей партнёрки:\n"
        f"- Рефералов: {user_stats['referrals_count']}\n"
        f"- Баланс: {user_stats['balance']} ⭐️\n"
        f"- Всего заработано: {user_stats['total_earned']} ⭐️\n\n"
        f"Накопленные звёзды можно вывести или использовать в сервисе.\n"
        f"Минимальная сумма для вывода — {MIN_WITHDRAW_STARS} звезд"
    )

    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")
    btn2 = types.InlineKeyboardButton("👤 Профиль", callback_data="profile")

    if user_stats['withdraw_balance'] >= (MIN_WITHDRAW_STARS * STAR_RATE):
        btn3 = types.InlineKeyboardButton("💸 Вывод средств", callback_data="withdraw_menu")
        markup.add(btn1, btn2, btn3)
    else:
        markup.add(btn1, btn2)

    if call.data == "earn_stars":
        bot.send_message(call.message.chat.id, earn_text, parse_mode='Markdown', reply_markup=markup)
    else:
        try:
            bot.edit_message_text(
                earn_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=markup
            )
        except Exception as e:
            logging.error(f"Ошибка при редактировании сообщения: {e}")
            bot.send_message(call.message.chat.id, earn_text, parse_mode='Markdown', reply_markup=markup)


# ========== ПОКУПКА ЗВЕЗД ==========

@bot.callback_query_handler(func=lambda call: call.data == "buy_stars")
def buy_stars(call):
    """Начало покупки звезд"""
    if is_user_banned(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Вы заблокированы!")
        return

    markup = types.InlineKeyboardMarkup()
    btn_back = types.InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")
    markup.add(btn_back)

    try:
        bot.edit_message_text(
            "📨 *Введите получателя звезд*\n\n"
            "Укажите @username пользователя Telegram",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=markup
        )
    except:
        bot.send_message(
            call.message.chat.id,
            "📨 *Введите получателя звезд*\n\n"
            "Укажите @username пользователя Telegram",
            parse_mode='Markdown',
            reply_markup=markup
        )

    bot.register_next_step_handler_by_chat_id(call.message.chat.id, process_recipient)


def process_recipient(message):
    """Обработка получателя звезд"""
    if is_user_banned(message.from_user.id):
        return

    recipient = message.text.strip()
    save_user_session(message.from_user.id, "recipient", recipient)

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_50 = types.InlineKeyboardButton("50⭐", callback_data="calc_50")
    btn_100 = types.InlineKeyboardButton("100⭐", callback_data="calc_100")
    btn_200 = types.InlineKeyboardButton("200⭐", callback_data="calc_200")
    btn_500 = types.InlineKeyboardButton("500⭐", callback_data="calc_500")
    btn_custom = types.InlineKeyboardButton("Другое количество", callback_data="calc_custom")
    markup.add(btn_50, btn_100, btn_200, btn_500, btn_custom)

    current_rate = update_uah_rate()

    bot.send_message(
        message.chat.id,
        f"🧮 *Калькулятор звезд*\n\n"
        f"📊 Текущий курс:\n"
        f"• 1 звезда = {STAR_RATE}$\n"
        f"• 1$ = {current_rate}₴\n\n"
        f"Выберите количество звезд или введите свое:",
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('calc_'))
def calculator_handler(call):
    """Обработка выбора количества звезд"""
    if is_user_banned(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Вы заблокированы!")
        return

    if call.data == "calc_custom":
        msg = bot.send_message(call.message.chat.id, "💫 Введите количество звезд:")
        bot.register_next_step_handler(msg, process_custom_amount)
        return

    stars_map = {
        "calc_50": 50,
        "calc_100": 100,
        "calc_200": 200,
        "calc_500": 500
    }

    stars = stars_map.get(call.data, 50)
    process_stars_count_callback(call, stars)


def process_custom_amount(message):
    """Обработка пользовательского количества звезд"""
    if is_user_banned(message.from_user.id):
        return

    try:
        stars = int(message.text)
        if stars < MIN_STARS:
            bot.send_message(message.chat.id, f"❌ Минимальное количество: {MIN_STARS} звезд")
            return

        save_user_session(message.from_user.id, "stars", stars)

        prices = {
            "balance": calculate_price(stars),
            "crypto": calculate_price(stars),
            "ton": calculate_price(stars),
            "monobank": calculate_price(stars, "monobank")
        }

        recipient = get_user_session(message.from_user.id, "recipient")
        safe_recipient = escape_markdown(recipient) if recipient else ""
        user_balance = get_user_balance(message.from_user.id)

        markup = types.InlineKeyboardMarkup(row_width=1)

        if user_balance >= stars:
            btn_balance = types.InlineKeyboardButton(
                f"💎 Баланс ({user_balance}⭐) - Бесплатно",
                callback_data=f"pay_balance_{stars}"
            )
            markup.add(btn_balance)

        btn_crypto = types.InlineKeyboardButton(
            f"💳 Crypto Bot - {prices['crypto']['usd']:.2f}$ ({prices['crypto']['uah']:.0f}₴)",
            callback_data=f"pay_crypto_{stars}"
        )
        btn_ton = types.InlineKeyboardButton(
            f"⚡ TON - {prices['ton']['usd']:.2f}$ ({prices['ton']['uah']:.0f}₴)",
            callback_data=f"pay_ton_{stars}"
        )
        btn_monobank = types.InlineKeyboardButton(
            f"💳 Monobank - {prices['monobank']['uah']:.0f}₴",
            callback_data=f"pay_monobank_{stars}"
        )
        markup.add(btn_crypto, btn_ton, btn_monobank)

        balance_info = f"\n💎 *Ваш баланс:* {user_balance} звезд" if user_balance > 0 else ""

        bot.send_message(
            message.chat.id,
            f"📊 *Детали заказа*\n\n"
            f"👤 Получатель: {safe_recipient}\n"
            f"⭐ Звезд: {stars}{balance_info}\n\n"
            f"Выберите способ оплаты:",
            parse_mode='Markdown',
            reply_markup=markup
        )

    except ValueError:
        bot.send_message(message.chat.id, "❌ Пожалуйста, введите число")


def process_stars_count_callback(call, stars):
    """Обработка выбора количества звезд из списка"""
    prices = {
        "balance": calculate_price(stars),
        "crypto": calculate_price(stars),
        "ton": calculate_price(stars),
        "monobank": calculate_price(stars, "monobank")
    }

    save_user_session(call.from_user.id, "stars", stars)
    recipient = get_user_session(call.from_user.id, "recipient")
    safe_recipient = escape_markdown(recipient) if recipient else ""

    user_balance = get_user_balance(call.from_user.id)

    markup = types.InlineKeyboardMarkup(row_width=1)

    if user_balance >= stars:
        btn_balance = types.InlineKeyboardButton(
            f"💎 Баланс ({user_balance}⭐) - Бесплатно",
            callback_data=f"pay_balance_{stars}"
        )
        markup.add(btn_balance)

    btn_crypto = types.InlineKeyboardButton(
        f"💳 Crypto Bot - {prices['crypto']['usd']:.2f}$ ({prices['crypto']['uah']:.0f}₴)",
        callback_data=f"pay_crypto_{stars}"
    )
    btn_ton = types.InlineKeyboardButton(
        f"⚡ TON - {prices['ton']['usd']:.2f}$ ({prices['ton']['uah']:.0f}₴)",
        callback_data=f"pay_ton_{stars}"
    )
    btn_monobank = types.InlineKeyboardButton(
        f"💳 Monobank - {prices['monobank']['uah']:.0f}₴",
        callback_data=f"pay_monobank_{stars}"
    )
    markup.add(btn_crypto, btn_ton, btn_monobank)

    balance_info = f"\n💎 *Ваш баланс:* {user_balance} звезд" if user_balance > 0 else ""

    try:
        bot.edit_message_text(
            f"📊 *Детали заказа*\n\n"
            f"👤 Получатель: {safe_recipient}\n"
            f"⭐ Звезд: {stars}{balance_info}\n\n"
            f"Выберите способ оплаты:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=markup
        )
    except Exception as e:
        logging.error(f"Ошибка при редактировании сообщения: {e}")
        bot.send_message(
            call.message.chat.id,
            f"📊 *Детали заказа*\n\n"
            f"👤 Получатель: {safe_recipient}\n"
            f"⭐ Звезд: {stars}{balance_info}\n\n"
            f"Выберите способ оплаты:",
            parse_mode='Markdown',
            reply_markup=markup
        )


# ========== ОПЛАТА ==========

@bot.callback_query_handler(func=lambda call: call.data.startswith('pay_balance_'))
def process_balance_payment(call):
    """Обработка оплаты с баланса"""
    if is_user_banned(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Вы заблокированы!")
        return

    try:
        stars = int(call.data.split('_')[2])
        user_balance = get_user_balance(call.from_user.id)

        if user_balance < stars:
            bot.answer_callback_query(call.id, f"❌ Недостаточно звезд на балансе. У вас: {user_balance}⭐")
            return

        update_user_balance(call.from_user.id, stars, add=False)

        recipient = get_user_session(call.from_user.id, "recipient")
        order_id = create_order(
            call.from_user.id,
            call.from_user.username or call.from_user.first_name,
            recipient,
            stars,
            0,
            "balance"
        )

        update_order(order_id, {"status": "completed"})

        markup = types.InlineKeyboardMarkup()
        btn_back = types.InlineKeyboardButton("⬅️ На главную", callback_data="back_to_main")
        markup.add(btn_back)

        try:
            bot.edit_message_text(
                f"✅ *Оплата проведена успешно!*\n\n"
                f"⭐ Использовано звезд: {stars}\n"
                f"💎 Остаток на балансе: {user_balance - stars} звезд\n\n"
                f"Заказ #{order_id} выполнен и отправлен получателю.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=markup
            )
        except:
            bot.send_message(
                call.message.chat.id,
                f"✅ *Оплата проведена успешно!*\n\n"
                f"⭐ Использовано звезд: {stars}\n"
                f"💎 Остаток на балансе: {user_balance - stars} звезд\n\n"
                f"Заказ #{order_id} выполнен и отправлен получателю.",
                parse_mode='Markdown',
                reply_markup=markup
            )

        notify_admins_balance_order(order_id)

    except Exception as e:
        logging.error(f"Ошибка в process_balance_payment: {e}")
        bot.answer_callback_query(call.id, "❌ Произошла ошибка при обработке платежа")


@bot.callback_query_handler(func=lambda call: call.data.startswith('pay_crypto_'))
def process_crypto_payment_new(call):
    """Обработка оплаты через Crypto Bot"""
    if is_user_banned(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Вы заблокированы!")
        return

    try:
        stars = int(call.data.split('_')[2])
        prices = calculate_price(stars)

        user_id = call.from_user.id
        recipient = get_user_session(user_id, "recipient")
        safe_recipient = escape_markdown(recipient) if recipient else ""

        payment_link, comment = generate_crypto_payment_link(user_id, prices["usd"], stars, "stars")

        order_id = create_order(
            user_id,
            call.from_user.username or call.from_user.first_name,
            recipient,
            stars,
            prices["usd"],
            "crypto"
        )

        markup = types.InlineKeyboardMarkup(row_width=1)
        btn_pay = types.InlineKeyboardButton("💳 Оплатить", url=payment_link)
        markup.add(btn_pay)

        try:
            bot.edit_message_text(
                f"💳 *Оплата через Crypto Bot*\n\n"
                f"👤 Получатель: {safe_recipient}\n"
                f"⭐️ Звёзды: {stars}\n"
                f"💵 Сумма к оплате: {prices['usd']:.2f}$\n\n"
                f"⚠️ *Важно:*\n"
                f"Сумма оплаты должна ТОЧНО совпадать с указанной выше.\n"
                f"При оплате другой суммы заказ может не обработаться.\n\n"
                f"Если возникли сложности — напишите в поддержку.\n"
                f"Нажмите кнопку '💳 Оплатить' ниже и завершите оплату.\n"
                f"Чтобы отменить заказ отправьте любую фотографию или ссылку.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=markup
            )
        except:
            bot.send_message(
                call.message.chat.id,
                f"💳 *Оплата через Crypto Bot*\n\n"
                f"👤 Получатель: {safe_recipient}\n"
                f"⭐️ Звёзды: {stars}\n"
                f"💵 Сумма к оплате: {prices['usd']:.2f}$\n\n"
                f"⚠️ *Важно:*\n"
                f"Сумма оплаты должна ТОЧНО совпадать с указанной выше.\n"
                f"При оплате другой суммы заказ может не обработаться.\n\n"
                f"Если возникли сложности — напишите в поддержку.\n"
                f"Нажмите кнопку '💳 Оплатить' ниже и завершите оплату.\n"
                f"Чтобы отменить заказ отправьте любую фотографию или ссылку.",
                parse_mode='Markdown',
                reply_markup=markup
            )

        update_order(order_id, {"payment_proof": f"COMMENT: {comment}"})

        order = get_order(order_id)
        if order:
            admin_message = (
                f"🛒 *Новый заказ через Crypto Bot*\n\n"
                f"📋 *ID*: #{order_id}\n"
                f"👤 *Пользователь*: {escape_markdown(order['user_name'] or '')}\n"
                f"🆔 *User ID*: {order['user_id']}\n"
                f"👥 *Получатель*: {safe_recipient}\n"
                f"⭐ *Количество звезд*: {order['stars']}\n"
                f"💰 *Сумма*: {order['amount']:.2f}$\n"
                f"🔗 *Комментарий для проверки*: `{comment}`\n\n"
                f"⏰ *Время*: {datetime.now().strftime('%H:%M:%S')}"
            )

            for admin_id in ADMIN_IDS:
                try:
                    bot.send_message(admin_id, admin_message, parse_mode='Markdown')
                except Exception as e:
                    logging.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")

        msg = bot.send_message(call.message.chat.id, "📸 После оплаты отправьте скриншот подтверждения:")
        bot.register_next_step_handler(msg, process_crypto_proof_new, order_id, comment)

    except Exception as e:
        logging.error(f"Ошибка в process_crypto_payment_new: {e}")
        bot.answer_callback_query(call.id, "❌ Произошла ошибка")


def process_crypto_proof_new(message, order_id, comment):
    """Обработка скриншота оплаты через Crypto Bot"""
    if is_user_banned(message.from_user.id):
        return

    if message.photo:
        file_id = message.photo[-1].file_id

        updates = {
            "payment_proof": f"COMMENT: {comment} + фото",
            "payment_photo_id": file_id
        }

        update_order(order_id, updates)

        order = get_order(order_id)
        process_referral_earnings(order["user_id"], order_id, order["stars"], order["amount"])

        bot.send_message(message.chat.id,
                         "✅ Скриншот подтверждения получен! Заказ отправлен администраторам на проверку.")

        notify_admins_with_photo(order, file_id)
    else:
        bot.send_message(message.chat.id, "❌ Пожалуйста, отправьте скриншот подтверждения оплаты")
        msg = bot.send_message(message.chat.id, "📸 Отправьте скриншот подтверждения:")
        bot.register_next_step_handler(msg, process_crypto_proof_new, order_id, comment)


# ========== АДМИН ПАНЕЛЬ ==========

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    """Панель администратора"""
    if message.from_user.id not in ADMIN_IDS:
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("👥 Управление пользователями", callback_data="admin_users")
    btn2 = types.InlineKeyboardButton("💰 Управление балансами", callback_data="admin_balance")
    btn3 = types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")
    btn4 = types.InlineKeyboardButton("📦 Управление заказами", callback_data="admin_orders")
    btn5 = types.InlineKeyboardButton("💸 Управление выводами", callback_data="admin_withdrawals")
    btn6 = types.InlineKeyboardButton("📝 Логи администраторов", callback_data="admin_logs")
    btn7 = types.InlineKeyboardButton("🗄️ Управление БД", callback_data="admin_db")
    btn8 = types.InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn8)

    bot.send_message(
        message.chat.id,
        "👨‍💼 *Панель администратора*\n\n"
        "Выберите раздел:",
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "admin_users")
def admin_users_menu(call):
    """Меню управления пользователями"""
    if call.from_user.id not in ADMIN_IDS:
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🔍 Найти пользователя", callback_data="admin_find_user")
    btn2 = types.InlineKeyboardButton("🚫 Заблокировать", callback_data="admin_ban_user")
    btn3 = types.InlineKeyboardButton("✅ Разблокировать", callback_data="admin_unban_user")
    btn4 = types.InlineKeyboardButton("📋 Список забаненных", callback_data="admin_banned_list")
    btn5 = types.InlineKeyboardButton("👤 Инфо пользователя", callback_data="admin_user_info")
    btn6 = types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_back")
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6)

    bot.edit_message_text(
        "👥 *Управление пользователями*\n\nВыберите действие:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "admin_balance")
def admin_balance_menu(call):
    """Меню управления балансами"""
    if call.from_user.id not in ADMIN_IDS:
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("➕ Пополнить баланс", callback_data="admin_add_balance")
    btn2 = types.InlineKeyboardButton("➖ Списать баланс", callback_data="admin_remove_balance")
    btn3 = types.InlineKeyboardButton("📊 Топ по балансу", callback_data="admin_top_balance")
    btn4 = types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_back")
    markup.add(btn1, btn2, btn3, btn4)

    bot.edit_message_text(
        "💰 *Управление балансами*\n\nВыберите действие:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "admin_stats")
def admin_stats_menu(call):
    """Меню статистики"""
    if call.from_user.id not in ADMIN_IDS:
        return

    data = load_data()

    total_users = len(data["users"])
    total_orders = len(data["orders"])
    pending_orders = len([o for o in data["orders"] if o["status"] == "pending"])
    completed_orders = len([o for o in data["orders"] if o["status"] == "completed"])
    banned_users = len(data["banned_users"])

    total_balance = sum([u.get("balance", 0) for u in data["users"].values()])
    total_earned = sum([u.get("total_earned", 0) for u in data["users"].values()])
    total_withdraw_balance = sum([u.get("withdraw_balance", 0) for u in data["users"].values()])

    markup = types.InlineKeyboardMarkup()
    btn_back = types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_back")
    markup.add(btn_back)

    stats_text = (
        f"📊 *Статистика бота*\n\n"
        f"👥 Пользователей: {total_users}\n"
        f"🚫 Забанено: {banned_users}\n"
        f"⭐ Всего звезд на балансах: {total_balance}\n"
        f"💰 Всего заработано: {total_earned} звезд\n"
        f"💵 Всего $ для вывода: ${total_withdraw_balance:.2f}\n\n"
        f"📦 Всего заказов: {total_orders}\n"
        f"🟡 Ожидают обработки: {pending_orders}\n"
        f"🟢 Выполнено: {completed_orders}\n"
        f"🔴 Отклонено: {total_orders - pending_orders - completed_orders}"
    )

    bot.edit_message_text(
        stats_text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "admin_orders")
def admin_orders_menu(call):
    """Меню управления заказами"""
    if call.from_user.id not in ADMIN_IDS:
        return

    data = load_data()

    recent_orders = sorted(data["orders"], key=lambda x: x["id"], reverse=True)[:5]

    orders_text = "📦 *Последние заказы*\n\n"

    for order in recent_orders:
        status_icons = {
            'pending': '🟡',
            'completed': '🟢',
            'rejected': '🔴',
            'cancelled': '⚫'
        }

        product = f"{order['stars']} звезд"
        if order.get("premium_duration"):
            product = f"Premium ({order['premium_duration']})"

        orders_text += (
            f"{status_icons.get(order['status'], '⚪')} *Заказ #{order['id']}*\n"
            f"👤 Пользователь: {escape_markdown(order.get('user_name', 'Нет'))} (ID: {order['user_id']})\n"
            f"📦 Товар: {product}\n"
            f"💰 Сумма: {order['amount']:.2f}$\n"
            f"📊 Статус: {order['status']}\n\n"
        )

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🟡 Ожидающие заказы", callback_data="admin_pending_orders")
    btn2 = types.InlineKeyboardButton("📋 Все заказы", callback_data="admin_all_orders")
    btn3 = types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_back")
    markup.add(btn1, btn2, btn3)

    bot.edit_message_text(
        orders_text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "admin_withdrawals")
def admin_withdrawals_menu(call):
    """Меню управления выводами"""
    if call.from_user.id not in ADMIN_IDS:
        return

    data = load_data()

    pending_withdrawals = [w for w in data["withdrawals"] if w["status"] == "pending"]
    total_withdrawals = len(data["withdrawals"])
    total_paid = sum([w["net_amount"] for w in data["withdrawals"] if w["status"] == "completed"])

    stats_text = (
        f"💸 *Управление выводами*\n\n"
        f"📋 Всего заявок: {total_withdrawals}\n"
        f"🟡 Ожидают обработки: {len(pending_withdrawals)}\n"
        f"🟢 Выплачено: {len([w for w in data['withdrawals'] if w['status'] == 'completed'])}\n"
        f"🔴 Отклонено: {len([w for w in data['withdrawals'] if w['status'] == 'rejected'])}\n"
        f"💰 Общая выплаченная сумма: ${total_paid:.2f}\n\n"
        f"*Последние заявки:*\n"
    )

    recent_withdrawals = sorted(data["withdrawals"], key=lambda x: x["id"], reverse=True)[:5]

    for w in recent_withdrawals:
        status_icons = {
            'pending': '🟡',
            'completed': '🟢',
            'rejected': '🔴'
        }

        user_stats = get_user_stats(w["user_id"])
        username = user_stats.get('username', 'без ника')

        stats_text += (
            f"{status_icons.get(w['status'], '⚪')} *Заявка #{w['id']}*\n"
            f"👤 Пользователь: @{escape_markdown(username)} (ID: {w['user_id']})\n"
            f"⭐ Звезд: {w['stars']}\n"
            f"💵 Сумма: ${w['net_amount']:.2f}\n"
            f"📊 Статус: {w['status']}\n\n"
        )

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🟡 Ожидающие выплаты", callback_data="admin_pending_withdrawals")
    btn2 = types.InlineKeyboardButton("📋 Все заявки", callback_data="admin_all_withdrawals")
    btn3 = types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_back")
    markup.add(btn1, btn2, btn3)

    bot.edit_message_text(
        stats_text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "admin_logs")
def admin_logs_menu(call):
    """Меню логов администраторов"""
    if call.from_user.id not in ADMIN_IDS:
        return

    data = load_data()

    recent_logs = sorted(data["admin_logs"], key=lambda x: x["id"], reverse=True)[:10]

    logs_text = "📝 *Логи администраторов*\n\n"

    if not recent_logs:
        logs_text += "Логов пока нет"
    else:
        for log in recent_logs:
            logs_text += (
                f"🆔 *Лог #{log['id']}*\n"
                f"👤 Админ: {log['admin_id']}\n"
                f"📝 Действие: {log['action']}\n"
                f"📋 Детали: {escape_markdown(log['details'])}\n"
                f"⏰ Время: {log['timestamp']}\n\n"
            )

    markup = types.InlineKeyboardMarkup()
    btn_back = types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_back")
    markup.add(btn_back)

    bot.edit_message_text(
        logs_text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "admin_db")
def admin_db_menu(call):
    """Меню управления базой данных"""
    if call.from_user.id not in ADMIN_IDS:
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("💾 Создать бэкап", callback_data="admin_backup")
    btn2 = types.InlineKeyboardButton("🔄 Сбросить БД", callback_data="admin_reset_db")
    btn3 = types.InlineKeyboardButton("📁 Показать структуру", callback_data="admin_db_structure")
    btn4 = types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_back")
    markup.add(btn1, btn2, btn3, btn4)

    bot.edit_message_text(
        "🗄️ *Управление базой данных*\n\nВыберите действие:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "admin_broadcast")
def admin_broadcast_menu(call):
    """Меню рассылки"""
    if call.from_user.id not in ADMIN_IDS:
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    btn1 = types.InlineKeyboardButton("📢 Отправить рассылку", callback_data="admin_send_broadcast")
    btn2 = types.InlineKeyboardButton("📊 Статистика рассылок", callback_data="admin_broadcast_stats")
    btn3 = types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_back")
    markup.add(btn1, btn2, btn3)

    bot.edit_message_text(
        "📢 *Управление рассылкой*\n\nВыберите действие:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "admin_back")
def admin_back(call):
    """Возврат в главное меню админки"""
    if call.from_user.id not in ADMIN_IDS:
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("👥 Управление пользователями", callback_data="admin_users")
    btn2 = types.InlineKeyboardButton("💰 Управление балансами", callback_data="admin_balance")
    btn3 = types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")
    btn4 = types.InlineKeyboardButton("📦 Управление заказами", callback_data="admin_orders")
    btn5 = types.InlineKeyboardButton("💸 Управление выводами", callback_data="admin_withdrawals")
    btn6 = types.InlineKeyboardButton("📝 Логи администраторов", callback_data="admin_logs")
    btn7 = types.InlineKeyboardButton("🗄️ Управление БД", callback_data="admin_db")
    btn8 = types.InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn8)

    bot.edit_message_text(
        "👨‍💼 *Панель администратора*\n\nВыберите раздел:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )


# ========== АДМИН КОМАНДЫ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ ==========

@bot.callback_query_handler(func=lambda call: call.data == "admin_find_user")
def admin_find_user(call):
    """Поиск пользователя"""
    if call.from_user.id not in ADMIN_IDS:
        return

    msg = bot.send_message(
        call.message.chat.id,
        "🔍 *Поиск пользователя*\n\n"
        "Введите ID пользователя, @username или реферальный код:",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(msg, process_find_user)


def process_find_user(message):
    """Обработка поиска пользователя"""
    if message.from_user.id not in ADMIN_IDS:
        return

    search_query = message.text.strip()
    data = load_data()

    found_users = []

    if search_query.isdigit():
        user_id = int(search_query)
        user_id_str = str(user_id)
        if user_id_str in data["users"]:
            found_users.append(data["users"][user_id_str])

    if search_query.startswith('@'):
        search_username = search_query[1:]
    else:
        search_username = search_query

    for user in data["users"].values():
        if user.get("username") == search_username:
            found_users.append(user)
        elif user.get("referral_code") == search_query:
            found_users.append(user)
        elif search_query.lower() in (user.get("first_name", "") or "").lower():
            found_users.append(user)

    if not found_users:
        bot.send_message(message.chat.id, "❌ Пользователь не найден")
        return

    response = "🔍 *Результаты поиска:*\n\n"

    for user in found_users[:5]:
        referrals_count = 0
        referral_code = user.get("referral_code")

        if referral_code:
            for uid, u in data["users"].items():
                if u.get("referred_by") == referral_code:
                    referrals_count += 1

        banned_status = "🚫 ЗАБАНЕН\n" if user.get("is_banned") else ""
        ban_reason = f"Причина: {user.get('ban_reason')}\n" if user.get("is_banned") else ""

        response += (
            f"{banned_status}{ban_reason}"
            f"🆔 ID: `{user['user_id']}`\n"
            f"👤 Имя: {escape_markdown(user.get('first_name', ''))} {escape_markdown(user.get('last_name', ''))}\n"
            f"📛 Ник: @{escape_markdown(user.get('username', 'нет'))}\n"
            f"⭐ Баланс: {user.get('balance', 0)}\n"
            f"💰 Всего заработано: {user.get('total_earned', 0)}\n"
            f"💵 Баланс для вывода: ${user.get('withdraw_balance', 0):.2f}\n"
            f"👥 Рефералов: {referrals_count}\n"
            f"🔗 Реферальный код: {user.get('referral_code', 'нет')}\n"
            f"📅 Регистрация: {user.get('created_at', 'неизвестно')}\n"
            f"{'-' * 30}\n"
        )

    bot.send_message(message.chat.id, response, parse_mode='Markdown')


@bot.callback_query_handler(func=lambda call: call.data == "admin_user_info")
def admin_user_info_callback(call):
    """Информация о пользователе через меню"""
    if call.from_user.id not in ADMIN_IDS:
        return

    msg = bot.send_message(
        call.message.chat.id,
        "👤 *Информация о пользователе*\n\n"
        "Введите ID пользователя:",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(msg, process_user_info_admin)


def process_user_info_admin(message):
    """Обработка запроса информации о пользователе"""
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        user_id = int(message.text)
        user_stats = get_user_stats(user_id)

        data = load_data()
        user_id_str = str(user_id)

        if user_id_str in data["users"]:
            user = data["users"][user_id_str]

            first_name = escape_markdown(user.get('first_name', ''))
            last_name = escape_markdown(user.get('last_name', ''))
            username = escape_markdown(user.get('username', 'нет'))
            ban_reason = escape_markdown(user.get('ban_reason', 'нет'))

            referrals = []
            referral_code = user.get("referral_code")
            if referral_code:
                for uid, u in data["users"].items():
                    if u.get("referred_by") == referral_code:
                        ref_username = escape_markdown(u.get('username', 'Без имени'))
                        referrals.append(f"@{ref_username} (ID: {uid})")

            user_orders = [o for o in data["orders"] if o["user_id"] == user_id]
            total_spent = sum([o["amount"] for o in user_orders if o["status"] == "completed"])

            user_withdrawals = [w for w in data["withdrawals"] if w["user_id"] == user_id]
            total_withdrawn = sum([w["net_amount"] for w in user_withdrawals if w["status"] == "completed"])

            info_text = (
                f"👤 *Информация о пользователе*\n\n"
                f"🆔 ID: `{user_id}`\n"
                f"👤 Имя: {first_name} {last_name}\n"
                f"📛 Ник: @{username}\n"
                f"🚫 Статус: {'Забанен' if user.get('is_banned') else 'Активен'}\n"
                f"📝 Причина бана: {ban_reason}\n\n"
                f"⭐ Баланс: {user.get('balance', 0)} звезд\n"
                f"💰 Всего заработано: {user.get('total_earned', 0)} звезд\n"
                f"💵 Для вывода: ${user.get('withdraw_balance', 0):.2f}\n"
                f"💸 Всего выведено: ${user.get('total_withdrawn', 0):.2f}\n"
                f"🔗 Реферальный код: {user.get('referral_code', 'нет')}\n"
                f"👥 Рефералов: {user_stats['referrals_count']}\n"
                f"📅 Регистрация: {user.get('created_at', 'неизвестно')}\n\n"
                f"📦 Заказов: {len(user_orders)}\n"
                f"💰 Всего потрачено: {total_spent:.2f}$\n"
                f"💸 Выводов: {len([w for w in user_withdrawals if w['status'] == 'completed'])}\n"
                f"💵 Всего выведено: ${total_withdrawn:.2f}"
            )

            if referrals:
                info_text += f"\n\n👥 *Последние рефералы:*\n" + "\n".join(referrals[:5])
                if len(referrals) > 5:
                    info_text += f"\n... и еще {len(referrals) - 5}"

            bot.send_message(message.chat.id, info_text, parse_mode='Markdown')
        else:
            bot.send_message(message.chat.id, f"❌ Пользователь {user_id} не найден")

    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверный формат ID пользователя")
    except Exception as e:
        logging.error(f"Ошибка в process_user_info_admin: {e}")
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")


@bot.callback_query_handler(func=lambda call: call.data == "admin_ban_user")
def admin_ban_user(call):
    """Блокировка пользователя"""
    if call.from_user.id not in ADMIN_IDS:
        return

    msg = bot.send_message(
        call.message.chat.id,
        "🚫 *Блокировка пользователя*\n\n"
        "Введите ID пользователя для блокировки:",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(msg, process_ban_user_step1)


def process_ban_user_step1(message):
    """Обработка блокировки пользователя - шаг 1"""
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        user_id = int(message.text.strip())
        msg = bot.send_message(
            message.chat.id,
            f"Введите причину блокировки пользователя {user_id}:",
            parse_mode='Markdown'
        )
        bot.register_next_step_handler(msg, process_ban_user_step2, user_id)
    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверный ID пользователя")


def process_ban_user_step2(message, user_id):
    """Обработка блокировки пользователя - шаг 2"""
    if message.from_user.id not in ADMIN_IDS:
        return

    reason = message.text.strip()

    if ban_user(user_id, reason, message.from_user.id):
        try:
            bot.send_message(
                user_id,
                f"❌ *Вы были заблокированы!*\n\n"
                f"Причина: {reason}\n\n"
                f"По вопросам обращайтесь в поддержку.",
                parse_mode='Markdown'
            )
        except:
            pass

        bot.send_message(message.chat.id, f"✅ Пользователь {user_id} заблокирован")
    else:
        bot.send_message(message.chat.id, f"❌ Пользователь {user_id} не найден")


@bot.callback_query_handler(func=lambda call: call.data == "admin_unban_user")
def admin_unban_user(call):
    """Разблокировка пользователя"""
    if call.from_user.id not in ADMIN_IDS:
        return

    msg = bot.send_message(
        call.message.chat.id,
        "✅ *Разблокировка пользователя*\n\n"
        "Введите ID пользователя для разблокировки:",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(msg, process_unban_user)


def process_unban_user(message):
    """Обработка разблокировки пользователя"""
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        user_id = int(message.text.strip())

        if unban_user(user_id, message.from_user.id):
            try:
                bot.send_message(
                    user_id,
                    "✅ *Ваш аккаунт разблокирован!*\n\n"
                    "Теперь вы снова можете пользоваться ботом.",
                    parse_mode='Markdown'
                )
            except:
                pass

            bot.send_message(message.chat.id, f"✅ Пользователь {user_id} разблокирован")
        else:
            bot.send_message(message.chat.id, f"❌ Пользователь {user_id} не найден или не забанен")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверный ID пользователя")


@bot.callback_query_handler(func=lambda call: call.data == "admin_banned_list")
def admin_banned_list(call):
    """Список забаненных пользователей"""
    if call.from_user.id not in ADMIN_IDS:
        return

    data = load_data()

    banned_text = "🚫 *Забаненные пользователи:*\n\n"

    if not data["banned_users"]:
        banned_text += "Нет забаненных пользователей"
    else:
        for user_id in data["banned_users"][:20]:
            user_id_str = str(user_id)
            if user_id_str in data["users"]:
                user = data["users"][user_id_str]
                banned_text += (
                    f"🆔 ID: `{user_id}`\n"
                    f"👤 Имя: {escape_markdown(user.get('first_name', ''))} {escape_markdown(user.get('last_name', ''))}\n"
                    f"📛 Ник: @{escape_markdown(user.get('username', 'нет'))}\n"
                    f"📝 Причина: {user.get('ban_reason', 'не указана')}\n"
                    f"{'-' * 30}\n"
                )

    markup = types.InlineKeyboardMarkup()
    btn_back = types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_users")
    markup.add(btn_back)

    bot.edit_message_text(
        banned_text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )


# ========== АДМИН КОМАНДЫ ДЛЯ РАБОТЫ С БАЛАНСАМИ ==========

@bot.callback_query_handler(func=lambda call: call.data == "admin_add_balance")
def admin_add_balance(call):
    """Пополнение баланса"""
    if call.from_user.id not in ADMIN_IDS:
        return

    msg = bot.send_message(
        call.message.chat.id,
        "➕ *Пополнение баланса*\n\n"
        "Введите ID пользователя:",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(msg, process_add_balance_step1)


def process_add_balance_step1(message):
    """Обработка пополнения баланса - шаг 1"""
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        user_id = int(message.text.strip())
        msg = bot.send_message(
            message.chat.id,
            f"Введите количество звезд для начисления пользователю {user_id}:",
            parse_mode='Markdown'
        )
        bot.register_next_step_handler(msg, process_add_balance_step2, user_id)
    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверный ID пользователя")


def process_add_balance_step2(message, user_id):
    """Обработка пополнения баланса - шаг 2"""
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        stars = int(message.text.strip())

        if update_user_balance(user_id, stars, add=True):
            usd_earned = stars * STAR_RATE
            update_withdraw_balance(user_id, usd_earned, add=True)

            add_admin_log(
                message.from_user.id,
                "add_balance",
                f"Начислено {stars} звезд (${usd_earned:.2f}) пользователю {user_id}"
            )

            try:
                bot.send_message(
                    user_id,
                    f"🎉 *Вам начислены звезды!*\n\n"
                    f"⭐ Количество: {stars}\n"
                    f"💰 В долларах: ${usd_earned:.2f}\n"
                    f"💫 Текущий баланс: {get_user_balance(user_id)} звезд\n"
                    f"💵 Баланс для вывода: ${get_user_withdraw_balance(user_id):.2f}",
                    parse_mode='Markdown'
                )
            except:
                pass

            bot.send_message(
                message.chat.id,
                f"✅ Пользователю {user_id} начислено {stars} звезд (${usd_earned:.2f})"
            )
        else:
            bot.send_message(message.chat.id, f"❌ Пользователь {user_id} не найден")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверное количество звезд")


@bot.callback_query_handler(func=lambda call: call.data == "admin_remove_balance")
def admin_remove_balance(call):
    """Списание баланса"""
    if call.from_user.id not in ADMIN_IDS:
        return

    msg = bot.send_message(
        call.message.chat.id,
        "➖ *Списание баланса*\n\n"
        "Введите ID пользователя:",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(msg, process_remove_balance_step1)


def process_remove_balance_step1(message):
    """Обработка списания баланса - шаг 1"""
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        user_id = int(message.text.strip())
        msg = bot.send_message(
            message.chat.id,
            f"Введите количество звезд для списания у пользователя {user_id}:",
            parse_mode='Markdown'
        )
        bot.register_next_step_handler(msg, process_remove_balance_step2, user_id)
    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверный ID пользователя")


def process_remove_balance_step2(message, user_id):
    """Обработка списания баланса - шаг 2"""
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        stars = int(message.text.strip())

        user_balance = get_user_balance(user_id)
        if user_balance < stars:
            bot.send_message(
                message.chat.id,
                f"❌ Недостаточно звезд на балансе. У пользователя: {user_balance} звезд"
            )
            return

        if update_user_balance(user_id, stars, add=False):
            usd_lost = stars * STAR_RATE
            update_withdraw_balance(user_id, usd_lost, add=False)

            add_admin_log(
                message.from_user.id,
                "remove_balance",
                f"Списано {stars} звезд (${usd_lost:.2f}) у пользователя {user_id}"
            )

            try:
                bot.send_message(
                    user_id,
                    f"⚠️ *С вашего баланса списаны звезды*\n\n"
                    f"⭐ Количество: {stars}\n"
                    f"💰 В долларах: ${usd_lost:.2f}\n"
                    f"💫 Текущий баланс: {get_user_balance(user_id)} звезд\n"
                    f"💵 Баланс для вывода: ${get_user_withdraw_balance(user_id):.2f}",
                    parse_mode='Markdown'
                )
            except:
                pass

            bot.send_message(
                message.chat.id,
                f"✅ С пользователя {user_id} списано {stars} звезд (${usd_lost:.2f})"
            )
        else:
            bot.send_message(message.chat.id, f"❌ Пользователь {user_id} не найден")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверное количество звезд")


@bot.callback_query_handler(func=lambda call: call.data == "admin_top_balance")
def admin_top_balance(call):
    """Топ по балансу"""
    if call.from_user.id not in ADMIN_IDS:
        return

    data = load_data()

    top_balance = sorted(
        data["users"].values(),
        key=lambda x: x.get("balance", 0),
        reverse=True
    )[:10]

    response = "*Топ по балансу звезд:*\n\n"
    for i, user in enumerate(top_balance, 1):
        username = user.get('username', 'Без имени')
        user_id = user.get('user_id', 'N/A')
        balance = user.get('balance', 0)
        withdraw_balance = user.get('withdraw_balance', 0)

        banned_status = "🚫 " if user.get("is_banned") else ""

        response += (
            f"{i}. {banned_status}@{escape_markdown(username)} "
            f"\\(ID: {user_id}\\)\n"
            f"   Баланс: {balance}⭐ \\| $ для вывода: ${withdraw_balance:.2f}\n\n"
        )

    markup = types.InlineKeyboardMarkup()
    btn_back = types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_balance")
    markup.add(btn_back)

    bot.edit_message_text(
        response,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )


# ========== АДМИН КОМАНДЫ ДЛЯ РАБОТЫ С ЗАКАЗАМИ ==========

@bot.callback_query_handler(func=lambda call: call.data == "admin_pending_orders")
def admin_pending_orders(call):
    """Ожидающие заказы"""
    if call.from_user.id not in ADMIN_IDS:
        return

    data = load_data()

    pending_orders = [o for o in data["orders"] if o["status"] == "pending"]

    if not pending_orders:
        bot.answer_callback_query(call.id, "✅ Нет заказов, ожидающих обработки")
        return

    response = "🟡 *Заказы, ожидающие обработки:*\n\n"

    for order in pending_orders[:10]:
        product = f"{order['stars']} звезд"
        if order.get("premium_duration"):
            product = f"Premium ({order['premium_duration']})"

        response += (
            f"📋 *Заказ #{order['id']}*\n"
            f"👤 Пользователь: {escape_markdown(order.get('user_name', 'Нет'))} \\(ID: {order['user_id']}\\)\n"
            f"📦 Товар: {product}\n"
            f"💰 Сумма: {order['amount']:.2f}$\n"
            f"🔗 Оплата: {order['payment_method']}\n"
            f"⏰ Дата: {order['created_at']}\n\n"
        )

    markup = types.InlineKeyboardMarkup()
    btn_back = types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_orders")
    markup.add(btn_back)

    bot.edit_message_text(
        response,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "admin_all_orders")
def admin_all_orders(call):
    """Все заказы"""
    if call.from_user.id not in ADMIN_IDS:
        return

    data = load_data()

    total_orders = len(data["orders"])
    completed_orders = len([o for o in data["orders"] if o["status"] == "completed"])
    pending_orders = len([o for o in data["orders"] if o["status"] == "pending"])
    rejected_orders = len([o for o in data["orders"] if o["status"] == "rejected"])
    cancelled_orders = len([o for o in data["orders"] if o["status"] == "cancelled"])

    total_amount = sum([o["amount"] for o in data["orders"] if o["status"] == "completed"])

    stats_text = (
        f"📦 *Статистика заказов:*\n\n"
        f"📋 Всего заказов: {total_orders}\n"
        f"🟢 Выполнено: {completed_orders}\n"
        f"🟡 Ожидают: {pending_orders}\n"
        f"🔴 Отклонено: {rejected_orders}\n"
        f"⚫ Отменено: {cancelled_orders}\n"
        f"💰 Общая сумма: {total_amount:.2f}$\n\n"
        f"💾 Для получения полного списка заказов используйте команду /export_orders"
    )

    markup = types.InlineKeyboardMarkup()
    btn_back = types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_orders")
    markup.add(btn_back)

    bot.edit_message_text(
        stats_text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )


# ========== АДМИН КОМАНДЫ ДЛЯ РАБОТЫ С ВЫВОДАМИ ==========

@bot.callback_query_handler(func=lambda call: call.data == "admin_pending_withdrawals")
def admin_pending_withdrawals(call):
    """Ожидающие выплаты"""
    if call.from_user.id not in ADMIN_IDS:
        return

    data = load_data()

    pending_withdrawals = [w for w in data["withdrawals"] if w["status"] == "pending"]

    if not pending_withdrawals:
        bot.answer_callback_query(call.id, "✅ Нет заявок, ожидающих обработки")
        return

    response = "🟡 *Заявки на вывод, ожидающие обработки:*\n\n"

    for w in pending_withdrawals[:10]:
        user_stats = get_user_stats(w["user_id"])
        username = user_stats.get('username', 'без ника')

        response += (
            f"📋 *Заявка #{w['id']}*\n"
            f"👤 Пользователь: @{escape_markdown(username)} \\(ID: {w['user_id']}\\)\n"
            f"⭐ Звезд: {w['stars']}\n"
            f"💰 Сумма: ${w['usd_amount']:.2f}\n"
            f"📊 Комиссия: ${w['fee']:.2f}\n"
            f"💵 К выплате: ${w['net_amount']:.2f}\n"
            f"⏰ Дата: {w['created_at']}\n\n"
        )

    markup = types.InlineKeyboardMarkup()
    btn_back = types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_withdrawals")
    markup.add(btn_back)

    bot.edit_message_text(
        response,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "admin_all_withdrawals")
def admin_all_withdrawals(call):
    """Все заявки на вывод"""
    if call.from_user.id not in ADMIN_IDS:
        return

    markup = types.InlineKeyboardMarkup()
    btn_back = types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_withdrawals")
    markup.add(btn_back)

    bot.edit_message_text(
        "📋 Для просмотра всех заявок на вывод используйте команду /export_withdrawals",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )


# ========== АДМИН КОМАНДЫ ДЛЯ РАБОТЫ С БАЗОЙ ДАННЫХ ==========

@bot.callback_query_handler(func=lambda call: call.data == "admin_backup")
def admin_backup_db(call):
    """Создание бэкапа БД"""
    if call.from_user.id not in ADMIN_IDS:
        return

    data = load_data()
    backup_file = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    add_admin_log(
        call.from_user.id,
        "backup_db",
        f"Создана резервная копия: {backup_file}"
    )

    bot.answer_callback_query(call.id, f"✅ Резервная копия создана: {backup_file}")


@bot.callback_query_handler(func=lambda call: call.data == "admin_reset_db")
def admin_reset_db(call):
    """Сброс базы данных"""
    if call.from_user.id not in ADMIN_IDS:
        return

    markup = types.InlineKeyboardMarkup()
    btn_confirm = types.InlineKeyboardButton("✅ Да, сбросить", callback_data="admin_reset_confirm")
    btn_cancel = types.InlineKeyboardButton("❌ Отмена", callback_data="admin_db")
    markup.add(btn_confirm, btn_cancel)

    bot.edit_message_text(
        "⚠️ *ВНИМАНИЕ!*\n\n"
        "Вы собираетесь сбросить базу данных к начальному состоянию.\n"
        "Все данные будут удалены!\n\n"
        "Вы уверены?",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "admin_reset_confirm")
def admin_reset_confirm(call):
    """Подтверждение сброса БД"""
    if call.from_user.id not in ADMIN_IDS:
        return

    init_db()

    add_admin_log(
        call.from_user.id,
        "reset_db",
        "База данных сброшена к начальному состоянию"
    )

    bot.answer_callback_query(call.id, "✅ База данных сброшена")

    admin_db_menu(call)


@bot.callback_query_handler(func=lambda call: call.data == "admin_db_structure")
def admin_db_structure(call):
    """Структура базы данных"""
    if call.from_user.id not in ADMIN_IDS:
        return

    data = load_data()

    structure_text = (
        f"📁 *Структура базы данных:*\n\n"
        f"👥 Пользователей: {len(data['users'])}\n"
        f"📦 Заказов: {len(data['orders'])}\n"
        f"💸 Заявок на вывод: {len(data['withdrawals'])}\n"
        f"💫 Реферальных начислений: {len(data['referral_earnings'])}\n"
        f"🚫 Забаненных: {len(data['banned_users'])}\n"
        f"📝 Логов админов: {len(data['admin_logs'])}\n\n"
        f"💾 Размер файла: {os.path.getsize(DATA_FILE) / 1024:.2f} КБ\n"
        f"📅 Последнее изменение: {datetime.fromtimestamp(os.path.getmtime(DATA_FILE)).strftime('%d.%m.%Y %H:%M:%S')}"
    )

    markup = types.InlineKeyboardMarkup()
    btn_back = types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_db")
    markup.add(btn_back)

    bot.edit_message_text(
        structure_text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )


# ========== АДМИН КОМАНДЫ ДЛЯ РАССЫЛКИ ==========

@bot.callback_query_handler(func=lambda call: call.data == "admin_send_broadcast")
def admin_send_broadcast(call):
    """Отправка рассылки"""
    if call.from_user.id not in ADMIN_IDS:
        return

    msg = bot.send_message(
        call.message.chat.id,
        "📢 *Отправка рассылки*\n\n"
        "Введите текст для рассылки (поддерживается Markdown):",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(msg, process_broadcast_message)


def process_broadcast_message(message):
    """Обработка текста рассылки"""
    if message.from_user.id not in ADMIN_IDS:
        return

    broadcast_text = message.text
    data = load_data()

    sent_count = 0
    failed_count = 0
    total_users = len(data["users"])

    markup = types.InlineKeyboardMarkup()
    btn_stop = types.InlineKeyboardButton("⏹️ Остановить", callback_data="admin_stop_broadcast")
    markup.add(btn_stop)

    status_msg = bot.send_message(
        message.chat.id,
        f"🔄 *Начинаю рассылку...*\n\n"
        f"Всего пользователей: {total_users}\n"
        f"Отправлено: 0\n"
        f"Не удалось: 0",
        parse_mode='Markdown',
        reply_markup=markup
    )

    for user_id_str, user_data in data["users"].items():
        try:
            user_id = int(user_id_str)

            if user_data.get("is_banned", False):
                continue

            bot.send_message(user_id, broadcast_text, parse_mode='Markdown')
            sent_count += 1

            if sent_count % 10 == 0:
                try:
                    bot.edit_message_text(
                        f"🔄 *Рассылка в процессе...*\n\n"
                        f"Всего пользователей: {total_users}\n"
                        f"Отправлено: {sent_count}\n"
                        f"Не удалось: {failed_count}",
                        status_msg.chat.id,
                        status_msg.message_id,
                        parse_mode='Markdown',
                        reply_markup=markup
                    )
                except:
                    pass

        except Exception as e:
            failed_count += 1
            logging.error(f"Не удалось отправить рассылку пользователю {user_id_str}: {e}")

    bot.edit_message_text(
        f"✅ *Рассылка завершена!*\n\n"
        f"Всего пользователей: {total_users}\n"
        f"Успешно отправлено: {sent_count}\n"
        f"Не удалось: {failed_count}\n\n"
        f"Охват: {(sent_count / total_users * 100 if total_users > 0 else 0):.1f}%",
        status_msg.chat.id,
        status_msg.message_id,
        parse_mode='Markdown'
    )

    add_admin_log(
        message.from_user.id,
        "send_broadcast",
        f"Отправлена рассылка на {sent_count} пользователей. Охват: {(sent_count / total_users * 100 if total_users > 0 else 0):.1f}%"
    )


@bot.callback_query_handler(func=lambda call: call.data == "admin_broadcast_stats")
def admin_broadcast_stats(call):
    """Статистика рассылок"""
    if call.from_user.id not in ADMIN_IDS:
        return

    data = load_data()

    total_users = len(data["users"])
    active_users = len([u for u in data["users"].values() if not u.get("is_banned", False)])

    broadcast_sent = data.get("broadcast_sent", {})
    unique_users = set()

    for key in broadcast_sent.keys():
        parts = key.split('_')
        if len(parts) >= 3:
            try:
                user_id = int(parts[2])
                unique_users.add(user_id)
            except:
                pass

    stats_text = (
        f"📊 *Статистика рассылок*\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"👤 Активных пользователей: {active_users}\n"
        f"📨 Автоматических рассылок отправлено: {len(broadcast_sent)}\n"
        f"👤 Уникальных получателей: {len(unique_users)}\n\n"
        f"Расписание автоматических сообщений:*\n"
    )

    for i, msg_info in enumerate(BROADCAST_MESSAGES):
        stats_text += f"{i + 1}. Через {msg_info['delay_hours']} час(а/ов) после регистрации\n"

    markup = types.InlineKeyboardMarkup()
    btn_back = types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_broadcast")
    markup.add(btn_back)

    bot.edit_message_text(
        stats_text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "admin_stop_broadcast")
def admin_stop_broadcast(call):
    """Остановка рассылки"""
    if call.from_user.id not in ADMIN_IDS:
        return

    bot.answer_callback_query(call.id, "Рассылка остановлена вручную")

    try:
        bot.edit_message_text(
            "⏹️ *Рассылка остановлена вручную*",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
    except:
        pass


# ========== ТЕКСТОВЫЕ АДМИН КОМАНДЫ ==========

@bot.message_handler(commands=['status'])
def status_command(message):
    """Команда статуса"""
    if message.from_user.id not in ADMIN_IDS:
        return

    data = load_data()

    total_orders = len(data["orders"])
    pending_orders = len([o for o in data["orders"] if o["status"] == "pending"])
    completed_orders = len([o for o in data["orders"] if o["status"] == "completed"])
    rejected_orders = len([o for o in data["orders"] if o["status"] == "rejected"])
    cancelled_orders = len([o for o in data["orders"] if o["status"] == "cancelled"])

    total_amount = sum([o["amount"] for o in data["orders"] if o["status"] == "completed"])

    premium_orders = len([o for o in data["orders"] if o.get("premium_duration")])

    total_users = len(data["users"])

    total_referrals = len([u for u in data["users"].values() if u.get("referred_by")])

    total_stars_balance = sum([u.get("balance", 0) for u in data["users"].values()])

    total_withdrawals = len(data["withdrawals"])
    pending_withdrawals = len([w for w in data["withdrawals"] if w["status"] == "pending"])
    completed_withdrawals = len([w for w in data["withdrawals"] if w["status"] == "completed"])
    total_withdrawn = sum([w["net_amount"] for w in data["withdrawals"] if w["status"] == "completed"])
    total_withdraw_balance = sum([u.get("withdraw_balance", 0) for u in data["users"].values()])

    bot.send_message(
        message.chat.id,
        f"📊 *Статистика бота*\n\n"
        f"👥 Пользователей: {total_users}\n"
        f"👥 Рефералов: {total_referrals}\n"
        f"⭐ Всего звезд на балансах: {total_stars_balance}\n"
        f"💵 Всего $ для вывода: ${total_withdraw_balance:.2f}\n\n"
        f"📦 Всего заказов: {total_orders}\n"
        f"👑 Premium заказов: {premium_orders}\n"
        f"🟡 Ожидают: {pending_orders}\n"
        f"🟢 Подтверждены: {completed_orders}\n"
        f"🔴 Отклонены: {rejected_orders}\n"
        f"⚫ Отменены: {cancelled_orders}\n"
        f"💰 Общая сумма: {total_amount:.2f}$\n\n"
        f"💸 Всего заявок на вывод: {total_withdrawals}\n"
        f"🟡 Ожидают выплаты: {pending_withdrawals}\n"
        f"🟢 Выплачено: {completed_withdrawals}\n"
        f"🔴 Отклонено: {total_withdrawals - pending_withdrawals - completed_withdrawals}\n"
        f"💰 Всего выплачено: ${total_withdrawn:.2f}",
        parse_mode='Markdown'
    )


@bot.message_handler(commands=['top'])
def top_referrals_command(message):
    """Топ пользователей"""
    if message.from_user.id not in ADMIN_IDS:
        return

    data = load_data()

    top_balance = sorted(
        data["users"].values(),
        key=lambda x: x.get("balance", 0),
        reverse=True
    )[:10]

    top_refs = []
    for user in data["users"].values():
        ref_count = 0
        referral_code = user.get("referral_code")
        if referral_code:
            ref_count = len([u for u in data["users"].values() if u.get("referred_by") == referral_code])

        top_refs.append((user, ref_count))

    top_refs = sorted(top_refs, key=lambda x: x[1], reverse=True)[:10]

    response = "🏆 *Топ по балансу звезд:*\n\n"
    for i, user in enumerate(top_balance, 1):
        response += f"{i}. @{user.get('username', 'Без имени')} (ID: {user['user_id']})\n"
        response += f"   Баланс: {user.get('balance', 0)}⭐ | Для вывода: ${user.get('withdraw_balance', 0):.2f}\n\n"

    response += "👥 *Топ по рефералам:*\n\n"
    for i, (user, ref_count) in enumerate(top_refs, 1):
        response += f"{i}. @{user.get('username', 'Без имени')} (ID: {user['user_id']})\n"
        response += f"   Рефералов: {ref_count}\n\n"

    bot.send_message(message.chat.id, response, parse_mode='Markdown')


@bot.message_handler(commands=['addstars'])
def add_stars_command(message):
    """Команда добавления звезд"""
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        parts = message.text.split()
        if len(parts) != 3:
            bot.send_message(message.chat.id, "Использование: /addstars <user_id> <количество>")
            return

        user_id = int(parts[1])
        stars = int(parts[2])

        update_user_balance(user_id, stars, add=True)
        usd_earned = stars * STAR_RATE
        update_withdraw_balance(user_id, usd_earned, add=True)

        add_admin_log(
            message.from_user.id,
            "addstars_command",
            f"Начислено {stars} звезд (${usd_earned:.2f}) пользователю {user_id}"
        )

        try:
            bot.send_message(
                user_id,
                f"🎉 *Вам начислены звезды!*\n\n"
                f"⭐ Количество: {stars}\n"
                f"💰 В долларах: ${usd_earned:.2f}\n"
                f"💫 Текущий баланс: {get_user_balance(user_id)} звезд\n"
                f"💵 Баланс для вывода: ${get_user_withdraw_balance(user_id):.2f}",
                parse_mode='Markdown'
            )
        except:
            pass

        bot.send_message(
            message.chat.id,
            f"✅ Пользователю {user_id} начислено {stars} звезд (${usd_earned:.2f})"
        )

    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверный формат команды")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")


@bot.message_handler(commands=['removestars'])
def remove_stars_command(message):
    """Команда списания звезд"""
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        parts = message.text.split()
        if len(parts) != 3:
            bot.send_message(message.chat.id, "Использование: /removestars <user_id> <количество>")
            return

        user_id = int(parts[1])
        stars = int(parts[2])

        user_balance = get_user_balance(user_id)
        if user_balance < stars:
            bot.send_message(
                message.chat.id,
                f"❌ Недостаточно звезд на балансе. У пользователя: {user_balance} звезд"
            )
            return

        update_user_balance(user_id, stars, add=False)
        usd_lost = stars * STAR_RATE
        update_withdraw_balance(user_id, usd_lost, add=False)

        add_admin_log(
            message.from_user.id,
            "removestars_command",
            f"Списано {stars} звезд (${usd_lost:.2f}) у пользователя {user_id}"
        )

        try:
            bot.send_message(
                user_id,
                f"⚠️ *С вашего баланса списаны звезды*\n\n"
                f"⭐ Количество: {stars}\n"
                f"💰 В долларах: ${usd_lost:.2f}\n"
                f"💫 Текущий баланс: {get_user_balance(user_id)} звезд\n"
                f"💵 Баланс для вывода: ${get_user_withdraw_balance(user_id):.2f}",
                parse_mode='Markdown'
            )
        except:
            pass

        bot.send_message(
            message.chat.id,
            f"✅ С пользователя {user_id} списано {stars} звезд (${usd_lost:.2f})"
        )

    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверный формат команды")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")


@bot.message_handler(commands=['ban'])
def ban_command(message):
    """Команда бана пользователя"""
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            bot.send_message(message.chat.id, "Использование: /ban <user_id> <причина>")
            return

        user_id = int(parts[1])
        reason = parts[2]

        if ban_user(user_id, reason, message.from_user.id):
            try:
                bot.send_message(
                    user_id,
                    f"❌ *Вы были заблокированы!*\n\n"
                    f"Причина: {reason}\n\n"
                    f"По вопросам обращайтесь в поддержку.",
                    parse_mode='Markdown'
                )
            except:
                pass

            bot.send_message(message.chat.id, f"✅ Пользователь {user_id} заблокирован")
        else:
            bot.send_message(message.chat.id, f"❌ Пользователь {user_id} не найден")

    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверный формат команды")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")


@bot.message_handler(commands=['unban'])
def unban_command(message):
    """Команда разбана пользователя"""
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.send_message(message.chat.id, "Использование: /unban <user_id>")
            return

        user_id = int(parts[1])

        if unban_user(user_id, message.from_user.id):
            try:
                bot.send_message(
                    user_id,
                    "✅ *Ваш аккаунт разблокирован!*\n\n"
                    "Теперь вы снова можете пользоваться ботом.",
                    parse_mode='Markdown'
                )
            except:
                pass

            bot.send_message(message.chat.id, f"✅ Пользователь {user_id} разблокирован")
        else:
            bot.send_message(message.chat.id, f"❌ Пользователь {user_id} не найден или не забанен")

    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверный формат команды")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")


@bot.message_handler(commands=['userinfo'])
def userinfo_command(message):
    """Команда информации о пользователе"""
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.send_message(message.chat.id, "Использование: /userinfo <user_id>")
            return

        user_id = int(parts[1])
        user_stats = get_user_stats(user_id)

        data = load_data()
        user_id_str = str(user_id)

        if user_id_str in data["users"]:
            user = data["users"][user_id_str]

            first_name = escape_markdown(user.get('first_name', ''))
            last_name = escape_markdown(user.get('last_name', ''))
            username = escape_markdown(user.get('username', 'нет'))
            ban_reason = escape_markdown(user.get('ban_reason', 'нет'))

            referrals = []
            referral_code = user.get("referral_code")
            if referral_code:
                for uid, u in data["users"].items():
                    if u.get("referred_by") == referral_code:
                        ref_username = escape_markdown(u.get('username', 'Без имени'))
                        referrals.append(f"@{ref_username} (ID: {uid})")

            user_orders = [o for o in data["orders"] if o["user_id"] == user_id]
            total_spent = sum([o["amount"] for o in user_orders if o["status"] == "completed"])

            user_withdrawals = [w for w in data["withdrawals"] if w["user_id"] == user_id]
            total_withdrawn = sum([w["net_amount"] for w in user_withdrawals if w["status"] == "completed"])

            info_text = (
                f"👤 *Информация о пользователе*\n\n"
                f"🆔 ID: `{user_id}`\n"
                f"👤 Имя: {first_name} {last_name}\n"
                f"📛 Ник: @{username}\n"
                f"🚫 Статус: {'Забанен' if user.get('is_banned') else 'Активен'}\n"
                f"📝 Причина бана: {ban_reason}\n\n"
                f"⭐ Баланс: {user.get('balance', 0)} звезд\n"
                f"💰 Всего заработано: {user.get('total_earned', 0)} звезд\n"
                f"💵 Для вывода: ${user.get('withdraw_balance', 0):.2f}\n"
                f"💸 Всего выведено: ${user.get('total_withdrawn', 0):.2f}\n"
                f"🔗 Реферальный код: {user.get('referral_code', 'нет')}\n"
                f"👥 Рефералов: {user_stats['referrals_count']}\n"
                f"📅 Регистрация: {user.get('created_at', 'неизвестно')}\n\n"
                f"📦 Заказов: {len(user_orders)}\n"
                f"💰 Всего потрачено: {total_spent:.2f}$\n"
                f"💸 Выводов: {len([w for w in user_withdrawals if w['status'] == 'completed'])}\n"
                f"💵 Всего выведено: ${total_withdrawn:.2f}"
            )

            if referrals:
                info_text += f"\n\n👥 *Последние рефералы:*\n" + "\n".join(referrals[:5])
                if len(referrals) > 5:
                    info_text += f"\n... и еще {len(referrals) - 5}"

            bot.send_message(message.chat.id, info_text, parse_mode='Markdown')
        else:
            bot.send_message(message.chat.id, f"❌ Пользователь {user_id} не найден")

    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверный формат команды")
    except Exception as e:
        logging.error(f"Ошибка в userinfo_command: {e}")
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")


@bot.message_handler(commands=['export_orders'])
def export_orders_command(message):
    """Экспорт заказов"""
    if message.from_user.id not in ADMIN_IDS:
        return

    data = load_data()

    if not data["orders"]:
        bot.send_message(message.chat.id, "📭 Нет заказов для экспорта")
        return

    export_file = f"orders_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(export_file, 'w', encoding='utf-8') as f:
        json.dump(data["orders"], f, ensure_ascii=False, indent=2)

    add_admin_log(
        message.from_user.id,
        "export_orders",
        f"Экспортировано {len(data['orders'])} заказов в {export_file}"
    )

    bot.send_message(
        message.chat.id,
        f"✅ Экспортировано {len(data['orders'])} заказов в файл: {export_file}"
    )


@bot.message_handler(commands=['export_users'])
def export_users_command(message):
    """Экспорт пользователей"""
    if message.from_user.id not in ADMIN_IDS:
        return

    data = load_data()

    if not data["users"]:
        bot.send_message(message.chat.id, "👥 Нет пользователей для экспорта")
        return

    export_file = f"users_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(export_file, 'w', encoding='utf-8') as f:
        json.dump(data["users"], f, ensure_ascii=False, indent=2)

    add_admin_log(
        message.from_user.id,
        "export_users",
        f"Экспортировано {len(data['users'])} пользователей в {export_file}"
    )

    bot.send_message(
        message.chat.id,
        f"✅ Экспортировано {len(data['users'])} пользователей в файл: {export_file}"
    )


@bot.message_handler(commands=['export_withdrawals'])
def export_withdrawals_command(message):
    """Экспорт заявок на вывод"""
    if message.from_user.id not in ADMIN_IDS:
        return

    data = load_data()

    if not data["withdrawals"]:
        bot.send_message(message.chat.id, "💸 Нет заявок на вывод для экспорта")
        return

    export_file = f"withdrawals_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(export_file, 'w', encoding='utf-8') as f:
        json.dump(data["withdrawals"], f, ensure_ascii=False, indent=2)

    add_admin_log(
        message.from_user.id,
        "export_withdrawals",
        f"Экспортировано {len(data['withdrawals'])} заявок на вывод в {export_file}"
    )

    bot.send_message(
        message.chat.id,
        f"✅ Экспортировано {len(data['withdrawals'])} заявок на вывод в файл: {export_file}"
    )


@bot.message_handler(commands=['backup'])
def backup_data_command(message):
    """Создание бэкапа"""
    if message.from_user.id not in ADMIN_IDS:
        return

    data = load_data()
    backup_file = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    bot.send_message(message.chat.id, f"✅ Резервная копия создана: {backup_file}")


@bot.message_handler(commands=['resetdb'])
def reset_db_command(message):
    """Сброс базы данных"""
    if message.from_user.id not in ADMIN_IDS:
        return

    init_db()
    bot.send_message(message.chat.id, "✅ База данных сброшена и создана заново")


@bot.message_handler(commands=['balance'])
def check_balance(message):
    """Проверка баланса"""
    user_stats = get_user_stats(message.from_user.id)
    bot.send_message(
        message.chat.id,
        f"💰 *Ваш баланс*\n\n"
        f"⭐ Доступно: {user_stats['balance']} звезд\n"
        f"💵 Для вывода: ${user_stats['withdraw_balance']:.2f}\n"
        f"💰 Всего заработано: {user_stats['total_earned']} звезд\n"
        f"👥 Приглашено друзей: {user_stats['referrals_count']}",
        parse_mode='Markdown'
    )


@bot.message_handler(commands=['ref'])
def ref_info(message):
    """Информация о реферальной программе"""
    user_stats = get_user_stats(message.from_user.id)

    # Генерируем правильную реферальную ссылку
    bot_username = bot.get_me().username
    referral_link = f"https://t.me/{bot_username}?start={user_stats['referral_code']}"

    bot.send_message(
        message.chat.id,
        f"💰 *Партнерская программа*\n\n"
        f"Приглашайте людей и получаете:\n"
        f"• +{REFERRAL_SIGNUP_BONUS} звезды ⭐️ за каждого, кто зашел в бота\n"
        f"• +{REFERRAL_PURCHASE_BONUS} звезд ⭐️, если он совершил покупку\n\n"
        f"🔗 Ваша ссылка:\n"
        f"`{referral_link}`\n\n"
        f"📊 Статистика:\n"
        f"• Приглашено: {user_stats['referrals_count']}\n"
        f"• Заработано: {user_stats['total_earned']} звезд\n"
        f"• Для вывода: ${user_stats['withdraw_balance']:.2f}",
        parse_mode='Markdown'
    )


# ========== ОБРАБОТКА ОБЫЧНЫХ СООБЩЕНИЙ ==========

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    """Обработка текстовых сообщений"""
    if is_user_banned(message.from_user.id):
        return

    if message.text == "🌟 Купить звезды":
        buy_stars_callback = type('obj', (object,), {'message': message, 'data': 'buy_stars'})
        buy_stars(buy_stars_callback)
    elif message.text == "👑 Купить Premium":
        buy_premium_callback = type('obj', (object,), {'message': message, 'data': 'buy_premium'})
        buy_premium(buy_premium_callback)
    elif message.text == "📋 Мои заказы":
        my_orders_callback = type('obj', (object,), {'message': message, 'data': 'my_orders'})
        my_orders(my_orders_callback)
    elif message.text == "👤 Профиль":
        profile_callback = type('obj', (object,), {'message': message, 'data': 'profile'})
        show_profile(profile_callback)
    elif message.text == "💰 Заработать звезды":
        earn_callback = type('obj', (object,), {'message': message, 'data': 'earn_stars'})
        show_earn_stars(earn_callback)
    else:
        bot.send_message(message.chat.id, "Пожалуйста, используйте меню для навигации")

@bot.callback_query_handler(func=lambda call: call.data.startswith('pay_monobank_'))
def process_monobank_payment(call):
    """Обработка оплаты через Monobank"""
    if is_user_banned(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Вы заблокированы!")
        return

    try:
        stars = int(call.data.split('_')[2])
        prices = calculate_price(stars, "monobank")

        user_id = call.from_user.id
        recipient = get_user_session(user_id, "recipient")
        safe_recipient = escape_markdown(recipient) if recipient else ""

        order_id = create_order(
            user_id,
            call.from_user.username or call.from_user.first_name,
            recipient,
            stars,
            prices["uah"],
            "monobank"
        )

        markup = types.InlineKeyboardMarkup(row_width=1)
        btn_back = types.InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")
        markup.add(btn_back)

        try:
            bot.edit_message_text(
                f"💳 *Оплата через Monobank*\n\n"
                f"👤 Получатель: {safe_recipient}\n"
                f"⭐ Звезд: {stars}\n"
                f"💰 Сумма к оплате: {prices['uah']:.0f}₴\n\n"
                f"💳 *Реквизиты для оплаты:*\n"
                f"Номер карты: `{escape_markdown(MONOBANK_CARD)}`\n"
                f"Получатель: Рома\n\n"
                f"⏳ *Важно:*\n"
                f"Проверка платежа может занять 5–15 минут после отправки — это нормально.\n\n"
                f"📸 После оплаты отправьте скриншот чека в этот чат для подтверждения.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=markup
            )
        except:
            bot.send_message(
                call.message.chat.id,
                f"💳 *Оплата через Monobank*\n\n"
                f"👤 Получатель: {safe_recipient}\n"
                f"⭐ Звезд: {stars}\n"
                f"💰 Сумма к оплате: {prices['uah']:.0f}₴\n\n"
                f"💳 *Реквизиты для оплаты:*\n"
                f"Номер карты: `{escape_markdown(MONOBANK_CARD)}`\n"
                f"Получатель: Рома\n\n"
                f"⏳ *Важно:*\n"
                f"Проверка платежа может занять 5–15 минут после отправки — это нормально.\n\n"
                f"📸 После оплаты отправьте скриншот чека в этот чат для подтверждения.",
                parse_mode='Markdown',
                reply_markup=markup
            )

        msg = bot.send_message(call.message.chat.id, "📸 Отправьте скриншот чека об оплате:")
        bot.register_next_step_handler(msg, process_monobank_proof, order_id)

    except Exception as e:
        logging.error(f"Ошибка в process_monobank_payment: {e}")
        bot.answer_callback_query(call.id, "❌ Произошла ошибка")


def process_monobank_proof(message, order_id):
    """Обработка скриншота чека Monobank"""
    if is_user_banned(message.from_user.id):
        return

    if message.photo:
        file_id = message.photo[-1].file_id

        updates = {
            "payment_proof": "Скриншот чека Monobank",
            "payment_photo_id": file_id
        }

        update_order(order_id, updates)

        order = get_order(order_id)
        process_referral_earnings(order["user_id"], order_id, order["stars"], order["amount"])

        bot.send_message(message.chat.id, "✅ Скриншот чека получен! Заказ отправлен администраторам на проверку.")

        notify_admins_with_photo(order, file_id)
    else:
        bot.send_message(message.chat.id, "❌ Пожалуйста, отправьте скриншот чека")
        msg = bot.send_message(message.chat.id, "📸 Отправьте скриншот чека об оплате:")
        bot.register_next_step_handler(msg, process_monobank_proof, order_id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('pay_ton_'))
def process_ton_payment(call):
    """Обработка оплаты через TON"""
    if is_user_banned(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Вы заблокированы!")
        return

    try:
        stars = int(call.data.split('_')[2])
        prices = calculate_price(stars, "ton")
        amount = prices["usd"]

        user_id = call.from_user.id
        recipient = get_user_session(user_id, "recipient")
        safe_recipient = escape_markdown(recipient) if recipient else ""

        order_id = create_order(
            user_id,
            call.from_user.username or call.from_user.first_name,
            recipient,
            stars,
            amount,
            "ton"
        )

        markup = types.InlineKeyboardMarkup(row_width=1)
        btn_back = types.InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")
        markup.add(btn_back)

        try:
            bot.edit_message_text(
                f"⚡️ *Оплата через TON*\n\n"
                f"👤 Получатель: {safe_recipient}\n"
                f"⭐️ Звёзды: {stars}\n"
                f"💰 Сумма: {amount:.2f}$ ({prices['uah']:.0f}₴)\n"
                f"👛 Адрес для оплаты: `{escape_markdown(TON_WALLET)}`\n\n"
                f"⏳ *Важно:*\n"
                f"После оплаты обработка может занять до 10–15 минут — это нормально, "
                f"транзакция должна подтвердиться в сети.\n\n"
                f"📸 После отправки перевода пришлите скриншот транзакции в этот чат.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=markup
            )
        except:
            bot.send_message(
                call.message.chat.id,
                f"⚡️ *Оплата через TON*\n\n"
                f"👤 Получатель: {safe_recipient}\n"
                f"⭐️ Звёзды: {stars}\n"
                f"💰 Сумма: {amount:.2f}$ ({prices['uah']:.0f}₴)\n"
                f"👛 Адрес для оплаты: `{escape_markdown(TON_WALLET)}`\n\n"
                f"⏳ *Важно:*\n"
                f"После оплата обработка может занять до 10–15 минут — это нормально, "
                f"транзакция должна подтвердиться в сети.\n\n"
                f"📸 После отправки перевода пришлите скриншот транзакции в этот чат.",
                parse_mode='Markdown',
                reply_markup=markup
            )

        msg = bot.send_message(call.message.chat.id, "📸 Отправьте скриншот транзакции (фото):")
        bot.register_next_step_handler(msg, process_ton_proof, order_id)

    except Exception as e:
        logging.error(f"Ошибка в process_ton_payment: {e}")
        bot.answer_callback_query(call.id, "❌ Произошла ошибка")


def process_ton_proof(message, order_id):
    """Обработка скриншота транзакции TON"""
    if is_user_banned(message.from_user.id):
        return

    if message.photo:
        file_id = message.photo[-1].file_id

        updates = {
            "payment_proof": "Фото транзакции TON",
            "payment_photo_id": file_id
        }

        update_order(order_id, updates)

        order = get_order(order_id)
        process_referral_earnings(order["user_id"], order_id, order["stars"], order["amount"])

        bot.send_message(message.chat.id, "✅ Скриншот транзакции получен! Заказ отправлен администраторам на проверку.")

        notify_admins_with_photo(order, file_id)
    else:
        bot.send_message(message.chat.id, "❌ Пожалуйста, отправьте скриншот транзакции")
        msg = bot.send_message(message.chat.id, "📸 Отправьте скриншот транзакции (фото):")
        bot.register_next_step_handler(msg, process_ton_proof, order_id)


# ========== ВЫВОД СРЕДСТВ ==========

@bot.callback_query_handler(func=lambda call: call.data == "withdraw_menu")
def withdraw_menu(call):
    """Меню вывода средств"""
    if is_user_banned(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Вы заблокированы!")
        return

    user_stats = get_user_stats(call.from_user.id)
    withdraw_balance = user_stats['withdraw_balance']

    min_stars_for_balance = MIN_WITHDRAW_STARS
    min_usd_for_withdraw = min_stars_for_balance * STAR_RATE

    if withdraw_balance < min_usd_for_withdraw:
        bot.answer_callback_query(
            call.id,
            f"❌ Минимальная сумма для вывода: ${min_usd_for_withdraw:.2f} ({min_stars_for_balance}⭐)"
        )
        return

    max_stars = int(withdraw_balance / STAR_RATE)

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_80 = types.InlineKeyboardButton(f"80⭐ (${80 * STAR_RATE:.2f})", callback_data=f"withdraw_80")
    btn_100 = types.InlineKeyboardButton(f"100⭐ (${100 * STAR_RATE:.2f})", callback_data=f"withdraw_100")
    btn_250 = types.InlineKeyboardButton(f"250⭐ (${250 * STAR_RATE:.2f})", callback_data=f"withdraw_250")
    btn_500 = types.InlineKeyboardButton(f"500⭐ (${500 * STAR_RATE:.2f})", callback_data=f"withdraw_500")
    btn_all = types.InlineKeyboardButton(f"Все ${withdraw_balance:.2f}", callback_data=f"withdraw_all_{max_stars}")
    btn_custom = types.InlineKeyboardButton("Другое количество", callback_data="withdraw_custom")
    btn_back = types.InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")
    markup.add(btn_80, btn_100, btn_250, btn_500, btn_all, btn_custom, btn_back)

    bot.edit_message_text(
        f"💸 *Вывод средств*\n\n"
        f"💰 *Доступно для вывода:* ${withdraw_balance:.2f}\n"
        f"⭐ *Примерно звезд:* {max_stars}\n"
        f"📊 *Комиссия:* {WITHDRAW_FEE_PERCENT}%\n\n"
        f"Выберите количество звезд для вывода:\n"
        f"• 80⭐ = ${80 * STAR_RATE:.2f} → ${80 * STAR_RATE * (1 - WITHDRAW_FEE_PERCENT / 100):.2f} после комиссии\n"
        f"• 100⭐ = ${100 * STAR_RATE:.2f} → ${100 * STAR_RATE * (1 - WITHDRAW_FEE_PERCENT / 100):.2f} после комиссии\n"
        f"• 250⭐ = ${250 * STAR_RATE:.2f} → ${250 * STAR_RATE * (1 - WITHDRAW_FEE_PERCENT / 100):.2f} после комиссии\n"
        f"• 500⭐ = ${500 * STAR_RATE:.2f} → ${500 * STAR_RATE * (1 - WITHDRAW_FEE_PERCENT / 100):.2f} после комиссии",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('withdraw_'))
def process_withdraw_selection(call):
    """Обработка выбора суммы вывода"""
    if is_user_banned(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Вы заблокированы!")
        return

    if call.data == "withdraw_custom":
        msg = bot.send_message(
            call.message.chat.id,
            f"💸 Введите количество звезд для вывода (минимум {MIN_WITHDRAW_STARS}⭐):"
        )
        bot.register_next_step_handler(msg, process_custom_withdraw)
        return

    user_stats = get_user_stats(call.from_user.id)
    withdraw_balance = user_stats['withdraw_balance']

    if call.data.startswith("withdraw_all_"):
        try:
            max_stars = int(call.data.split("_")[2])
            stars = max_stars
        except:
            bot.answer_callback_query(call.id, "❌ Ошибка при обработке")
            return
    else:
        stars_map = {
            "withdraw_80": 80,
            "withdraw_100": 100,
            "withdraw_250": 250,
            "withdraw_500": 500
        }
        stars = stars_map.get(call.data, 80)

    usd_needed = stars * STAR_RATE
    if withdraw_balance < usd_needed:
        bot.answer_callback_query(
            call.id,
            f"❌ Недостаточно средств. Нужно: ${usd_needed:.2f}, доступно: ${withdraw_balance:.2f}"
        )
        return

    process_withdraw_request(call, stars)


def process_custom_withdraw(message):
    """Обработка пользовательской суммы вывода"""
    if is_user_banned(message.from_user.id):
        return

    try:
        stars = int(message.text)

        if stars < MIN_WITHDRAW_STARS:
            bot.send_message(message.chat.id, f"❌ Минимальная сумма для вывода: {MIN_WITHDRAW_STARS} звезд")
            return

        user_stats = get_user_stats(message.from_user.id)
        withdraw_balance = user_stats['withdraw_balance']
        usd_needed = stars * STAR_RATE

        if withdraw_balance < usd_needed:
            max_stars = int(withdraw_balance / STAR_RATE)
            bot.send_message(
                message.chat.id,
                f"❌ Недостаточно средств. Доступно: ${withdraw_balance:.2f} (примерно {max_stars}⭐)"
            )
            return

        class FakeCall:
            def __init__(self):
                self.from_user = message.from_user
                self.message = message
                self.data = f"custom_{stars}"

        process_withdraw_request(FakeCall(), stars)

    except ValueError:
        bot.send_message(message.chat.id, "❌ Пожалуйста, введите число")


def process_withdraw_request(call, stars):
    """Обработка запроса на вывод"""
    user_id = call.from_user.id
    user_stats = get_user_stats(user_id)

    calculation = calculate_withdraw(stars)

    markup = types.InlineKeyboardMarkup()
    btn_confirm = types.InlineKeyboardButton("✅ Подтвердить вывод", callback_data=f"confirm_withdraw_{stars}")
    btn_cancel = types.InlineKeyboardButton("❌ Отмена", callback_data="withdraw_menu")
    markup.add(btn_confirm, btn_cancel)

    bot.edit_message_text(
        f"💸 *Подтверждение вывода*\n\n"
        f"⭐ *Звезд для вывода:* {stars}\n"
        f"💰 *Сумма в $:* ${calculation['usd_amount']:.2f}\n"
        f"📊 *Комиссия ({WITHDRAW_FEE_PERCENT}%):* ${calculation['fee_amount']:.2f}\n"
        f"💵 *К получению:* ${calculation['net_amount']:.2f}\n\n"
        f"После подтверждения заявка будет отправлена администраторам на обработку.",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_withdraw_'))
def confirm_withdraw(call):
    """Подтверждение вывода средств"""
    if is_user_banned(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Вы заблокированы!")
        return

    try:
        stars = int(call.data.split('_')[2])
        user_id = call.from_user.id
        user_stats = get_user_stats(user_id)

        withdraw_balance = user_stats['withdraw_balance']
        usd_needed = stars * STAR_RATE

        if withdraw_balance < usd_needed:
            bot.answer_callback_query(call.id, "❌ Недостаточно средств!")
            return

        calculation = calculate_withdraw(stars)
        withdrawal_id = add_withdrawal(
            user_id,
            stars,
            calculation['usd_amount'],
            calculation['net_amount'],
            calculation['fee_amount']
        )

        update_withdraw_balance(user_id, usd_needed, add=False)

        notify_admins_withdrawal(withdrawal_id)

        markup = types.InlineKeyboardMarkup()
        btn_back = types.InlineKeyboardButton("⬅️ На главную", callback_data="back_to_main")
        markup.add(btn_back)

        bot.edit_message_text(
            f"✅ *Заявка на вывод создана!*\n\n"
            f"📋 *ID заявки:* #{withdrawal_id}\n"
            f"⭐ *Звезд:* {stars}\n"
            f"💰 *Сумма:* ${calculation['usd_amount']:.2f}\n"
            f"💵 *К получению:* ${calculation['net_amount']:.2f}\n\n"
            f"Заявка отправлена администраторам на обработку. "
            f"Выплата будет произведена в течение 24 часов.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=markup
        )

        bot.answer_callback_query(call.id, "✅ Заявка отправлена!")

    except Exception as e:
        logging.error(f"Ошибка в confirm_withdraw: {e}")
        bot.answer_callback_query(call.id, "❌ Произошла ошибка")


# ========== ЗАКАЗЫ ==========

@bot.callback_query_handler(func=lambda call: call.data == "my_orders")
def my_orders(call):
    """Показать заказы пользователя"""
    if is_user_banned(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Вы заблокированы!")
        return

    orders = get_user_orders(call.from_user.id, limit=10)

    if not orders:
        markup = types.InlineKeyboardMarkup()
        btn_back = types.InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")
        markup.add(btn_back)
        bot.send_message(call.message.chat.id, "📭 У вас еще нет заказов", reply_markup=markup)
        return

    response = "📋 *Ваши последние заказы*\n\n"
    for order in orders:
        try:
            status_icons = {
                'pending': '🟡',
                'completed': '🟢',
                'rejected': '🔴',
                'cancelled': '⚫'
            }

            product = f"{order['stars']} звезд"
            if order.get("premium_duration"):
                product = f"Premium ({order['premium_duration']})"

            method_texts = {
                "balance": "💎 Баланс",
                "crypto": "💳 Crypto Bot",
                "ton": "⚡ TON",
                "monobank": "💳 Monobank"
            }

            method_text = method_texts.get(order["payment_method"], order["payment_method"])
            amount_text = f"{order['amount']:.2f}{'₴' if order.get('currency') == 'UAH' else '$'}"

            response += (
                f"{status_icons.get(order['status'], '⚪')} *Заказ #{order['id']}*\n"
                f"📦 Товар: {product}\n"
                f"⭐ Звезд: {order['stars']}\n"
                f"💰 Сумма: {amount_text}\n"
                f"📊 Статус: {order['status']}\n"
                f"🔗 Оплата: {method_text}\n"
                f"⏰ Дата: {order['created_at']}\n\n"
            )
        except Exception as e:
            logging.error(f"Ошибка при обработке заказа: {e}")
            continue

    markup = types.InlineKeyboardMarkup()
    btn_back = types.InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")
    markup.add(btn_back)

    bot.send_message(call.message.chat.id, response, parse_mode='Markdown', reply_markup=markup)


# ========== PREMIUM ==========

@bot.callback_query_handler(func=lambda call: call.data == "buy_premium")
def buy_premium(call):
    """Покупка Premium"""
    if is_user_banned(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Вы заблокированы!")
        return

    premium_options = {
        "3 месяца": {"price": "12.99", "code": "3"},
        "6 месяцев": {"price": "17.99", "code": "6"},
        "1 год": {"price": "31.99", "code": "12"}
    }

    markup = types.InlineKeyboardMarkup(row_width=1)
    for duration, data in premium_options.items():
        stars_needed = int(float(data["price"]) / STAR_RATE)
        btn = types.InlineKeyboardButton(
            f"{duration} - {data['price']}$ ({stars_needed}⭐)",
            callback_data=f"premium_choose_{data['code']}_{data['price']}_{stars_needed}"
        )
        markup.add(btn)

    btn_back = types.InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")
    markup.add(btn_back)

    try:
        bot.edit_message_text(
            f"👑 *Telegram Premium*\n\n"
            f"💎 Получите все преимущества:\n"
            f"• Увеличенные лимиты\n"
            f"• Эксклюзивные стикеры\n"
            f"• Отключение рекламы\n"
            f"• И многое другое\n\n"
            f"💰 Выберите вариант:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=markup
        )
    except Exception as e:
        logging.error(f"Ошибка при редактировании сообщения: {e}")
        bot.send_message(
            call.message.chat.id,
            f"👑 *Telegram Premium*\n\n"
            f"💎 Получите все преимущества:\n"
            f"• Увеличенные лимиты\n"
            f"• Эксклюзивные стикеры\n"
            f"• Отключение рекламы\n"
            f"• И многое другое\n\n"
            f"💰 Выберите вариант:",
            parse_mode='Markdown',
            reply_markup=markup
        )


@bot.callback_query_handler(func=lambda call: call.data.startswith('premium_choose_'))
def select_premium_duration(call):
    """Выбор продолжительности Premium"""
    if is_user_banned(call.from_user.id):
        return

    try:
        parts = call.data.split('_')

        if len(parts) != 5:
            return

        code = parts[2]
        price_str = parts[3]
        stars_str = parts[4]

        try:
            price = float(price_str)
            stars = int(stars_str)
        except ValueError:
            bot.answer_callback_query(call.id, "❌ Ошибка в данных заказа")
            return

        premium_names = {
            "3": "3 месяца",
            "6": "6 месяцев",
            "12": "1 год"
        }

        display_duration = premium_names.get(code, "Неизвестно")

        user_balance = get_user_balance(call.from_user.id)

        markup = types.InlineKeyboardMarkup(row_width=1)

        if user_balance >= stars:
            btn_balance = types.InlineKeyboardButton(
                f"💎 Использовать баланс ({user_balance}⭐)",
                callback_data=f"premium_pay_balance_{code}_{price_str}_{stars}"
            )
            markup.add(btn_balance)

        btn1 = types.InlineKeyboardButton(
            "💳 Crypto Bot",
            callback_data=f"premium_pay_crypto_{code}_{price_str}_{stars}"
        )
        btn2 = types.InlineKeyboardButton(
            "⚡ TON",
            callback_data=f"premium_pay_ton_{code}_{price_str}_{stars}"
        )
        btn3 = types.InlineKeyboardButton(
            "💳 Monobank",
            callback_data=f"premium_pay_monobank_{code}_{price_str}_{stars}"
        )
        markup.add(btn1, btn2, btn3)

        btn_back = types.InlineKeyboardButton("⬅️ Назад", callback_data="buy_premium")
        markup.add(btn_back)

        balance_info = f"\n💎 *Ваш баланс:* {user_balance} звезд (нужно {stars})" if user_balance > 0 else ""

        try:
            bot.edit_message_text(
                f"👑 *Telegram Premium ({display_duration})*\n\n"
                f"💰 Цена: {price}$\n"
                f"⭐ Необходимо звезд: {stars}{balance_info}\n\n"
                f"Выберите способ оплаты:",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=markup
            )
        except Exception as e:
            logging.error(f"Ошибка при редактировании сообщения: {e}")
            bot.send_message(
                call.message.chat.id,
                f"👑 *Telegram Premium ({display_duration})*\n\n"
                f"💰 Цена: {price}$\n"
                f"⭐ Необходимо звезд: {stars}{balance_info}\n\n"
                f"Выберите способ оплаты:",
                parse_mode='Markdown',
                reply_markup=markup
            )

    except Exception as e:
        logging.error(f"Ошибка в select_premium_duration: {e}")
        bot.answer_callback_query(call.id, "❌ Произошла ошибка при обработке заказа")


# Остальные функции для Premium аналогичны...

# ========== ВОЗВРАТ В ГЛАВНОЕ МЕНЮ ==========

@bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
def back_to_main(call):
    """Возврат в главное меню"""
    if is_user_banned(call.from_user.id):
        return

    clear_user_session(call.from_user.id)

    user_stats = get_user_stats(call.from_user.id)
    withdraw_balance = user_stats['withdraw_balance']

    has_withdrawable = withdraw_balance >= (MIN_WITHDRAW_STARS * STAR_RATE)

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🌟 Купить звезды", callback_data="buy_stars")
    btn2 = types.InlineKeyboardButton("👑 Купить Premium", callback_data="buy_premium")
    btn3 = types.InlineKeyboardButton("👤 Профиль", callback_data="profile")
    btn4 = types.InlineKeyboardButton("👨‍💻 Поддержка", url=SUPPORT_URL)
    btn5 = types.InlineKeyboardButton("📋 Мои заказы", callback_data="my_orders")
    btn6 = types.InlineKeyboardButton("📢 Наш канал", url=CHANNEL_URL)
    btn7 = types.InlineKeyboardButton("💰 Заработать звезды", callback_data="earn_stars")

    if has_withdrawable:
        btn8 = types.InlineKeyboardButton(f"💸 Вывод ${withdraw_balance:.2f}", callback_data="withdraw_menu")
        markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn8)
    else:
        markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7)

    try:
        bot.edit_message_text(
            "✨ *Добро пожаловать в VL Shop!*\n\n"
            "Здесь вы можете купить Telegram Звёзды и Premium по выгодным ценам "
            "и с быстрой обработкой заказов. Цены ниже, чем в самом приложении.\n\n"
            "Выберите нужный раздел ниже.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=markup
        )
    except Exception as e:
        logging.error(f"Ошибка при возврате в главное меню: {e}")
        bot.send_message(
            call.message.chat.id,
            "✨ *Добро пожаловать в VL Shop!*\n\n"
            "Здесь вы можете купить Telegram Звёзды и Premium по выгодным ценам "
            "и с быстрой обработкой заказов. Цены ниже, чем в самом приложении.\n\n"
            "Выберите нужный раздел ниже.",
            parse_mode='Markdown',
            reply_markup=markup
        )


# ========== ОБРАБОТКА ДЕЙСТВИЙ АДМИНИСТРАТОРОВ ==========

@bot.callback_query_handler(
    func=lambda call: call.data.startswith('accept_') or call.data.startswith('reject_')
)
def admin_action(call):
    """Обработка действий администратора по заказам"""
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "❌ У вас нет прав для этого действия")
        return

    action, order_id = call.data.split('_')
    order_id = int(order_id)

    order = get_order(order_id)

    if not order:
        bot.answer_callback_query(call.id, "❌ Заказ не найден")
        return

    if action == "accept":
        update_order(order_id, {"status": "completed"})
        status_text = "✅ подтвержден"

        add_admin_log(
            call.from_user.id,
            "accept_order",
            f"Подтвержден заказ #{order_id} от пользователя {order['user_id']}"
        )

        try:
            bot.send_message(
                order["user_id"],
                f"🎉 *Ваш заказ #{order_id} подтвержден*\n\n"
                f"Товар будет отправлен в течении 30-60 минут.",
                parse_mode='Markdown'
            )
        except:
            pass

    else:
        update_order(order_id, {"status": "rejected"})
        status_text = "❌ отклонен"

        add_admin_log(
            call.from_user.id,
            "reject_order",
            f"Отклонен заказ #{order_id} от пользователя {order['user_id']}"
        )

        try:
            bot.send_message(
                order["user_id"],
                f"❌ *Ваш заказ #{order_id} отклонен*\n\n"
                f"Если у вас есть вопросы, обратитесь в поддержку.",
                parse_mode='Markdown'
            )
        except:
            pass

    try:
        if call.message.photo:
            admin_name = call.from_user.username or call.from_user.first_name or call.from_user.id
            new_caption = call.message.caption + f"\n\n✅ *Статус: {status_text.upper()} администратором {escape_markdown(str(admin_name))}*"
            bot.edit_message_caption(
                new_caption,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )
        else:
            admin_name = call.from_user.username or call.from_user.first_name or call.from_user.id
            bot.edit_message_text(
                f"Заказ #{order_id} {status_text} администратором {admin_name}",
                call.message.chat.id,
                call.message.message_id
            )
    except Exception as e:
        logging.error(f"Ошибка при редактировании сообщения: {e}")

    bot.answer_callback_query(call.id, f"Заказ {status_text}")


@bot.callback_query_handler(
    func=lambda call: call.data.startswith('withdraw_accept_') or call.data.startswith('withdraw_reject_')
)
def process_withdraw_admin_action(call):
    """Обработка действий администратора по выводам"""
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "❌ У вас нет прав для этого действия")
        return

    action, withdrawal_id = call.data.split('_')[2], int(call.data.split('_')[3])

    data = load_data()
    withdrawal = None
    for w in data["withdrawals"]:
        if w["id"] == withdrawal_id:
            withdrawal = w
            break

    if not withdrawal:
        bot.answer_callback_query(call.id, "❌ Заявка не найдена")
        return

    user_id = withdrawal["user_id"]

    if action == "accept":
        update_withdrawal(withdrawal_id, {
            "status": "completed",
            "processed_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "processed_by": call.from_user.id
        })

        data = load_data()
        user_id_str = str(user_id)
        if user_id_str in data["users"]:
            data["users"][user_id_str]["total_withdrawn"] += withdrawal["net_amount"]
            save_data(data)

        try:
            bot.send_message(
                user_id,
                f"🎉 *Ваша заявка на вывод #{withdrawal_id} одобрена!*\n\n"
                f"💰 *Сумма:* ${withdrawal['net_amount']:.2f}\n"
                f"⭐ *Звезд:* {withdrawal['stars']}\n"
                f"⏰ *Время обработки:* {datetime.now().strftime('%H:%M:%S')}\n\n"
                f"Средства будут переведены в течение 24 часов.",
                parse_mode='Markdown'
            )
        except:
            pass

        status_text = "✅ выплачена"

        add_admin_log(
            call.from_user.id,
            "withdraw_accept",
            f"Одобрен вывод #{withdrawal_id} пользователю {user_id} на сумму ${withdrawal['net_amount']:.2f}"
        )

    else:
        update_withdraw_balance(user_id, withdrawal["usd_amount"], add=True)

        update_withdrawal(withdrawal_id, {
            "status": "rejected",
            "processed_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "processed_by": call.from_user.id
        })

        try:
            bot.send_message(
                user_id,
                f"❌ *Ваша заявка на вывод #{withdrawal_id} отклонена*\n\n"
                f"⭐ *Звезд:* {withdrawal['stars']} возвращены на баланс\n"
                f"💵 *Баланс для вывода:* ${get_user_withdraw_balance(user_id):.2f}\n\n"
                f"По вопросам обращайтесь в поддержку.",
                parse_mode='Markdown'
            )
        except:
            pass

        status_text = "❌ отклонена"

        add_admin_log(
            call.from_user.id,
            "withdraw_reject",
            f"Отклонен вывод #{withdrawal_id} пользователю {user_id}"
        )

    try:
        admin_name = call.from_user.username or call.from_user.first_name or call.from_user.id
        bot.edit_message_text(
            f"Заявка на вывод #{withdrawal_id} {status_text} администратором {admin_name}",
            call.message.chat.id,
            call.message.message_id
        )
    except Exception as e:
        logging.error(f"Ошибка при редактировании сообщения: {e}")

    bot.answer_callback_query(call.id, f"Заявка {status_text}")


# ========== ОСНОВНОЙ ЦИКЛ ==========

if __name__ == "__main__":
    # Обновляем курс валют
    update_uah_rate()

    print("=" * 50)
    print("Инициализация бота VL Shop...")
    print("=" * 50)

    # Инициализация базы данных
    print("Инициализация базы данных...")
    init_db()

    # Запуск потока рассылки
    broadcast_thread = threading.Thread(target=send_broadcast_messages, daemon=True)
    broadcast_thread.start()
    print("Поток рассылки запущен...")

    # Вывод информации о конфигурации
    print(f"Файл базы данных: {DATA_FILE}")
    print(f"Минимальная сумма вывода: {MIN_WITHDRAW_STARS} звезд (${MIN_WITHDRAW_STARS * STAR_RATE:.2f})")
    print(f"Комиссия на вывод: {WITHDRAW_FEE_PERCENT}%")
    print(f"Реферальный бонус за регистрацию: {REFERRAL_SIGNUP_BONUS} звезд")
    print(f"Реферальный бонус за покупку: {REFERRAL_PURCHASE_BONUS} звезд")
    print(f"Автоматическая рассылка настроена: {len(BROADCAST_MESSAGES)} сообщений")
    print("=" * 50)
    print("Бот запущен и готов к работе!")
    print("=" * 50)

    # Запуск бота
    bot.infinity_polling()
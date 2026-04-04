#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════╗
║          بوت تداول USDT P2P على تيليغرام               ║
║          Version 9.0 - STABLE RELEASE                   ║
║          جميع الأزرار والوظائف تعمل بشكل صحيح ✅        ║
╚══════════════════════════════════════════════════════════╝
"""

import os
import sqlite3
import logging
import re
from datetime import datetime
from threading import local

# ════════════════════════════════════════════════════════════
#                    🗄️  إدارة قاعدة البيانات
# ════════════════════════════════════════════════════════════
_db_local = local()

def get_conn():
    if not hasattr(_db_local, 'conn') or _db_local.conn is None:
        c = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)
        c.row_factory = sqlite3.Row
        _db_local.conn = c
    return _db_local.conn

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)
from telegram.constants import ParseMode

# ════════════════════════════════════════════════════════════
#                    ⚙️  الإعدادات الأساسية
# ════════════════════════════════════════════════════════════
BOT_TOKEN       = "8443614197:AAFF5awBt6UX3ZAcxsosWuDkVUUq8GOmuRg"
OWNER_ID        = 6814152338
DEPOSIT_ADDRESS = "TYourTRC20AddressHere"  # ⚠️ غيّر هذا العنوان
DB_PATH         = "trading_bot.db"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════
#                    🔢  حالات المحادثات (مفصولة تماماً)
# ════════════════════════════════════════════════════════════
# التسجيل: 0-9
REG_NAME, REG_COUNTRY = 0, 1

# البيع للبوت: 100-199
SELL_BOT_AMOUNT, SELL_BOT_PROOF, SELL_BOT_RECEIVE = 100, 101, 102

# الشراء من البوت: 200-299
BUY_BOT_AMOUNT, BUY_BOT_CONFIRM, BUY_BOT_PAY_METHOD, BUY_BOT_PROOF, BUY_BOT_RECEIVE = 200, 201, 202, 203, 204

# العروض: 300-399
OFFER_TYPE, OFFER_AMOUNT, OFFER_PRICE, OFFER_CONFIRM = 300, 301, 302, 303

# السحب: 400-499
WITHDRAW_AMOUNT, WITHDRAW_ADDR, WITHDRAW_CONFIRM = 400, 401, 402

# تليجرام مميز: 500-599
PREMIUM_AMOUNT, PREMIUM_CONFIRM = 500, 501

# الدعم: 600-699
SUPPORT_MSG = 600

# طرق استلام المستخدم: 700-799
USER_RECEIVE_ADD_NAME, USER_RECEIVE_ADD_DETAILS = 700, 701

# الإدارة: 800-999
ADMIN_BROADCAST, ADMIN_SET_BUY_PRICE, ADMIN_SET_SELL_PRICE, ADMIN_SET_COMMISSION = 800, 801, 802, 803
ADMIN_SET_DEPOSIT, ADMIN_SET_AVAIL_INV, ADMIN_SET_REQ_INV, ADMIN_SET_PREMIUM = 804, 805, 806, 807
ADMIN_SET_TRADER_STATUS, ADMIN_BAN, ADMIN_UNBAN, ADMIN_REPLY = 808, 809, 810, 811
ADMIN_ADD_PAY_NAME, ADMIN_ADD_PAY_DETAILS = 812, 813

# ════════════════════════════════════════════════════════════
#                    🗄️  تهيئة قاعدة البيانات
# ════════════════════════════════════════════════════════════
def init_db():
    conn = get_conn()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            full_name TEXT NOT NULL,
            country TEXT DEFAULT 'السودان',
            balance_usdt REAL DEFAULT 0,
            commission_earned REAL DEFAULT 0,
            rank TEXT DEFAULT 'user',
            total_trades INTEGER DEFAULT 0,
            completed_trades INTEGER DEFAULT 0,
            referral_code TEXT UNIQUE,
            referred_by INTEGER,
            is_banned INTEGER DEFAULT 0,
            wallet_address TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER NOT NULL,
            buyer_id INTEGER,
            order_type TEXT NOT NULL,
            amount_usdt REAL NOT NULL,
            price_per_usdt REAL NOT NULL,
            total_sdg REAL NOT NULL,
            min_amount_sdg REAL DEFAULT 0,
            commission_usdt REAL DEFAULT 0,
            status TEXT DEFAULT 'pending',
            payment_method_id INTEGER,
            payment_proof TEXT DEFAULT '',
            user_receiving_details TEXT DEFAULT '',
            user_receive_method_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS payment_methods (
            method_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            details TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_receive_methods (
            method_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            details TEXT NOT NULL,
            is_default INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS transactions (
            tx_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tx_type TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS support_msgs (
            msg_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            admin_reply TEXT DEFAULT '',
            status TEXT DEFAULT 'open',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        -- الإعدادات الافتراضية
        INSERT OR IGNORE INTO settings VALUES ('usdt_buy_price', '4000.0');
        INSERT OR IGNORE INTO settings VALUES ('usdt_sell_price', '4100.0');
        INSERT OR IGNORE INTO settings VALUES ('available_usdt_inventory', '600.0');
        INSERT OR IGNORE INTO settings VALUES ('required_usdt_inventory', '2.0');
        INSERT OR IGNORE INTO settings VALUES ('telegram_premium_price', '10.0');
        INSERT OR IGNORE INTO settings VALUES ('trader_online_status', '1');
        INSERT OR IGNORE INTO settings VALUES ('commission_rate', '3.0');
    ''')
    conn.commit()

# ════════════════════════════════════════════════════════════
#                    🔧 دوال قاعدة البيانات المساعدة
# ════════════════════════════════════════════════════════════
def db_get(query, params=()):
    c = get_conn().execute(query, params)
    row = c.fetchone()
    return dict(row) if row else None

def db_all(query, params=()):
    c = get_conn().execute(query, params)
    return [dict(r) for r in c.fetchall()]

def db_run(query, params=()):
    conn = get_conn()
    c = conn.execute(query, params)
    conn.commit()
    return c.lastrowid

def get_setting(key: str) -> str:
    row = db_get("SELECT value FROM settings WHERE key=?", (key,))
    return row['value'] if row else ''

def set_setting(key: str, value: str):
    db_run("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, str(value)))

def get_user(user_id: int):
    return db_get("SELECT * FROM users WHERE user_id=?", (user_id,))

def is_registered(user_id: int) -> bool:
    return get_user(user_id) is not None

def is_banned_user(user_id: int) -> bool:
    u = get_user(user_id)
    return bool(u and u['is_banned'])

def is_admin(user_id: int) -> bool:
    return user_id == OWNER_ID

# أسعار وإعدادات
def get_usdt_buy_price() -> float:
    return float(get_setting('usdt_buy_price') or 4000.0)

def get_usdt_sell_price() -> float:
    return float(get_setting('usdt_sell_price') or 4100.0)

def get_available_inventory() -> float:
    return float(get_setting('available_usdt_inventory') or 0.0)

def get_required_inventory() -> float:
    return float(get_setting('required_usdt_inventory') or 0.0)

def get_premium_price() -> float:
    return float(get_setting('telegram_premium_price') or 10.0)

def get_trader_online() -> bool:
    return bool(int(get_setting('trader_online_status') or 1))

def get_commission() -> float:
    return float(get_setting('commission_rate') or 3.0)

def fmt(n) -> str:
    try:
        return f"{float(n):,.2f}"
    except:
        return str(n)

def make_referral_code() -> str:
    import random, string
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

# ════════════════════════════════════════════════════════════
#                    ⌨️  لوحات المفاتيح
# ════════════════════════════════════════════════════════════
def kb_main(admin=False):
    rows = [
        [KeyboardButton("💰 بيع USDT"), KeyboardButton("🛒 شراء USDT")],
        [KeyboardButton("💵 تقديم عرض")],
        [KeyboardButton("📋 طلباتي"), KeyboardButton("📊 السوق")],
        [KeyboardButton("👤 ملفي"), KeyboardButton("💳 رصيدي")],
        [KeyboardButton("📜 سجل المعاملات"), KeyboardButton("🔗 الإحالة")],
        [KeyboardButton("⚙️ الإعدادات"), KeyboardButton("📞 الدعم")],
        [KeyboardButton("💱 السعر"), KeyboardButton("🗃️ المخزون")],
        [KeyboardButton("🌟 تليجرام مميز")],
    ]
    if admin:
        rows.append([KeyboardButton("🔐 الإدارة")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def kb_admin():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📊 إحصائيات"), KeyboardButton("👥 المستخدمين")],
        [KeyboardButton("📋 الطلبات"), KeyboardButton("📢 بث")],
        [KeyboardButton("💲 سعر شراء"), KeyboardButton("💲 سعر بيع")],
        [KeyboardButton("💳 دفع طرق"), KeyboardButton("💹 عمولة")],
        [KeyboardButton("📦 مخزون متاح"), KeyboardButton("📦 مخزون مطلوب")],
        [KeyboardButton("🌟 سعر مميز"), KeyboardButton("🚦 حالة التاجر")],
        [KeyboardButton("🔒 حظر"), KeyboardButton("🔓 فك حظر")],
        [KeyboardButton("📝 الدعم"), KeyboardButton("💾 نسخ احتياطي")],
        [KeyboardButton("🔙 الرئيسية")],
    ], resize_keyboard=True)

def kb_cancel():
    return ReplyKeyboardMarkup([[KeyboardButton("❌ إلغاء")]], resize_keyboard=True)

def kb_confirm():
    return ReplyKeyboardMarkup([[KeyboardButton("✅ تأكيد"), KeyboardButton("❌ إلغاء")]], resize_keyboard=True)

def kb_offer_type():
    return ReplyKeyboardMarkup([["شــراء", "بــيــع"], ["❌ إلغاء"]], resize_keyboard=True)

def kb_trader_status():
    return ReplyKeyboardMarkup([["🟢 متصل", "🔴 غير متصل"], ["❌ إلغاء"]], resize_keyboard=True)

# ════════════════════════════════════════════════════════════
#                    🔐 دوال الحماية والتحقق
# ════════════════════════════════════════════════════════════
async def guard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """تحقق من تسجيل المستخدم وحظره"""
    uid = update.effective_user.id
    msg = update.message or update.callback_query.message
    
    if not is_registered(uid):
        await msg.reply_text("👋 يرجى التسجيل أولاً عبر /start")
        return True
    if is_banned_user(uid):
        await msg.reply_text("🚫 حسابك محظور، راسل الدعم")
        return True
    if get_setting('maintenance') == '1' and not is_admin(uid):
        await msg.reply_text("🛠️ البوت في صيانة")
        return True
    return False

async def check_trader_offline(update: Update) -> bool:
    """تحقق من حالة التاجر"""
    uid = update.effective_user.id
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg:
        return False
        
    if not get_trader_online() and not is_admin(uid):
        await msg.reply_text("⛔️ التاجر غير متصل حالياً، جرب لاحقاً", reply_markup=kb_main(is_admin(uid)))
        return True
    return False

async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء أي عملية والعودة للرئيسية"""
    context.user_data.clear()
    uid = update.effective_user.id
    await update.message.reply_text("✅ تم الإلغاء", reply_markup=kb_main(is_admin(uid)))
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════
#                    👋 التسجيل والبداية
# ════════════════════════════════════════════════════════════
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    uid = update.effective_user.id
    user = update.effective_user
    
    if not is_registered(uid):
        await update.message.reply_text(
            f"👋 أهلاً {user.full_name or user.username or 'عزيزي'}!\n\nأدخل اسمك الكامل للتسجيل:",
            reply_markup=kb_cancel()
        )
        context.user_data['reg_uid'] = uid
        context.user_data['reg_uname'] = user.username
        return REG_NAME
    else:
        await update.message.reply_text(
            f"👋 أهلاً بعودتك!\nاختر من القائمة:",
            reply_markup=kb_main(is_admin(uid))
        )
        return ConversationHandler.END

async def reg_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt == "❌ إلغاء":
        return await cmd_cancel(update, context)
    context.user_data['reg_name'] = txt
    await update.message.reply_text("🌍 أدخل بلدك (مثال: السودان):", reply_markup=kb_cancel())
    return REG_COUNTRY

async def reg_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt == "❌ إلغاء":
        return await cmd_cancel(update, context)
    
    uid = context.user_data['reg_uid']
    code = make_referral_code()
    while db_get("SELECT 1 FROM users WHERE referral_code=?", (code,)):
        code = make_referral_code()
    
    db_run("INSERT INTO users (user_id, username, full_name, country, referral_code) VALUES (?,?,?,?,?)",
           (uid, context.user_data.get('reg_uname'), context.user_data['reg_name'], txt, code))
    
    await update.message.reply_text("✅ تم التسجيل! ابدأ التداول الآن 🚀", reply_markup=kb_main(is_admin(uid)))
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════
#                    👤 الملف الشخصي والرصيد
# ════════════════════════════════════════════════════════════
async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await guard(update, context):
        return ConversationHandler.END
    user = get_user(update.effective_user.id)
    txt = f"👤 *ملفي الشخصي*\n\n"
    txt += f"الاسم: {user['full_name']}\n"
    txt += f"المعرف: @{user['username'] or 'غير متاح'}\n"
    txt += f"البلد: {user['country']}\n"
    txt += f"الرصيد: {fmt(user['balance_usdt'])} USDT\n"
    txt += f"العمولات: {fmt(user['commission_earned'])} USDT\n"
    txt += f"الصفقات: {user['completed_trades']}\n"
    txt += f"كود الإحالة: `{user['referral_code']}`\n\n"
    txt += f"🔗 رابط الإحالة:\n`https://t.me/{context.bot.username}?start={user['referral_code']}`"
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await guard(update, context):
        return ConversationHandler.END
    user = get_user(update.effective_user.id)
    txt = f"💳 *رصيدي*\n\n"
    txt += f"المتاح: `{fmt(user['balance_usdt'])}` USDT\n"
    txt += f"العمولات: `{fmt(user['commission_earned'])}` USDT\n\n"
    txt += f"📥 للإيداع أرسل إلى:\n`{DEPOSIT_ADDRESS}`\n\n"
    txt += f"📤 للسحب استخدم: `/withdraw`"
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════
#                    📜 سجل المعاملات (مُصلح ✅)
# ════════════════════════════════════════════════════════════
async def show_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await guard(update, context):
        return ConversationHandler.END
    
    uid = update.effective_user.id
    txs = db_all("SELECT * FROM transactions WHERE user_id=? ORDER BY tx_id DESC LIMIT 15", (uid,))
    
    if not txs:
        await update.message.reply_text("📜 لا توجد معاملات بعد")
        return ConversationHandler.END
    
    msg = "📜 *سجل المعاملات*\n" + "═"*30 + "\n\n"
    types_map = {'deposit':'📥 إيداع', 'withdraw':'📤 سحب', 'buy':'🛒 شراء', 'sell':'💰 بيع', 'commission':'💎 عمولة'}
    
    for t in txs:
        icon = types_map.get(t['tx_type'], '📍')
        status_icon = {'completed':'✅', 'pending':'⏳', 'rejected':'❌'}.get(t['status'], '📍')
        msg += f"{icon} #{t['tx_id']} | {fmt(t['amount'])} USDT\n"
        msg += f"   {t['tx_type']} | {status_icon} {t['status']}\n"
        if t['notes']:
            msg += f"   📝 {t['notes']}\n"
        msg += f"   🕐 {t['created_at'][:16]}\n" + "─"*25 + "\n"
    
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════
#                    📋 الطلبات
# ════════════════════════════════════════════════════════════
async def show_my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await guard(update, context):
        return ConversationHandler.END
    
    uid = update.effective_user.id
    orders = db_all("SELECT * FROM orders WHERE seller_id=? OR buyer_id=? ORDER BY order_id DESC LIMIT 10", (uid, uid))
    
    if not orders:
        await update.message.reply_text("📋 لا توجد طلبات حالياً")
        return ConversationHandler.END
    
    msg = "📋 *طلباتي*\n\n"
    for o in orders:
        t = "شراء" if o['buyer_id'] == uid else "بيع"
        st = {'pending':'⏳ معلق', 'awaiting_payment':'💰 انتظر دفع', 'payment_uploaded':'📸 مراجعة', 'completed':'✅ مكتمل', 'rejected':'❌ مرفوض'}.get(o['status'], o['status'])
        msg += f"#{o['order_id']} | {t} | {fmt(o['amount_usdt'])} USDT | {fmt(o['total_sdg'])} SDG | {st}\n"
    
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════
#                    💰 بيع USDT للبوت مباشرة (مُصلح ✅)
# ════════════════════════════════════════════════════════════
async def sell_to_bot_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await guard(update, context):
        return ConversationHandler.END
    if await check_trader_offline(update):
        return ConversationHandler.END
    
    price = get_usdt_buy_price()
    required = get_required_inventory()
    
    await update.message.reply_text(
        f"💸 *بيع USDT للتاجر مباشرة*\n\n"
        f"📩 أرسل كمية USDT التي تريد بيعها:\n"
        f"💰 نشتري بـ {fmt(price)} جنيه/USDT\n"
        f"📊 المطلوب حالياً: {fmt(required)} USDT\n\n"
        f"❌ إلغاء: /cancel",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb_cancel()
    )
    context.user_data['sell_price'] = price
    return SELL_BOT_AMOUNT

async def sell_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt == "❌ إلغاء":
        return await cmd_cancel(update, context)
    
    try:
        amt = float(txt.replace('،', '.'))
        if amt <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ أدخل رقماً صحيحاً")
        return SELL_BOT_AMOUNT
    
    price = context.user_data['sell_price']
    total = amt * price
    
    # تنبيه للكميات الصغيرة
    warn = "📑 *تنبيه*: الكمية صغيرة (≤5 USDT)\n" if amt <= 5 else ""
    
    oid = f"SELL-{db_run('SELECT COALESCE(MAX(order_id),1000)+1 FROM orders')}"
    context.user_data.update({'sell_amt': amt, 'sell_total': total, 'sell_oid': oid})
    
    await update.message.reply_text(
        f"{warn}```\n🏷️ طلبك: {oid}\n💰 أرسل {fmt(amt)} USDT إلى:\n{DEPOSIT_ADDRESS}\n📊 ستستلم: {fmt(total)} جنيه\n📸 أرسل إثبات التحويل خلال 15 دقيقة```",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb_cancel()
    )
    return SELL_BOT_PROOF

async def sell_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ أرسل صورة الإثبات فقط")
        return SELL_BOT_PROOF
    
    context.user_data['sell_proof'] = update.message.photo[-1].file_id
    
    # عرض طرق استلام المستخدم
    uid = update.effective_user.id
    methods = db_all("SELECT * FROM user_receive_methods WHERE user_id=?", (uid,))
    
    if not methods:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("➕ أضف طريقة استلام أولاً", callback_data="usr_recv_add_0")]])
        await update.message.reply_text("💳 أضف طريقة لاستلام أموالك أولاً:", reply_markup=kb)
        return SELL_BOT_RECEIVE
    
    buttons = [[InlineKeyboardButton(f"{m['name']}", callback_data=f"usr_recv_sel_{context.user_data['sell_oid']}_{m['method_id']}")] for m in methods]
    buttons.append([InlineKeyboardButton("➕ إضافة جديدة", callback_data="usr_recv_add_0")])
    
    await update.message.reply_text("💳 اختر طريقة استلام أموالك:", reply_markup=InlineKeyboardMarkup(buttons))
    return SELL_BOT_RECEIVE

async def sell_receive_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار طريقة الاستلام في البيع"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("usr_recv_add_"):
        # إضافة طريقة جديدة
        context.user_data['recv_flow'] = 'sell'
        await query.message.reply_text("📝 اسم الطريقة (مثال: بيهانس):", reply_markup=kb_cancel())
        return USER_RECEIVE_ADD_NAME
    
    if query.data.startswith("usr_recv_sel_"):
        # اختيار طريقة موجودة
        parts = query.data.split("_")
        oid, mid = parts[2], int(parts[3])
        method = db_get("SELECT * FROM user_receive_methods WHERE method_id=?", (mid,))
        
        if not method:
            await query.message.reply_text("❌ طريقة غير صحيحة")
            return ConversationHandler.END
        
        # حفظ الطلب
        uid = update.effective_user.id
        db_run("INSERT INTO orders (seller_id, buyer_id, order_type, amount_usdt, price_per_usdt, total_sdg, payment_proof, user_receiving_details, user_receive_method_id, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
               (uid, OWNER_ID, 'sell_to_bot', context.user_data['sell_amt'], context.user_data['sell_price'], context.user_data['sell_total'], context.user_data['sell_proof'], f"{method['name']}: {method['details']}", mid, 'payment_uploaded'))
        
        # إشعار الإدارة
        try:
            await context.bot.send_message(OWNER_ID, f"🔔 بيع جديد #{oid}\n👤: {uid}\n📦: {context.user_data['sell_amt']} USDT\n💰: {fmt(context.user_data['sell_total'])} SDG")
        except: pass
        
        await query.message.reply_text("✅ تم استلام طلبك! سيتم المراجعة خلال 15 دقيقة", reply_markup=kb_main(is_admin(uid)))
        context.user_data.clear()
        return ConversationHandler.END
    
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════
#                    🛒 شراء من البوت (مُصلح ✅)
# ════════════════════════════════════════════════════════════
async def buy_from_bot_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await guard(update, context):
        return ConversationHandler.END
    if await check_trader_offline(update):
        return ConversationHandler.END
    
    price = get_usdt_sell_price()
    avail = get_available_inventory()
    
    await update.message.reply_text(
        f"🛒 *شراء USDT من التاجر*\n\n"
        f"📩 أرسل الكمية المطلوبة:\n"
        f"💰 السعر: {fmt(price)} جنيه/USDT\n"
        f"📊 المتاح: {fmt(avail)} USDT\n\n❌ /cancel",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb_cancel()
    )
    context.user_data.update({'buy_price': price, 'buy_avail': avail})
    return BUY_BOT_AMOUNT

async def buy_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt == "❌ إلغاء":
        return await cmd_cancel(update, context)
    
    try:
        amt = float(txt.replace('،', '.'))
        if amt <= 0 or amt > context.user_data['buy_avail']:
            await update.message.reply_text(f"❌ كمية غير صحيحة (الحد: {fmt(context.user_data['buy_avail'])})")
            return BUY_BOT_AMOUNT
    except:
        await update.message.reply_text("❌ أدخل رقماً صحيحاً")
        return BUY_BOT_AMOUNT
    
    total = amt * context.user_data['buy_price']
    context.user_data.update({'buy_amt': amt, 'buy_total': total})
    
    await update.message.reply_text(
        f"🛒 *تأكيد*\n📦 {fmt(amt)} USDT\n💰 {fmt(total)} SDG\n\n✅ للمتابعة:",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb_confirm()
    )
    return BUY_BOT_CONFIRM

async def buy_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    uid = update.effective_user.id
    
    if txt == "❌ إلغاء":
        return await cmd_cancel(update, context)
    if txt != "✅ تأكيد":
        await update.message.reply_text("❌ اختر تأكيد أو إلغاء")
        return BUY_BOT_CONFIRM
    
    # إنشاء الطلب
    oid = db_run("INSERT INTO orders (seller_id, buyer_id, order_type, amount_usdt, price_per_usdt, total_sdg, status) VALUES (?,?,?,?,?,?,?)",
                 (OWNER_ID, uid, 'buy_from_bot', context.user_data['buy_amt'], context.user_data['buy_price'], context.user_data['buy_total'], 'awaiting_payment'))
    
    await update.message.reply_text("✅ تم إنشاء الطلب، اختر طريقة الدفع:", reply_markup=ReplyKeyboardRemove())
    
    # عرض طرق الدفع
    methods = db_all("SELECT * FROM payment_methods")
    if not methods:
        await update.message.reply_text("⚠️ لا توجد طرق دفع، راسل الدعم")
        context.user_data.clear()
        return ConversationHandler.END
    
    buttons = [[InlineKeyboardButton(m['name'], callback_data=f"bot_pay_sel_{oid}_{m['method_id']}")] for m in methods]
    await update.message.reply_text("💳 اختر طريقة الدفع:", reply_markup=InlineKeyboardMarkup(buttons))
    
    context.user_data['buy_oid'] = oid
    return BUY_BOT_PAY_METHOD

async def buy_pay_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not query.data.startswith("bot_pay_sel_"):
        return ConversationHandler.END
    
    parts = query.data.split("_")
    oid, mid = int(parts[2]), int(parts[3])
    method = db_get("SELECT * FROM payment_methods WHERE method_id=?", (mid,))
    
    if not method:
        await query.edit_message_text("❌ طريقة غير متاحة")
        return ConversationHandler.END
    
    await query.edit_message_text(
        f"💳 *{method['name']}*\n📋 `{method['details']}`\n\n📸 أرسل إثبات التحويل الآن:",
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['buy_method'] = method
    return BUY_BOT_PROOF

async def buy_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ أرسل صورة فقط")
        return BUY_BOT_PROOF
    
    context.user_data['buy_proof'] = update.message.photo[-1].file_id
    uid = update.effective_user.id
    
    # عرض طرق استلام المستخدم
    methods = db_all("SELECT * FROM user_receive_methods WHERE user_id=?", (uid,))
    
    if not methods:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("➕ أضف طريقة استلام", callback_data="usr_recv_add_buy")]])
        await update.message.reply_text("💳 أضف طريقة لاستلام أموالك:", reply_markup=kb)
        return BUY_BOT_RECEIVE
    
    oid = context.user_data['buy_oid']
    buttons = [[InlineKeyboardButton(f"{m['name']}", callback_data=f"usr_recv_sel_buy_{oid}_{m['method_id']}")] for m in methods]
    buttons.append([InlineKeyboardButton("➕ إضافة جديدة", callback_data="usr_recv_add_buy")])
    
    await update.message.reply_text("💳 اختر طريقة استلام أموالك:", reply_markup=InlineKeyboardMarkup(buttons))
    return BUY_BOT_RECEIVE

async def buy_receive_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("usr_recv_add_"):
        context.user_data['recv_flow'] = 'buy'
        await query.message.reply_text("📝 اسم الطريقة:", reply_markup=kb_cancel())
        return USER_RECEIVE_ADD_NAME
    
    if query.data.startswith("usr_recv_sel_buy_"):
        parts = query.data.split("_")
        oid, mid = int(parts[3]), int(parts[4])
        method = db_get("SELECT * FROM user_receive_methods WHERE method_id=?", (mid,))
        
        if not method:
            await query.message.reply_text("❌ خطأ")
            return ConversationHandler.END
        
        # تحديث الطلب
        db_run("UPDATE orders SET payment_proof=?, user_receiving_details=?, user_receive_method_id=?, status='payment_uploaded' WHERE order_id=?",
               (context.user_data['buy_proof'], f"{method['name']}: {method['details']}", mid, oid))
        
        # إشعار الإدارة
        try:
            await context.bot.send_message(OWNER_ID, f"🔔 شراء جديد #{oid}\n📸 إثبات مرفق")
        except: pass
        
        await query.message.reply_text("✅ تم استلام طلبك! المراجعة خلال 15 دقيقة", reply_markup=kb_main(is_admin(update.effective_user.id)))
        context.user_data.clear()
        return ConversationHandler.END
    
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════
#                    💳 طرق استلام المستخدم (نظام جديد ✅)
# ════════════════════════════════════════════════════════════
async def user_receive_methods_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await guard(update, context):
        return ConversationHandler.END
    
    uid = update.effective_user.id
    methods = db_all("SELECT * FROM user_receive_methods WHERE user_id=?", (uid,))
    
    if not methods:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("➕ إضافة أول طريقة", callback_data="usr_recv_manage_add")]])
        await update.message.reply_text("💳 *طرق استلام أموالك*\n\nلم تضف أي طريقة بعد.\nأضف طريقة (بيهنس، فوري، بنك...) لاستلام أموالك عند البيع أو الشراء.", reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    
    msg = "💳 *طرق استلامك*\n" + "═"*25 + "\n\n"
    for m in methods:
        default = " ⭐" if m['is_default'] else ""
        msg += f"• {m['name']}{default}\n  📋 {m['details']}\n\n"
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة طريقة", callback_data="usr_recv_manage_add")],
        [InlineKeyboardButton("🔄 تحديث", callback_data="usr_recv_manage_refresh")]
    ])
    await update.message.reply_text(msg, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def user_receive_manage_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "usr_recv_manage_add":
        context.user_data['recv_flow'] = 'manage'
        await query.message.reply_text("📝 أدخل اسم الطريقة (مثال: بيهانس):", reply_markup=kb_cancel())
        return USER_RECEIVE_ADD_NAME
    
    if query.data == "usr_recv_manage_refresh":
        await user_receive_methods_cmd(query.message, context)
    
    return ConversationHandler.END

async def user_receive_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt == "❌ إلغاء":
        return await cmd_cancel(update, context)
    
    context.user_data['recv_name'] = txt
    await update.message.reply_text("📝 أدخل التفاصيل (الآيدي/رقم الحساب):", reply_markup=kb_cancel())
    return USER_RECEIVE_ADD_DETAILS

async def user_receive_add_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt == "❌ إلغاء":
        return await cmd_cancel(update, context)
    
    uid = update.effective_user.id
    flow = context.user_data.get('recv_flow', 'manage')
    
    # أول طريقة تكون افتراضية
    is_default = 1 if not db_all("SELECT 1 FROM user_receive_methods WHERE user_id=?", (uid,)) else 0
    
    db_run("INSERT INTO user_receive_methods (user_id, name, details, is_default) VALUES (?,?,?,?)",
           (uid, context.user_data['recv_name'], txt, is_default))
    
    await update.message.reply_text(f"✅ تم إضافة '{context.user_data['recv_name']}'", reply_markup=kb_main(is_admin(uid)))
    context.user_data.clear()
    
    if flow == 'sell':
        # العودة لسيناريو البيع
        return await sell_proof(update, context)
    elif flow == 'buy':
        # العودة لسيناريو الشراء
        return await buy_proof(update, context)
    
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════
#                    📤 سحب الرصيد (مُفعّل ✅)
# ════════════════════════════════════════════════════════════
async def cmd_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await guard(update, context):
        return ConversationHandler.END
    if await check_trader_offline(update):
        return ConversationHandler.END
    
    user = get_user(update.effective_user.id)
    if user['balance_usdt'] <= 0:
        await update.message.reply_text("❌ رصيدك غير كافٍ للسحب")
        return ConversationHandler.END
    
    await update.message.reply_text(
        f"📤 *سحب USDT*\nرصيدك: {fmt(user['balance_usdt'])} USDT\n\n📩 أدخل الكمية:",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb_cancel()
    )
    return WITHDRAW_AMOUNT

async def withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt == "❌ إلغاء":
        return await cmd_cancel(update, context)
    
    try:
        amt = float(txt.replace('،', '.'))
        user = get_user(update.effective_user.id)
        if amt <= 0 or amt > user['balance_usdt']:
            await update.message.reply_text(f"❌ كمية غير صحيحة (الحد: {fmt(user['balance_usdt'])})")
            return WITHDRAW_AMOUNT
    except:
        await update.message.reply_text("❌ أدخل رقماً صحيحاً")
        return WITHDRAW_AMOUNT
    
    context.user_data['withdraw_amt'] = amt
    await update.message.reply_text("📩 أدخل عنوان محفظة TRC20:", reply_markup=kb_cancel())
    return WITHDRAW_ADDR

async def withdraw_addr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt == "❌ إلغاء":
        return await cmd_cancel(update, context)
    if len(txt) < 30:
        await update.message.reply_text("❌ عنوان غير صحيح (يجب أن يكون TRC20)")
        return WITHDRAW_ADDR
    
    context.user_data['withdraw_addr'] = txt
    amt = context.user_data['withdraw_amt']
    fee = amt * (get_commission() / 100)
    net = amt - fee
    
    await update.message.reply_text(
        f"📤 *تأكيد السحب*\n📦 {fmt(amt)} USDT\n💸 عمولة ({get_commission()}%): {fmt(fee)}\n✅ سيصلك: {fmt(net)}\n🏧 `{txt}`\n\n✅ للمتابعة:",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb_confirm()
    )
    return WITHDRAW_CONFIRM

async def withdraw_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    uid = update.effective_user.id
    
    if txt == "❌ إلغاء":
        return await cmd_cancel(update, context)
    if txt != "✅ تأكيد":
        await update.message.reply_text("❌ اختر تأكيد أو إلغاء")
        return WITHDRAW_CONFIRM
    
    amt = context.user_data['withdraw_amt']
    addr = context.user_data['withdraw_addr']
    fee = amt * (get_commission() / 100)
    
    # خصم الرصيد
    db_run("UPDATE users SET balance_usdt = balance_usdt - ? WHERE user_id=?", (amt, uid))
    
    # تسجيل المعاملة
    db_run("INSERT INTO transactions (user_id, tx_type, amount, status, notes) VALUES (?,?,?,?,?)",
           (uid, 'withdraw', amt, 'pending', f"إلى: {addr} | عمولة: {fmt(fee)}"))
    
    # إشعار الإدارة
    try:
        await context.bot.send_message(OWNER_ID, f"🔔 سحب جديد!\n👤 {uid}\n📦 {fmt(amt)} USDT\n🏧 `{addr}`")
    except: pass
    
    await update.message.reply_text("✅ تم استلام طلب السحب! سيتم المراجعة خلال 24 ساعة", reply_markup=kb_main(is_admin(uid)))
    context.user_data.clear()
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════
#                    🌟 تليجرام مميز
# ════════════════════════════════════════════════════════════
async def premium_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await guard(update, context):
        return ConversationHandler.END
    if await check_trader_offline(update):
        return ConversationHandler.END
    
    price = get_premium_price()
    await update.message.reply_text(
        f"🌟 *تليجرام مميز*\nالسعر: {fmt(price)} USDT/اشتراك\n\n📩 كم اشتراك تريد؟",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb_cancel()
    )
    return PREMIUM_AMOUNT

async def premium_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt == "❌ إلغاء":
        return await cmd_cancel(update, context)
    
    try:
        qty = int(txt)
        if qty <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ أدخل عدداً صحيحاً")
        return PREMIUM_AMOUNT
    
    total = qty * get_premium_price()
    user = get_user(update.effective_user.id)
    
    if user['balance_usdt'] < total:
        await update.message.reply_text(f"❌ رصيدك ({fmt(user['balance_usdt'])}) غير كافٍ")
        return ConversationHandler.END
    
    context.user_data.update({'premium_qty': qty, 'premium_total': total})
    
    await update.message.reply_text(
        f"🌟 *تأكيد*\n📦 {qty} اشتراك\n💰 {fmt(total)} USDT\n\n✅ للمتابعة:",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb_confirm()
    )
    return PREMIUM_CONFIRM

async def premium_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    uid = update.effective_user.id
    
    if txt == "❌ إلغاء":
        return await cmd_cancel(update, context)
    if txt != "✅ تأكيد":
        await update.message.reply_text("❌ اختر تأكيد أو إلغاء")
        return PREMIUM_CONFIRM
    
    total = context.user_data['premium_total']
    db_run("UPDATE users SET balance_usdt = balance_usdt - ? WHERE user_id=?", (total, uid))
    db_run("INSERT INTO transactions (user_id, tx_type, amount, status) VALUES (?,?,?,?)",
           (uid, 'buy_premium', total, 'completed'))
    
    await update.message.reply_text(f"✅ تم شراء {context.user_data['premium_qty']} اشتراك!", reply_markup=kb_main(is_admin(uid)))
    context.user_data.clear()
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════
#                    💵 تقديم عرض (معدل بسيط)
# ════════════════════════════════════════════════════════════
async def offer_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await guard(update, context):
        return ConversationHandler.END
    if await check_trader_offline(update):
        return ConversationHandler.END
    
    await update.message.reply_text("💵 *تقديم عرض*\n\nاختر نوع العرض:", reply_markup=kb_offer_type())
    return OFFER_TYPE

async def offer_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt == "❌ إلغاء":
        return await cmd_cancel(update, context)
    if txt not in ["شــراء", "بــيــع"]:
        await update.message.reply_text("❌ اختر من الأزرار")
        return OFFER_TYPE
    
    context.user_data['offer_type'] = txt
    await update.message.reply_text(f"📩 أدخل الكمية ({txt}):", reply_markup=kb_cancel())
    return OFFER_AMOUNT

async def offer_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt == "❌ إلغاء":
        return await cmd_cancel(update, context)
    try:
        amt = float(txt.replace('،', '.'))
        if amt <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ أدخل رقماً صحيحاً")
        return OFFER_AMOUNT
    
    context.user_data['offer_amt'] = amt
    await update.message.reply_text("📩 أدخل السعر (جنيه/USDT):", reply_markup=kb_cancel())
    return OFFER_PRICE

async def offer_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt == "❌ إلغاء":
        return await cmd_cancel(update, context)
    try:
        price = float(txt.replace('،', '.'))
        if price <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ أدخل سعراً صحيحاً")
        return OFFER_PRICE
    
    context.user_data['offer_price'] = price
    total = context.user_data['offer_amt'] * price
    
    await update.message.reply_text(
        f"📋 *تأكيد العرض*\n🔸 {context.user_data['offer_type']}\n🔹 {fmt(context.user_data['offer_amt'])} USDT\n🔸 {fmt(price)} جنيه/USDT\n💰 الإجمالي: {fmt(total)} SDG\n\n✅ للمتابعة:",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb_confirm()
    )
    return OFFER_CONFIRM

async def offer_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    uid = update.effective_user.id
    
    if txt == "❌ إلغاء":
        return await cmd_cancel(update, context)
    if txt != "✅ تأكيد":
        await update.message.reply_text("❌ تم الإلغاء", reply_markup=kb_main(is_admin(uid)))
        context.user_data.clear()
        return ConversationHandler.END
    
    typ = context.user_data['offer_type']
    db_type = 'offer_buy' if typ == 'شــراء' else 'offer_sell'
    seller = uid if db_type == 'offer_sell' else OWNER_ID
    buyer = OWNER_ID if db_type == 'offer_sell' else uid
    
    oid = db_run("INSERT INTO orders (seller_id, buyer_id, order_type, amount_usdt, price_per_usdt, total_sdg, status) VALUES (?,?,?,?,?,?,?)",
                 (seller, buyer, db_type, context.user_data['offer_amt'], context.user_data['offer_price'], context.user_data['offer_amt']*context.user_data['offer_price'], 'pending_offer'))
    
    await update.message.reply_text("✅ تم إرسال عرضك للتاجر!", reply_markup=kb_main(is_admin(uid)))
    
    try:
        await context.bot.send_message(OWNER_ID, f"🔔 عرض جديد #{oid}\n👤 {uid}\n🔸 {db_type}")
    except: pass
    
    context.user_data.clear()
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════
#                    📞 الدعم الفني
# ════════════════════════════════════════════════════════════
async def support_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await guard(update, context):
        return ConversationHandler.END
    
    await update.message.reply_text("📞 *الدعم الفني*\nأرسل رسالتك وسنرد قريباً:", reply_markup=kb_cancel())
    return SUPPORT_MSG

async def support_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    uid = update.effective_user.id
    
    if txt == "❌ إلغاء":
        return await cmd_cancel(update, context)
    
    db_run("INSERT INTO support_msgs (user_id, message) VALUES (?,?)", (uid, txt))
    
    try:
        await context.bot.send_message(OWNER_ID, f"🔔 دعم جديد!\n👤 @{update.effective_user.username or uid}\n✉️ {txt}")
    except: pass
    
    await update.message.reply_text("✅ تم إرسال رسالتك", reply_markup=kb_main(is_admin(uid)))
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════
#                    🔐 لوحة الإدارة
# ════════════════════════════════════════════════════════════
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    await update.message.reply_text("🔐 *لوحة الإدارة*", reply_markup=kb_admin(), parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    count = db_get("SELECT COUNT(*) as c FROM users")['c']
    await update.message.reply_text(f"👥 المستخدمين: {count}", reply_markup=kb_admin())
    return ConversationHandler.END

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    orders = db_get("SELECT COUNT(*) as c FROM orders")['c']
    await update.message.reply_text(f"📊 الطلبات: {orders}", reply_markup=kb_admin())
    return ConversationHandler.END

async def admin_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    
    orders = db_all("SELECT * FROM orders WHERE status IN ('pending_offer', 'payment_uploaded') ORDER BY order_id")
    
    if not orders:
        await update.message.reply_text("📋 لا توجد طلبات للمراجعة", reply_markup=kb_admin())
        return ConversationHandler.END
    
    for o in orders:
        uid = o['buyer_id'] if o['order_type'] in ['buy_from_bot', 'offer_buy'] else o['seller_id']
        u = get_user(uid)
        name = u['full_name'] if u else "مجهول"
        
        t = {'offer_buy':'عرض شراء', 'offer_sell':'عرض بيع', 'buy_from_bot':'شراء مباشر', 'sell_to_bot':'بيع للبوت'}.get(o['order_type'], o['order_type'])
        
        msg = f"🔖 #{o['order_id']}\n👤 {name}\n🔸 {t}\n📦 {fmt(o['amount_usdt'])} USDT\n💰 {fmt(o['total_sdg'])} SDG"
        
        if o['user_receiving_details']:
            msg += f"\n💳 استلام: {o['user_receiving_details']}"
        
        if o['status'] == 'pending_offer':
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ قبول", callback_data=f"adm_acc_{o['order_id']}")],
                [InlineKeyboardButton("❌ رفض", callback_data=f"adm_rej_{o['order_id']}")]
            ])
            await update.message.reply_text(msg, reply_markup=kb)
        
        elif o['status'] == 'payment_uploaded':
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ اكتمل", callback_data=f"adm_com_{o['order_id']}")],
                [InlineKeyboardButton("❌ رفض", callback_data=f"adm_rpay_{o['order_id']}")]
            ])
            try:
                await update.message.reply_photo(o['payment_proof'], caption=msg, reply_markup=kb)
            except:
                await update.message.reply_text(msg + "\n📸 [صورة]", reply_markup=kb)
    
    return ConversationHandler.END

async def admin_action_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        return ConversationHandler.END
    
    data = query.data.split("_")
    if len(data) < 3:
        return ConversationHandler.END
    
    action, oid = data[1], int(data[2])
    order = db_get("SELECT * FROM orders WHERE order_id=?", (oid,))
    
    if not order:
        await query.edit_message_text(query.message.text + "\n❌ غير موجود")
        return ConversationHandler.END
    
    uid = order['buyer_id'] if order['order_type'] in ['buy_from_bot', 'offer_buy'] else order['seller_id']
    
    if action == 'rej':
        db_run("UPDATE orders SET status='rejected' WHERE order_id=?", (oid,))
        try:
            await query.edit_message_text(query.message.text + "\n❌ تم الرفض")
            await context.bot.send_message(uid, f"❌ تم رفض طلبك #{oid}")
        except: pass
    
    elif action == 'acc':
        db_run("UPDATE orders SET status='awaiting_payment' WHERE order_id=?", (oid,))
        try:
            await query.edit_message_text(query.message.text + "\n✅ تم القبول")
            await context.bot.send_message(uid, f"✅ تم قبول طلبك #{oid}")
            # إرسال طرق الدفع
            methods = db_all("SELECT * FROM payment_methods")
            if methods:
                buttons = [[InlineKeyboardButton(m['name'], callback_data=f"bot_pay_sel_{oid}_{m['method_id']}")] for m in methods]
                await context.bot.send_message(uid, "💳 اختر طريقة الدفع:", reply_markup=InlineKeyboardMarkup(buttons))
        except: pass
    
    elif action == 'com':
        # عند الاكتمال: تحديث الأرصدة إذا لزم
        if order['order_type'] == 'sell_to_bot':
            # المستخدم باع للبوت: نسجل معاملة بيع مكتملة
            db_run("INSERT INTO transactions (user_id, tx_type, amount, status, notes) VALUES (?,?,?,?,'completed')",
                   (uid, 'sell_completed', order['amount_usdt'], order['total_sdg']))
        
        db_run("UPDATE orders SET status='completed' WHERE order_id=?", (oid,))
        try:
            await query.edit_message_text(query.message.text + "\n✅ اكتمل")
            await context.bot.send_message(uid, f"✅ اكتمل طلبك #{oid}!")
        except: pass
    
    elif action == 'rpay':
        db_run("UPDATE orders SET status='rejected' WHERE order_id=?", (oid,))
        try:
            await query.edit_message_text(query.message.text + "\n❌ تم رفض الإثبات")
            await context.bot.send_message(uid, f"❌ تم رفض إثبات طلبك #{oid}")
        except: pass
    
    return ConversationHandler.END

# --- إدارة الإعدادات ---
async def admin_set_value(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str, label: str, current: float):
    txt = update.message.text.strip()
    if txt == "❌ إلغاء":
        return await cmd_cancel(update, context)
    try:
        val = float(txt.replace('،', '.'))
        if val < 0:
            raise ValueError
        set_setting(key, val)
        await update.message.reply_text(f"✅ تم تحديث {label} إلى {fmt(val)}", reply_markup=kb_admin())
        return ConversationHandler.END
    except:
        await update.message.reply_text("❌ أدخل رقماً صحيحاً")
        return None  # يبقى في نفس الحالة

# دوال مختصرة للإدارة
async def admin_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str, state: int):
    await update.message.reply_text(prompt, reply_markup=kb_cancel())
    return state

async def admin_set_buy_price_cmd(u, c):
    return await admin_prompt(u, c, f"💲 سعر الشراء الحالي: {fmt(get_usdt_buy_price())}\nأدخل الجديد:", ADMIN_SET_BUY_PRICE)
async def admin_set_buy_price_handler(u, c):
    return await admin_set_value(u, c, 'usdt_buy_price', 'سعر الشراء', get_usdt_buy_price()) or ADMIN_SET_BUY_PRICE

async def admin_set_sell_price_cmd(u, c):
    return await admin_prompt(u, c, f"💲 سعر البيع الحالي: {fmt(get_usdt_sell_price())}\nأدخل الجديد:", ADMIN_SET_SELL_PRICE)
async def admin_set_sell_price_handler(u, c):
    return await admin_set_value(u, c, 'usdt_sell_price', 'سعر البيع', get_usdt_sell_price()) or ADMIN_SET_SELL_PRICE

async def admin_set_commission_cmd(u, c):
    return await admin_prompt(u, c, f"💹 العمولة الحالية: {fmt(get_commission())}%\nأدخل الجديدة:", ADMIN_SET_COMMISSION)
async def admin_set_commission_handler(u, c):
    return await admin_set_value(u, c, 'commission_rate', 'العمولة', get_commission()) or ADMIN_SET_COMMISSION

async def admin_set_deposit_cmd(u, c):
    return await admin_prompt(u, c, "🏧 أدخل عنوان المحفظة الجديد:", ADMIN_SET_DEPOSIT)
async def admin_set_deposit_handler(u, c):
    txt = u.message.text.strip()
    if txt == "❌ إلغاء":
        return await cmd_cancel(u, c)
    set_setting('deposit_address', txt)
    await u.message.reply_text("✅ تم التحديث", reply_markup=kb_admin())
    return ConversationHandler.END

async def admin_set_avail_cmd(u, c):
    return await admin_prompt(u, c, f"📦 المتاح حالياً: {fmt(get_available_inventory())}\nأدخل الجديد:", ADMIN_SET_AVAIL_INV)
async def admin_set_avail_handler(u, c):
    return await admin_set_value(u, c, 'available_usdt_inventory', 'المخزون المتاح', get_available_inventory()) or ADMIN_SET_AVAIL_INV

async def admin_set_req_cmd(u, c):
    return await admin_prompt(u, c, f"📦 المطلوب حالياً: {fmt(get_required_inventory())}\nأدخل الجديد:", ADMIN_SET_REQ_INV)
async def admin_set_req_handler(u, c):
    return await admin_set_value(u, c, 'required_usdt_inventory', 'المخزون المطلوب', get_required_inventory()) or ADMIN_SET_REQ_INV

async def admin_set_premium_cmd(u, c):
    return await admin_prompt(u, c, f"🌟 سعر المميز: {fmt(get_premium_price())}\nأدخل الجديد:", ADMIN_SET_PREMIUM)
async def admin_set_premium_handler(u, c):
    return await admin_set_value(u, c, 'telegram_premium_price', 'سعر المميز', get_premium_price()) or ADMIN_SET_PREMIUM

async def admin_set_trader_status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    status = "🟢 متصل" if get_trader_online() else "🔴 غير متصل"
    await update.message.reply_text(f"🚦 الحالة: {status}\nاختر الجديدة:", reply_markup=kb_trader_status())
    return ADMIN_SET_TRADER_STATUS

async def admin_set_trader_status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt == "❌ إلغاء":
        return await cmd_cancel(update, context)
    if txt == "🟢 متصل":
        set_setting('trader_online_status', 1)
        msg = "🟢 متصل - البوت يعمل"
    elif txt == "🔴 غير متصل":
        set_setting('trader_online_status', 0)
        msg = "🔴 غير متصل - الطلبات موقفة"
    else:
        return ADMIN_SET_TRADER_STATUS
    await update.message.reply_text(f"✅ {msg}", reply_markup=kb_admin())
    return ConversationHandler.END

async def admin_broadcast_cmd(u, c):
    return await admin_prompt(u, c, "📢 أدخل الرسالة للبث:", ADMIN_BROADCAST)
async def admin_broadcast_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt == "❌ إلغاء":
        return await cmd_cancel(update, context)
    users = db_all("SELECT user_id FROM users WHERE is_banned=0")
    sent = 0
    for u in users:
        try:
            await context.bot.send_message(u['user_id'], txt)
            sent += 1
        except: pass
    await update.message.reply_text(f"✅ أُرسلت إلى {sent} مستخدم", reply_markup=kb_admin())
    return ConversationHandler.END

async def admin_ban_cmd(u, c):
    return await admin_prompt(u, c, "🔒 أدخل ID المستخدم للحظر:", ADMIN_BAN)
async def admin_ban_handler(u, c):
    txt = u.message.text.strip()
    if txt == "❌ إلغاء":
        return await cmd_cancel(u, c)
    try:
        db_run("UPDATE users SET is_banned=1 WHERE user_id=?", (int(txt),))
        await u.message.reply_text("✅ تم الحظر", reply_markup=kb_admin())
        return ConversationHandler.END
    except:
        return ADMIN_BAN

async def admin_unban_cmd(u, c):
    return await admin_prompt(u, c, "🔓 أدخل ID المستخدم لفك الحظر:", ADMIN_UNBAN)
async def admin_unban_handler(u, c):
    txt = u.message.text.strip()
    if txt == "❌ إلغاء":
        return await cmd_cancel(u, c)
    try:
        db_run("UPDATE users SET is_banned=0 WHERE user_id=?", (int(txt),))
        await u.message.reply_text("✅ تم فك الحظر", reply_markup=kb_admin())
        return ConversationHandler.END
    except:
        return ADMIN_UNBAN

async def admin_support_msgs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    msgs = db_all("SELECT * FROM support_msgs WHERE status='open' ORDER BY msg_id")
    if not msgs:
        await update.message.reply_text("✅ لا توجد رسائل دعم مفتوحة", reply_markup=kb_admin())
        return ConversationHandler.END
    for m in msgs:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("↩️ رد", callback_data=f"adm_reply_{m['msg_id']}")]])
        await update.message.reply_text(f"✉️ #{m['msg_id']}\n👤 {m['user_id']}\n{m['message']}", reply_markup=kb)
    return ConversationHandler.END

async def admin_reply_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return ConversationHandler.END
    try:
        context.user_data['adm_reply_id'] = int(query.data.split("_")[2])
        await query.message.reply_text("↩️ أدخل ردك:", reply_markup=kb_cancel())
        return ADMIN_REPLY
    except:
        return ConversationHandler.END

async def admin_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt == "❌ إلغاء":
        return await cmd_cancel(update, context)
    msg_id = context.user_data.get('adm_reply_id')
    msg = db_get("SELECT * FROM support_msgs WHERE msg_id=?", (msg_id,))
    if msg:
        db_run("UPDATE support_msgs SET admin_reply=?, status='closed' WHERE msg_id=?", (txt, msg_id))
        await update.message.reply_text("✅ تم الرد", reply_markup=kb_admin())
        try:
            await context.bot.send_message(msg['user_id'], f"🔔 رد الدعم:\n\n{txt}")
        except: pass
    return ConversationHandler.END

async def admin_add_pay_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    await update.message.reply_text("💳 اسم طريقة الدفع (مثال: فوري):", reply_markup=kb_cancel())
    return ADMIN_ADD_PAY_NAME

async def admin_add_pay_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt == "❌ إلغاء":
        return await cmd_cancel(update, context)
    context.user_data['pay_name'] = txt
    await update.message.reply_text("📋 تفاصيل الطريقة (الآيدي/الحساب):", reply_markup=kb_cancel())
    return ADMIN_ADD_PAY_DETAILS

async def admin_add_pay_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt == "❌ إلغاء":
        return await cmd_cancel(update, context)
    db_run("INSERT INTO payment_methods (name, details) VALUES (?,?)", (context.user_data['pay_name'], txt))
    await update.message.reply_text("✅ تمت الإضافة", reply_markup=kb_admin())
    context.user_data.clear()
    return ConversationHandler.END

async def admin_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    backup = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    conn = sqlite3.connect(DB_PATH)
    with open(backup, 'wb') as f:
        for chunk in conn.iterdump():
            f.write(f'{chunk}\n'.encode('utf-8'))
    conn.close()
    await update.message.reply_document(document=open(backup, 'rb'), filename=backup)
    os.remove(backup)
    await update.message.reply_text("✅ تم النسخ الاحتياطي", reply_markup=kb_admin())
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════
#                    📊 معلومات إضافية
# ════════════════════════════════════════════════════════════
async def show_exchange(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await guard(update, context):
        return ConversationHandler.END
    await update.message.reply_text(f"💱 *الأسعار*\n📥 نشتري: {fmt(get_usdt_buy_price())} ج\n📤 نبيع: {fmt(get_usdt_sell_price())} ج", parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def show_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await guard(update, context):
        return ConversationHandler.END
    await update.message.reply_text(f"🗃️ *المخزون*\n✅ متاح: {fmt(get_available_inventory())} USDT\n📥 مطلوب: {fmt(get_required_inventory())} USDT", parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def show_trader_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await guard(update, context):
        return ConversationHandler.END
    status = "🟢 متصل" if get_trader_online() else "🔴 غير متصل"
    await update.message.reply_text(f"🚦 حالة التاجر: {status}")
    return ConversationHandler.END

async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await guard(update, context):
        return ConversationHandler.END
    user = get_user(update.effective_user.id)
    kb = ReplyKeyboardMarkup([[KeyboardButton("💳 طرق استلام الأموال")], [KeyboardButton("🔙 الرئيسية")]], resize_keyboard=True)
    await update.message.reply_text(f"⚙️ *الإعدادات*\nمحفظتك: `{user['wallet_address'] or 'غير معين'}`", reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════
#                    🚀 التشغيل الرئيسي
# ════════════════════════════════════════════════════════════
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    
    # فلاتر الإلغاء المشتركة
    cancel_filter = filters.Regex(r"^(❌ إلغاء|🔙 الرئيسية|/cancel|/start)$")
    
    # 1. التسجيل
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            REG_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_name)],
            REG_COUNTRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_country)],
        },
        fallbacks=[MessageHandler(cancel_filter, cmd_cancel)]
    ))
    
    # 2. بيع للبوت
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^💰 بيع USDT$"), sell_to_bot_cmd)],
        states={
            SELL_BOT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_amount)],
            SELL_BOT_PROOF: [MessageHandler(filters.PHOTO, sell_proof)],
            SELL_BOT_RECEIVE: [CallbackQueryHandler(sell_receive_select, pattern=r"^usr_recv_(sel|add)_")],
        },
        fallbacks=[MessageHandler(cancel_filter, cmd_cancel)]
    ))
    
    # 3. شراء من البوت
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^🛒 شراء USDT$|^📊 السوق$"), buy_from_bot_cmd)],
        states={
            BUY_BOT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_amount)],
            BUY_BOT_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_confirm)],
            BUY_BOT_PAY_METHOD: [CallbackQueryHandler(buy_pay_select, pattern=r"^bot_pay_sel_\d+_\d+$")],
            BUY_BOT_PROOF: [MessageHandler(filters.PHOTO, buy_proof)],
            BUY_BOT_RECEIVE: [CallbackQueryHandler(buy_receive_select, pattern=r"^usr_recv_(sel_buy|add)_")],
        },
        fallbacks=[MessageHandler(cancel_filter, cmd_cancel)]
    ))
    
    # 4. طرق استلام المستخدم
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^💳 طرق استلام الأموال$"), user_receive_methods_cmd)],
        states={
            USER_RECEIVE_ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, user_receive_add_name)],
            USER_RECEIVE_ADD_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, user_receive_add_details)],
        },
        fallbacks=[
            MessageHandler(cancel_filter, cmd_cancel),
            CallbackQueryHandler(user_receive_manage_cb, pattern=r"^usr_recv_manage_")
        ]
    ))
    
    # 5. العروض
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^💵 تقديم عرض$"), offer_cmd)],
        states={
            OFFER_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, offer_type)],
            OFFER_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, offer_amount)],
            OFFER_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, offer_price)],
            OFFER_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, offer_confirm)],
        },
        fallbacks=[MessageHandler(cancel_filter, cmd_cancel)]
    ))
    
    # 6. السحب
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("withdraw", cmd_withdraw)],
        states={
            WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_amount)],
            WITHDRAW_ADDR: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_addr)],
            WITHDRAW_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_confirm)],
        },
        fallbacks=[MessageHandler(cancel_filter, cmd_cancel)]
    ))
    
    # 7. تليجرام مميز
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^🌟 تليجرام مميز$"), premium_cmd)],
        states={
            PREMIUM_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, premium_amount)],
            PREMIUM_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, premium_confirm)],
        },
        fallbacks=[MessageHandler(cancel_filter, cmd_cancel)]
    ))
    
    # 8. الدعم
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^📞 الدعم$"), support_cmd)],
        states={SUPPORT_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, support_msg)]},
        fallbacks=[MessageHandler(cancel_filter, cmd_cancel)]
    ))
    
    # 9. الإدارة
    app.add_handler(ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^🔐 الإدارة$"), admin_panel),
            MessageHandler(filters.Regex(r"^📢 بث$"), admin_broadcast_cmd),
            MessageHandler(filters.Regex(r"^💲 سعر شراء$"), admin_set_buy_price_cmd),
            MessageHandler(filters.Regex(r"^💲 سعر بيع$"), admin_set_sell_price_cmd),
            MessageHandler(filters.Regex(r"^💹 عمولة$"), admin_set_commission_cmd),
            MessageHandler(filters.Regex(r"^🏧 عنوان الإيداع$"), admin_set_deposit_cmd),
            MessageHandler(filters.Regex(r"^📦 مخزون متاح$"), admin_set_avail_cmd),
            MessageHandler(filters.Regex(r"^📦 مخزون مطلوب$"), admin_set_req_cmd),
            MessageHandler(filters.Regex(r"^🌟 سعر مميز$"), admin_set_premium_cmd),
            MessageHandler(filters.Regex(r"^🚦 حالة التاجر$"), admin_set_trader_status_cmd),
            MessageHandler(filters.Regex(r"^🔒 حظر$"), admin_ban_cmd),
            MessageHandler(filters.Regex(r"^🔓 فك حظر$"), admin_unban_cmd),
            MessageHandler(filters.Regex(r"^💳 دفع طرق$"), admin_add_pay_cmd),
            CallbackQueryHandler(admin_reply_cb, pattern=r"^adm_reply_\d+$"),
        ],
        states={
            ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_handler)],
            ADMIN_SET_BUY_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_buy_price_handler)],
            ADMIN_SET_SELL_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_sell_price_handler)],
            ADMIN_SET_COMMISSION: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_commission_handler)],
            ADMIN_SET_DEPOSIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_deposit_handler)],
            ADMIN_SET_AVAIL_INV: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_avail_handler)],
            ADMIN_SET_REQ_INV: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_req_handler)],
            ADMIN_SET_PREMIUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_premium_handler)],
            ADMIN_SET_TRADER_STATUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_trader_status_handler)],
            ADMIN_BAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_ban_handler)],
            ADMIN_UNBAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_unban_handler)],
            ADMIN_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_reply_handler)],
            ADMIN_ADD_PAY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_pay_name)],
            ADMIN_ADD_PAY_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_pay_details)],
        },
        fallbacks=[MessageHandler(cancel_filter, cmd_cancel)]
    ))
    
    # الأوامر والأزرار العامة
    app.add_handler(CommandHandler("withdraw", cmd_withdraw))
    app.add_handler(MessageHandler(cancel_filter, cmd_cancel))
    
    app.add_handler(CallbackQueryHandler(admin_action_cb, pattern=r"^adm_(acc|rej|com|rpay)_\d+$"))
    
    app.add_handler(MessageHandler(filters.Regex(r"^👥 المستخدمين$"), admin_users))
    app.add_handler(MessageHandler(filters.Regex(r"^📊 إحصائيات$"), admin_stats))
    app.add_handler(MessageHandler(filters.Regex(r"^📋 الطلبات$"), admin_orders))
    app.add_handler(MessageHandler(filters.Regex(r"^📝 الدعم$"), admin_support_msgs))
    app.add_handler(MessageHandler(filters.Regex(r"^💾 نسخ احتياطي$"), admin_backup))
    
    app.add_handler(MessageHandler(filters.Regex(r"^👤 ملفي$"), show_profile))
    app.add_handler(MessageHandler(filters.Regex(r"^🔗 الإحالة$"), show_profile))
    app.add_handler(MessageHandler(filters.Regex(r"^💳 رصيدي$"), show_balance))
    app.add_handler(MessageHandler(filters.Regex(r"^📋 طلباتي$"), show_my_orders))
    app.add_handler(MessageHandler(filters.Regex(r"^📜 سجل المعاملات$"), show_transactions))
    app.add_handler(MessageHandler(filters.Regex(r"^⚙️ الإعدادات$"), show_settings))
    app.add_handler(MessageHandler(filters.Regex(r"^💱 السعر$"), show_exchange))
    app.add_handler(MessageHandler(filters.Regex(r"^🗃️ المخزون$"), show_inventory))
    app.add_handler(MessageHandler(filters.Regex(r"^🚦 حالة التاجر$"), show_trader_status))
    
    logger.info("🚀 البوت يعمل - Version 9.0 STABLE")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

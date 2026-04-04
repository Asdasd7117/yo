#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════╗
║          بوت تداول USDT P2P على تيليغرام               ║
║          Version 10.4 - SYNTAX ERROR FIXED              ║
╚══════════════════════════════════════════════════════════╝
"""

import os, sys, sqlite3, logging, random, string
from datetime import datetime
from threading import local

# تثبيت تلقائي للمكتبة في حال لم تكن مثبتة على الاستضافة
os.system(f"{sys.executable} -m pip install python-telegram-bot==20.6 --quiet")

_db_local = local()

def get_conn():
    if not hasattr(_db_local, 'conn') or _db_local.conn is None:
        c = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)
        c.row_factory = sqlite3.Row
        _db_local.conn = c
    return _db_local.conn

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
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
DEPOSIT_ADDRESS = "TYourTRC20AddressHere"  # ⚠️ ضع عنوان محفظتك الحقيقي
DB_PATH         = "trading_bot.db"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════
#                    🗄️  قاعدة البيانات
# ════════════════════════════════════════════════════════════
def init_db():
    conn = get_conn()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT DEFAULT '', full_name TEXT NOT NULL, country TEXT DEFAULT 'السودان', balance_usdt REAL DEFAULT 0, commission_earned REAL DEFAULT 0, rank TEXT DEFAULT 'user', total_trades INTEGER DEFAULT 0, completed_trades INTEGER DEFAULT 0, referral_code TEXT UNIQUE, referred_by INTEGER, is_banned INTEGER DEFAULT 0, wallet_address TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS orders (order_id INTEGER PRIMARY KEY AUTOINCREMENT, seller_id INTEGER NOT NULL, buyer_id INTEGER, order_type TEXT NOT NULL, amount_usdt REAL NOT NULL, price_per_usdt REAL NOT NULL, total_sdg REAL NOT NULL, status TEXT DEFAULT 'pending', payment_method_id INTEGER, payment_proof TEXT DEFAULT '', receive_method_id INTEGER, user_account_details TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS payment_methods (method_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, details TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS receive_methods (method_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, details TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS transactions (tx_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, tx_type TEXT NOT NULL, amount REAL NOT NULL, status TEXT DEFAULT 'pending', notes TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS support_msgs (msg_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, message TEXT NOT NULL, admin_reply TEXT DEFAULT '', status TEXT DEFAULT 'open', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT OR IGNORE INTO settings VALUES ('usdt_buy_price', '4000.0');
        INSERT OR IGNORE INTO settings VALUES ('usdt_sell_price', '4100.0');
        INSERT OR IGNORE INTO settings VALUES ('trader_online_status', '1');
        INSERT OR IGNORE INTO settings VALUES ('commission_rate', '3.0');
        INSERT OR IGNORE INTO settings VALUES ('available_usdt_inventory', '1000.0');
        INSERT OR IGNORE INTO settings VALUES ('required_usdt_inventory', '50.0');
    ''')
    conn.commit()

def db_get(q, p=()):
    c = get_conn().execute(q, p).fetchone()
    return dict(c) if c else None

def db_all(q, p=()):
    return [dict(r) for r in get_conn().execute(q, p).fetchall()]

def db_run(q, p=()):
    c = get_conn().execute(q, p); get_conn().commit(); return c.lastrowid

def get_s(k):
    r = db_get("SELECT value FROM settings WHERE key=?", (k,))
    return r['value'] if r else '0'

def set_s(k, v): db_run("INSERT OR REPLACE INTO settings VALUES (?,?)", (k, str(v)))
def get_user(uid): return db_get("SELECT * FROM users WHERE user_id=?", (uid,))
def is_admin(uid): return uid == OWNER_ID
def is_online(): return bool(int(get_s('trader_online_status') or 1))
def fmt(n): return f"{float(n):,.2f}"
def make_ref(): return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

# ════════════════════════════════════════════════════════════
#                    ⌨️  لوحات المفاتيح
# ════════════════════════════════════════════════════════════
def kb_main(admin=False):
    rows = [
        [KeyboardButton("💰 بيع USDT"), KeyboardButton("🛒 شراء USDT")],
        [KeyboardButton("💵 تقديم عرض")],
        [KeyboardButton("👤 ملفي"), KeyboardButton("💳 رصيدي")],
        [KeyboardButton("📋 طلباتي"), KeyboardButton("📊 السوق")],
        [KeyboardButton("📜 سجل المعاملات"), KeyboardButton("🔗 الإحالة")],
        [KeyboardButton("⚙️ الإعدادات"), KeyboardButton("📞 الدعم")],
        [KeyboardButton("💱 سعر الصرف"), KeyboardButton("🗃️ المخزون")],
        [KeyboardButton("🌟 تليجرام مميز")]
    ]
    if admin: rows.append([KeyboardButton("🔐 الإدارة")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def kb_admin():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📋 جميع الطلبات"), KeyboardButton("👥 المستخدمين")],
        [KeyboardButton("💲 تعديل سعر الشراء"), KeyboardButton("💲 تعديل سعر البيع")],
        [KeyboardButton("💳 إضافة طريقة دفع"), KeyboardButton("💵 إضافة طريقة استلام")],
        [KeyboardButton("📢 إرسال للجميع"), KeyboardButton("🚦 حالة التاجر")],
        [KeyboardButton("🔒 حظر"), KeyboardButton("🔓 فك حظر")],
        [KeyboardButton("📝 رسائل الدعم"), KeyboardButton("🔙 الرئيسية")]
    ], resize_keyboard=True)

def kb_cancel(): return ReplyKeyboardMarkup([[KeyboardButton("❌ إلغاء")]], resize_keyboard=True)
def kb_confirm(): return ReplyKeyboardMarkup([[KeyboardButton("✅ تأكيد"), KeyboardButton("❌ إلغاء")]], resize_keyboard=True)
def kb_offer(): return ReplyKeyboardMarkup([["شــراء", "بــيــع"], ["❌ إلغاء"]], resize_keyboard=True)
def kb_trader(): return ReplyKeyboardMarkup([["🟢 تشغيل", "🔴 إيقاف"], ["❌ إلغاء"]], resize_keyboard=True)

# ════════════════════════════════════════════════════════════
#                    🔐 دوال الحماية
# ════════════════════════════════════════════════════════════
async def guard(upd, ctx):
    uid = upd.effective_user.id
    msg = upd.message or upd.callback_query.message
    if not get_user(uid):
        await msg.reply_text("👋 سجل أولاً عبر /start"); return True
    if get_user(uid)['is_banned']:
        await msg.reply_text("🚫 حسابك محظور"); return True
    return False

async def check_trader(upd):
    uid = upd.effective_user.id
    msg = upd.message or (upd.callback_query.message if upd.callback_query else None)
    if msg and not is_online() and not is_admin(uid):
        await msg.reply_text("⛔️ التاجر غير متصل حالياً.", reply_markup=kb_main(is_admin(uid))); return True
    return False

async def cancel_flow(upd, ctx):
    ctx.user_data.clear()
    await upd.message.reply_text("✅ تم الإلغاء", reply_markup=kb_main(is_admin(upd.effective_user.id)))
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════
#                    👋 التسجيل والمعلومات
# ════════════════════════════════════════════════════════════
async def start_cmd(upd, ctx):
    ctx.user_data.clear()
    uid = upd.effective_user.id
    if not get_user(uid):
        await upd.message.reply_text("👋 أدخل اسمك الكامل للتسجيل:", reply_markup=kb_cancel())
        ctx.user_data['reg_uid'] = uid; ctx.user_data['reg_uname'] = upd.effective_user.username
        return 0
    await upd.message.reply_text("أهلاً بعودتك!", reply_markup=kb_main(is_admin(uid)))
    return ConversationHandler.END

async def reg_name(upd, ctx):
    if upd.message.text.strip() == "❌ إلغاء": return await cancel_flow(upd, ctx)
    ctx.user_data['reg_name'] = upd.message.text.strip()
    await upd.message.reply_text("🌍 أدخل بلدك:", reply_markup=kb_cancel()); return 1

async def reg_country(upd, ctx):
    if upd.message.text.strip() == "❌ إلغاء": return await cancel_flow(upd, ctx)
    uid, code = ctx.user_data['reg_uid'], make_ref()
    while db_get("SELECT 1 FROM users WHERE referral_code=?", (code,)): code = make_ref()
    db_run("INSERT INTO users (user_id, username, full_name, country, referral_code) VALUES (?,?,?,?,?)",
           (uid, ctx.user_data.get('reg_uname'), ctx.user_data['reg_name'], upd.message.text.strip(), code))
    await upd.message.reply_text("✅ تم التسجيل!", reply_markup=kb_main(is_admin(uid)))
    return ConversationHandler.END

async def show_profile(upd, ctx):
    if await guard(upd, ctx): return
    u = get_user(upd.effective_user.id)
    await upd.message.reply_text(f"👤 *ملفي*\nالاسم: {u['full_name']}\nالرصيد: {fmt(u['balance_usdt'])} USDT\n🔗 رابط إحالتك: `https://t.me/{ctx.bot.username}?start={u['referral_code']}`", parse_mode=ParseMode.MARKDOWN)

async def show_balance(upd, ctx):
    if await guard(upd, ctx): return
    u = get_user(upd.effective_user.id)
    await upd.message.reply_text(f"💳 *الرصيد*: `{fmt(u['balance_usdt'])}` USDT\n📥 للإيداع: `{DEPOSIT_ADDRESS}`", parse_mode=ParseMode.MARKDOWN)

async def show_orders(upd, ctx):
    if await guard(upd, ctx): return
    uid = upd.effective_user.id
    rows = db_all("SELECT * FROM orders WHERE seller_id=? OR buyer_id=? ORDER BY order_id DESC LIMIT 10", (uid, uid))
    if not rows: return await upd.message.reply_text("📋 لا توجد طلبات حالياً")
    txt = "📋 *طلباتي*\n"
    for r in rows:
        t = "شراء" if r['buyer_id']==uid else "بيع"
        st = {'pending':'⏳','completed':'✅','rejected':'❌','awaiting_payment':'💳','pending_approval':'🔍','pending_offer':'📝'}.get(r['status'], r['status'])
        txt += f"#{r['order_id']} | {t} | {fmt(r['amount_usdt'])} USDT | {st}\n"
    await upd.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

async def show_tx(upd, ctx):
    if await guard(upd, ctx): return
    rows = db_all("SELECT * FROM transactions WHERE user_id=? ORDER BY tx_id DESC LIMIT 15", (upd.effective_user.id,))
    if not rows: return await upd.message.reply_text("📜 لا توجد معاملات بعد")
    txt = "📜 *سجل المعاملات*\n"
    for t in rows: txt += f"#{t['tx_id']} | {t['tx_type']} | {fmt(t['amount'])} USDT | {t['status']}\n"
    await upd.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

async def show_settings(upd, ctx):
    if await guard(upd, ctx): return
    await upd.message.reply_text("⚙️ *الإعدادات*\n📞 الدعم الفني متاح عبر الزر المخصص.", parse_mode=ParseMode.MARKDOWN)

async def show_inventory(upd, ctx):
    if await guard(upd, ctx): return
    await upd.message.reply_text(f"🗃️ *المخزون*\n✅ المتاح: `{get_s('available_usdt_inventory')}` USDT\n📥 المطلوب: `{get_s('required_usdt_inventory')}` USDT", parse_mode=ParseMode.MARKDOWN)

async def show_exchange(upd, ctx):
    if await guard(upd, ctx): return
    await upd.message.reply_text(f"💱 *سعر الصرف*\n📥 نشتري بـ: `{get_s('usdt_buy_price')}` جنيه\n📤 نبيع بـ: `{get_s('usdt_sell_price')}` جنيه", parse_mode=ParseMode.MARKDOWN)

# ════════════════════════════════════════════════════════════
#                    🛒 شراء USDT
# ════════════════════════════════════════════════════════════
BUY_STEPS = {'START': 100, 'AMT': 101, 'CONF': 102, 'WAIT_PAY': 103, 'WAIT_RECV': 104, 'WAIT_ACC': 105, 'DONE': 106}

async def buy_start(upd, ctx):
    if await guard(upd, ctx): return ConversationHandler.END
    if await check_trader(upd): return ConversationHandler.END
    ctx.user_data['flow'] = 'BUY'
    await upd.message.reply_text("🛒 *شراء USDT*\nأدخل الكمية (USDT):", reply_markup=kb_cancel(), parse_mode=ParseMode.MARKDOWN)
    return BUY_STEPS['AMT']

async def buy_amt(upd, ctx):
    t = upd.message.text.strip()
    if t == "❌ إلغاء": return await cancel_flow(upd, ctx)
    try:
        amt = float(t.replace('،', '.'))
        if amt <= 0: raise ValueError
    except:
        return await upd.message.reply_text("❌ أدخل رقماً صحيحاً") or BUY_STEPS['AMT']
    ctx.user_data['amt'] = amt
    ctx.user_data['price'] = float(get_s('usdt_sell_price'))
    ctx.user_data['total'] = amt * ctx.user_data['price']
    await upd.message.reply_text(f"📦 {amt} USDT\n💰 {fmt(ctx.user_data['total'])} SDG\n✅ تأكيد:", reply_markup=kb_confirm())
    return BUY_STEPS['CONF']

async def buy_conf(upd, ctx):
    t = upd.message.text.strip()
    if t == "❌ إلغاء": return await cancel_flow(upd, ctx)
    if t != "✅ تأكيد":
        await upd.message.reply_text("❌ اختر تأكيد أو إلغاء")
        return BUY_STEPS['CONF']
    
    methods = db_all("SELECT * FROM payment_methods")
    if not methods: return await upd.message.reply_text("⚠️ لا توجد طرق دفع مضافة") or cancel_flow(upd, ctx)
    
    buttons = [[InlineKeyboardButton(m['name'], callback_data=f"pay_sel_{m['method_id']}")] for m in methods]
    await upd.message.reply_text("💳 اختر طريقة الدفع:", reply_markup=InlineKeyboardMarkup(buttons))
    return BUY_STEPS['WAIT_PAY']

async def global_inline_handler(upd, ctx):
    q = upd.callback_query
    await q.answer()
    data = q.data
    flow = ctx.user_data.get('flow')
    
    try:
        if data.startswith("pay_sel_") and flow == "BUY":
            mid = int(data.split("_")[1])
            m = db_get("SELECT * FROM payment_methods WHERE method_id=?", (mid,))
            ctx.user_data['pay_mid'] = mid
            await q.edit_message_text(f"💳 *{m['name']}*\n🔢 حول إلى: `{m['details']}`\n📸 أرسل صورة الإثبات:", parse_mode=ParseMode.MARKDOWN)
            return BUY_STEPS['WAIT_RECV']
            
        elif data.startswith("recv_sel_") and (flow == "BUY" or flow == "SELL"):
            mid = int(data.split("_")[1])
            m = db_get("SELECT * FROM receive_methods WHERE method_id=?", (mid,))
            ctx.user_data['recv_mid'] = mid
            await q.edit_message_text(f"💵 *{m['name']}*\n📝 أدخل رقم حسابك/آيديك لاستلام المبلغ:")
            return BUY_STEPS['WAIT_ACC'] if flow == "BUY" else SELL_STEPS['WAIT_ACC']
            
    except Exception as e:
        logger.error(f"Inline Handler Error: {e}")
        await q.edit_message_text("❌ حدث خطأ، أعد المحاولة من البداية.")
        return ConversationHandler.END
    return None

async def buy_proof(upd, ctx):
    if not upd.message.photo:
        await upd.message.reply_text("❌ أرسل صورة فقط")
        return BUY_STEPS['WAIT_PAY']
    ctx.user_data['proof'] = upd.message.photo[-1].file_id
    methods = db_all("SELECT * FROM receive_methods")
    if not methods: return await upd.message.reply_text("⚠️ لا توجد طرق استلام") or cancel_flow(upd, ctx)
    buttons = [[InlineKeyboardButton(m['name'], callback_data=f"recv_sel_{m['method_id']}")] for m in methods]
    await upd.message.reply_text("💵 اختر طريقة استلام أموالك:", reply_markup=InlineKeyboardMarkup(buttons))
    return BUY_STEPS['WAIT_RECV']

async def buy_acc(upd, ctx):
    t = upd.message.text.strip()
    if t == "❌ إلغاء": return await cancel_flow(upd, ctx)
    if len(t) < 3:
        await upd.message.reply_text("❌ أدخل رقم صحيح")
        return BUY_STEPS['WAIT_ACC']
    ctx.user_data['acc'] = t
    recv_name = db_get('SELECT name FROM receive_methods WHERE method_id=?', (ctx.user_data['recv_mid'],))['name']
    await upd.message.reply_text(f"✅ *تأكيد*\n💰 {fmt(ctx.user_data['total'])} SDG\n💵 {recv_name}\n🔢 `{t}`\n✅ للمتابعة:", reply_markup=kb_confirm(), parse_mode=ParseMode.MARKDOWN)
    return BUY_STEPS['DONE']

async def buy_finish(upd, ctx):
    t = upd.message.text.strip()
    if t == "❌ إلغاء": return await cancel_flow(upd, ctx)
    if t != "✅ تأكيد": return ConversationHandler.END
    
    uid = upd.effective_user.id
    oid = db_run("""INSERT INTO orders (seller_id, buyer_id, order_type, amount_usdt, price_per_usdt, total_sdg, status, payment_method_id, payment_proof, receive_method_id, user_account_details) 
              VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
           (OWNER_ID, uid, 'buy', ctx.user_data['amt'], ctx.user_data['price'], ctx.user_data['total'], 'pending_approval', ctx.user_data['pay_mid'], ctx.user_data['proof'], ctx.user_data['recv_mid'], ctx.user_data['acc']))
    
    try:
        cap = f"🔔 *طلب شراء* #{uid}\n📦 {ctx.user_data['amt']} USDT | 💰 {fmt(ctx.user_data['total'])} SDG\n🔢 حساب: `{ctx.user_data['acc']}`"
        await ctx.bot.send_photo(OWNER_ID, ctx.user_data['proof'], caption=cap, parse_mode=ParseMode.MARKDOWN)
    except:
        await ctx.bot.send_message(OWNER_ID, f"🔔 طلب شراء #{uid} (الصورة لم تصل)")
    
    await upd.message.reply_text("✅ تم إرسال الطلب!", reply_markup=kb_main(is_admin(uid)))
    ctx.user_data.clear()
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════
#                    💰 بيع USDT
# ════════════════════════════════════════════════════════════
SELL_STEPS = {'START': 200, 'AMT': 201, 'CONF': 202, 'WAIT_RECV': 203, 'WAIT_ACC': 204, 'DONE': 205}

async def sell_start(upd, ctx):
    if await guard(upd, ctx): return ConversationHandler.END
    if await check_trader(upd): return ConversationHandler.END
    ctx.user_data['flow'] = 'SELL'
    await upd.message.reply_text("💰 *بيع USDT*\nأدخل الكمية:", reply_markup=kb_cancel(), parse_mode=ParseMode.MARKDOWN)
    return SELL_STEPS['AMT']

async def sell_amt(upd, ctx):
    t = upd.message.text.strip()
    if t == "❌ إلغاء": return await cancel_flow(upd, ctx)
    try:
        amt = float(t.replace('،', '.'))
        if amt <= 0: raise ValueError
    except:
        return await upd.message.reply_text("❌ رقم صحيح") or SELL_STEPS['AMT']
    ctx.user_data['amt'] = amt
    ctx.user_data['price'] = float(get_s('usdt_buy_price'))
    ctx.user_data['total'] = amt * ctx.user_data['price']
    await upd.message.reply_text(f"📦 {amt} USDT | 💰 {fmt(ctx.user_data['total'])} SDG\n✅ تأكيد:", reply_markup=kb_confirm())
    return SELL_STEPS['CONF']

async def sell_conf(upd, ctx):
    t = upd.message.text.strip()
    if t == "❌ إلغاء": return await cancel_flow(upd, ctx)
    if t != "✅ تأكيد":
        await upd.message.reply_text("❌ اختر تأكيد أو إلغاء")
        return SELL_STEPS['CONF']
    await upd.message.reply_text(f"📥 أرسل USDT إلى:\n`{DEPOSIT_ADDRESS}`\n📸 ثم أرسل إثبات التحويل:", reply_markup=kb_cancel(), parse_mode=ParseMode.MARKDOWN)
    return SELL_STEPS['WAIT_RECV']

async def sell_proof(upd, ctx):
    if not upd.message.photo:
        await upd.message.reply_text("❌ صورة فقط")
        return SELL_STEPS['WAIT_RECV']
    ctx.user_data['proof'] = upd.message.photo[-1].file_id
    methods = db_all("SELECT * FROM receive_methods")
    if not methods: return await upd.message.reply_text("⚠️ لا توجد طرق استلام") or cancel_flow(upd, ctx)
    buttons = [[InlineKeyboardButton(m['name'], callback_data=f"recv_sel_{m['method_id']}")] for m in methods]
    await upd.message.reply_text("💵 اختر طريقة استلام أموالك:", reply_markup=InlineKeyboardMarkup(buttons))
    return SELL_STEPS['WAIT_ACC']

async def sell_acc(upd, ctx):
    t = upd.message.text.strip()
    if t == "❌ إلغاء": return await cancel_flow(upd, ctx)
    ctx.user_data['acc'] = t
    await upd.message.reply_text(f"✅ *تأكيد*\n💵 {fmt(ctx.user_data['total'])} SDG\n🔢 `{t}`\n✅ للمتابعة:", reply_markup=kb_confirm(), parse_mode=ParseMode.MARKDOWN)
    return SELL_STEPS['DONE']

async def sell_finish(upd, ctx):
    t = upd.message.text.strip()
    if t == "❌ إلغاء": return await cancel_flow(upd, ctx)
    if t != "✅ تأكيد": return ConversationHandler.END
    
    uid = upd.effective_user.id
    oid = db_run("""INSERT INTO orders (seller_id, buyer_id, order_type, amount_usdt, price_per_usdt, total_sdg, status, payment_proof, receive_method_id, user_account_details) 
              VALUES (?,?,?,?,?,?,?,?,?,?)""",
           (uid, OWNER_ID, 'sell', ctx.user_data['amt'], ctx.user_data['price'], ctx.user_data['total'], 'pending_approval', ctx.user_data['proof'], ctx.user_data['recv_mid'], ctx.user_data['acc']))
    
    try:
        cap = f"🔔 *طلب بيع* #{uid}\n📦 {ctx.user_data['amt']} USDT | 💰 {fmt(ctx.user_data['total'])} SDG\n🔢 حساب: `{ctx.user_data['acc']}`"
        await ctx.bot.send_photo(OWNER_ID, ctx.user_data['proof'], caption=cap, parse_mode=ParseMode.MARKDOWN)
    except:
        await ctx.bot.send_message(OWNER_ID, f"🔔 طلب بيع #{uid}")
    await upd.message.reply_text("✅ تم الاستلام!", reply_markup=kb_main(is_admin(uid)))
    ctx.user_data.clear()
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════
#                    💵 عرض + 📤 سحب + 🌟 + 
# ════════════════════════════════════════════════════════════
async def offer_cmd(upd, ctx):
    if await guard(upd, ctx): return ConversationHandler.END
    if await check_trader(upd): return ConversationHandler.END
    await upd.message.reply_text("💵 *تقديم عرض*\nاختر النوع:", reply_markup=kb_offer()); return 300

async def offer_type(upd, ctx):
    t = upd.message.text.strip()
    if t == "❌ إلغاء": return await cancel_flow(upd, ctx)
    if t not in ["شــراء","بــيــع"]: return await upd.message.reply_text("❌ اختر من الأزرار") or 300
    ctx.user_data['otype'] = t; await upd.message.reply_text("📩 أدخل الكمية (USDT):", reply_markup=kb_cancel()); return 301

async def offer_amt(upd, ctx):
    t = upd.message.text.strip()
    if t == "❌ إلغاء": return await cancel_flow(upd, ctx)
    try:
        amt = float(t.replace('،', '.'))
    except:
        return await upd.message.reply_text("❌ رقم صحيح") or 301
    ctx.user_data['amt'] = amt; await upd.message.reply_text("📩 أدخل السعر:", reply_markup=kb_cancel()); return 302

async def offer_price(upd, ctx):
    t = upd.message.text.strip()
    if t == "❌ إلغاء": return await cancel_flow(upd, ctx)
    try:
        p = float(t.replace('،', '.'))
    except:
        return await upd.message.reply_text("❌ سعر صحيح") or 302
    ctx.user_data['price'] = p
    await upd.message.reply_text(f"📋 {ctx.user_data['otype']} | {fmt(ctx.user_data['amt'])} USDT | 💰 {fmt(p)}\n✅ تأكيد:", reply_markup=kb_confirm(), parse_mode=ParseMode.MARKDOWN); return 303

async def offer_conf(upd, ctx):
    t = upd.message.text.strip()
    if t != "✅ تأكيد": return await cancel_flow(upd, ctx)
    uid = upd.effective_user.id
    typ = 'offer_buy' if ctx.user_data['otype'] == 'شــراء' else 'offer_sell'
    s = uid if typ == 'offer_sell' else OWNER_ID
    b = OWNER_ID if typ == 'offer_sell' else uid
    oid = db_run("INSERT INTO orders (seller_id,buyer_id,order_type,amount_usdt,price_per_usdt,total_sdg,status) VALUES (?,?,?,?,?,?,?)", (s,b,typ,ctx.user_data['amt'],ctx.user_data['price'],ctx.user_data['amt']*ctx.user_data['price'],'pending_offer'))
    try: await ctx.bot.send_message(OWNER_ID, f"🔔 عرض جديد #{oid}")
    except: pass
    await upd.message.reply_text("✅ تم الإرسال!", reply_markup=kb_main(is_admin(uid))); ctx.user_data.clear(); return ConversationHandler.END

async def withdraw_start(upd, ctx):
    if await guard(upd, ctx): return ConversationHandler.END
    u = get_user(upd.effective_user.id)
    if u['balance_usdt'] <= 0: return await upd.message.reply_text("❌ رصيدك فارغ")
    await upd.message.reply_text(f"📤 *سحب*\nرصيدك: {fmt(u['balance_usdt'])} USDT\nأدخل الكمية:", reply_markup=kb_cancel(), parse_mode=ParseMode.MARKDOWN); return 400

async def withdraw_amt(upd, ctx):
    t = upd.message.text.strip()
    if t == "❌ إلغاء": return await cancel_flow(upd, ctx)
    try:
        a = float(t.replace('،', '.'))
        u = get_user(upd.effective_user.id)
        if a <= 0 or a > u['balance_usdt']:
            raise ValueError
    except:
        return await upd.message.reply_text("❌ كمية خاطئة أو غير كافية") or 400
    ctx.user_data['amt'] = a
    await upd.message.reply_text("📩 أدخل عنوان TRC20:", reply_markup=kb_cancel()); return 401

async def withdraw_addr(upd, ctx):
    t = upd.message.text.strip()
    if t == "❌ إلغاء": return await cancel_flow(upd, ctx)
    if len(t) < 30: return await upd.message.reply_text("❌ عنوان غير صحيح") or 401
    ctx.user_data['addr'] = t
    await upd.message.reply_text(f"📤 تأكيد: {fmt(ctx.user_data['amt'])} إلى `{t}`\n✅ تأكيد:", reply_markup=kb_confirm(), parse_mode=ParseMode.MARKDOWN); return 402

async def withdraw_conf(upd, ctx):
    t = upd.message.text.strip()
    if t != "✅ تأكيد": return await cancel_flow(upd, ctx)
    uid = upd.effective_user.id
    db_run("UPDATE users SET balance_usdt=balance_usdt-? WHERE user_id=?", (ctx.user_data['amt'], uid))
    db_run("INSERT INTO transactions (user_id,tx_type,amount,status,notes) VALUES (?,?,?,?,?)", (uid, 'withdraw', ctx.user_data['amt'], 'pending', f"إلى: {ctx.user_data['addr']}"))
    try: await ctx.bot.send_message(OWNER_ID, f"🔔 سحب جديد!\n👤 {uid} | 📦 {fmt(ctx.user_data['amt'])} USDT")
    except: pass
    await upd.message.reply_text("✅ تم إرسال طلب السحب!", reply_markup=kb_main(is_admin(uid))); ctx.user_data.clear(); return ConversationHandler.END

async def premium_cmd(upd, ctx):
    if await guard(upd, ctx): return ConversationHandler.END
    if await check_trader(upd): return ConversationHandler.END
    await upd.message.reply_text(f"🌟 *تليجرام مميز*\nالسعر: {fmt(get_s('usdt_sell_price'))} USDT\nأدخل الكمية:", reply_markup=kb_cancel(), parse_mode=ParseMode.MARKDOWN); return 500

async def premium_amt(upd, ctx):
    t = upd.message.text.strip()
    if t == "❌ إلغاء": return await cancel_flow(upd, ctx)
    try:
        q = int(t)
        u = get_user(upd.effective_user.id)
        p = float(get_s('usdt_sell_price'))
        if q <= 0 or q * p > u['balance_usdt']:
            raise ValueError
    except:
        return await upd.message.reply_text("❌ كمية أو رصيد غير كافٍ") or 500
    ctx.user_data['qty'] = q
    ctx.user_data['total'] = q * p
    await upd.message.reply_text(f"🌟 تأكيد: {q} اشتراك بـ {fmt(q*p)} USDT\n✅ تأكيد:", reply_markup=kb_confirm(), parse_mode=ParseMode.MARKDOWN); return 501

async def premium_conf(upd, ctx):
    t = upd.message.text.strip()
    if t != "✅ تأكيد": return await cancel_flow(upd, ctx)
    db_run("UPDATE users SET balance_usdt=balance_usdt-? WHERE user_id=?", (ctx.user_data['total'], upd.effective_user.id))
    db_run("INSERT INTO transactions (user_id,tx_type,amount,status) VALUES (?,?,?,?)", (upd.effective_user.id, 'premium', ctx.user_data['total'], 'completed'))
    await upd.message.reply_text(f"✅ تم شراء {ctx.user_data['qty']} اشتراك!", reply_markup=kb_main(is_admin(upd.effective_user.id))); ctx.user_data.clear(); return ConversationHandler.END

async def support_cmd(upd, ctx):
    if await guard(upd, ctx): return ConversationHandler.END
    await upd.message.reply_text("📞 *الدعم الفني*\nاكتب مشكلتك:", reply_markup=kb_cancel(), parse_mode=ParseMode.MARKDOWN); return 600

async def support_msg(upd, ctx):
    t = upd.message.text.strip()
    if t == "❌ إلغاء": return await cancel_flow(upd, ctx)
    db_run("INSERT INTO support_msgs (user_id,message) VALUES (?,?)", (upd.effective_user.id, t))
    try: await ctx.bot.send_message(OWNER_ID, f"📩 دعم جديد من {upd.effective_user.id}:\n{t}")
    except: pass
    await upd.message.reply_text("✅ تم الإرسال", reply_markup=kb_main(is_admin(upd.effective_user.id))); return ConversationHandler.END

# ════════════════════════════════════════════════════════════
#                    🔐 لوحة الإدارة
# ════════════════════════════════════════════════════════════
async def admin_panel(upd, ctx):
    if not is_admin(upd.effective_user.id): return
    await upd.message.reply_text("🔐 *لوحة الإدارة*", reply_markup=kb_admin(), parse_mode=ParseMode.MARKDOWN)

async def admin_orders(upd, ctx):
    if not is_admin(upd.effective_user.id): return
    rows = db_all("SELECT * FROM orders WHERE status IN ('pending_offer','pending_approval') ORDER BY order_id")
    if not rows: return await upd.message.reply_text("📋 لا توجد طلبات قيد المراجعة", reply_markup=kb_admin())
    for r in rows:
        uid = r['buyer_id'] if r['order_type'] in ['buy','offer_buy'] else r['seller_id']
        u = get_user(uid)
        t = {'buy':'🛒 شراء','sell':'💰 بيع','offer_buy':'💵 عرض شراء','offer_sell':'💵 عرض بيع'}.get(r['order_type'], r['order_type'])
        txt = f"🔖 *#{r['order_id']}*\n👤 {u['full_name'] if u else uid}\n🔸 {t}\n📦 {fmt(r['amount_usdt'])} USDT\n💰 {fmt(r['total_sdg'])} SDG\n📶 {r['status']}"
        if r['user_account_details']: txt += f"\n🔢 حساب: `{r['user_account_details']}`"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ قبول", callback_data=f"adm_acc_{r['order_id']}")],[InlineKeyboardButton("❌ رفض", callback_data=f"adm_rej_{r['order_id']}")]])
        try:
            if r['payment_proof']: await upd.message.reply_photo(r['payment_proof'], caption=txt, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
            else: await upd.message.reply_text(txt, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        except: await upd.message.reply_text(txt + "\n⚠️ خطأ في الصورة", reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

async def admin_action(upd, ctx):
    q = upd.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    data = q.data.split("_")
    if len(data)<3: return
    act, oid = data[1], int(data[2])
    order = db_get("SELECT * FROM orders WHERE order_id=?", (oid,))
    if not order: return await q.edit_message_text("❌ غير موجود")
    uid = order['buyer_id'] if order['order_type'] in ['buy','offer_buy'] else order['seller_id']
    
    if act == "rej":
        db_run("UPDATE orders SET status='rejected' WHERE order_id=?", (oid,))
        try: await q.edit_message_text(q.message.text + "\n\n❌ تم الرفض"); await ctx.bot.send_message(uid, f"❌ رفض طلبك #{oid}")
        except: pass
    elif act == "acc":
        db_run("UPDATE orders SET status='completed' WHERE order_id=?", (oid,))
        try: await q.edit_message_text(q.message.text + "\n\n✅ تم الإتمام"); await ctx.bot.send_message(uid, f"✅ تم إتمام طلبك #{oid}")
        except: pass
        db_run("INSERT INTO transactions (user_id,tx_type,amount,status) VALUES (?,?,?,?)",(uid,'trade_complete',order['amount_usdt'],'completed'))

async def admin_trader_status(upd, ctx):
    if not is_admin(upd.effective_user.id): return
    if upd.message.text == "❌ إلغاء": return await upd.message.reply_text("✅ تم الإلغاء", reply_markup=kb_admin())
    if upd.message.text in ["🟢 تشغيل", "🔴 إيقاف"]:
        val = 1 if upd.message.text == "🟢 تشغيل" else 0
        set_s('trader_online_status', val)
        await upd.message.reply_text(f"🚦 تم التحديث: {'🟢 متصل' if val else '🔴 غير متصل'}", reply_markup=kb_admin())
    else: await upd.message.reply_text("🚦 اختر الحالة:", reply_markup=kb_trader())

async def admin_add_pay_n(upd, ctx):
    if not is_admin(upd.effective_user.id): return
    ctx.user_data['name'] = upd.message.text.strip()
    await upd.message.reply_text("📋 أدخل التفاصيل (آيدي/حساب):", reply_markup=kb_cancel()); return 70

async def admin_add_pay_d(upd, ctx):
    db_run("INSERT INTO payment_methods (name,details) VALUES (?,?)", (ctx.user_data['name'], upd.message.text.strip()))
    await upd.message.reply_text("✅ تمت إضافة طريقة الدفع", reply_markup=kb_admin()); ctx.user_data.clear(); return ConversationHandler.END

async def admin_add_recv_n(upd, ctx):
    if not is_admin(upd.effective_user.id): return
    ctx.user_data['name'] = upd.message.text.strip()
    await upd.message.reply_text("📋 أدخل التفاصيل:", reply_markup=kb_cancel()); return 71

async def admin_add_recv_d(upd, ctx):
    db_run("INSERT INTO receive_methods (name,details) VALUES (?,?)", (ctx.user_data['name'], upd.message.text.strip()))
    await upd.message.reply_text("✅ تمت إضافة طريقة الاستلام", reply_markup=kb_admin()); ctx.user_data.clear(); return ConversationHandler.END

async def admin_set_val(upd, ctx, key, label):
    if not is_admin(upd.effective_user.id): return
    t = upd.message.text.strip()
    if t == "❌ إلغاء": return await upd.message.reply_text("✅ تم الإلغاء", reply_markup=kb_admin())
    try:
        v = float(t.replace('،', '.'))
        set_s(key, v)
        await upd.message.reply_text(f"✅ تم تحديث {label} إلى {fmt(v)}", reply_markup=kb_admin())
        return ConversationHandler.END
    except:
        return await upd.message.reply_text("❌ أدخل رقماً صحيحاً")

# ════════════════════════════════════════════════════════════
#                    🚀 التشغيل الرئيسي
# ════════════════════════════════════════════════════════════
def main():
    print("🚀 جاري تهيئة البوت...")
    init_db()
    print("✅ قاعدة البيانات جاهزة")
    
    app = Application.builder().token(BOT_TOKEN).build()
    c_filter = filters.Regex(r"^(❌ إلغاء|🔙 الرئيسية|/cancel)$")
    
    # تسجيل
    app.add_handler(ConversationHandler(entry_points=[CommandHandler("start", start_cmd)], states={0:[MessageHandler(filters.TEXT&~filters.COMMAND, reg_name)], 1:[MessageHandler(filters.TEXT&~filters.COMMAND, reg_country)]}, fallbacks=[MessageHandler(c_filter, cancel_flow)]))
    
    # شراء
    app.add_handler(ConversationHandler(entry_points=[MessageHandler(filters.Regex(r"^🛒 شراء USDT$"), buy_start)], 
        states={BUY_STEPS['AMT']:[MessageHandler(filters.TEXT&~filters.COMMAND, buy_amt)], 
                BUY_STEPS['CONF']:[MessageHandler(filters.TEXT&~filters.COMMAND, buy_conf)],
                BUY_STEPS['WAIT_PAY']:[CallbackQueryHandler(global_inline_handler)],
                BUY_STEPS['WAIT_RECV']:[MessageHandler(filters.PHOTO, buy_proof), CallbackQueryHandler(global_inline_handler)],
                BUY_STEPS['WAIT_ACC']:[MessageHandler(filters.TEXT&~filters.COMMAND, buy_acc)],
                BUY_STEPS['DONE']:[MessageHandler(filters.TEXT&~filters.COMMAND, buy_finish)]}, 
        fallbacks=[MessageHandler(c_filter, cancel_flow)]))
                
    # بيع
    app.add_handler(ConversationHandler(entry_points=[MessageHandler(filters.Regex(r"^💰 بيع USDT$"), sell_start)], 
        states={SELL_STEPS['AMT']:[MessageHandler(filters.TEXT&~filters.COMMAND, sell_amt)], 
                SELL_STEPS['CONF']:[MessageHandler(filters.TEXT&~filters.COMMAND, sell_conf)],
                SELL_STEPS['WAIT_RECV']:[MessageHandler(filters.PHOTO, sell_proof), CallbackQueryHandler(global_inline_handler)],
                SELL_STEPS['WAIT_ACC']:[CallbackQueryHandler(global_inline_handler), MessageHandler(filters.TEXT&~filters.COMMAND, sell_acc)],
                SELL_STEPS['DONE']:[MessageHandler(filters.TEXT&~filters.COMMAND, sell_finish)]}, 
        fallbacks=[MessageHandler(c_filter, cancel_flow)]))

    # عرض
    app.add_handler(ConversationHandler(entry_points=[MessageHandler(filters.Regex(r"^💵 تقديم عرض$"), offer_cmd)],
        states={300:[MessageHandler(filters.TEXT&~filters.COMMAND, offer_type)], 301:[MessageHandler(filters.TEXT&~filters.COMMAND, offer_amt)], 302:[MessageHandler(filters.TEXT&~filters.COMMAND, offer_price)], 303:[MessageHandler(filters.TEXT&~filters.COMMAND, offer_conf)]}, fallbacks=[MessageHandler(c_filter, cancel_flow)]))
                
    # سحب / مميز / دعم
    app.add_handler(ConversationHandler(entry_points=[CommandHandler("withdraw", withdraw_start)], states={400:[MessageHandler(filters.TEXT&~filters.COMMAND, withdraw_amt)], 401:[MessageHandler(filters.TEXT&~filters.COMMAND, withdraw_addr)], 402:[MessageHandler(filters.TEXT&~filters.COMMAND, withdraw_conf)]}, fallbacks=[MessageHandler(c_filter, cancel_flow)]))
    app.add_handler(ConversationHandler(entry_points=[MessageHandler(filters.Regex(r"^🌟 تليجرام مميز$"), premium_cmd)], states={500:[MessageHandler(filters.TEXT&~filters.COMMAND, premium_amt)], 501:[MessageHandler(filters.TEXT&~filters.COMMAND, premium_conf)]}, fallbacks=[MessageHandler(c_filter, cancel_flow)]))
    app.add_handler(ConversationHandler(entry_points=[MessageHandler(filters.Regex(r"^📞 الدعم$"), support_cmd)], states={600:[MessageHandler(filters.TEXT&~filters.COMMAND, support_msg)]}, fallbacks=[MessageHandler(c_filter, cancel_flow)]))
    
    # إدارة
    app.add_handler(MessageHandler(filters.Regex(r"^🔐 الإدارة$"), admin_panel))
    app.add_handler(MessageHandler(filters.Regex(r"^📋 جميع الطلبات$"), admin_orders))
    app.add_handler(CallbackQueryHandler(admin_action, pattern=r"^adm_(acc|rej)_\d+$"))
    app.add_handler(MessageHandler(filters.Regex(r"^🚦 حالة التاجر$"), admin_trader_status))
    
    app.add_handler(ConversationHandler(entry_points=[MessageHandler(filters.Regex(r"^💲 تعديل سعر الشراء$"), lambda u,c: u.message.reply_text("💲 أدخل السعر الجديد:", reply_markup=kb_cancel()))], states={800:[MessageHandler(filters.TEXT&~filters.COMMAND, lambda u,c: admin_set_val(u,c,'usdt_buy_price','سعر الشراء'))]}, fallbacks=[MessageHandler(c_filter, cancel_flow)]))
    app.add_handler(ConversationHandler(entry_points=[MessageHandler(filters.Regex(r"^💲 تعديل سعر البيع$"), lambda u,c: u.message.reply_text("💲 أدخل السعر الجديد:", reply_markup=kb_cancel()))], states={801:[MessageHandler(filters.TEXT&~filters.COMMAND, lambda u,c: admin_set_val(u,c,'usdt_sell_price','سعر البيع'))]}, fallbacks=[MessageHandler(c_filter, cancel_flow)]))
    
    app.add_handler(ConversationHandler(entry_points=[MessageHandler(filters.Regex(r"^💳 إضافة طريقة دفع$"), lambda u,c: u.message.reply_text("💳 أدخل الاسم:", reply_markup=kb_cancel()))], states={70:[MessageHandler(filters.TEXT&~filters.COMMAND, admin_add_pay_n), MessageHandler(filters.TEXT&~filters.COMMAND, admin_add_pay_d)]}, fallbacks=[MessageHandler(c_filter, cancel_flow)]))
    app.add_handler(ConversationHandler(entry_points=[MessageHandler(filters.Regex(r"^💵 إضافة طريقة استلام$"), lambda u,c: u.message.reply_text("💵 أدخل الاسم:", reply_markup=kb_cancel()))], states={71:[MessageHandler(filters.TEXT&~filters.COMMAND, admin_add_recv_n), MessageHandler(filters.TEXT&~filters.COMMAND, admin_add_recv_d)]}, fallbacks=[MessageHandler(c_filter, cancel_flow)]))

    # أزرار عامة
    app.add_handler(MessageHandler(c_filter, cancel_flow))
    app.add_handler(MessageHandler(filters.Regex(r"^👤 ملفي$|^🔗 الإحالة$"), show_profile))
    app.add_handler(MessageHandler(filters.Regex(r"^💳 رصيدي$"), show_balance))
    app.add_handler(MessageHandler(filters.Regex(r"^📋 طلباتي$"), show_orders))
    app.add_handler(MessageHandler(filters.Regex(r"^📜 سجل المعاملات$"), show_tx))
    app.add_handler(MessageHandler(filters.Regex(r"^⚙️ الإعدادات$"), show_settings))
    app.add_handler(MessageHandler(filters.Regex(r"^💱 سعر الصرف$"), show_exchange))
    app.add_handler(MessageHandler(filters.Regex(r"^🗃️ المخزون$"), show_inventory))
    app.add_handler(MessageHandler(filters.Regex(r"^📊 السوق$"), show_exchange))
    
    print("📡 جاري الاتصال بـ Telegram (Polling)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()

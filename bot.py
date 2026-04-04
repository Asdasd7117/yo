#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════╗
║          بوت تداول USDT P2P العملاق - النسخة الكاملة    ║
║  ✅ نظام الإحالات | ✅ إدارة الأرصدة | ✅ السجلات | ✅ المتجر ║
║  ✅ إرسال السكرين | ✅ التحكم بالأسعار | ✅ حالة التاجر     ║
╚══════════════════════════════════════════════════════════╝
"""

import os, sqlite3, logging, random, string, json, asyncio
from datetime import datetime
from threading import local
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
#                    ⚙️  الإعدادات والتوكن
# ════════════════════════════════════════════════════════════
BOT_TOKEN       = "8443614197:AAFF5awBt6UX3ZAcxsosWuDkVUUq8GOmuRg"
OWNER_ID        = 6814152338
DB_PATH         = "trading_bot.db"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════
#                    🗄️  محرك قاعدة البيانات
# ════════════════════════════════════════════════════════════
_db_local = local()
def get_conn():
    if not hasattr(_db_local, 'conn') or _db_local.conn is None:
        c = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)
        c.row_factory = sqlite3.Row
        _db_local.conn = c
    return _db_local.conn

def init_db():
    conn = get_conn()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, country TEXT, 
            balance_usdt REAL DEFAULT 0, commission_earned REAL DEFAULT 0, rank TEXT DEFAULT 'user',
            total_trades INTEGER DEFAULT 0, completed_trades INTEGER DEFAULT 0,
            referral_code TEXT UNIQUE, referred_by INTEGER, is_banned INTEGER DEFAULT 0,
            wallet_address TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT, seller_id INTEGER, buyer_id INTEGER,
            order_type TEXT, amount_usdt REAL, price_per_usdt REAL, total_sdg REAL, 
            status TEXT DEFAULT 'pending', payment_method_id INTEGER, payment_proof TEXT,
            receive_method_id INTEGER, user_account_details TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS payment_methods (method_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, details TEXT);
        CREATE TABLE IF NOT EXISTS receive_methods (method_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, details TEXT);
        CREATE TABLE IF NOT EXISTS transactions (tx_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, tx_type TEXT, amount REAL, status TEXT DEFAULT 'pending', notes TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS support_msgs (msg_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, message TEXT, admin_reply TEXT, status TEXT DEFAULT 'open', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
        
        INSERT OR IGNORE INTO settings VALUES ('usdt_buy_price', '4000.0'), ('usdt_sell_price', '4100.0'), 
        ('trader_online_status', '1'), ('commission_rate', '3.0'), ('available_usdt_inventory', '1000.0'),
        ('welcome_msg', 'أهلاً بك في بوت التداول المعتمد.');
    ''')

# دوال العمليات
def db_get(q, p=()): return dict(r) if (r := get_conn().execute(q, p).fetchone()) else None
def db_all(q, p=()): return [dict(r) for r in get_conn().execute(q, p).fetchall()]
def db_run(q, p=()): return get_conn().execute(q, p).lastrowid
def get_s(k): r = db_get("SELECT value FROM settings WHERE key=?", (k,)); return r['value'] if r else '0'
def set_s(k, v): db_run("INSERT OR REPLACE INTO settings VALUES (?,?)", (k, str(v)))
def is_admin(uid): return uid == OWNER_ID
def fmt(n): return f"{float(n):,.2f}"

# ════════════════════════════════════════════════════════════
#                    🔢  الحالات (States)
# ════════════════════════════════════════════════════════════
(REG_NAME, REG_COUNTRY, BUY_AMT, BUY_CONF, BUY_PAY_SEL, BUY_PROOF, BUY_RECV_SEL, BUY_ACC, BUY_DONE, 
 SELL_AMT, SELL_CONF, SELL_RECV_SEL, SELL_ACC, SELL_DONE, 
 ADD_PAY_NAME, ADD_PAY_VAL, ADD_RECV_NAME, ADD_RECV_VAL,
 SET_BUY_PR, SET_SELL_PR, TRADER_STAT, BROADCAST_MSG) = range(22)

# ════════════════════════════════════════════════════════════
#                    ⌨️  لوحات المفاتيح
# ════════════════════════════════════════════════════════════
def kb_main(admin=False):
    rows = [
        [KeyboardButton("🛒 شراء USDT"), KeyboardButton("💰 بيع USDT")],
        [KeyboardButton("👤 ملفي"), KeyboardButton("💳 رصيدي")],
        [KeyboardButton("📋 طلباتي"), KeyboardButton("📊 السوق")],
        [KeyboardButton("📜 سجل المعاملات"), KeyboardButton("🔗 الإحالة")],
        [KeyboardButton("💱 سعر الصرف"), KeyboardButton("🗃️ المخزون")],
        [KeyboardButton("📞 الدعم"), KeyboardButton("🌟 تليجرام مميز")]
    ]
    if admin: rows.append([KeyboardButton("🔐 الإدارة")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def kb_admin():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📋 جميع الطلبات"), KeyboardButton("🚦 حالة التاجر")],
        [KeyboardButton("💲 تعديل سعر الشراء"), KeyboardButton("💲 تعديل سعر البيع")],
        [KeyboardButton("💳 إضافة طريقة دفع"), KeyboardButton("💵 إضافة طريقة استلام")],
        [KeyboardButton("📢 إرسال للجميع"), KeyboardButton("🔙 الرئيسية")]
    ], resize_keyboard=True)

def kb_cancel(): return ReplyKeyboardMarkup([[KeyboardButton("❌ إلغاء")]], resize_keyboard=True)
def kb_confirm(): return ReplyKeyboardMarkup([[KeyboardButton("✅ تأكيد"), KeyboardButton("❌ إلغاء")]], resize_keyboard=True)

# ════════════════════════════════════════════════════════════
#                    🚀 منطق البوت
# ════════════════════════════════════════════════════════════

async def start(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = upd.effective_user.id
    user = db_get("SELECT * FROM users WHERE user_id=?", (uid,))
    if not user:
        await upd.message.reply_text("👋 مرحباً بك في نظام التداول الذكي.\nللبدء، يرجى إرسال اسمك بالكامل:", reply_markup=kb_cancel())
        return REG_NAME
    await upd.message.reply_text(get_s('welcome_msg'), reply_markup=kb_main(is_admin(uid)))
    return ConversationHandler.END

async def reg_name(upd, ctx):
    if upd.message.text == "❌ إلغاء": return await cancel(upd, ctx)
    ctx.user_data['n'] = upd.message.text
    await upd.message.reply_text("🌍 حسناً، من أي بلد تتابعنا؟", reply_markup=kb_cancel())
    return REG_COUNTRY

async def reg_country(upd, ctx):
    uid = upd.effective_user.id
    ref = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    db_run("INSERT INTO users (user_id, username, full_name, country, referral_code) VALUES (?,?,?,?,?)",
           (uid, upd.effective_user.username, ctx.user_data['n'], upd.message.text, ref))
    await upd.message.reply_text("✅ تم التسجيل بنجاح!", reply_markup=kb_main(is_admin(uid)))
    return ConversationHandler.END

# 🛒 نظام الشراء المطور
async def buy_start(upd, ctx):
    if get_s('trader_online_status') == '0' and not is_admin(upd.effective_user.id):
        await upd.message.reply_text("⛔️ التاجر غير متاح حالياً لاستلام طلبات جديدة.")
        return ConversationHandler.END
    await upd.message.reply_text("🛒 أدخل كمية الـ USDT المراد شراؤها:", reply_markup=kb_cancel())
    return BUY_AMT

async def buy_amt(upd, ctx):
    if upd.message.text == "❌ إلغاء": return await cancel(upd, ctx)
    try:
        amt = float(upd.message.text.replace(',', '.'))
        ctx.user_data['amt'] = amt
        price = float(get_s('usdt_sell_price'))
        ctx.user_data['total'] = amt * price
        await upd.message.reply_text(f"📦 الكمية: {amt} USDT\n💰 السعر: {price} SDG\n💵 الإجمالي: {fmt(amt * price)} SDG\n\n✅ هل تود المتابعة واختيار وسيلة الدفع؟", reply_markup=kb_confirm())
        return BUY_CONF
    except: return BUY_AMT

async def buy_conf(upd, ctx):
    if upd.message.text == "✅ تأكيد":
        mths = db_all("SELECT * FROM payment_methods")
        if not mths:
            await upd.message.reply_text("⚠️ لا توجد وسائل دفع، تواصل مع الإدارة.")
            return await cancel(upd, ctx)
        btns = [[InlineKeyboardButton(m['name'], callback_data=f"bpay_{m['method_id']}")] for m in mths]
        await upd.message.reply_text("💳 اختر وسيلة الدفع المناسبة لك:", reply_markup=InlineKeyboardMarkup(btns))
        return BUY_PAY_SEL
    return await cancel(upd, ctx)

async def buy_pay_sel(upd, ctx):
    q = upd.callback_query
    await q.answer()
    mid = q.data.split("_")[1]
    ctx.user_data['pmid'] = mid
    m = db_get("SELECT * FROM payment_methods WHERE method_id=?", (mid,))
    await q.edit_message_text(f"🔢 يرجى تحويل `{fmt(ctx.user_data['total'])}` SDG إلى:\n\n`{m['details']}`\n\n📸 أرسل صورة الإيصال (Screenshot) الآن:", parse_mode=ParseMode.MARKDOWN)
    return BUY_PROOF

async def buy_proof(upd, ctx):
    if not upd.message.photo:
        await upd.message.reply_text("❌ يجب إرسال صورة إيصال التحويل للمتابعة.")
        return BUY_PROOF
    ctx.user_data['proof'] = upd.message.photo[-1].file_id
    mths = db_all("SELECT * FROM receive_methods")
    btns = [[InlineKeyboardButton(m['name'], callback_data=f"brecv_{m['method_id']}")] for m in mths]
    await upd.message.reply_text("💵 اختر وسيلة استلام الـ USDT:", reply_markup=InlineKeyboardMarkup(btns))
    return BUY_RECV_SEL

async def buy_recv_sel(upd, ctx):
    q = upd.callback_query
    await q.answer()
    ctx.user_data['rmid'] = q.data.split("_")[1]
    await q.edit_message_text("📝 أرسل الآن عنوان محفظتك أو رقم الحساب لاستلام الـ USDT:")
    return BUY_ACC

async def buy_acc(upd, ctx):
    ctx.user_data['acc'] = upd.message.text
    await upd.message.reply_text("✅ تم تأكيد البيانات، هل تود إرسال الطلب نهائياً للتاجر؟", reply_markup=kb_confirm())
    return BUY_DONE

async def buy_finish(upd, ctx):
    if upd.message.text != "✅ تأكيد": return await cancel(upd, ctx)
    uid = upd.effective_user.id
    oid = db_run("INSERT INTO orders (buyer_id, order_type, amount_usdt, price_per_usdt, total_sdg, status, payment_method_id, payment_proof, receive_method_id, user_account_details) VALUES (?,?,?,?,?,?,?,?,?,?)",
           (uid, 'buy', ctx.user_data['amt'], float(get_s('usdt_sell_price')), ctx.user_data['total'], 'pending', ctx.user_data['pmid'], ctx.user_data['proof'], ctx.user_data['rmid'], ctx.user_data['acc']))
    
    # الإرسال الفوري للتاجر مع السكرين شوت
    caption = f"🔔 *طلب شراء جديد #{oid}*\n👤 العميل: `{uid}`\n📦 الكمية: {ctx.user_data['amt']} USDT\n💰 المبلغ: {fmt(ctx.user_data['total'])} SDG\n🔢 حساب الاستلام: `{ctx.user_data['acc']}`"
    await ctx.bot.send_photo(chat_id=OWNER_ID, photo=ctx.user_data['proof'], caption=caption, parse_mode=ParseMode.MARKDOWN)
    
    await upd.message.reply_text("🚀 تم إرسال طلبك! سيتم تنبيهك عند الموافقة.", reply_markup=kb_main(is_admin(uid)))
    ctx.user_data.clear()
    return ConversationHandler.END

# 🚦 حالة التاجر (مصلح)
async def trader_stat_start(upd, ctx):
    if not is_admin(upd.effective_user.id): return ConversationHandler.END
    await upd.message.reply_text("🚦 التحكم في ظهور التاجر:", reply_markup=ReplyKeyboardMarkup([["🟢 تشغيل", "🔴 إيقاف"], ["❌ إلغاء"]], resize_keyboard=True))
    return TRADER_STAT

async def trader_stat_done(upd, ctx):
    t = upd.message.text
    if t == "🟢 تشغيل": set_s('trader_online_status', '1')
    elif t == "🔴 إيقاف": set_s('trader_online_status', '0')
    await upd.message.reply_text(f"✅ الحالة الحالية: {t}", reply_markup=kb_admin())
    return ConversationHandler.END

# 💲 تعديل الأسعار
async def price_buy_start(upd, ctx):
    if not is_admin(upd.effective_user.id): return ConversationHandler.END
    await upd.message.reply_text("💲 أدخل سعر الشراء الجديد (SDG):", reply_markup=kb_cancel())
    return SET_BUY_PR

async def price_buy_done(upd, ctx):
    try:
        val = float(upd.message.text)
        set_s('usdt_buy_price', val)
        await upd.message.reply_text(f"✅ تم تعديل سعر الشراء إلى: {val}", reply_markup=kb_admin())
    except: pass
    return ConversationHandler.END

# 📢 الإرسال الجماعي
async def broadcast_start(upd, ctx):
    if not is_admin(upd.effective_user.id): return ConversationHandler.END
    await upd.message.reply_text("📢 أرسل الرسالة التي تريد تعميمها لجميع المستخدمين:", reply_markup=kb_cancel())
    return BROADCAST_MSG

async def broadcast_done(upd, ctx):
    msg = upd.message.text
    users = db_all("SELECT user_id FROM users")
    count = 0
    for u in users:
        try:
            await ctx.bot.send_message(chat_id=u['user_id'], text=f"📢 *تنبيه من الإدارة:*\n\n{msg}", parse_mode=ParseMode.MARKDOWN)
            count += 1
        except: pass
    await upd.message.reply_text(f"✅ تمت العملية بنجاح. أرسلت إلى {count} مستخدم.", reply_markup=kb_admin())
    return ConversationHandler.END

async def cancel(upd, ctx):
    ctx.user_data.clear()
    await upd.message.reply_text("⚠️ تم الإلغاء.", reply_markup=kb_main(is_admin(upd.effective_user.id)))
    return ConversationHandler.END

# 🏁 تشغيل
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    
    # تجميع الحوارات
    buy_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^🛒 شراء USDT$"), buy_start)],
        states={
            BUY_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_amt)],
            BUY_CONF: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_conf)],
            BUY_PAY_SEL: [CallbackQueryHandler(buy_pay_sel, pattern=r"^bpay_")],
            BUY_PROOF: [MessageHandler(filters.PHOTO, buy_proof)],
            BUY_RECV_SEL: [CallbackQueryHandler(buy_recv_sel, pattern=r"^brecv_")],
            BUY_ACC: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_acc)],
            BUY_DONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_finish)]
        },
        fallbacks=[MessageHandler(filters.Regex("❌ إلغاء"), cancel)], per_message=False
    )

    admin_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^🚦 حالة التاجر$"), trader_stat_start),
            MessageHandler(filters.Regex(r"^💲 تعديل سعر الشراء$"), price_buy_start),
            MessageHandler(filters.Regex(r"^📢 إرسال للجميع$"), broadcast_start)
        ],
        states={
            TRADER_STAT: [MessageHandler(filters.Regex(r"^(🟢 تشغيل|🔴 إيقاف)$"), trader_stat_done)],
            SET_BUY_PR: [MessageHandler(filters.TEXT & ~filters.COMMAND, price_buy_done)],
            BROADCAST_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_done)]
        },
        fallbacks=[MessageHandler(filters.Regex("❌ إلغاء"), cancel)]
    )

    reg_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            REG_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_name)],
            REG_COUNTRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_country)]
        },
        fallbacks=[MessageHandler(filters.Regex("❌ إلغاء"), cancel)]
    )

    app.add_handler(reg_conv); app.add_handler(buy_conv); app.add_handler(admin_conv)
    
    # الأزرار العامة
    app.add_handler(MessageHandler(filters.Regex(r"^👤 ملفي$"), lambda u,c: u.message.reply_text(f"👤 الاسم: {db_get('SELECT full_name FROM users WHERE user_id=?', (u.effective_user.id,))['full_name']}")))
    app.add_handler(MessageHandler(filters.Regex(r"^💱 سعر الصرف$"), lambda u,c: u.message.reply_text(f"📥 شراء: {get_s('usdt_buy_price')}\n📤 بيع: {get_s('usdt_sell_price')}")))
    app.add_handler(MessageHandler(filters.Regex(r"^🗃️ المخزون$"), lambda u,c: u.message.reply_text(f"المتاح: {get_s('available_usdt_inventory')} USDT")))
    app.add_handler(MessageHandler(filters.Regex(r"^🔐 الإدارة$"), lambda u,c: u.message.reply_text("لوحة الإدارة:", reply_markup=kb_admin()) if is_admin(u.effective_user.id) else None))
    app.add_handler(MessageHandler(filters.Regex(r"^🔙 الرئيسية$"), lambda u,c: u.message.reply_text("الرئيسية:", reply_markup=kb_main(is_admin(u.effective_user.id)))))

    app.run_polling()

if __name__ == "__main__": main()

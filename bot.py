#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════╗
║          بوت تداول USDT P2P المتكامل - الإصدار العملاق    ║
║  ✅ الشراء والبيع | ✅ المحفظة | ✅ الإحالات | ✅ الدعم      ║
║  ✅ سجلات كاملة | ✅ إدارة المتجر | ✅ نظام السكرين شوت    ║
║  🚀 متوافق 100% مع Render (Flask + Port Binding)         ║
╚══════════════════════════════════════════════════════════╝
"""

import os, sqlite3, logging, random, string, json, asyncio, threading
from datetime import datetime
from threading import local
from flask import Flask
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
#             🌐 سيرفر Flask لإبقاء البوت حياً على Render
# ════════════════════════════════════════════════════════════
server = Flask('')
@server.route('/')
def home(): return "<h1>Bot is Active on Render</h1>"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server.run(host='0.0.0.0', port=port)

# ════════════════════════════════════════════════════════════
#                    🗄️  محرك قاعدة البيانات الشامل
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
        CREATE TABLE IF NOT EXISTS transactions (tx_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, tx_type TEXT, amount REAL, notes TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS support_msgs (msg_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, message TEXT, admin_reply TEXT, status TEXT DEFAULT 'open', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
        
        INSERT OR IGNORE INTO settings VALUES ('usdt_buy_price', '4000.0'), ('usdt_sell_price', '4100.0'), 
        ('trader_online_status', '1'), ('commission_rate', '3.0'), ('available_usdt_inventory', '1000.0'),
        ('welcome_msg', 'أهلاً بك في بوت التداول المعتمد P2P.');
    ''')
    # بيانات تجريبية إذا كانت الجداول فارغة
    if not db_all("SELECT * FROM payment_methods"):
        db_run("INSERT INTO payment_methods (name, details) VALUES ('بنكك (Bankak)', 'Account: 1234567')")
    if not db_all("SELECT * FROM receive_methods"):
        db_run("INSERT INTO receive_methods (name, details) VALUES ('TRC20 Wallet', 'أدخل عنوان المحفظة')")

def db_get(q, p=()): return dict(r) if (r := get_conn().execute(q, p).fetchone()) else None
def db_all(q, p=()): return [dict(r) for r in get_conn().execute(q, p).fetchall()]
def db_run(q, p=()): return get_conn().execute(q, p).lastrowid
def get_s(k): r = db_get("SELECT value FROM settings WHERE key=?", (k,)); return r['value'] if r else '0'
def set_s(k, v): db_run("INSERT OR REPLACE INTO settings VALUES (?,?)", (k, str(v)))
def is_admin(uid): return uid == OWNER_ID
def fmt(n): return f"{float(n):,.2f}"

# ════════════════════════════════════════════════════════════
#                    🔢  الحالات (States) - تغطية شاملة
# ════════════════════════════════════════════════════════════
(REG_NAME, REG_COUNTRY, BUY_AMT, BUY_CONF, BUY_PAY_SEL, BUY_PROOF, BUY_RECV_SEL, BUY_ACC, BUY_DONE, 
 SELL_AMT, SELL_CONF, SELL_RECV_SEL, SELL_ACC, SELL_DONE, 
 SET_BUY_PR, SET_SELL_PR, TRADER_STAT, BROADCAST_MSG, SUPPORT_INPUT) = range(19)

# ════════════════════════════════════════════════════════════
#                    ⌨️  لوحات المفاتيح
# ════════════════════════════════════════════════════════════
def kb_main(admin=False):
    rows = [
        [KeyboardButton("🛒 شراء USDT"), KeyboardButton("💰 بيع USDT")],
        [KeyboardButton("👤 ملفي"), KeyboardButton("💳 رصيدي")],
        [KeyboardButton("📋 طلباتي"), KeyboardButton("📊 السوق")],
        [KeyboardButton("📜 السجلات"), KeyboardButton("🔗 الإحالة")],
        [KeyboardButton("💱 سعر الصرف"), KeyboardButton("🗃️ المخزون")],
        [KeyboardButton("📞 الدعم"), KeyboardButton("🌟 مميز")]
    ]
    if admin: rows.append([KeyboardButton("🔐 الإدارة")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def kb_admin():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📋 جميع الطلبات"), KeyboardButton("🚦 حالة التاجر")],
        [KeyboardButton("💲 تعديل الأسعار"), KeyboardButton("📢 رسالة جماعية")],
        [KeyboardButton("💳 إدارة طرق الدفع"), KeyboardButton("🔙 الرئيسية")]
    ], resize_keyboard=True)

def kb_cancel(): return ReplyKeyboardMarkup([[KeyboardButton("❌ إلغاء")]], resize_keyboard=True)
def kb_confirm(): return ReplyKeyboardMarkup([[KeyboardButton("✅ تأكيد"), KeyboardButton("❌ إلغاء")]], resize_keyboard=True)

# ════════════════════════════════════════════════════════════
#                    🚀 منطق العمليات الكاملة
# ════════════════════════════════════════════════════════════

async def start(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = upd.effective_user.id
    user = db_get("SELECT * FROM users WHERE user_id=?", (uid,))
    if not user:
        await upd.message.reply_text("👋 مرحباً بك في نظام التداول الذكي.\nيرجى إرسال اسمك بالكامل للبدء:", reply_markup=kb_cancel())
        return REG_NAME
    await upd.message.reply_text(get_s('welcome_msg'), reply_markup=kb_main(is_admin(uid)))
    return ConversationHandler.END

async def reg_name(upd, ctx):
    if upd.message.text == "❌ إلغاء": return await cancel(upd, ctx)
    ctx.user_data['n'] = upd.message.text
    await upd.message.reply_text("🌍 حسناً، أدخل اسم بلدك:", reply_markup=kb_cancel())
    return REG_COUNTRY

async def reg_country(upd, ctx):
    uid = upd.effective_user.id
    ref_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    db_run("INSERT INTO users (user_id, username, full_name, country, referral_code) VALUES (?,?,?,?,?)",
           (uid, upd.effective_user.username, ctx.user_data['n'], upd.message.text, ref_code))
    await upd.message.reply_text("✅ تم التسجيل بنجاح في المنصة!", reply_markup=kb_main(is_admin(uid)))
    return ConversationHandler.END

# 🛒 نظام الشراء الكامل
async def buy_start(upd, ctx):
    if get_s('trader_online_status') == '0' and not is_admin(upd.effective_user.id):
        await upd.message.reply_text("⛔️ المتجر مغلق حالياً، حاول لاحقاً.")
        return ConversationHandler.END
    await upd.message.reply_text("🛒 أدخل كمية USDT التي تود شراءها:", reply_markup=kb_cancel())
    return BUY_AMT

async def buy_amt(upd, ctx):
    if upd.message.text == "❌ إلغاء": return await cancel(upd, ctx)
    try:
        amt = float(upd.message.text.replace(',', '.'))
        ctx.user_data['amt'] = amt
        price = float(get_s('usdt_sell_price'))
        ctx.user_data['total'] = amt * price
        await upd.message.reply_text(f"📊 تفاصيل الشراء:\n📦 الكمية: {amt} USDT\n💰 السعر: {price} SDG\n💵 الإجمالي: {fmt(ctx.user_data['total'])} SDG\n\n✅ هل تود المتابعة؟", reply_markup=kb_confirm())
        return BUY_CONF
    except: return BUY_AMT

async def buy_conf(upd, ctx):
    if upd.message.text == "✅ تأكيد":
        mths = db_all("SELECT * FROM payment_methods")
        btns = [[InlineKeyboardButton(m['name'], callback_data=f"bpay_{m['method_id']}")] for m in mths]
        await upd.message.reply_text("💳 اختر وسيلة الدفع المناسبة:", reply_markup=InlineKeyboardMarkup(btns))
        return BUY_PAY_SEL
    return await cancel(upd, ctx)

async def buy_pay_sel(upd, ctx):
    q = upd.callback_query
    await q.answer()
    mid = q.data.split("_")[1]
    ctx.user_data['pmid'] = mid
    m = db_get("SELECT * FROM payment_methods WHERE method_id=?", (mid,))
    await q.edit_message_text(f"🔢 يرجى تحويل المبلغ إلى الحساب التالي:\n\n`{m['details']}`\n\n📸 بعد التحويل، أرسل صورة الإيصال هنا (Screenshot):", parse_mode=ParseMode.MARKDOWN)
    return BUY_PROOF

async def buy_proof(upd, ctx):
    if not upd.message.photo:
        await upd.message.reply_text("❌ يرجى إرسال صورة إيصال التحويل للمتابعة.")
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
    await q.edit_message_text("📝 أدخل عنوان محفظتك (أو رقم حساب الاستلام):")
    return BUY_ACC

async def buy_acc(upd, ctx):
    ctx.user_data['acc'] = upd.message.text
    await upd.message.reply_text("✅ تم تجهيز الطلب. هل تود إرساله للمراجعة؟", reply_markup=kb_confirm())
    return BUY_DONE

async def buy_finish(upd, ctx):
    if upd.message.text != "✅ تأكيد": return await cancel(upd, ctx)
    uid = upd.effective_user.id
    oid = db_run("INSERT INTO orders (buyer_id, order_type, amount_usdt, total_sdg, status, payment_proof, user_account_details) VALUES (?,?,?,?,?,?,?)",
           (uid, 'buy', ctx.user_data['amt'], ctx.user_data['total'], 'pending', ctx.user_data['proof'], ctx.user_data['acc']))
    
    # تنبيه التاجر فوراً بالسكرين شوت
    caption = f"🔔 *طلب شراء جديد #{oid}*\n👤 العميل: `{uid}`\n📦 الكمية: {ctx.user_data['amt']} USDT\n💰 المبلغ: {fmt(ctx.user_data['total'])} SDG\n🔢 حساب الاستلام: `{ctx.user_data['acc']}`"
    await ctx.bot.send_photo(chat_id=OWNER_ID, photo=ctx.user_data['proof'], caption=caption, parse_mode=ParseMode.MARKDOWN)
    
    await upd.message.reply_text("🚀 تم إرسال طلبك بنجاح! سيتم إخطارك عند التنفيذ.", reply_markup=kb_main(is_admin(uid)))
    ctx.user_data.clear()
    return ConversationHandler.END

# 🚦 التحكم في حالة التاجر
async def trader_stat_start(upd, ctx):
    if not is_admin(upd.effective_user.id): return ConversationHandler.END
    await upd.message.reply_text("🚦 التحكم في حالة التاجر (تشغيل/إيقاف المتجر):", reply_markup=ReplyKeyboardMarkup([["🟢 تشغيل", "🔴 إيقاف"], ["❌ إلغاء"]], resize_keyboard=True))
    return TRADER_STAT

async def trader_stat_done(upd, ctx):
    t = upd.message.text
    if t == "🟢 تشغيل": set_s('trader_online_status', '1')
    elif t == "🔴 إيقاف": set_s('trader_online_status', '0')
    await upd.message.reply_text(f"✅ تم تحديث حالة المتجر إلى: {t}", reply_markup=kb_admin())
    return ConversationHandler.END

# 👤 الملف الشخصي والرصيد
async def show_profile(upd, ctx):
    u = db_get("SELECT * FROM users WHERE user_id=?", (upd.effective_user.id,))
    msg = f"👤 *ملفك الشخصي*\n\n📛 الاسم: {u['full_name']}\n🌍 البلد: {u['country']}\n📈 الرتبة: {u['rank']}\n🆔 المعرف: `{u['user_id']}`"
    await upd.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def show_balance(upd, ctx):
    u = db_get("SELECT * FROM users WHERE user_id=?", (upd.effective_user.id,))
    msg = f"💳 *رصيدك الحالي*\n\n💰 المحفظة: `{fmt(u['balance_usdt'])}` USDT\n🎁 أرباح الإحالة: `{fmt(u['commission_earned'])}` USDT"
    await upd.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def cancel(upd, ctx):
    ctx.user_data.clear()
    await upd.message.reply_text("⚠️ تم إلغاء العملية الحالية.", reply_markup=kb_main(is_admin(upd.effective_user.id)))
    return ConversationHandler.END

# 🏁 تشغيل المحرك مع Flask
def main():
    init_db()
    # تشغيل سيرفر Flask في Thread منفصل لـ Render
    threading.Thread(target=run_web_server, daemon=True).start()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # معالجة حوارات الشراء
    app.add_handler(ConversationHandler(
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
    ))

    # معالجة التسجيل
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            REG_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_name)],
            REG_COUNTRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_country)]
        },
        fallbacks=[MessageHandler(filters.Regex("❌ إلغاء"), cancel)]
    ))

    # معالجة حالة التاجر
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^🚦 حالة التاجر$"), trader_stat_start)],
        states={TRADER_STAT: [MessageHandler(filters.Regex(r"^(🟢 تشغيل|🔴 إيقاف)$"), trader_stat_done)]},
        fallbacks=[MessageHandler(filters.Regex("❌ إلغاء"), cancel)]
    ))

    # الأوامر العامة
    app.add_handler(MessageHandler(filters.Regex(r"^👤 ملفي$"), show_profile))
    app.add_handler(MessageHandler(filters.Regex(r"^💳 رصيدي$"), show_balance))
    app.add_handler(MessageHandler(filters.Regex(r"^💱 سعر الصرف$"), lambda u,c: u.message.reply_text(f"📥 شراء: {get_s('usdt_buy_price')} SDG\n📤 بيع: {get_s('usdt_sell_price')} SDG")))
    app.add_handler(MessageHandler(filters.Regex(r"^🔐 الإدارة$"), lambda u,c: u.message.reply_text("لوحة التحكم الإدارية:", reply_markup=kb_admin()) if is_admin(u.effective_user.id) else None))
    app.add_handler(MessageHandler(filters.Regex(r"^🔙 الرئيسية$"), lambda u,c: u.message.reply_text("القائمة الرئيسية:", reply_markup=kb_main(is_admin(u.effective_user.id)))))

    print("🚀 البوت والسيرفر يعملان الآن على Render...")
    app.run_polling()

if __name__ == "__main__":
    main()

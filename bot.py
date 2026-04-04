#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════╗
║          بوت تداول USDT P2P على تيليغرام               ║
║          Version 10.0 - STABLE & EXACT FLOW             ║
╚══════════════════════════════════════════════════════════╝
"""

import os
import sqlite3
import logging
import re
from datetime import datetime
from threading import local

# ════════════════════════════════════════════════════════════
#                    🗄️  إعداد قاعدة البيانات
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
BOT_TOKEN       = "8796739637:AAE2KeCf4WOqvxUGl1tqSYUjnx1sXrhMbmI"
OWNER_ID        = 7946243967
DEPOSIT_ADDRESS = "TYourTRC20AddressHere"  # ⚠️ ضع عنوان محفظتك الحقيقي هنا
DB_PATH         = "trading_bot.db"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.FileHandler('bot.log', encoding='utf-8'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════
#                    🔢  حالات المحادثات (مفصولة تماماً)
# ════════════════════════════════════════════════════════════
REG_NAME, REG_COUNTRY = 0, 1

BUY_AMT, BUY_CONF, BUY_SEND_PROOF, BUY_RECV_SEL, BUY_INPUT_ACC, BUY_DONE = 10, 11, 12, 13, 14, 15
SELL_AMT, SELL_CONF, SELL_SEND_PROOF, SELL_RECV_SEL, SELL_INPUT_ACC, SELL_DONE = 20, 21, 22, 23, 24, 25
OFFER_TYPE, OFFER_AMT, OFFER_PRICE, OFFER_CONF = 30, 31, 32, 33

WITHDRAW_AMT, WITHDRAW_ADDR, WITHDRAW_CONF = 40, 41, 42
PREMIUM_AMT, PREMIUM_CONF = 50, 51
SUPPORT_MSG = 60

ADMIN_SET_BUY, ADMIN_SET_SELL, ADMIN_ADD_PAY_N, ADMIN_ADD_PAY_D = 80, 81, 82, 83
ADMIN_ADD_RECV_N, ADMIN_ADD_RECV_D, ADMIN_BROADCAST, ADMIN_REPLY = 84, 85, 86, 87

# ════════════════════════════════════════════════════════════
#                    🗄️  تهيئة قاعدة البيانات
# ════════════════════════════════════════════════════════════
def init_db():
    conn = get_conn()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT DEFAULT '', full_name TEXT NOT NULL,
            country TEXT DEFAULT 'السودان', balance_usdt REAL DEFAULT 0, commission_earned REAL DEFAULT 0,
            rank TEXT DEFAULT 'user', total_trades INTEGER DEFAULT 0, completed_trades INTEGER DEFAULT 0,
            referral_code TEXT UNIQUE, referred_by INTEGER, is_banned INTEGER DEFAULT 0,
            wallet_address TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT, seller_id INTEGER NOT NULL, buyer_id INTEGER,
            order_type TEXT NOT NULL, amount_usdt REAL NOT NULL, price_per_usdt REAL NOT NULL,
            total_sdg REAL NOT NULL, status TEXT DEFAULT 'pending', payment_method_id INTEGER,
            payment_proof TEXT DEFAULT '', receive_method_id INTEGER, user_account_details TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS payment_methods (
            method_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, details TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS receive_methods (
            method_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, details TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS transactions (
            tx_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, tx_type TEXT NOT NULL,
            amount REAL NOT NULL, status TEXT DEFAULT 'pending', notes TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS support_msgs (
            msg_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, message TEXT NOT NULL,
            admin_reply TEXT DEFAULT '', status TEXT DEFAULT 'open', created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT OR IGNORE INTO settings VALUES ('usdt_buy_price', '4000.0');
        INSERT OR IGNORE INTO settings VALUES ('usdt_sell_price', '4100.0');
        INSERT OR IGNORE INTO settings VALUES ('trader_online_status', '1');
        INSERT OR IGNORE INTO settings VALUES ('commission_rate', '3.0');
    ''')
    conn.commit()

# ════════════════════════════════════════════════════════════
#                    🔧 دوال مساعدة
# ════════════════════════════════════════════════════════════
def db_get(q, p=()): return dict(c) if (c:=get_conn().execute(q,p).fetchone()) else None
def db_all(q, p=()): return [dict(r) for r in get_conn().execute(q,p).fetchall()]
def db_run(q, p=()): c=get_conn().execute(q,p); get_conn().commit(); return c.lastrowid

def get_s(k): return (r:=db_get("SELECT value FROM settings WHERE key=?", (k,))) and r['value'] or ''
def set_s(k, v): db_run("INSERT OR REPLACE INTO settings VALUES (?,?)", (k, str(v)))

def get_user(uid): return db_get("SELECT * FROM users WHERE user_id=?", (uid,))
def is_admin(uid): return uid == OWNER_ID
def is_online(): return bool(int(get_s('trader_online_status') or 1))
def fmt(n): return f"{float(n):,.2f}"
def make_ref(): import random, string; return ''.join(random.choices(string.ascii_uppercase+string.digits, k=8))

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

# ════════════════════════════════════════════════════════════
#                    🔐 التحقق والحماية
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
        await msg.reply_text("⛔️ التاجر غير متصل حالياً، لا يمكن استقبال طلبات جديدة.", reply_markup=kb_main(is_admin(uid)))
        return True
    return False

async def cancel(upd, ctx):
    ctx.user_data.clear()
    await upd.message.reply_text("✅ تم الإلغاء", reply_markup=kb_main(is_admin(upd.effective_user.id)))
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════
#                    👋 التسجيل والبداية
# ════════════════════════════════════════════════════════════
async def start_cmd(upd, ctx):
    ctx.user_data.clear()
    uid = upd.effective_user.id
    if not get_user(uid):
        await upd.message.reply_text("👋 أدخل اسمك الكامل للتسجيل:", reply_markup=kb_cancel())
        ctx.user_data['reg_uid'] = uid
        ctx.user_data['reg_uname'] = upd.effective_user.username
        return REG_NAME
    await upd.message.reply_text(f"أهلاً بعودتك!", reply_markup=kb_main(is_admin(uid)))
    return ConversationHandler.END

async def reg_name(upd, ctx):
    t = upd.message.text.strip()
    if t=="❌ إلغاء": return await cancel(upd, ctx)
    ctx.user_data['reg_name'] = t
    await upd.message.reply_text("🌍 أدخل بلدك:", reply_markup=kb_cancel())
    return REG_COUNTRY

async def reg_country(upd, ctx):
    t = upd.message.text.strip()
    if t=="❌ إلغاء": return await cancel(upd, ctx)
    uid, code = ctx.user_data['reg_uid'], make_ref()
    while db_get("SELECT 1 FROM users WHERE referral_code=?", (code,)): code = make_ref()
    db_run("INSERT INTO users (user_id, username, full_name, country, referral_code) VALUES (?,?,?,?,?)",
           (uid, ctx.user_data.get('reg_uname'), ctx.user_data['reg_name'], t, code))
    await upd.message.reply_text("✅ تم التسجيل!", reply_markup=kb_main(is_admin(uid)))
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════
#                    👤 الملف الشخصي والرصيد والسجل
# ════════════════════════════════════════════════════════════
async def show_profile(upd, ctx):
    if await guard(upd, ctx): return ConversationHandler.END
    u = get_user(upd.effective_user.id)
    txt = f"👤 *ملفي*\nالاسم: {u['full_name']}\nالبلد: {u['country']}\nالرصيد: {fmt(u['balance_usdt'])} USDT\nالعمولات: {fmt(u['commission_earned'])}\n🔗 رابط إحالتك: `https://t.me/{ctx.bot.username}?start={u['referral_code']}`"
    await upd.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def show_balance(upd, ctx):
    if await guard(upd, ctx): return ConversationHandler.END
    u = get_user(upd.effective_user.id)
    await upd.message.reply_text(f"💳 *الرصيد*: `{fmt(u['balance_usdt'])}` USDT\n📥 للإيداع: `{DEPOSIT_ADDRESS}`\n📤 للسحب: `/withdraw`", parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def show_orders(upd, ctx):
    if await guard(upd, ctx): return ConversationHandler.END
    uid = upd.effective_user.id
    rows = db_all("SELECT * FROM orders WHERE seller_id=? OR buyer_id=? ORDER BY order_id DESC LIMIT 10", (uid, uid))
    if not rows: return await upd.message.reply_text("📋 لا توجد طلبات حالياً")
    txt = "📋 *طلباتي*\n"
    for r in rows:
        t = "شراء" if r['buyer_id']==uid else "بيع"
        st = {'pending':'⏳','completed':'✅','rejected':'❌','awaiting_payment':'💳','pending_approval':'🔍'}.get(r['status'], r['status'])
        txt += f"#{r['order_id']} | {t} | {fmt(r['amount_usdt'])} USDT | {st}\n"
    await upd.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def show_tx(upd, ctx):
    if await guard(upd, ctx): return ConversationHandler.END
    rows = db_all("SELECT * FROM transactions WHERE user_id=? ORDER BY tx_id DESC LIMIT 15", (upd.effective_user.id,))
    if not rows: return await upd.message.reply_text("📜 لا توجد معاملات بعد")
    txt = "📜 *سجل المعاملات*\n" + "═"*20 + "\n"
    for t in rows:
        txt += f"#{t['tx_id']} | {t['tx_type']} | {fmt(t['amount'])} USDT | {t['status']}\n"
        if t['notes']: txt += f"📝 {t['notes']}\n"
    await upd.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def show_settings(upd, ctx):
    if await guard(upd, ctx): return ConversationHandler.END
    await upd.message.reply_text("⚙️ *الإعدادات*\n📞 الدعم الفني متاح عبر الزر المخصص.\nللتواصل مع الإدارة حول مشكلتك، اضغط 📞 الدعم", parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def show_market(upd, ctx):
    if await guard(upd, ctx): return ConversationHandler.END
    buy, sell = float(get_s('usdt_buy_price')), float(get_s('usdt_sell_price'))
    await upd.message.reply_text(f"📊 *سوق USDT*\n📥 نشتري منك بـ: {fmt(buy)} جنيه\n📤 نبيع لك بـ: {fmt(sell)} جنيه", parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════
#                    🛒 شراء USDT (سير العمل الصحيح)
# ════════════════════════════════════════════════════════════
async def buy_start(upd, ctx):
    if await guard(upd, ctx): return ConversationHandler.END
    if await check_trader(upd): return ConversationHandler.END
    await upd.message.reply_text("🛒 *شراء USDT*\nأدخل الكمية (USDT):", reply_markup=kb_cancel(), parse_mode=ParseMode.MARKDOWN)
    return BUY_AMT

async def buy_amt(upd, ctx):
    t = upd.message.text.strip()
    if t=="❌ إلغاء": return await cancel(upd, ctx)
    try:
        amt = float(t.replace('،', '.'))
        if amt<=0: raise ValueError
    except: return await upd.message.reply_text("❌ أدخل رقماً صحيحاً") or BUY_AMT
    
    price = float(get_s('usdt_sell_price'))
    ctx.user_data.update({'oid': f"BUY-{datetime.now().strftime('%s')}", 'amt': amt, 'price': price, 'total': amt*price})
    await upd.message.reply_text(f"📦 الكمية: {amt} USDT\n💰 الإجمالي: {fmt(amt*price)} SDG\n\n✅ للتأكيد:", reply_markup=kb_confirm())
    return BUY_CONF

async def buy_conf(upd, ctx):
    t = upd.message.text.strip()
    if t=="❌ إلغاء": return await cancel(upd, ctx)
    if t!="✅ تأكيد": await upd.message.reply_text("❌ اختر تأكيد أو إلغاء"); return BUY_CONF
    
    methods = db_all("SELECT * FROM payment_methods")
    if not methods: return await upd.message.reply_text("⚠️ لا توجد طرق دفع مضافة حالياً، راسل الإدارة") or cancel(upd, ctx)
    
    buttons = [[InlineKeyboardButton(m['name'], callback_data=f"pay_sel_{ctx.user_data['oid']}_{m['method_id']}")] for m in methods]
    await upd.message.reply_text("💳 اختر طريقة الدفع التي ستحول عليها:", reply_markup=InlineKeyboardMarkup(buttons))
    return BUY_SEND_PROOF

async def buy_pay_sel(upd, ctx):
    q = upd.callback_query
    await q.answer()
    if not q.data.startswith("pay_sel_"): return ConversationHandler.END
    _, oid, mid = q.data.split("_")
    ctx.user_data['pay_mid'] = int(mid)
    m = db_get("SELECT * FROM payment_methods WHERE method_id=?", (int(mid),))
    await q.edit_message_text(f"💳 *{m['name']}*\n🔢 حول إلى: `{m['details']}`\n📸 أرسل الآن صورة إثبات التحويل:", parse_mode=ParseMode.MARKDOWN)
    return BUY_RECV_SEL

async def buy_proof(upd, ctx):
    if not upd.message.photo: await upd.message.reply_text("❌ أرسل صورة فقط"); return BUY_RECV_SEL
    ctx.user_data['proof'] = upd.message.photo[-1].file_id
    
    methods = db_all("SELECT * FROM receive_methods")
    if not methods: return await upd.message.reply_text("⚠️ لا توجد طرق استلام مضافة، راسل الإدارة") or cancel(upd, ctx)
    
    buttons = [[InlineKeyboardButton(m['name'], callback_data=f"recv_sel_{ctx.user_data['oid']}_{m['method_id']}")] for m in methods]
    await upd.message.reply_text("💵 اختر طريقة استلام أموالك بها:", reply_markup=InlineKeyboardMarkup(buttons))
    return BUY_INPUT_ACC

async def buy_recv_sel(upd, ctx):
    q = upd.callback_query
    await q.answer()
    if not q.data.startswith("recv_sel_"): return ConversationHandler.END
    _, oid, mid = q.data.split("_")
    ctx.user_data['recv_mid'] = int(mid)
    m = db_get("SELECT * FROM receive_methods WHERE method_id=?", (int(mid),))
    await q.edit_message_text(f"💵 *{m['name']}*\n📝 أدخل رقم الحساب/الآيدي الخاص بك لاستلام المبلغ على هذه الطريقة:")
    return BUY_INPUT_ACC

async def buy_input_acc(upd, ctx):
    t = upd.message.text.strip()
    if t=="❌ إلغاء": return await cancel(upd, ctx)
    if not t or len(t)<3: await upd.message.reply_text("❌ أدخل رقم حساب صحيح"); return BUY_INPUT_ACC
    
    ctx.user_data['acc'] = t
    await upd.message.reply_text(f"✅ *تأكيد البيانات*\n💰 المبلغ: {fmt(ctx.user_data['total'])} SDG\n💳 طريقة الدفع: {db_get('SELECT name FROM payment_methods WHERE method_id=?', (ctx.user_data['pay_mid'],))['name']}\n💵 طريقة الاستلام: {db_get('SELECT name FROM receive_methods WHERE method_id=?', (ctx.user_data['recv_mid'],))['name']}\n🔢 حسابك: `{t}`\n\nهل أنت متأكد؟", reply_markup=kb_confirm(), parse_mode=ParseMode.MARKDOWN)
    return BUY_DONE

async def buy_finish(upd, ctx):
    t = upd.message.text.strip()
    if t=="❌ إلغاء": return await cancel(upd, ctx)
    if t!="✅ تأكيد": await upd.message.reply_text("❌ تم الإلغاء"); return BUY_DONE
    
    uid = upd.effective_user.id
    db_run("""INSERT INTO orders (seller_id, buyer_id, order_type, amount_usdt, price_per_usdt, total_sdg, 
              status, payment_method_id, payment_proof, receive_method_id, user_account_details) 
              VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
           (OWNER_ID, uid, 'buy', ctx.user_data['amt'], ctx.user_data['price'], ctx.user_data['total'],
            'pending_approval', ctx.user_data['pay_mid'], ctx.user_data['proof'], ctx.user_data['recv_mid'], ctx.user_data['acc']))
    
    try: await ctx.bot.send_message(OWNER_ID, f"🔔 *طلب شراء جديد*\n🆔: {uid}\n📦: {ctx.user_data['amt']} USDT\n💰: {fmt(ctx.user_data['total'])} SDG\nراجع قسم: 📋 جميع الطلبات", parse_mode=ParseMode.MARKDOWN)
    except: pass
    await upd.message.reply_text("✅ تم إرسال طلبك للمراجعة!", reply_markup=kb_main(is_admin(uid)))
    ctx.user_data.clear()
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════
#                    💰 بيع USDT (سير العمل الصحيح)
# ════════════════════════════════════════════════════════════
async def sell_start(upd, ctx):
    if await guard(upd, ctx): return ConversationHandler.END
    if await check_trader(upd): return ConversationHandler.END
    await upd.message.reply_text("💰 *بيع USDT للتاجر*\nأدخل الكمية (USDT):", reply_markup=kb_cancel(), parse_mode=ParseMode.MARKDOWN)
    return SELL_AMT

async def sell_amt(upd, ctx):
    t = upd.message.text.strip()
    if t=="❌ إلغاء": return await cancel(upd, ctx)
    try:
        amt = float(t.replace('،', '.'))
        if amt<=0: raise ValueError
    except: return await upd.message.reply_text("❌ أدخل رقماً صحيحاً") or SELL_AMT
    ctx.user_data['amt'] = amt
    price = float(get_s('usdt_buy_price'))
    ctx.user_data.update({'price': price, 'total': amt*price, 'oid': f"SELL-{datetime.now().strftime('%s')}"})
    await upd.message.reply_text(f"📦 {amt} USDT | 💰 {fmt(amt*price)} SDG\n✅ للتأكيد:", reply_markup=kb_confirm())
    return SELL_CONF

async def sell_conf(upd, ctx):
    t = upd.message.text.strip()
    if t=="❌ إلغاء": return await cancel(upd, ctx)
    if t!="✅ تأكيد": await upd.message.reply_text("❌ اختر تأكيد أو إلغاء"); return SELL_CONF
    
    await upd.message.reply_text(f"📥 أرسل `USDT` إلى محفظة التاجر:\n`{DEPOSIT_ADDRESS}`\n📸 ثم أرسل صورة إثبات التحويل:", reply_markup=kb_cancel(), parse_mode=ParseMode.MARKDOWN)
    return SELL_RECV_SEL

async def sell_proof(upd, ctx):
    if not upd.message.photo: await upd.message.reply_text("❌ أرسل صورة فقط"); return SELL_RECV_SEL
    ctx.user_data['proof'] = upd.message.photo[-1].file_id
    methods = db_all("SELECT * FROM receive_methods")
    if not methods: return await upd.message.reply_text("⚠️ لا توجد طرق استلام مضافة، راسل الإدارة") or cancel(upd, ctx)
    buttons = [[InlineKeyboardButton(m['name'], callback_data=f"recv_sel_{ctx.user_data['oid']}_{m['method_id']}")] for m in methods]
    await upd.message.reply_text("💵 اختر طريقة استلام أموالك:", reply_markup=InlineKeyboardMarkup(buttons))
    return SELL_INPUT_ACC

async def sell_recv_sel(upd, ctx):
    q = upd.callback_query
    await q.answer()
    if not q.data.startswith("recv_sel_"): return ConversationHandler.END
    _, oid, mid = q.data.split("_")
    ctx.user_data['recv_mid'] = int(mid)
    m = db_get("SELECT * FROM receive_methods WHERE method_id=?", (int(mid),))
    await q.edit_message_text(f"💵 *{m['name']}*\n📝 أدخل رقم حسابك لاستلام المبلغ:")
    return SELL_INPUT_ACC

async def sell_input_acc(upd, ctx):
    t = upd.message.text.strip()
    if t=="❌ إلغاء": return await cancel(upd, ctx)
    ctx.user_data['acc'] = t
    await upd.message.reply_text(f"✅ *تأكيد*\n💵 {fmt(ctx.user_data['total'])} SDG\n💵 طريقة: {db_get('SELECT name FROM receive_methods WHERE method_id=?', (ctx.user_data['recv_mid'],))['name']}\n🔢 حسابك: `{t}`\n✅ للمتابعة:", reply_markup=kb_confirm(), parse_mode=ParseMode.MARKDOWN)
    return SELL_DONE

async def sell_finish(upd, ctx):
    t = upd.message.text.strip()
    if t=="❌ إلغاء": return await cancel(upd, ctx)
    if t!="✅ تأكيد": await upd.message.reply_text("❌ تم الإلغاء"); return SELL_DONE
    
    uid = upd.effective_user.id
    db_run("""INSERT INTO orders (seller_id, buyer_id, order_type, amount_usdt, price_per_usdt, total_sdg, status, 
              payment_proof, receive_method_id, user_account_details) VALUES (?,?,?,?,?,?,?,?,?,?)""",
           (uid, OWNER_ID, 'sell', ctx.user_data['amt'], ctx.user_data['price'], ctx.user_data['total'], 'pending_approval',
            ctx.user_data['proof'], ctx.user_data['recv_mid'], ctx.user_data['acc']))
    try: await ctx.bot.send_message(OWNER_ID, f"🔔 *طلب بيع جديد*\n👤: {uid}\n📦: {ctx.user_data['amt']} USDT\nراجع: 📋 جميع الطلبات", parse_mode=ParseMode.MARKDOWN)
    except: pass
    await upd.message.reply_text("✅ تم استلام طلبك!", reply_markup=kb_main(is_admin(uid)))
    ctx.user_data.clear()
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════
#                    💵 تقديم عرض
# ════════════════════════════════════════════════════════════
async def offer_start(upd, ctx):
    if await guard(upd, ctx): return ConversationHandler.END
    if await check_trader(upd): return ConversationHandler.END
    await upd.message.reply_text("💵 *تقديم عرض*\nاختر النوع:", reply_markup=kb_offer())
    return OFFER_TYPE

async def offer_type(upd, ctx):
    t = upd.message.text.strip()
    if t=="❌ إلغاء": return await cancel(upd, ctx)
    if t not in ["شــراء","بــيــع"]: return await upd.message.reply_text("❌ اختر من الأزرار") or OFFER_TYPE
    ctx.user_data['otype'] = t
    await upd.message.reply_text("📩 أدخل الكمية (USDT):", reply_markup=kb_cancel())
    return OFFER_AMT

async def offer_amt(upd, ctx):
    t = upd.message.text.strip()
    if t=="❌ إلغاء": return await cancel(upd, ctx)
    try:
        amt=float(t.replace('،','.')); 
        if amt<=0: raise ValueError
    except: return await upd.message.reply_text("❌ رقم صحيح") or OFFER_AMT
    ctx.user_data['amt']=amt
    await upd.message.reply_text("📩 أدخل السعر (جنيه/USDT):", reply_markup=kb_cancel())
    return OFFER_PRICE

async def offer_price(upd, ctx):
    t = upd.message.text.strip()
    if t=="❌ إلغاء": return await cancel(upd, ctx)
    try:
        p=float(t.replace('،','.')); 
        if p<=0: raise ValueError
    except: return await upd.message.reply_text("❌ سعر صحيح") or OFFER_PRICE
    ctx.user_data['price']=p
    await upd.message.reply_text(f"📋 *ملخص العرض*\n🔸 {ctx.user_data['otype']} | {fmt(ctx.user_data['amt'])} USDT\n💰 السعر: {fmt(p)}\n✅ للتأكيد:", reply_markup=kb_confirm(), parse_mode=ParseMode.MARKDOWN)
    return OFFER_CONF

async def offer_conf(upd, ctx):
    t = upd.message.text.strip()
    if t=="❌ إلغاء": return await cancel(upd, ctx)
    if t!="✅ تأكيد": return await upd.message.reply_text("❌ تم الإلغاء") or cancel(upd, ctx)
    
    uid=upd.effective_user.id
    typ='offer_buy' if ctx.user_data['otype']=='شــراء' else 'offer_sell'
    s=uid if typ=='offer_sell' else OWNER_ID
    b=OWNER_ID if typ=='offer_sell' else uid
    db_run("INSERT INTO orders (seller_id,buyer_id,order_type,amount_usdt,price_per_usdt,total_sdg,status) VALUES (?,?,?,?,?,?,?)",
           (s,b,typ,ctx.user_data['amt'],ctx.user_data['price'],ctx.user_data['amt']*ctx.user_data['price'],'pending_offer'))
    try: await ctx.bot.send_message(OWNER_ID, f"🔔 عرض جديد! رقم #{db_get('SELECT MAX(order_id) FROM orders')['MAX(order_id)']} راجع 📋 جميع الطلبات")
    except: pass
    await upd.message.reply_text("✅ تم إرسال عرضك!", reply_markup=kb_main(is_admin(uid)))
    ctx.user_data.clear()
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════
#                    📤 سحب + 🌟 مميز + 📞 دعم
# ════════════════════════════════════════════════════════════
async def withdraw_start(upd, ctx):
    if await guard(upd, ctx): return ConversationHandler.END
    u=get_user(upd.effective_user.id)
    if u['balance_usdt']<=0: return await upd.message.reply_text("❌ رصيدك فارغ") or ConversationHandler.END
    await upd.message.reply_text(f"📤 *سحب*\nرصيدك: {fmt(u['balance_usdt'])} USDT\nأدخل الكمية:", reply_markup=kb_cancel(), parse_mode=ParseMode.MARKDOWN)
    return WITHDRAW_AMT

async def withdraw_amt(upd, ctx):
    t=upd.message.text.strip()
    if t=="❌ إلغاء": return await cancel(upd, ctx)
    try:
        a=float(t.replace('،','.')); u=get_user(upd.effective_user.id)
        if a<=0 or a>u['balance_usdt']: raise ValueError
    except: return await upd.message.reply_text("❌ كمية خاطئة") or WITHDRAW_AMT
    ctx.user_data['amt']=a
    await upd.message.reply_text("📩 أدخل عنوان محفظة TRC20:", reply_markup=kb_cancel())
    return WITHDRAW_ADDR

async def withdraw_addr(upd, ctx):
    t=upd.message.text.strip()
    if t=="❌ إلغاء": return await cancel(upd, ctx)
    if len(t)<30: return await upd.message.reply_text("❌ عنوان TRC20 غير صحيح") or WITHDRAW_ADDR
    ctx.user_data['addr']=t
    await upd.message.reply_text(f"📤 تأكيد السحب: {fmt(ctx.user_data['amt'])} USDT إلى `{t}`\n✅ للمتابعة:", reply_markup=kb_confirm(), parse_mode=ParseMode.MARKDOWN)
    return WITHDRAW_CONF

async def withdraw_conf(upd, ctx):
    t=upd.message.text.strip()
    if t=="❌ إلغاء": return await cancel(upd, ctx)
    if t!="✅ تأكيد": return await upd.message.reply_text("❌ تم الإلغاء") or cancel(upd, ctx)
    uid=upd.effective_user.id; a=ctx.user_data['amt']; addr=ctx.user_data['addr']
    db_run("UPDATE users SET balance_usdt=balance_usdt-? WHERE user_id=?",(a,uid))
    db_run("INSERT INTO transactions (user_id,tx_type,amount,status,notes) VALUES (?,?,?,?,?)",(uid,'withdraw',a,'pending',f"إلى: {addr}"))
    try: await ctx.bot.send_message(OWNER_ID, f"🔔 سحب جديد!\n👤 {uid} | 📦 {a} USDT | 🏧 {addr}")
    except: pass
    await upd.message.reply_text("✅ تم إرسال طلب السحب!", reply_markup=kb_main(is_admin(uid)))
    ctx.user_data.clear(); return ConversationHandler.END

async def premium_cmd(upd, ctx):
    if await guard(upd, ctx): return ConversationHandler.END
    if await check_trader(upd): return ConversationHandler.END
    p=float(get_s('usdt_sell_price')); await upd.message.reply_text(f"🌟 *تليجرام مميز*\nالسعر: {fmt(p)} USDT\nأدخل الكمية:", reply_markup=kb_cancel(), parse_mode=ParseMode.MARKDOWN)
    return PREMIUM_AMT
async def premium_amt(upd, ctx):
    t=upd.message.text.strip()
    if t=="❌ إلغاء": return await cancel(upd, ctx)
    try: q=int(t); u=get_user(upd.effective_user.id); p=float(get_s('usdt_sell_price'))
    if q<=0 or q*p>u['balance_usdt']: raise ValueError
    except: return await upd.message.reply_text("❌ كمية أو رصيد غير كافٍ") or PREMIUM_AMT
    ctx.user_data['qty']=q; ctx.user_data['total']=q*p
    await upd.message.reply_text(f"🌟 تأكيد شراء {q} اشتراك بـ {fmt(q*p)} USDT\n✅ للمتابعة:", reply_markup=kb_confirm(), parse_mode=ParseMode.MARKDOWN)
    return PREMIUM_CONF
async def premium_conf(upd, ctx):
    t=upd.message.text.strip()
    if t=="❌ إلغاء": return await cancel(upd, ctx)
    if t!="✅ تأكيد": return await upd.message.reply_text("❌ تم الإلغاء") or cancel(upd, ctx)
    uid=upd.effective_user.id; db_run("UPDATE users SET balance_usdt=balance_usdt-? WHERE user_id=?",(ctx.user_data['total'],uid))
    db_run("INSERT INTO transactions (user_id,tx_type,amount,status) VALUES (?,?,?,?)",(uid,'premium',ctx.user_data['total'],'completed'))
    await upd.message.reply_text(f"✅ تم شراء {ctx.user_data['qty']} اشتراك!", reply_markup=kb_main(is_admin(uid))); ctx.user_data.clear()
    return ConversationHandler.END

async def support_cmd(upd, ctx):
    if await guard(upd, ctx): return ConversationHandler.END
    await upd.message.reply_text("📞 *الدعم الفني*\nاكتب مشكلتك وسنرد قريباً:", reply_markup=kb_cancel(), parse_mode=ParseMode.MARKDOWN)
    return SUPPORT_MSG
async def support_msg(upd, ctx):
    t=upd.message.text.strip()
    if t=="❌ إلغاء": return await cancel(upd, ctx)
    uid=upd.effective_user.id; db_run("INSERT INTO support_msgs (user_id,message) VALUES (?,?)",(uid,t))
    try: await ctx.bot.send_message(OWNER_ID, f"📩 دعم جديد من {uid}:\n{t}")
    except: pass
    await upd.message.reply_text("✅ تم الإرسال", reply_markup=kb_main(is_admin(uid))); return ConversationHandler.END

# ════════════════════════════════════════════════════════════
#                    🔐 لوحة الإدارة
# ════════════════════════════════════════════════════════════
async def admin_panel(upd, ctx):
    if not is_admin(upd.effective_user.id): return ConversationHandler.END
    await upd.message.reply_text("🔐 *لوحة الإدارة*", reply_markup=kb_admin(), parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def admin_orders(upd, ctx):
    if not is_admin(upd.effective_user.id): return ConversationHandler.END
    rows = db_all("SELECT * FROM orders WHERE status IN ('pending_offer','pending_approval') ORDER BY order_id")
    if not rows: return await upd.message.reply_text("📋 لا توجد طلبات قيد المراجعة", reply_markup=kb_admin())
    
    for r in rows:
        uid = r['buyer_id'] if r['order_type'] in ['buy','offer_buy'] else r['seller_id']
        u = get_user(uid)
        t = {'buy':'🛒 شراء','sell':'💰 بيع','offer_buy':'💵 عرض شراء','offer_sell':'💵 عرض بيع'}.get(r['order_type'], r['order_type'])
        txt = f"🔖 *#{r['order_id']}*\n👤 {u['full_name'] if u else uid}\n🔸 {t}\n📦 {fmt(r['amount_usdt'])} USDT\n💰 {fmt(r['total_sdg'])} SDG\n📶 {r['status']}"
        if r['user_account_details']: txt += f"\n🔢 حساب المستخدم: `{r['user_account_details']}`"
        
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ قبول", callback_data=f"adm_acc_{r['order_id']}")],
            [InlineKeyboardButton("❌ رفض", callback_data=f"adm_rej_{r['order_id']}")]
        ])
        try:
            if r['payment_proof']: await upd.message.reply_photo(r['payment_proof'], caption=txt, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
            else: await upd.message.reply_text(txt, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        except: pass
    return ConversationHandler.END

async def admin_action(upd, ctx):
    q = upd.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return ConversationHandler.END
    data = q.data.split("_")
    if len(data)<3: return ConversationHandler.END
    act, oid = data[1], int(data[2])
    order = db_get("SELECT * FROM orders WHERE order_id=?", (oid,))
    if not order: return await q.edit_message_text("❌ الطلب غير موجود")
    
    uid = order['buyer_id'] if order['order_type'] in ['buy','offer_buy'] else order['seller_id']
    
    if act=="rej":
        db_run("UPDATE orders SET status='rejected' WHERE order_id=?",(oid,))
        try: await q.edit_message_text(q.message.text + "\n\n❌ تم رفض الطلب")
        except: pass
        try: await ctx.bot.send_message(uid, f"❌ تم رفض طلبك #{oid}")
        except: pass
        
    elif act=="acc":
        if order['status']=='pending_offer':
            db_run("UPDATE orders SET status='awaiting_payment' WHERE order_id=?",(oid,))
            try: await q.edit_message_text(q.message.text + "\n\n✅ تم قبول العرض. انتظر إشعار الدفع.")
            except: pass
            try: await ctx.bot.send_message(uid, f"✅ تم قبول عرضك #{oid}. يرجى بدء عملية الشراء/البيع لدفع التفاصيل.")
            except: pass
        else:
            # إتمام الطلب النهائي
            db_run("UPDATE orders SET status='completed' WHERE order_id=?",(oid,))
            try: await q.edit_message_text(q.message.text + "\n\n✅ تم إتمام الطلب بنجاح")
            except: pass
            try: await ctx.bot.send_message(uid, f"✅ تم إتمام طلبك #{oid} بنجاح!")
            except: pass
            # تسجيل المعاملة إذا لزم
            db_run("INSERT INTO transactions (user_id,tx_type,amount,status) VALUES (?,?,?,?)",(uid,'trade_complete',order['amount_usdt'],'completed'))
    return ConversationHandler.END

# --- إعدادات الإدارة ---
async def admin_set_val(upd, ctx, key, label):
    t=upd.message.text.strip()
    if t=="❌ إلغاء": return await cancel(upd, ctx)
    try: v=float(t.replace('،','.')); set_s(key,v); await upd.message.reply_text(f"✅ تم تحديث {label} إلى {fmt(v)}", reply_markup=kb_admin()); return ConversationHandler.END
    except: return await upd.message.reply_text("❌ أدخل رقماً صحيحاً") or None

async def admin_add_method(upd, ctx, table, label):
    t=upd.message.text.strip()
    if t=="❌ إلغاء": return await cancel(upd, ctx)
    if 'name' not in ctx.user_data: ctx.user_data['name']=t; await upd.message.reply_text(f"📋 أدخل تفاصيل {label}:", reply_markup=kb_cancel()); return ctx.user_data.get('state')
    db_run(f"INSERT INTO {table} (name,details) VALUES (?,?)",(ctx.user_data['name'], t))
    await upd.message.reply_text(f"✅ تمت إضافة {label}", reply_markup=kb_admin()); ctx.user_data.clear(); return ConversationHandler.END

# دوال مختصرة للأزرار
async def adm_buy_price(upd,ctx): return await upd.message.reply_text("💲 أدخل سعر الشراء الجديد:", reply_markup=kb_cancel()) or ADMIN_SET_BUY
async def adm_sell_price(upd,ctx): return await upd.message.reply_text("💲 أدخل سعر البيع الجديد:", reply_markup=kb_cancel()) or ADMIN_SET_SELL
async def adm_add_pay(upd,ctx): ctx.user_data['state']=ADMIN_ADD_PAY_N; return await upd.message.reply_text("💳 أدخل اسم طريقة الدفع:", reply_markup=kb_cancel())
async def adm_add_recv(upd,ctx): ctx.user_data['state']=ADMIN_ADD_RECV_N; return await upd.message.reply_text("💵 أدخل اسم طريقة الاستلام:", reply_markup=kb_cancel())
async def adm_trader_status(upd,ctx):
    s = "🟢 متصل" if is_online() else "🔴 غير متصل"
    kb = ReplyKeyboardMarkup([["🟢 تشغيل","🔴 إيقاف"],["❌ إلغاء"]], resize_keyboard=True)
    await upd.message.reply_text(f"🚦 حالة التاجر: {s}", reply_markup=kb); return 999

# ════════════════════════════════════════════════════════════
#                    🚀 التطبيق الرئيسي
# ════════════════════════════════════════════════════════════
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    c_filter = filters.Regex(r"^(❌ إلغاء|🔙 الرئيسية|/cancel)$")
    
    # 1. تسجيل
    app.add_handler(ConversationHandler(entry_points=[CommandHandler("start", start_cmd)], states={REG_NAME:[MessageHandler(filters.TEXT&~filters.COMMAND, reg_name)], REG_COUNTRY:[MessageHandler(filters.TEXT&~filters.COMMAND, reg_country)]}, fallbacks=[MessageHandler(c_filter, cancel)]))
    
    # 2. شراء
    app.add_handler(ConversationHandler(entry_points=[MessageHandler(filters.Regex(r"^🛒 شراء USDT$"), buy_start)], 
        states={BUY_AMT:[MessageHandler(filters.TEXT&~filters.COMMAND, buy_amt)], BUY_CONF:[MessageHandler(filters.TEXT&~filters.COMMAND, buy_conf)], 
                BUY_SEND_PROOF:[CallbackQueryHandler(buy_pay_sel, pattern=r"^pay_sel_")], 
                BUY_RECV_SEL:[MessageHandler(filters.PHOTO, buy_proof), CallbackQueryHandler(buy_recv_sel, pattern=r"^recv_sel_")], 
                BUY_INPUT_ACC:[MessageHandler(filters.TEXT&~filters.COMMAND, buy_input_acc)], 
                BUY_DONE:[MessageHandler(filters.TEXT&~filters.COMMAND, buy_finish)]}, fallbacks=[MessageHandler(c_filter, cancel)]))
    
    # 3. بيع
    app.add_handler(ConversationHandler(entry_points=[MessageHandler(filters.Regex(r"^💰 بيع USDT$"), sell_start)], 
        states={SELL_AMT:[MessageHandler(filters.TEXT&~filters.COMMAND, sell_amt)], SELL_CONF:[MessageHandler(filters.TEXT&~filters.COMMAND, sell_conf)],
                SELL_RECV_SEL:[MessageHandler(filters.PHOTO, sell_proof), CallbackQueryHandler(sell_recv_sel, pattern=r"^recv_sel_")],
                SELL_INPUT_ACC:[MessageHandler(filters.TEXT&~filters.COMMAND, sell_input_acc)],
                SELL_DONE:[MessageHandler(filters.TEXT&~filters.COMMAND, sell_finish)]}, fallbacks=[MessageHandler(c_filter, cancel)]))
                
    # 4. عرض
    app.add_handler(ConversationHandler(entry_points=[MessageHandler(filters.Regex(r"^💵 تقديم عرض$"), offer_start)],
        states={OFFER_TYPE:[MessageHandler(filters.TEXT&~filters.COMMAND, offer_type)], OFFER_AMT:[MessageHandler(filters.TEXT&~filters.COMMAND, offer_amt)],
                OFFER_PRICE:[MessageHandler(filters.TEXT&~filters.COMMAND, offer_price)], OFFER_CONF:[MessageHandler(filters.TEXT&~filters.COMMAND, offer_conf)]}, fallbacks=[MessageHandler(c_filter, cancel)]))
                
    # 5. سحب / مميز / دعم
    app.add_handler(ConversationHandler(entry_points=[CommandHandler("withdraw", withdraw_start)], states={WITHDRAW_AMT:[MessageHandler(filters.TEXT&~filters.COMMAND, withdraw_amt)], WITHDRAW_ADDR:[MessageHandler(filters.TEXT&~filters.COMMAND, withdraw_addr)], WITHDRAW_CONF:[MessageHandler(filters.TEXT&~filters.COMMAND, withdraw_conf)]}, fallbacks=[MessageHandler(c_filter, cancel)]))
    app.add_handler(ConversationHandler(entry_points=[MessageHandler(filters.Regex(r"^🌟 تليجرام مميز$"), premium_cmd)], states={PREMIUM_AMT:[MessageHandler(filters.TEXT&~filters.COMMAND, premium_amt)], PREMIUM_CONF:[MessageHandler(filters.TEXT&~filters.COMMAND, premium_conf)]}, fallbacks=[MessageHandler(c_filter, cancel)]))
    app.add_handler(ConversationHandler(entry_points=[MessageHandler(filters.Regex(r"^📞 الدعم$"), support_cmd)], states={SUPPORT_MSG:[MessageHandler(filters.TEXT&~filters.COMMAND, support_msg)]}, fallbacks=[MessageHandler(c_filter, cancel)]))
    
    # 6. إدارة
    app.add_handler(ConversationHandler(entry_points=[MessageHandler(filters.Regex(r"^🔐 الإدارة$"), admin_panel)], states={}, fallbacks=[]))
    app.add_handler(ConversationHandler(entry_points=[MessageHandler(filters.Regex(r"^📋 جميع الطلبات$"), admin_orders)], states={}, fallbacks=[]))
    app.add_handler(CallbackQueryHandler(admin_action, pattern=r"^adm_(acc|rej)_\d+$"))
    
    app.add_handler(ConversationHandler(entry_points=[MessageHandler(filters.Regex(r"^💲 تعديل سعر الشراء$"), adm_buy_price)], states={ADMIN_SET_BUY:[MessageHandler(filters.TEXT&~filters.COMMAND, lambda u,c: admin_set_val(u,c,'usdt_buy_price','سعر الشراء'))]}, fallbacks=[MessageHandler(c_filter, cancel)]))
    app.add_handler(ConversationHandler(entry_points=[MessageHandler(filters.Regex(r"^💲 تعديل سعر البيع$"), adm_sell_price)], states={ADMIN_SET_SELL:[MessageHandler(filters.TEXT&~filters.COMMAND, lambda u,c: admin_set_val(u,c,'usdt_sell_price','سعر البيع'))]}, fallbacks=[MessageHandler(c_filter, cancel)]))
    
    app.add_handler(ConversationHandler(entry_points=[MessageHandler(filters.Regex(r"^💳 إضافة طريقة دفع$"), adm_add_pay)], states={ADMIN_ADD_PAY_N:[MessageHandler(filters.TEXT&~filters.COMMAND, lambda u,c: admin_add_method(u,c,'payment_methods','الدفع'))], ADMIN_ADD_PAY_D:[MessageHandler(filters.TEXT&~filters.COMMAND, lambda u,c: admin_add_method(u,c,'payment_methods','الدفع'))]}, fallbacks=[MessageHandler(c_filter, cancel)]))
    app.add_handler(ConversationHandler(entry_points=[MessageHandler(filters.Regex(r"^💵 إضافة طريقة استلام$"), adm_add_recv)], states={ADMIN_ADD_RECV_N:[MessageHandler(filters.TEXT&~filters.COMMAND, lambda u,c: admin_add_method(u,c,'receive_methods','الاستلام'))], ADMIN_ADD_RECV_D:[MessageHandler(filters.TEXT&~filters.COMMAND, lambda u,c: admin_add_method(u,c,'receive_methods','الاستلام'))]}, fallbacks=[MessageHandler(c_filter, cancel)]))
    
    async def trader_toggle(u,c):
        t=u.message.text.strip()
        if t=="❌ إلغاء": return await cancel(u,c)
        set_s('trader_online_status', '1' if t=="🟢 تشغيل" else '0')
        await u.message.reply_text(f"✅ تم التحديث. التاجر {'متصل' if t=='🟢 تشغيل' else 'غير متصل'}", reply_markup=kb_admin())
        return ConversationHandler.END
    app.add_handler(ConversationHandler(entry_points=[MessageHandler(filters.Regex(r"^🚦 حالة التاجر$"), adm_trader_status)], states={999:[MessageHandler(filters.TEXT&~filters.COMMAND, trader_toggle)]}, fallbacks=[MessageHandler(c_filter, cancel)]))

    # أزرار عامة
    app.add_handler(MessageHandler(c_filter, cancel))
    app.add_handler(MessageHandler(filters.Regex(r"^👤 ملفي$|^🔗 الإحالة$"), show_profile))
    app.add_handler(MessageHandler(filters.Regex(r"^💳 رصيدي$"), show_balance))
    app.add_handler(MessageHandler(filters.Regex(r"^📋 طلباتي$"), show_orders))
    app.add_handler(MessageHandler(filters.Regex(r"^📜 سجل المعاملات$"), show_tx))
    app.add_handler(MessageHandler(filters.Regex(r"^⚙️ الإعدادات$"), show_settings))
    app.add_handler(MessageHandler(filters.Regex(r"^📊 السوق$"), show_market))
    
    logger.info("🚀 البوت يعمل - Version 10.0")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

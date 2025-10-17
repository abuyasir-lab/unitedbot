import logging
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeExpiredError, PhoneCodeInvalidError
from telethon.tl.functions.channels import CreateChannelRequest
import aiosqlite
import signal
import sys
import os
import random

GROUP_NAMES = [
    ("Vision 2030 Forum", "Discuss national development goals"),
    ("Shura Circle", "Explore legislative advisory topics"),
    ("Legal Insights", "Understand Sharia and legal systems"),
    ("Women Empowerment SA", "Discuss progress in women's rights"),
    ("Youth Voices KSA", "Engage young Saudis on policy ideas"),
    ("Economic Diversification", "Talk new industries beyond oil"),
    ("Green Arabia", "Explore sustainability and environment"),
    ("Cultural Heritage SA", "Celebrate Saudi traditions"),
    ("Digital Government", "Analyze e-government services"),
    ("Education Reformers", "Discuss changes in schooling"),
    ("Employment Hub", "Connect on Saudization and jobs"),
    ("Public Safety Forum", "Exchange views on security"),
    ("Municipality Connect", "Talk urban planning and services"),
    ("Healthcare Futures", "Discuss medical reforms"),
    ("Foreign Affairs Club", "Explore diplomatic relations"),
    ("Religious Studies Forum", "Discuss Islamic scholarship"),
    ("Legal Rights Lounge", "Raise awareness of civil rights"),
    ("Infrastructure Watch", "Track mega projects"),
    ("Tourism Talks", "Share experiences and insights"),
    ("Women in Leadership", "Support women in governance"),
    ("Civic Engagement KSA", "Promote participation in society"),
    ("Oil & Energy Forum", "Discuss economic implications"),
    ("Tech & AI Policy", "Explore innovation governance"),
    ("Ministry Spotlights", "Discuss functions of ministries"),
    ("Anti-Corruption Watch", "Talk integrity and reforms"),
    ("National Identity", "Explore symbols and heritage"),
    ("Local Councils Forum", "Engage with municipal governance"),
    ("Data Governance KSA", "Understand digital regulation"),
    ("Security & Defense", "Explore strategic affairs"),
    ("Judiciary Conversations", "Discuss legal interpretations"),
    ("Social Development", "Exchange views on reforms"),
    ("Media & Messaging", "Analyze government communication"),
    ("Tax & Finance Talk", "Explore financial policy"),
    ("Startup Governance", "Support innovation under regulation"),
    ("Policy Debates", "Discuss recent decisions"),
    ("Smart Cities SA", "Talk about urban technology"),
    ("Transport & Mobility", "Exchange on infrastructure plans"),
    ("Cultural Diplomacy", "Talk global outreach"),
    ("Public Policy Circle", "Discuss reform and planning"),
    ("Volunteer Nation", "Promote civic action"),
    ("Hajj & Umrah Desk", "Talk pilgrimage logistics"),
    ("Foreign Investment Club", "Explore FDI in Saudi Arabia"),
    ("Rights & Reforms", "Understand policy transitions"),
    ("Entrepreneurs Network", "Support government-backed ventures"),
    ("Women & Family Affairs", "Exchange on social policies"),
    ("Public Sector Innovators", "Boost government services"),
    ("KSA Think Tank", "Tackle public challenges"),
    ("National Dialogue Group", "Promote unity and debate"),
    ("Law & Order Watch", "Discuss crime and justice"),
    ("Regulatory Sandbox", "Test ideas under policy frameworks"),
    ("Future of Governance", "Speculate and imagine new models")
]

# Log yozish
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot_operations.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Sozlamalar
TOKEN = "7195938664:AAF37G5TFQ8dy9rsn6ejVU7dPfge01VBDCk"
API_ID = 12390185
API_HASH = "d5c37708982fc1c231d41200e5577562"

# Cheklovlar
MAX_GROUPS_PER_ACCOUNT_DAILY = 50
AUTO_CREATE_INTERVAL = 5  # daqiqa

# Holatlar
PHONE, CODE, PASSWORD, AUTO_SETTING, GROUP_SETTINGS = range(5)

# Ma'lumotlar bazasi
DB_NAME = "telegram_bot.db"


class MukammalBotBoshqaruvchi:
    def __init__(self, db_name: str):
        self.db_name = db_name

    async def bazani_boshlash(self):
        """Ma'lumotlar bazasini yaratish"""
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone TEXT UNIQUE,
                    session_string TEXT,
                    status TEXT DEFAULT 'faol',
                    avtomatik_guruh BOOLEAN DEFAULT 0,
                    guruh_nomi TEXT DEFAULT 'MeningGuruhim',
                    kunlik_guruhlar INTEGER DEFAULT 0,
                    oxirgi_guruh_yaratilgan TIMESTAMP,
                    yaratilgan TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            await db.execute('''
                CREATE TABLE IF NOT EXISTS group_creation (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER,
                    group_name TEXT,
                    status TEXT DEFAULT 'kutilyapti',
                    yaratilgan TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    boshlangan TIMESTAMP,
                    tugatilgan TIMESTAMP,
                    xatolik TEXT,
                    FOREIGN KEY (account_id) REFERENCES accounts (id)
                )
            ''')

            await db.execute('''
                CREATE TABLE IF NOT EXISTS daily_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER,
                    sana DATE DEFAULT CURRENT_DATE,
                    guruhlar_soni INTEGER DEFAULT 0,
                    FOREIGN KEY (account_id) REFERENCES accounts (id),
                    UNIQUE(account_id, sana)
                )
            ''')

            await db.execute('CREATE INDEX IF NOT EXISTS idx_account_status ON accounts(status)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_avtomatik_guruh ON accounts(avtomatik_guruh)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_group_status ON group_creation(status)')

            await db.commit()

    async def yangi_akkaunt_qoshish(self, phone: str, session_string: str, avtomatik_guruh: bool = False):
        """Yangi akkaunt qo'shish"""
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                """INSERT OR REPLACE INTO accounts 
                (phone, session_string, status, avtomatik_guruh) 
                VALUES (?, ?, 'faol', ?)""",
                (phone, session_string, 1 if avtomatik_guruh else 0)
            )
            await db.commit()

    async def akkauntni_olish(self, phone: str):
        """Akkauntni olish"""
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute(
                "SELECT * FROM accounts WHERE phone = ? AND status = 'faol'",
                (phone,)
            )
            row = await cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None

    async def barcha_akkauntlarni_olish(self):
        """Barcha faol akkauntlarni olish"""
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute(
                "SELECT * FROM accounts WHERE status = 'faol' ORDER BY oxirgi_guruh_yaratilgan ASC"
            )
            rows = await cursor.fetchall()
            if rows:
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
            return []

    async def avtomatik_akkauntlarni_olish(self):
        """Avtomatik guruh yaratadigan akkauntlarni olish"""
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute(
                "SELECT * FROM accounts WHERE status = 'faol' AND avtomatik_guruh = 1"
            )
            rows = await cursor.fetchall()
            if rows:
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
            return []

    async def kunlik_cheklovni_tekshirish(self, account_id: int):
        """Kunlik cheklovni tekshirish"""
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute('''
                SELECT COALESCE(SUM(guruhlar_soni), 0) as bugungi_guruhlar
                FROM daily_stats 
                WHERE account_id = ? AND sana = DATE('now')
            ''', (account_id,))
            result = await cursor.fetchone()
            return result[0] if result else 0

    async def kunlik_statistikani_yangilash(self, account_id: int):
        """Kunlik statistikani yangilash"""
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute('''
                INSERT INTO daily_stats (account_id, guruhlar_soni)
                VALUES (?, 1)
                ON CONFLICT(account_id, sana) 
                DO UPDATE SET guruhlar_soni = guruhlar_soni + 1
            ''', (account_id,))
            await db.commit()

    async def guruh_navbatiga_qoshish(self, account_id: int, group_name: str):
        """Guruhni navbatga qo'shish"""
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "INSERT INTO group_creation (account_id, group_name) VALUES (?, ?)",
                (account_id, group_name)
            )
            await db.commit()

    async def kutayotgan_guruhlarni_olish(self, limit: int = 20):
        """Kutayotgan guruhlarni olish"""
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute('''
                SELECT gc.*, a.phone, a.session_string
                FROM group_creation gc
                JOIN accounts a ON gc.account_id = a.id
                WHERE gc.status = 'kutilyapti'
                AND a.status = 'faol'
                ORDER BY gc.yaratilgan ASC
                LIMIT ?
            ''', (limit,))
            rows = await cursor.fetchall()
            if rows:
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
            return []

    async def guruh_holatini_yangilash(self, guruh_id: int, status: str, xatolik: str = None):
        """Guruh holatini yangilash"""
        async with aiosqlite.connect(self.db_name) as db:
            if status == 'boshlandi':
                await db.execute(
                    "UPDATE group_creation SET status = ?, boshlangan = CURRENT_TIMESTAMP WHERE id = ?",
                    (status, guruh_id)
                )
            elif status == 'tugadi':
                await db.execute(
                    "UPDATE group_creation SET status = ?, tugatilgan = CURRENT_TIMESTAMP WHERE id = ?",
                    (status, guruh_id)
                )
            elif status == 'xato':
                await db.execute(
                    "UPDATE group_creation SET status = ?, tugatilgan = CURRENT_TIMESTAMP, xatolik = ? WHERE id = ?",
                    (status, xatolik, guruh_id)
                )
            await db.commit()

    async def akkauntni_yangilash(self, account_id: int):
        """Akkauntni yangilash"""
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "UPDATE accounts SET oxirgi_guruh_yaratilgan = CURRENT_TIMESTAMP WHERE id = ?",
                (account_id,)
            )
            await db.commit()

    async def avtomatik_guruh_sozlamasini_yangilash(self, account_id: int, avtomatik: bool, guruh_nomi: str = None):
        """Avtomatik guruh sozlamasini yangilash"""
        async with aiosqlite.connect(self.db_name) as db:
            if guruh_nomi:
                await db.execute(
                    "UPDATE accounts SET avtomatik_guruh = ?, guruh_nomi = ? WHERE id = ?",
                    (1 if avtomatik else 0, guruh_nomi, account_id)
                )
            else:
                await db.execute(
                    "UPDATE accounts SET avtomatik_guruh = ? WHERE id = ?",
                    (1 if avtomatik else 0, account_id)
                )
            await db.commit()


# Ma'lumotlar bazasini ishga tushirish
db_manager = MukammalBotBoshqaruvchi(DB_NAME)

# Botni yaratish
bot = (
    Application.builder()
    .token(TOKEN)
    .concurrent_updates(True)
    .build()
)


# Inline klaviaturalar
def asosiy_menu():
    """Asosiy menu"""
    keyboard = [
        [InlineKeyboardButton("➕ Add account", callback_data="add_account")],
        [InlineKeyboardButton("📊 Account management", callback_data="manage_accounts")],
        [InlineKeyboardButton("📈 Statistics", callback_data="stats")],
        [InlineKeyboardButton("⚙️ Automatic settings", callback_data="auto_settings")]
    ]
    return InlineKeyboardMarkup(keyboard)


def orqaga_tugmasi():
    """Orqaga tugmasi"""
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="main_menu")]])


def kod_klaviaturasi():
    """Kod kiritish uchun klaviatura"""
    keyboard = [
        [InlineKeyboardButton("1", callback_data="code_1"),
         InlineKeyboardButton("2", callback_data="code_2"),
         InlineKeyboardButton("3", callback_data="code_3")],
        [InlineKeyboardButton("4", callback_data="code_4"),
         InlineKeyboardButton("5", callback_data="code_5"),
         InlineKeyboardButton("6", callback_data="code_6")],
        [InlineKeyboardButton("7", callback_data="code_7"),
         InlineKeyboardButton("8", callback_data="code_8"),
         InlineKeyboardButton("9", callback_data="code_9")],
        [InlineKeyboardButton("0", callback_data="code_0"),
         InlineKeyboardButton("⌫ Delete", callback_data="code_delete"),
         InlineKeyboardButton("✅ Confirmation", callback_data="code_confirm")]
    ]
    return InlineKeyboardMarkup(keyboard)


def akkaunt_boshqaruv_menu(akkauntlar):
    """Akkaunt boshqaruv menyusi"""
    keyboard = []
    for acc in akkauntlar:
        avtomatik_holat = "✅" if acc['avtomatik_guruh'] else "❌"
        keyboard.append([
            InlineKeyboardButton(
                f"{avtomatik_holat} {acc['phone']}",
                callback_data=f"account_{acc['id']}"
            )
        ])
    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)


def akkaunt_sozlamalari_menu(account_id):
    """Akkaunt sozlamalari menyusi"""
    keyboard = [
        [InlineKeyboardButton("✅ Automatic group activation", callback_data=f"acc_auto_on_{account_id}")],
        [InlineKeyboardButton("❌ Automatic group deletion", callback_data=f"acc_auto_off_{account_id}")],
        [InlineKeyboardButton("✏️ Change group name", callback_data=f"acc_change_name_{account_id}")],
        [InlineKeyboardButton("🔙 Back", callback_data="manage_accounts")]
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start komandasi"""
    await db_manager.bazani_boshlash()

    xabar = (
        "🤖 **Perfect Group Creation Bot**\n\n"
        "🔹 **50 groups per day per account**\n"
        "🔹 **Automatic group creation**\n"
        "🔹 **Parallel operation**\n"
        "🔹 **Inline control**\n\n"
        "Select from the menu below:"
    )

    if update.message:
        await update.message.reply_text(xabar, reply_markup=asosiy_menu(), parse_mode='Markdown')
    else:
        await update.callback_query.edit_message_text(xabar, reply_markup=asosiy_menu(), parse_mode='Markdown')
    return ConversationHandler.END


async def inline_tugmalar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inline tugmalarni boshqarish"""
    query = update.callback_query
    if query:
        await query.answer()

    malumot = query.data if query else update.message.text

    if malumot == "main_menu":
        await start(update, context)

    elif malumot == "add_account":
        await query.edit_message_text(
            "📱 **Add new account**\n\n"
            "Send your phone number (masalan, +998901234567):",
            reply_markup=orqaga_tugmasi(),
            parse_mode='Markdown'
        )
        context.user_data['holat'] = PHONE
        return PHONE

    elif malumot == "manage_accounts":
        akkauntlar = await db_manager.barcha_akkauntlarni_olish()
        if akkauntlar:
            xabar = "📋 **Account management:**\n\n"
            for acc in akkauntlar:
                kunlik_guruhlar = await db_manager.kunlik_cheklovni_tekshirish(acc['id'])
                avtomatik_holat = "✅ On" if acc['avtomatik_guruh'] else "❌ Off"
                xabar += f"• {acc['phone']} - {kunlik_guruhlar}/50 - {avtomatik_holat}\n"
        else:
            xabar = "❌ There are no accounts available yet."

        await query.edit_message_text(
            xabar,
            reply_markup=akkaunt_boshqaruv_menu(akkauntlar) if akkauntlar else orqaga_tugmasi(),
            parse_mode='Markdown'
        )

    elif malumot.startswith("account_"):
        account_id = int(malumot.split("_")[1])
        akkauntlar = await db_manager.barcha_akkauntlarni_olish()
        akkaunt = next((acc for acc in akkauntlar if acc['id'] == account_id), None)

        if akkaunt:
            kunlik_guruhlar = await db_manager.kunlik_cheklovni_tekshirish(account_id)
            avtomatik_holat = "✅ Yoqilgan" if akkaunt['avtomatik_guruh'] else "❌ O'chirilgan"

            xabar = (
                f"📱 **Account: {akkaunt['phone']}**\n\n"
                f"🔹 **Automatic group:** {avtomatik_holat}\n"
                f"🔹 **Group name:** {akkaunt['guruh_nomi'] or 'MeningGuruhim'}\n"
                f"🔹 **Today's groups:** {kunlik_guruhlar}/50\n"
                f"🔹 **Status:** {akkaunt['status']}\n\n"
                "Change settings:"
            )

            await query.edit_message_text(
                xabar,
                reply_markup=akkaunt_sozlamalari_menu(account_id),
                parse_mode='Markdown'
            )

    elif malumot.startswith("acc_auto_on_"):
        account_id = int(malumot.split("_")[3])
        await db_manager.avtomatik_guruh_sozlamasini_yangilash(account_id, True)
        await query.answer("✅ Automatic group enabled!")
        await inline_tugmalar(update, context)

    elif malumot.startswith("acc_auto_off_"):
        account_id = int(malumot.split("_")[3])
        await db_manager.avtomatik_guruh_sozlamasini_yangilash(account_id, False)
        await query.answer("❌ Auto group deleted!")
        await inline_tugmalar(update, context)

    elif malumot.startswith("acc_change_name_"):
        account_id = int(malumot.split("_")[3])
        context.user_data['account_id'] = account_id
        context.user_data['holat'] = GROUP_SETTINGS

        await query.edit_message_text(
            "✏️ **Enter a new group name:**\n\n"
            "For example: `MyGroup`\n"
            "Groups: `MyGroup_1`, `MyGroup_2`, ...",
            reply_markup=orqaga_tugmasi(),
            parse_mode='Markdown'
        )
        return GROUP_SETTINGS

    elif malumot == "create_groups":
        context.user_data['holat'] = GROUP_SETTINGS
        await query.edit_message_text(
            "🔢 **How many groups do you want to create??**\n\n"
            "Enter a number (1-50):",
            reply_markup=orqaga_tugmasi(),
            parse_mode='Markdown'
        )
        return GROUP_SETTINGS

    elif malumot == "stats":
        akkauntlar = await db_manager.barcha_akkauntlarni_olish()
        jami_guruhlar = 0
        jami_akkauntlar = len(akkauntlar)
        faol_avtomatik = len([acc for acc in akkauntlar if acc['avtomatik_guruh']])

        xabar = "📈 **Bot statistics:**\n\n"
        for acc in akkauntlar:
            kunlik_guruhlar = await db_manager.kunlik_cheklovni_tekshirish(acc['id'])
            avtomatik_holat = "✅" if acc['avtomatik_guruh'] else "❌"
            xabar += f"• {avtomatik_holat} `{acc['phone']}`: {kunlik_guruhlar}/50\n"
            jami_guruhlar += kunlik_guruhlar

        xabar += f"\n**Total:** {jami_akkauntlar} akkaunt, {faol_avtomatik} automatic, {jami_guruhlar} guruh"

        await query.edit_message_text(
            xabar,
            reply_markup=asosiy_menu(),
            parse_mode='Markdown'
        )

    elif malumot == "auto_settings":
        await query.edit_message_text(
            "⚙️ **Automatic group creation**\n\n"
            "Every 5 minutes, 1 group is created for all active accounts.i.\n"
            "Maximum of 50 groups per day per account.\n\n"
            "Select a setting:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Turn on", callback_data="auto_on")],
                [InlineKeyboardButton("❌ Delete", callback_data="auto_off")],
                [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
            ]),
            parse_mode='Markdown'
        )

    return ConversationHandler.END


async def telefon_raqamini_olish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Telefon raqamini olish"""
    if update.message:
        telefon = update.message.text.strip()
    else:
        return ConversationHandler.END

    # Mavjud akkauntni tekshirish
    mavjud_akkaunt = await db_manager.akkauntni_olish(telefon)
    if mavjud_akkaunt:
        await update.message.reply_text(
            f"✅ `{telefon}` account already exists!",
            reply_markup=asosiy_menu(),
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    context.user_data['telefon'] = telefon

    try:
        # Yangi klient yaratish
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()

        # Kod so'rovini yuborish
        sent_code = await client.send_code_request(telefon)

        context.user_data['client'] = client
        context.user_data['phone_code_hash'] = sent_code.phone_code_hash
        context.user_data['kirilgan_kod'] = ""

        await update.message.reply_text(
            f"📱 `{telefon}` A code has been sent to the number!\n\n"
            "Enter the code:\n"
            "**Current code:** (bo'sh)",
            reply_markup=kod_klaviaturasi(),
            parse_mode='Markdown'
        )
        return CODE

    except Exception as e:
        await update.message.reply_text(
            f"❌ Xatolik: {str(e)}\n\nQayta urinib ko'ring.",
            reply_markup=asosiy_menu()
        )
        return ConversationHandler.END


async def kod_tugmalarini_boshqarish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kod tugmalarini boshqarish"""
    query = update.callback_query
    await query.answer()

    malumot = query.data
    joriy_kod = context.user_data.get('kirilgan_kod', '')

    if malumot.startswith("code_"):
        raqam = malumot.split("_")[1]

        if raqam.isdigit():
            if len(joriy_kod) < 10:
                joriy_kod += raqam
                context.user_data['kirilgan_kod'] = joriy_kod
        elif raqam == "delete":
            joriy_kod = joriy_kod[:-1] if joriy_kod else ""
            context.user_data['kirilgan_kod'] = joriy_kod
        elif raqam == "confirm":
            if joriy_kod:
                return await kodni_tasdiqlash(update, context, joriy_kod)
            else:
                await query.answer("❌ Please enter the code.!")
                return CODE

        # Yangilangan kodni ko'rsatish
        await query.edit_message_text(
            f"📱 Enter code:\n\n**Current code:** {joriy_kod or '(boʻsh)'}",
            reply_markup=kod_klaviaturasi(),
            parse_mode='Markdown'
        )

    return CODE


async def kodni_tasdiqlash(update: Update, context: ContextTypes.DEFAULT_TYPE, kod: str):
    """Kodni tasdiqlash"""
    query = update.callback_query

    client = context.user_data.get('client')
    telefon = context.user_data.get('telefon')
    phone_code_hash = context.user_data.get('phone_code_hash')

    if not all([client, telefon, phone_code_hash]):
        await query.edit_message_text(
            "❌ Sessiya xatosi. Qaytadan boshlang.",
            reply_markup=asosiy_menu()
        )
        return ConversationHandler.END

    try:
        # Kod bilan kirish
        await client.sign_in(
            phone=telefon,
            code=kod,
            phone_code_hash=phone_code_hash
        )

        # Avtomatik sozlamani so'rash
        await query.edit_message_text(
            f"✅ `{telefon}` Account added successfully!\n\n"
            "🔹 **Should we enable automatic group creation?**\n"
            "1 group is automatically created every 5 minutes.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Yes, turn it on.", callback_data="auto_yes")],
                [InlineKeyboardButton("❌ No, later.", callback_data="auto_no")]
            ]),
            parse_mode='Markdown'
        )

        context.user_data['session_string'] = client.session.save()
        await client.disconnect()

        return AUTO_SETTING

    except SessionPasswordNeededError:
        await query.edit_message_text(
            "🔒 2FA password is required. Enter your password:",
            reply_markup=orqaga_tugmasi()
        )
        return PASSWORD

    except Exception as e:
        await query.edit_message_text(
            f"❌ Xatolik: {str(e)}\n\nQaytadan urinib ko'ring.",
            reply_markup=asosiy_menu()
        )
        if client:
            await client.disconnect()
        return ConversationHandler.END


async def avtomatik_sozlamani_boshqarish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Avtomatik sozlamani boshqarish"""
    query = update.callback_query
    await query.answer()

    malumot = query.data
    telefon = context.user_data.get('telefon')
    session_string = context.user_data.get('session_string')

    if malumot == "auto_yes":
        await db_manager.yangi_akkaunt_qoshish(telefon, session_string, True)
        await query.edit_message_text(
            f"🎉 **{telefon} account added!**\n\n"
            "✅ **Automatic group enabled!**\n"
            "1 group is created every 5 minutes.\n"
            "Maximum of 50 groups per day per account.",
            reply_markup=asosiy_menu(),
            parse_mode='Markdown'
        )
    else:
        await db_manager.yangi_akkaunt_qoshish(telefon, session_string, False)
        await query.edit_message_text(
            f"✅ **{telefon} account added!**\n\n"
            "❌ **Auto group deleted.**\n"
            "You can enable it later from account management.",
            reply_markup=asosiy_menu(),
            parse_mode='Markdown'
        )

    return ConversationHandler.END


async def parolni_olish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Parolni olish"""
    if update.message:
        parol = update.message.text.strip()
    else:
        return PASSWORD

    client = context.user_data.get('client')
    telefon = context.user_data.get('telefon')

    try:
        # Parol bilan kirish
        await client.sign_in(password=parol)

        # Avtomatik sozlamani so'rash
        await update.message.reply_text(
            f"✅ `{telefon}` Account added successfully!\n\n"
            "🔹 **Should we enable automatic group creation??**\n"
            "1 group is automatically created every 5 minutes.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Yes, turn it on.", callback_data="auto_yes")],
                [InlineKeyboardButton("❌ No, later.", callback_data="auto_no")]
            ]),
            parse_mode='Markdown'
        )

        context.user_data['session_string'] = client.session.save()
        await client.disconnect()

        return AUTO_SETTING

    except Exception as e:
        await update.message.reply_text(
            f"❌ Xatolik: {str(e)}\n\nQaytadan urinib ko'ring.",
            reply_markup=asosiy_menu()
        )
        if client:
            await client.disconnect()
        return ConversationHandler.END


async def guruh_sozlamalarini_olish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Guruh sozlamalarini olish"""
    if update.message:
        matn = update.message.text.strip()

        # Akkaunt nomini o'zgartirish
        if 'account_id' in context.user_data:
            account_id = context.user_data['account_id']
            await db_manager.avtomatik_guruh_sozlamasini_yangilash(account_id, True, matn)
            await update.message.reply_text(
                f"✅ Group name `{matn}` changed to!",
                reply_markup=asosiy_menu(),
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        # Oddiy guruh yaratish
        try:
            guruh_soni = int(matn)
            if guruh_soni < 1 or guruh_soni > 50:
                await update.message.reply_text(
                    "❌ 1 dan 50 gacha raqam kiriting!",
                    reply_markup=orqaga_tugmasi()
                )
                return GROUP_SETTINGS

            # Guruh nomlarini yaratish
            akkauntlar = await db_manager.barcha_akkauntlarni_olish()
            guruhlar_yaratildi = 0

            for i in range(guruh_soni):
                if i >= len(akkauntlar):
                    break

                akkaunt = akkauntlar[i]
                kunlik_guruhlar = await db_manager.kunlik_cheklovni_tekshirish(akkaunt['id'])

                if kunlik_guruhlar < MAX_GROUPS_PER_ACCOUNT_DAILY:
                    name, desc = random.choice(GROUP_NAMES)
                    guruh_nomi = f"{name}"
                    await db_manager.guruh_navbatiga_qoshish(akkaunt['id'], guruh_nomi)
                    guruhlar_yaratildi += 1

            await update.message.reply_text(
                f"✅ **{guruhlar_yaratildi}** ta guruh navbatga qo'shildi! 🚀",
                reply_markup=asosiy_menu(),
                parse_mode='Markdown'
            )

        except ValueError:
            await update.message.reply_text(
                "❌ Faqat raqam kiriting!",
                reply_markup=orqaga_tugmasi()
            )
            return GROUP_SETTINGS

    return ConversationHandler.END


async def avtomatik_guruh_yaratish():
    """Avtomatik guruh yaratish"""
    try:
        akkauntlar = await db_manager.avtomatik_akkauntlarni_olish()
        logger.info(f"🔍 {len(akkauntlar)} ta avtomatik akkaunt topildi")

        for akkaunt in akkauntlar:
            kunlik_guruhlar = await db_manager.kunlik_cheklovni_tekshirish(akkaunt['id'])

            if kunlik_guruhlar < MAX_GROUPS_PER_ACCOUNT_DAILY:
                name, desc = random.choice(GROUP_NAMES)
                guruh_nomi = f"{name}"
                await db_manager.guruh_navbatiga_qoshish(akkaunt['id'], guruh_nomi)
                logger.info(f"✅ {akkaunt['phone']} uchun {guruh_nomi} navbatga qo'shildi")
            else:
                logger.info(f"⏸️ {akkaunt['phone']} kunlik cheklovga yetdi")

    except Exception as e:
        logger.error(f"❌ Avtomatik guruh yaratishda xatolik: {e}")


async def guruh_yaratish_protsessori():
    """Guruh yaratish protsessori"""
    while True:
        try:
            kutayotgan_guruhlar = await db_manager.kutayotgan_guruhlarni_olish(limit=10)

            if kutayotgan_guruhlar:
                logger.info(f"📦 {len(kutayotgan_guruhlar)} ta guruh yaratilmoqda...")

                for guruh in kutayotgan_guruhlar:
                    await bitta_guruh_yaratish(guruh)
                    await asyncio.sleep(2)  # 2 soniya kutish

            else:
                await asyncio.sleep(10)

        except Exception as e:
            logger.error(f"❌ Protsessorda xatolik: {e}")
            await asyncio.sleep(30)


async def bitta_guruh_yaratish(guruh):
    """Bitta guruh yaratish"""
    try:
        await db_manager.guruh_holatini_yangilash(guruh['id'], 'boshlandi')

        # Kunlik cheklovni tekshirish
        kunlik_guruhlar = await db_manager.kunlik_cheklovni_tekshirish(guruh['account_id'])
        if kunlik_guruhlar >= MAX_GROUPS_PER_ACCOUNT_DAILY:
            await db_manager.guruh_holatini_yangilash(
                guruh['id'],
                'xato',
                'Kunlik cheklovga yetdi (50 ta)'
            )
            return

        # Klient yaratish
        client = TelegramClient(
            StringSession(guruh['session_string']),
            API_ID,
            API_HASH
        )

        try:
            await client.connect()

            if not await client.is_user_authorized():
                await db_manager.guruh_holatini_yangilash(
                    guruh['id'],
                    'xato',
                    'Sessiya muddati tugadi'
                )
                return

            # Guruh yaratish
            natija = await client(CreateChannelRequest(
                title=guruh['group_name'],
                about="Avtomatik yaratilgan guruh",
                megagroup=True
            ))

            yaratilgan_guruh = natija.chats[0]
            await client.send_message(yaratilgan_guruh.id, "🤖 Guruhga xush kelibsiz!")

            # Ma'lumotlarni yangilash
            await db_manager.guruh_holatini_yangilash(guruh['id'], 'tugadi')
            await db_manager.kunlik_statistikani_yangilash(guruh['account_id'])
            await db_manager.akkauntni_yangilash(guruh['account_id'])

            logger.info(f"✅ {guruh['group_name']} guruhi yaratildi ({guruh['phone']})")

        except Exception as e:
            xatolik = str(e)
            await db_manager.guruh_holatini_yangilash(guruh['id'], 'xato', xatolik)
            logger.error(f"❌ {guruh['group_name']} yaratishda xatolik: {xatolik}")

        finally:
            await client.disconnect()

    except Exception as e:
        logger.error(f"💥 Guruh yaratishda kutilmagan xatolik: {e}")


async def konvertatsiyani_bekor_qilish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Konvertatsiyani bekor qilish"""
    await update.message.reply_text(
        "❌ Bekor qilindi.",
        reply_markup=asosiy_menu()
    )
    return ConversationHandler.END


async def xatolik_boshqaruvchi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xatolik boshqaruvchi"""
    logger.error(f"💥 Xatolik: {context.error}", exc_info=context.error)


def main():
    """Asosiy funksiya"""
    # Botni sozlash
    application = (
        Application.builder()
        .token(TOKEN)
        .concurrent_updates(True)
        .build()
    )

    # Konvertatsiya boshqaruvi
    konvertatsiya = ConversationHandler(
        entry_points=[CallbackQueryHandler(inline_tugmalar, pattern="^add_account$")],
        states={
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, telefon_raqamini_olish)],
            CODE: [CallbackQueryHandler(kod_tugmalarini_boshqarish, pattern="^code_")],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, parolni_olish)],
            AUTO_SETTING: [CallbackQueryHandler(avtomatik_sozlamani_boshqarish, pattern="^auto_")],
            GROUP_SETTINGS: [MessageHandler(filters.TEXT & ~filters.COMMAND, guruh_sozlamalarini_olish)],
        },
        fallbacks=[
            CommandHandler("cancel", konvertatsiyani_bekor_qilish),
            CallbackQueryHandler(start, pattern="^main_menu$")
        ],
        per_message=False
    )

    # Handlerni qo'shish
    application.add_handler(CommandHandler("start", start))
    application.add_handler(konvertatsiya)
    application.add_handler(CallbackQueryHandler(inline_tugmalar))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, inline_tugmalar))

    # Xatolik boshqaruvi
    application.add_error_handler(xatolik_boshqaruvchi)

    # Botni ishga tushirish
    logger.info("🚀 Bot ishga tushdi! Mukammal ishlaydi 🎉")

    # Avtomatik jarayonlarni boshlash
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Ma'lumotlar bazasini ishga tushirish
    loop.run_until_complete(db_manager.bazani_boshlash())

    # Background vazifalarni boshlash
    loop.create_task(guruh_yaratish_protsessori())
    loop.create_task(avtomatik_guruh_yaratish_job())

    # Botni ishga tushirish
    application.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )


async def avtomatik_guruh_yaratish_job():
    """Avtomatik guruh yaratish vazifasi"""
    while True:
        try:
            await avtomatik_guruh_yaratish()
            await asyncio.sleep(AUTO_CREATE_INTERVAL * 60)  # daqiqalarni soniyaga aylantirish
        except Exception as e:
            logger.error(f"❌ Avtomatik yaratishda xatolik: {e}")
            await asyncio.sleep(60)


if __name__ == "__main__":
    main()

from telegram import (
    Update,
    BotCommand,
    BotCommandScopeChat,
    BotCommandScopeAllPrivateChats,
    KeyboardButton,
    ReplyKeyboardMarkup,

    ReplyKeyboardRemove,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

from config import (
    TELEGRAM_TOKEN, ADMIN_ID,
    ASK_LANG, ASK_NAME, ASK_PHONE,
    ASK_REGION, ASK_CATEGORY, ASK_DOCTOR, ASK_QUESTION,
)
from data import TEXTS, VILOYATLAR, DOCTORS
from sheets import save_to_sheet, update_status_in_sheet


# ── Klaviaturalar ─────────────────────────────────────────────────────────────
def lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇺🇿 O'zbek",  callback_data="lang_uz"),
        InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
    ]])


def region_keyboard(lang: str) -> InlineKeyboardMarkup:
    regions = VILOYATLAR[lang]
    buttons = []
    for i in range(0, len(regions), 2):
        row = [InlineKeyboardButton(regions[i], callback_data=f"region_{regions[i]}")]
        if i + 1 < len(regions):
            row.append(InlineKeyboardButton(regions[i + 1], callback_data=f"region_{regions[i + 1]}"))
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def category_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(TEXTS[lang]["cat_mgmt"],  callback_data="cat_mgmt"),
            InlineKeyboardButton(TEXTS[lang]["cat_sales"], callback_data="cat_sales"),
        ],
        [
            InlineKeyboardButton(TEXTS[lang]["cat_doc"], callback_data="cat_doc"),
        ],
    ])


def doctor_keyboard(lang: str) -> InlineKeyboardMarkup:
    docs = DOCTORS[lang]
    buttons = []
    for i in range(0, len(docs), 2):
        row = [InlineKeyboardButton(docs[i], callback_data=f"doc_{docs[i]}")]
        if i + 1 < len(docs):
            row.append(InlineKeyboardButton(docs[i + 1], callback_data=f"doc_{docs[i + 1]}"))
        buttons.append(row)
    buttons.append([InlineKeyboardButton(TEXTS[lang]["back_btn"], callback_data="back_category")])
    return InlineKeyboardMarkup(buttons)


def back_keyboard(lang: str, target: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(TEXTS[lang]["back_btn"], callback_data=f"back_{target}")
    ]])


def phone_keyboard(lang: str) -> ReplyKeyboardMarkup:
    btn = KeyboardButton(TEXTS[lang]["phone_btn"], request_contact=True)
    return ReplyKeyboardMarkup([[btn]], resize_keyboard=True, one_time_keyboard=True)


def admin_keyboard(user_id: int, status: str = "active") -> InlineKeyboardMarkup:
    status_label = "✅ Aktiv" if status == "active" else "❌ Deaktiv"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📞 Mijoz bilan bog'lanish", callback_data=f"connect_{user_id}")],
        [InlineKeyboardButton(status_label,                callback_data=f"toggle_{user_id}")],
    ])


def disconnect_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔴 Ulanishni uzish", callback_data="disconnect")
    ]])


# ── Suhbat handlerlari ────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user.id == ADMIN_ID:
        await update.message.reply_text(
            "👨‍💼 *Admin paneliga xush kelibsiz!*\n\n"
            "📋 /list — Barcha foydalanuvchilar\n"
            "✅ /active — Aktiv foydalanuvchilar\n"
            "❌ /deactive — Deaktiv foydalanuvchilar\n"
            "⏹ /stop — Relay ulanishni uzish",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text(
        TEXTS["uz"]["welcome"],
        parse_mode="Markdown",
        reply_markup=lang_keyboard(),
    )
    return ASK_LANG


async def choose_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = query.data[len("lang_"):]
    context.user_data["lang"] = lang
    t = TEXTS[lang]
    await query.edit_message_text(
        f"{t['flag']} *{t['lang_name']}* {t['lang_selected']}.\n\n{t['ask_name']}",
        parse_mode="Markdown",
    )
    return ASK_NAME


async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "uz")
    t    = TEXTS[lang]
    name = update.message.text.strip()
    if len(name) < 3:
        await update.message.reply_text(t["name_short"])
        return ASK_NAME
    context.user_data["name"] = name
    await update.message.reply_text(
        t["ask_phone"], parse_mode="Markdown", reply_markup=phone_keyboard(lang)
    )
    return ASK_PHONE


async def ask_phone_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang  = context.user_data.get("lang", "uz")
    t     = TEXTS[lang]
    phone = update.message.contact.phone_number or ""
    phone = phone.strip()

    # Yopiq akkaunt — raqam bo'sh keladi, qo'lda kiritishni so'raymiz
    if not phone:
        await update.message.reply_text(
            t["phone_error"], parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ASK_PHONE

    if not phone.startswith("+"):
        phone = "+" + phone
    context.user_data["phone"] = phone
    await update.message.reply_text(t["phone_ok"], reply_markup=ReplyKeyboardRemove())
    await update.message.reply_text(t["ask_region"], reply_markup=region_keyboard(lang))
    return ASK_REGION


async def ask_phone_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang  = context.user_data.get("lang", "uz")
    t     = TEXTS[lang]
    phone = update.message.text.strip().replace(" ", "").replace("-", "")
    if not phone.startswith("+"):
        phone = "+" + phone
    if len(phone) < 10 or not phone[1:].isdigit():
        await update.message.reply_text(t["phone_error"], parse_mode="Markdown")
        return ASK_PHONE
    context.user_data["phone"] = phone
    await update.message.reply_text(t["phone_ok"], reply_markup=ReplyKeyboardRemove())
    await update.message.reply_text(t["ask_region"], reply_markup=region_keyboard(lang))
    return ASK_REGION


async def ask_region(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query  = update.callback_query
    await query.answer()
    lang   = context.user_data.get("lang", "uz")
    t      = TEXTS[lang]
    region = query.data[len("region_"):]
    context.user_data["region"] = region
    await query.edit_message_text(
        f"✅ *{region}*\n\n{t['ask_category']}",
        parse_mode="Markdown",
        reply_markup=category_keyboard(lang),
    )
    return ASK_CATEGORY


async def choose_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang  = context.user_data.get("lang", "uz")
    t     = TEXTS[lang]
    cat   = query.data

    if cat in ("cat_mgmt", "cat_sales"):
        key = "cat_mgmt" if cat == "cat_mgmt" else "cat_sales"
        context.user_data["category"] = t[key]
        await query.edit_message_text(
            f"{t[key]}\n\n{t['ask_question']}",
            parse_mode="Markdown",
            reply_markup=back_keyboard(lang, "category"),
        )
        return ASK_QUESTION
    else:
        context.user_data["category"] = t["cat_doc"]
        await query.edit_message_text(
            f"{t['cat_doc']}\n\n{t['ask_doctor']}",
            parse_mode="Markdown",
            reply_markup=doctor_keyboard(lang),
        )
        return ASK_DOCTOR


async def choose_doctor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query  = update.callback_query
    await query.answer()
    lang   = context.user_data.get("lang", "uz")
    t      = TEXTS[lang]
    doctor = query.data[len("doc_"):]
    context.user_data["category"] = f"{t['cat_doc']} — {doctor}"
    await query.edit_message_text(
        f"👨‍⚕️ *{doctor}*\n\n{t['ask_question']}",
        parse_mode="Markdown",
        reply_markup=back_keyboard(lang, "doctors"),
    )
    return ASK_QUESTION


async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang     = context.user_data.get("lang", "uz")
    t        = TEXTS[lang]
    question = update.message.text.strip()
    user     = update.effective_user
    name     = context.user_data["name"]
    phone    = context.user_data["phone"]
    region   = context.user_data["region"]
    category = context.user_data["category"]

    users = context.application.bot_data.setdefault("users", {})
    users[user.id] = {"name": name, "phone": phone, "region": region, "lang": lang,
                      "status": users.get(user.id, {}).get("status", "active")}

    await update.message.reply_text(
        t["done"].format(name=name, phone=phone,
                         region=region, category=category, question=question),
        parse_mode="Markdown",
    )

    flag     = TEXTS[lang]["flag"]
    username = f"@{user.username}" if user.username else "—"
    admin_msg = (
        TEXTS[lang]["admin_new_msg"]
        .replace("{{flag}}",     flag)
        .replace("{{name}}",     name)
        .replace("{{phone}}",    phone)
        .replace("{{region}}",   region)
        .replace("{{category}}", category)
        .replace("{{question}}", question)
        .replace("{{uid}}",      str(user.id))
        .replace("{{username}}", username)
        .replace("{{fullname}}", user.full_name)
    )
    try:
        await update.get_bot().send_message(
            chat_id=ADMIN_ID,
            text=admin_msg,
            parse_mode="Markdown",
            reply_markup=admin_keyboard(user.id, users[user.id]["status"]),
        )
    except Exception as e:
        print(f"Admin ga yuborishda xato: {e}")

    # Google Sheets ga saqlash
    save_to_sheet(
        name=name, phone=phone, region=region,
        category=category, question=question, lang=lang,
        telegram_id=user.id,
        username=f"@{user.username}" if user.username else "—",
        fullname=user.full_name,
        status=users[user.id]["status"],
    )

    return ConversationHandler.END


async def back_to_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query  = update.callback_query
    await query.answer()
    lang   = context.user_data.get("lang", "uz")
    t      = TEXTS[lang]
    region = context.user_data.get("region", "")
    await query.edit_message_text(
        f"✅ *{region}*\n\n{t['ask_category']}",
        parse_mode="Markdown",
        reply_markup=category_keyboard(lang),
    )
    return ASK_CATEGORY


async def back_to_doctors(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang  = context.user_data.get("lang", "uz")
    t     = TEXTS[lang]
    await query.edit_message_text(
        f"{t['cat_doc']}\n\n{t['ask_doctor']}",
        parse_mode="Markdown",
        reply_markup=doctor_keyboard(lang),
    )
    return ASK_DOCTOR


async def fill_warning(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Foydalanuvchi forma to'ldirayotganda ssenariydan tashqari xabar yozsa."""
    lang = context.user_data.get("lang")
    if lang:
        text = TEXTS[lang]["fill_warning"]
    else:
        # Til hali tanlanmagan — ikkala tilda ko'rsatish
        text = (
            "📝 Iltimos, avval ma'lumotlarni to'ldiring!\n"
            "Tugmalardan foydalaning.\n\n"
            "📝 Пожалуйста, сначала заполните данные!\n"
            "Используйте кнопки."
        )
    await update.message.reply_text(text)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "uz")
    await update.message.reply_text(
        TEXTS[lang]["cancel"], reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


# ── Status handlerlari ────────────────────────────────────────────────────────
async def toggle_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if update.effective_user.id != ADMIN_ID:
        return
    user_id = int(query.data[len("toggle_"):])
    users   = context.application.bot_data.setdefault("users", {})
    if user_id not in users:
        users[user_id] = {}
    current    = users[user_id].get("status", "active")
    new_status = "deactive" if current == "active" else "active"
    users[user_id]["status"] = new_status
    await query.edit_message_reply_markup(
        reply_markup=admin_keyboard(user_id, new_status)
    )
    update_status_in_sheet(user_id, new_status)


async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        return
    users = context.application.bot_data.get("users", {})
    if not users:
        await update.message.reply_text("📋 Hech qanday foydalanuvchi yo'q.")
        return
    lines = ["📋 *Barcha foydalanuvchilar:*\n━━━━━━━━━━━━━━━━━━"]
    for uid, info in users.items():
        icon  = "✅" if info.get("status", "active") == "active" else "❌"
        lines.append(f"{icon} *{info.get('name','—')}* | `{info.get('phone','—')}` | ID: `{uid}`")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def active_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        return
    users  = context.application.bot_data.get("users", {})
    active = {uid: i for uid, i in users.items() if i.get("status", "active") == "active"}
    if not active:
        await update.message.reply_text("✅ Aktiv foydalanuvchilar yo'q.")
        return
    lines = [f"✅ *Aktiv foydalanuvchilar ({len(active)} ta):*\n━━━━━━━━━━━━━━━━━━"]
    for uid, info in active.items():
        lines.append(f"• *{info.get('name','—')}* | `{info.get('phone','—')}` | ID: `{uid}`")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def deactive_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        return
    users    = context.application.bot_data.get("users", {})
    deactive = {uid: i for uid, i in users.items() if i.get("status", "active") == "deactive"}
    if not deactive:
        await update.message.reply_text("❌ Deaktiv foydalanuvchilar yo'q.")
        return
    lines = [f"❌ *Deaktiv foydalanuvchilar ({len(deactive)} ta):*\n━━━━━━━━━━━━━━━━━━"]
    for uid, info in deactive.items():
        lines.append(f"• *{info.get('name','—')}* | `{info.get('phone','—')}` | ID: `{uid}`")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── Relay handlerlari ─────────────────────────────────────────────────────────
async def handle_connect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if update.effective_user.id != ADMIN_ID:
        return
    user_id = int(query.data[len("connect_"):])
    context.application.bot_data["admin_relay"] = user_id
    users = context.application.bot_data.get("users", {})
    uinfo = users.get(user_id, {})
    name  = uinfo.get("name", f"ID {user_id}")
    lang  = uinfo.get("lang", "uz")
    await query.edit_message_reply_markup(reply_markup=None)
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"✅ *{name}* bilan bog'landingiz.\n"
            f"Xabaringizni yozing.\n"
            f"Tugatish uchun — /stop"
        ),
        parse_mode="Markdown",
        reply_markup=disconnect_keyboard(),
    )
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=TEXTS[lang]["admin_connecting"],
        )
    except Exception as e:
        print(f"User ga xabar yuborishda xato: {e}")


async def handle_disconnect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if update.effective_user.id != ADMIN_ID:
        return
    user_id = context.application.bot_data.pop("admin_relay", None)
    await query.edit_message_reply_markup(reply_markup=None)
    await context.bot.send_message(chat_id=ADMIN_ID, text="🔴 Ulanish uzildi.")
    if user_id:
        lang = context.application.bot_data.get("users", {}).get(user_id, {}).get("lang", "uz")
        try:
            await context.bot.send_message(chat_id=user_id, text=TEXTS[lang]["relay_ended_user"])
        except Exception:
            pass


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    lang = context.user_data.get("lang", "uz")
    if user.id == ADMIN_ID:
        user_id = context.application.bot_data.pop("admin_relay", None)
        if user_id:
            await update.message.reply_text("🔴 Ulanish uzildi.")
            u_lang = context.application.bot_data.get("users", {}).get(user_id, {}).get("lang", "uz")
            try:
                await context.bot.send_message(chat_id=user_id, text=TEXTS[u_lang]["relay_ended_user"])
            except Exception:
                pass
        else:
            await update.message.reply_text("⛔ Bot to'xtatildi.")
    else:
        context.user_data.clear()
        await update.message.reply_text(TEXTS[lang]["cancel"], reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user.id == ADMIN_ID:
        await update.message.reply_text(
            "👨‍💼 *Admin paneliga xush kelibsiz!*\n\n"
            "📋 /list — Barcha foydalanuvchilar\n"
            "✅ /active — Aktiv foydalanuvchilar\n"
            "❌ /deactive — Deaktiv foydalanuvchilar\n"
            "⏹ /stop — Relay ulanishni uzish",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text(
        TEXTS["uz"]["welcome"], parse_mode="Markdown", reply_markup=lang_keyboard()
    )
    return ASK_LANG


async def handle_general_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    user = update.effective_user
    text = update.message.text.strip()

    if user.id == ADMIN_ID:
        target_id = context.application.bot_data.get("admin_relay")
        if target_id:
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=f"👨‍💼 *Admin:*\n{text}",
                    parse_mode="Markdown",
                )
                await update.message.reply_text("✅ Xabar yuborildi.", reply_markup=disconnect_keyboard())
            except Exception as e:
                await update.message.reply_text(f"❌ Yuborib bo'lmadi: {e}")
        else:
            await update.message.reply_text(
                "⚠️ Hozir hech kim bilan bog'lanilmagan.\n"
                "Mijoz xabarini ko'rib, «📞 Mijoz bilan bog'lanish» tugmasini bosing."
            )
        return

    users    = context.application.bot_data.setdefault("users", {})
    uinfo    = users.get(user.id, {})
    lang     = uinfo.get("lang", "uz")
    username = f"@{user.username}" if user.username else "—"
    relay_id = context.application.bot_data.get("admin_relay")

    if relay_id == user.id:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"👤 *{user.full_name}:*\n{text}",
            parse_mode="Markdown",
            reply_markup=disconnect_keyboard(),
        )
    else:
        name_line = f"📋 {uinfo.get('name','—')} | {uinfo.get('phone','—')}\n" if uinfo else ""
        admin_msg = (
            TEXTS[lang]["admin_unknown_msg"]
            .replace("{{fullname}}", user.full_name)
            .replace("{{username}}", username)
            .replace("{{name_line}}", name_line)
            .replace("{{uid}}",      str(user.id))
            .replace("{{text}}",     text)
        )
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_msg,
            parse_mode="Markdown",
            reply_markup=admin_keyboard(user.id, uinfo.get("status", "active")),
        )
        await update.message.reply_text(TEXTS[lang]["msg_forwarded"])


# ── Main ──────────────────────────────────────────────────────────────────────
async def post_init(application: Application) -> None:
    user_commands = [
        BotCommand("start",   "▶️ Botni boshlash"),
        BotCommand("restart", "🔄 Qayta boshlash"),
        BotCommand("stop",    "⏹ To'xtatish"),
    ]
    admin_commands = user_commands + [
        BotCommand("active",   "✅ Aktiv foydalanuvchilar"),
        BotCommand("deactive", "❌ Deaktiv foydalanuvchilar"),
        BotCommand("list",     "📋 Barcha foydalanuvchilar"),
    ]
    await application.bot.set_my_commands(
        commands=user_commands,
        scope=BotCommandScopeAllPrivateChats(),
    )
    await application.bot.set_my_commands(
        commands=admin_commands,
        scope=BotCommandScopeChat(chat_id=ADMIN_ID),
    )


def main() -> None:
    if not TELEGRAM_TOKEN:
        raise ValueError("FORM_BOT_TOKEN o'rnatilmagan!")
    if ADMIN_ID == 0:
        raise ValueError("ADMIN_CHAT_ID o'rnatilmagan!")

    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CallbackQueryHandler(handle_connect,    pattern=r"^connect_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_disconnect, pattern=r"^disconnect$"))
    app.add_handler(CallbackQueryHandler(toggle_status,     pattern=r"^toggle_\d+$"))

    app.add_handler(CommandHandler("list",     list_users))
    app.add_handler(CommandHandler("active",   active_users))
    app.add_handler(CommandHandler("deactive", deactive_users))

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start",   start),
            CommandHandler("restart", restart_command),
        ],
        states={
            ASK_LANG: [
                CallbackQueryHandler(choose_lang, pattern=r"^lang_"),
                MessageHandler(filters.ALL & ~filters.COMMAND, fill_warning),
            ],
            ASK_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name),
                MessageHandler(filters.ALL & ~filters.COMMAND, fill_warning),
            ],
            ASK_PHONE: [
                MessageHandler(filters.CONTACT, ask_phone_contact),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_phone_text),
                MessageHandler(filters.ALL & ~filters.COMMAND, fill_warning),
            ],
            ASK_REGION: [
                CallbackQueryHandler(ask_region, pattern=r"^region_"),
                MessageHandler(filters.ALL & ~filters.COMMAND, fill_warning),
            ],
            ASK_CATEGORY: [
                CallbackQueryHandler(choose_category, pattern=r"^cat_"),
                MessageHandler(filters.ALL & ~filters.COMMAND, fill_warning),
            ],
            ASK_DOCTOR: [
                CallbackQueryHandler(choose_doctor,    pattern=r"^doc_"),
                CallbackQueryHandler(back_to_category, pattern=r"^back_category$"),
                MessageHandler(filters.ALL & ~filters.COMMAND, fill_warning),
            ],
            ASK_QUESTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_question),
                CallbackQueryHandler(back_to_category, pattern=r"^back_category$"),
                CallbackQueryHandler(back_to_doctors,  pattern=r"^back_doctors$"),
                MessageHandler(filters.ALL & ~filters.COMMAND, fill_warning),
            ],
        },
        fallbacks=[
            CommandHandler("stop",    stop_command),
            CommandHandler("restart", restart_command),
            CommandHandler("cancel",  cancel),
        ],
    )
    app.add_handler(conv)

    app.add_handler(CommandHandler("stop",    stop_command))
    app.add_handler(CommandHandler("restart", restart_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_general_message))

    print("✅ Bot ishga tushdi...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

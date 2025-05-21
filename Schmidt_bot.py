import logging
import os
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# Загрузка токена
load_dotenv()
TOKEN = os.getenv("7572240019:AAE7FqcATdy4yxWc9uPIFL-6NxV0fuY_AeI")

# Настройка логов
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Подключение к Google Sheets
def connect_to_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
             "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("Schmidt_bot.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open("BarTour_Bot_Data").sheet1
    return sheet

sheet = connect_to_sheet()

# Этапы диалога
CONFIRM_AGE, CONFIRM_PRIVACY, GET_NAME, GET_BIRTHDATE, MAIN_MENU, PHOTO = range(6)

user_data_store = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Вам есть 18 лет? (да/нет)")
    return CONFIRM_AGE

async def confirm_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if text == "да":
        await update.message.reply_text("Вы соглашаетесь на обработку персональных данных? (да/нет)")
        return CONFIRM_PRIVACY
    else:
        await update.message.reply_text("Доступ запрещён. Бот только для 18+.")
        return ConversationHandler.END

async def confirm_privacy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if text == "да":
        await update.message.reply_text("Введите ваше ФИО:")
        return GET_NAME
    else:
        await update.message.reply_text("Без согласия нельзя продолжить.")
        return ConversationHandler.END

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 3:
        await update.message.reply_text("ФИО должно содержать минимум 3 символа. Попробуйте снова:")
        return GET_NAME
    context.user_data['full_name'] = name
    await update.message.reply_text("Введите дату рождения в формате ДД.ММ.ГГГГ:")
    return GET_BIRTHDATE

async def get_birthdate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date_text = update.message.text.strip()
    try:
        datetime.strptime(date_text, "%d.%m.%Y")
        context.user_data['birthdate'] = date_text

        # Сохраняем пользователя
        user_id = update.effective_user.id
        user_data_store[user_id] = {
            "full_name": context.user_data['full_name'],
            "birthdate": date_text
        }

        # Запись в Google Sheets
        full_name = context.user_data['full_name']
        birthdate = context.user_data['birthdate']
        telegram_id = update.effective_user.id
        username = update.effective_user.username or ''
        sheet.append_row([str(telegram_id), username, full_name, birthdate])

        # Главное меню
        keyboard = [[KeyboardButton("📸 Загрузить фото")]]
        await update.message.reply_text("Вы успешно зарегистрированы! Выберите действие:",
                                        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return MAIN_MENU

    except ValueError:
        await update.message.reply_text("Неверный формат даты. Введите в формате ДД.ММ.ГГГГ:")
        return GET_BIRTHDATE

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "📸 Загрузить фото":
        await update.message.reply_text("Пожалуйста, отправьте фотографию:")
        return PHOTO
    else:
        await update.message.reply_text("Выберите действие из меню.")
        return MAIN_MENU

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file = await update.message.photo[-1].get_file()
    user_id = update.effective_user.id
    photo_path = f"photos/{user_id}_{photo_file.file_unique_id}.jpg"

    os.makedirs("photos", exist_ok=True)
    await photo_file.download_to_drive(photo_path)
    await update.message.reply_text("Фотография сохранена!")
    return MAIN_MENU

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Выход из диалога.")
    return ConversationHandler.END

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CONFIRM_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_age)],
            CONFIRM_PRIVACY: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_privacy)],
            GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            GET_BIRTHDATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_birthdate)],
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu)],
            PHOTO: [MessageHandler(filters.PHOTO, handle_photo)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    app.add_handler(conv_handler)
    app.run_polling()

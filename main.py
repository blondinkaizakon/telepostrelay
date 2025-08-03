
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.error import TelegramError, Conflict, NetworkError
import asyncio
import logging
import os
import sys
import signal
import time

# === Настройки ===
BOT_TOKEN = '7847097021:AAHJ3Ij4Gu12BZAkjMzSeLWyYDdkwuLf4rU'  # 
CHANNEL_ID = '@petrovskajaoksana'  # ← Ваш канал
DOWNLOAD_LINK = 'https://drive.google.com/file/d/1BGduGEC8YlxKWNMUxML74-z_mRh4zxbA/view?usp=drive_link'  # ← Ваша ссылка

# Текст сообщения
SUCCESS_MESSAGE = (
    "✅ Вы подписаны!\n\n"
    "Откройте материал по ссылке:\n"
    f"{DOWNLOAD_LINK}\n\n"
    "👉 Скопируйте ссылку и вставьте в браузер."
)

# === Логирование ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Глобальная переменная для отслеживания состояния бота
bot_running = False

# === Команда /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [[InlineKeyboardButton("Проверить подписку", callback_data="check_subscription")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await update.message.reply_text(
            f"Привет, {user.first_name}!\n"
            f"Подпишитесь на канал:\n"
            f"https://t.me/{CHANNEL_ID[1:]}\n\n"
            f"После этого нажмите кнопку ниже.",
            reply_markup=reply_markup
        )
        logger.info(f"Пользователь {user.id} ({user.first_name}) запустил бота")
    except Exception as e:
        logger.error(f"Ошибка при отправке стартового сообщения: {e}")

# === Проверка подписки ===
async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    
    try:
        await query.answer()
        logger.info(f"Проверка подписки для пользователя {user.id} ({user.first_name})")
        
        # Проверяем подписку на канал
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user.id)
        logger.info(f"Статус пользователя {user.id} в канале: {member.status}")
        
        if member.status in ['member', 'administrator', 'creator']:
            await query.edit_message_text(SUCCESS_MESSAGE)
            logger.info(f"Пользователь {user.id} получил доступ к материалам")
        else:
            keyboard = [[InlineKeyboardButton("Проверить подписку", callback_data="check_subscription")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"❌ Вы не подписаны на канал:\n"
                f"https://t.me/{CHANNEL_ID[1:]}\n\n"
                f"Подпишитесь и попробуйте снова.",
                reply_markup=reply_markup
            )
            logger.info(f"Пользователь {user.id} не подписан на канал")
            
    except TelegramError as e:
        error_message = str(e)
        logger.error(f"Telegram ошибка при проверке подписки для {user.id}: {error_message}")
        
        # Обрабатываем конкретные ошибки
        if "Bad Request" in error_message or "user not found" in error_message.lower():
            await query.edit_message_text(
                "❌ Ошибка проверки подписки.\n"
                "Убедитесь, что:\n"
                "1. Вы подписаны на канал\n"
                "2. Канал существует и доступен\n"
                "3. Попробуйте еще раз через несколько секунд"
            )
        else:
            await query.edit_message_text(f"❌ Техническая ошибка: {error_message}")
            
    except Exception as e:
        logger.error(f"Неожиданная ошибка при проверке подписки: {e}")
        try:
            await query.edit_message_text("❌ Произошла техническая ошибка. Попробуйте позже.")
        except:
            pass

# === Обработчик ошибок ===
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

# === Запуск бота ===
async def main():
    global bot_running
    
    if bot_running:
        logger.warning("Бот уже запущен!")
        return
        
    bot_running = True
    logger.info("Инициализация бота...")
    
    # Создаем приложение с дополнительными настройками
    app = (ApplicationBuilder()
           .token(BOT_TOKEN)
           .concurrent_updates(True)
           .build())
    
    # Добавляем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(check_subscription, pattern="check_subscription"))
    app.add_error_handler(error_handler)
    
    # Обработчик сигналов для graceful shutdown
    stop_event = asyncio.Event()
    
    def signal_handler(signum, frame):
        logger.info("Получен сигнал завершения...")
        stop_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        logger.info("Запуск бота...")
        await app.initialize()
        await app.start()
        
        # Очищаем pending updates и запускаем polling
        await app.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"]
        )
        
        logger.info("🤖 Бот успешно запущен и готов к работе!")
        logger.info(f"Канал для проверки: {CHANNEL_ID}")
        
        # Ждем сигнал остановки
        await stop_event.wait()
        
    except Conflict as e:
        logger.error("❌ КОНФЛИКТ: Другой экземпляр бота уже запущен!")
        logger.error("Решение: Остановите все процессы и запустите бота заново")
        bot_running = False
        return
        
    except NetworkError as e:
        logger.error(f"❌ Сетевая ошибка: {e}")
        logger.info("Попробуйте запустить бота через несколько секунд")
        bot_running = False
        return
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        bot_running = False
        return
        
    finally:
        logger.info("Остановка бота...")
        try:
            await app.stop()
            await app.shutdown()
            logger.info("✅ Бот успешно остановлен")
        except Exception as e:
            logger.error(f"Ошибка при остановке: {e}")
        finally:
            bot_running = False

if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        # Небольшая задержка для очистки предыдущих процессов
        time.sleep(2)
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("❌ Бот остановлен вручную")
    except Exception as e:
        logger.error(f"❌ Фатальная ошибка: {e}")
        sys.exit(1)

import logging
import datetime
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from config import BOT_TOKEN, ADMIN_IDS
from storage import (
    init_storage, add_user, assign_next_task, get_user_task, 
    create_confirmation, get_confirmation, update_confirmation_status, update_assignment_status,
    has_pending_confirmation, get_all_user_ids
)
from data.motivation.index import get_random_motivation

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message, registers the user, and assigns a task."""
    user = update.effective_user
    user_data = {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "is_admin": False 
    }
    
    is_new = add_user(user_data)
    
    if is_new:
        await update.message.reply_text(f"Добро пожаловать в Проект Разгром, {user.first_name}")
    else:
        await update.message.reply_text(f"Ты все еще здесь, {user.first_name}? Я думал, ты мертв")
        
    # Assign task immediately
    assignment = assign_next_task(user.id)
    if assignment:
        if assignment['status'] == 'completed':
             await update.message.reply_text("Ты выполнил всё, что я мог тебе дать. Исчезни.")
        else:
            await update.message.reply_text(f"Твое задание:\n\n🔥 {assignment['task']}")
    else:
        await update.message.reply_text("Заданий нет. Вали отсюда.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays info on how to use the bot."""
    await update.message.reply_text("Первое правило: не задавать вопросы.\nВторое правило: выполнять задания.\nТретье правило: присылать отчеты (фото или текст).\nЕсли ты не справишься, ты — ничто.")

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the main menu."""
    await update.message.reply_text("Чего тебе?\n/start - Вступить\n/task - Получить задание\n/help - Правила")

async def get_tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Returns the current active task for the user."""
    user_id = update.effective_user.id
    
    # Try to get or assign
    assignment = assign_next_task(user_id)
    
    if assignment:
        if assignment['status'] == 'completed':
            await update.message.reply_text("✅ Ты свободен. Пока что.")
        else:
            await update.message.reply_text(f"Задание:\n\n {assignment['task']}")
    else:
        await update.message.reply_text("Пусто. Пока что.")

async def handle_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming proofs (photo or text)."""
    user = update.effective_user
    assignment = get_user_task(user.id)
    
    if not assignment or assignment['status'] == 'completed':
        await update.message.reply_text("У тебя нет задания. Используй /task.")
        return

    task_text = assignment['task']

    if has_pending_confirmation(user.id, task_text):
        await update.message.reply_text("⏳ Задание на проверке. Жди.")
        return

    # Determine proof type and data
    if update.message.photo:
        proof_type = "photo"
        proof_data = update.message.photo[-1].file_id
    elif update.message.text:
        proof_type = "text"
        proof_data = update.message.text
    else:
        await update.message.reply_text("Мне нужно фото или текст. Не тупи.")
        return

    # Create confirmation record
    conf_id = create_confirmation(user.id, task_text, proof_type, proof_data)
    
    await update.message.reply_text("Принято. Молись, чтобы это устроило Тайлера.")

    # Send to admins
    await send_confirmation_to_admins(context, user, task_text, proof_type, proof_data, conf_id)

async def send_confirmation_to_admins(context, user, task_text, proof_type, proof_data, conf_id):
    """Sends a confirmation request to all admins."""
    keyboard = [
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{user.id}_{conf_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{user.id}_{conf_id}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    msg_text = f"📩 **Новый участник**\n👤: {user.first_name} (@{user.username})\n📝: {task_text}\n"
    if proof_type == "text":
        msg_text += f"💬: {proof_data}"
    
    for admin_id in ADMIN_IDS:
        try:
            if proof_type == "photo":
                await context.bot.send_photo(chat_id=admin_id, photo=proof_data, caption=msg_text, reply_markup=reply_markup, parse_mode="Markdown")
            else:
                await context.bot.send_message(chat_id=admin_id, text=msg_text, reply_markup=reply_markup, parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Failed to send to admin {admin_id}: {e}")

async def handle_confirmation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles admin approval/rejection."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    # Format: action_userid_confid
    parts = data.split("_")
    if len(parts) != 3:
        await query.answer("Invalid data", show_alert=True)
        return
        
    action, user_id_str, conf_id = parts
    user_id = int(user_id_str)
    
    conf = get_confirmation(user_id, conf_id)
    if not conf:
        await query.edit_message_caption(caption="Ошибка: Не найдено.") if query.message.photo else await query.edit_message_text(text="Ошибка: Не найдено.")
        return
        
    if conf['status'] != 'pending':
        await query.edit_message_caption(caption="Уже решено.") if query.message.photo else await query.edit_message_text(text="Уже решено.")
        return

    admin_user = update.effective_user
    
    if action == "approve":
        update_confirmation_status(user_id, conf_id, "approved", admin_user.id)
        update_assignment_status(user_id, conf['task'], "completed")
        
        # Notify User
        try:
            await context.bot.send_message(chat_id=user_id, text=f"✅ Тайлер доволен. Задание '{conf['task']}' выполнено. Пиши /task, если готов к большему.")
        except Exception:
            pass
            
        new_text = f"✅ **Одобрено** ({admin_user.first_name})\n👤: {user_id}\n📝: {conf['task']}"
        
    elif action == "reject":
        update_confirmation_status(user_id, conf_id, "rejected", admin_user.id)
        
        # Notify User
        try:
            await context.bot.send_message(chat_id=user_id, text=f"❌ Ты облажался. Задание '{conf['task']}' не принято. Переделывай.")
        except Exception:
            pass
            
        new_text = f"❌ **Уничтожено** ({admin_user.first_name})\n👤: {user_id}\n📝: {conf['task']}"

    # Edit Admin Message
    if query.message.photo:
        await query.edit_message_caption(caption=new_text, parse_mode="Markdown")
    else:
        await query.edit_message_text(text=new_text, parse_mode="Markdown")

async def send_daily_motivation(context: ContextTypes.DEFAULT_TYPE):
    """Sends a motivational quote to all users."""
    quote = get_random_motivation()
    user_ids = get_all_user_ids()
    
    for user_id in user_ids:
        try:
            await context.bot.send_message(chat_id=user_id, text=f"📢 **Мысль дня:**\n\n{quote}", parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Failed to send motivation to {user_id}: {e}")

async def resend_pending_confirmations(application):
    """Resends all pending confirmations to admins on startup."""
    user_ids = get_all_user_ids()
    pending_count = 0
    
    for user_id in user_ids:
        confirmations_file = f"data/users/{user_id}/confirmations.json"
        try:
            with open(confirmations_file, 'r', encoding='utf-8') as f:
                confirmations = json.load(f)
        except:
            continue
            
        profile_file = f"data/users/{user_id}/profile.json"
        try:
            with open(profile_file, 'r', encoding='utf-8') as f:
                profile = json.load(f)
        except:
            continue
        
        for conf in confirmations:
            if conf['status'] == 'pending':
                pending_count += 1
                # Create a mock user object
                class MockUser:
                    def __init__(self, uid, uname, fname):
                        self.id = uid
                        self.username = uname
                        self.first_name = fname
                
                user = MockUser(user_id, profile.get('username', 'unknown'), profile.get('first_name', 'User'))
                
                # Send to admins
                await send_confirmation_to_admins(
                    application.bot,
                    user,
                    conf['task'],
                    conf['proof_type'],
                    conf['proof_data'],
                    conf['id']
                )
    
    if pending_count > 0:
        logging.info(f"Resent {pending_count} pending confirmation(s) to admins")

def main():
    """Run the bot."""
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN not found in environment variables.")
        return

    init_storage()
    
    

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("menu", menu))
    application.add_handler(CommandHandler("getTasks", get_tasks_command))
    application.add_handler(CommandHandler("task", get_tasks_command))
    
    # Handler for proofs (Photo or Text, excluding commands)
    application.add_handler(MessageHandler(filters.PHOTO | (filters.TEXT & ~filters.COMMAND), handle_proof))
    
    # Handler for callbacks
    application.add_handler(CallbackQueryHandler(handle_confirmation_callback))
    
    # Daily Motivation Job
    job_queue = application.job_queue
    job_queue.run_daily(send_daily_motivation, time=datetime.time(hour=9, minute=0, second=0))

    # Resend pending confirmations on startup
    async def post_init(app):
        await resend_pending_confirmations(app)
    
    application.post_init = post_init

    application.run_polling()

if __name__ == "__main__":
    main()

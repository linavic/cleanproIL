import os
import requests
import time
import logging
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from keep_alive import keep_alive

# ==========================================
# ⚙️ הגדרות לבוט הניקיון - גרסה מתוקנת Topics
# ==========================================

PROMPT_FILE_NAME = "prompt_cleaning.txt" 

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TARGET_CHANNEL_ID = os.environ.get('TARGET_CHANNEL_ID') 

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# טעינת הפרומפט
try:
    with open(PROMPT_FILE_NAME, 'r', encoding='utf-8') as file:
        SYSTEM_PROMPT = file.read()
except FileNotFoundError:
    SYSTEM_PROMPT = "You are a cleaning service assistant."

chats_history = {}

def send_to_google_direct(history_text, user_text):
    """ שליחה לגוגל - מודל יציב 1.5 """
    model_name = "gemini-1.5-flash" # מודל מהיר ויציב
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": f"{SYSTEM_PROMPT}\n\nהיסטוריה:\n{history_text}\nלקוח: {user_text}\nאני:"}]
        }]
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            print(f"⚠️ Google Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # סינון הודעות מערכת שאינן טקסט
    if not update.message or not update.message.text: return

    user_text = update.message.text
    user_id = update.effective_user.id
    
    # זיהוי מאיזה נושא (Topic) נשלחה ההודעה
    # אם זה צ'אט רגיל, המשתנה יהיה None וזה בסדר
    topic_id = update.message.message_thread_id

    # ניהול היסטוריה
    if user_id not in chats_history: chats_history[user_id] = []
    
    history_txt = ""
    for msg in chats_history[user_id][-6:]:
        history_txt += f"{msg['role']}: {msg['text']}\n"

    # חיווי "מקליד..." בתוך הנושא הנכון
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing', message_thread_id=topic_id)
    
    # שליחה ל-AI
    bot_answer = send_to_google_direct(history_txt, user_text)
    
    if not bot_answer:
        bot_answer = "מצטער, אני מבריק דירה כרגע וקצת עמוס. (תקלה בחיבור לגוגל)"

    # שמירה בהיסטוריה
    chats_history[user_id].append({"role": "לקוח", "text": user_text})
    chats_history[user_id].append({"role": "אני", "text": bot_answer})
    
    # === התיקון הגדול: שליחה בחזרה לאותו Topic ===
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text=bot_answer, 
        message_thread_id=topic_id 
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chats_history[update.effective_user.id] = []
    topic_id = update.message.message_thread_id # זיהוי הנושא
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text="שלום! אני הבוט של Cleaning Pro IL 🧹. איך אפשר לעזור?",
        message_thread_id=topic_id
    )

if __name__ == '__main__':
    keep_alive()
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("🚀 Bot started with Topic support!")
    application.run_polling()
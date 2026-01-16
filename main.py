import os
import requests
import time
import logging
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from keep_alive import keep_alive

# ==========================================
# ⚙️ הגדרות לבוט הניקיון
# ==========================================

PROMPT_FILE_NAME = "prompt_cleaning.txt" 

# קריאת משתני סביבה
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TARGET_CHANNEL_ID = os.environ.get('TARGET_CHANNEL_ID') 

# בדיקה שמפתחות קיימים
if not GEMINI_API_KEY:
    print("❌ שגיאה קריטית: GEMINI_API_KEY חסר בהגדרות השרת!")
if not TELEGRAM_BOT_TOKEN:
    print("❌ שגיאה קריטית: TELEGRAM_BOT_TOKEN חסר בהגדרות השרת!")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# טעינת הפרומפט
try:
    with open(PROMPT_FILE_NAME, 'r', encoding='utf-8') as file:
        SYSTEM_PROMPT = file.read()
    print("✅ קובץ הפרומפט נטען בהצלחה.")
except FileNotFoundError:
    print("⚠️ קובץ הפרומפט לא נמצא, משתמש בברירת מחדל.")
    SYSTEM_PROMPT = "אתה עוזר חכם ושירותי של חברת ניקיון בשם 'Cleaning Pro IL'. התפקיד שלך הוא לעזור ללקוחות לתאם ניקיון, לתת הצעות מחיר ולענות באדיבות ובעברית."

chats_history = {}

def send_to_google_direct(history_text, user_text):
    """ שליחה לגוגל (Direct API) עם טיפול טוב יותר בשגיאות """
    # משתמשים במודל היציב ביותר
    model_name = "gemini-1.5-flash"
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": f"{SYSTEM_PROMPT}\n\nהיסטוריה:\n{history_text}\nלקוח: {user_text}\nאני:"}]
        }]
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        
        # הצלחה
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        
        # שגיאות נפוצות
        else:
            print(f"⚠️ שגיאה בבקשה לגוגל: סטטוס {response.status_code}")
            print(f"תוכן השגיאה: {response.text}") # זה יופיע בלוגים ויעזור לנו להבין מה קרה
            return None

    except Exception as e:
        print(f"❌ שגיאה כללית בחיבור לגוגל: {e}")
        return None

async def check_for_lead(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ זיהוי ליד (טלפון) ושליחה למנהל """
    if not update.message or not update.message.text:
        return

    user_text = update.message.text
    user_name = update.effective_user.first_name
    username = update.effective_user.username
    
    # זיהוי מספר טלפון ישראלי
    phone_pattern = re.compile(r'\b0?5[0-9]{8}\b') 
    clean_text = user_text.replace("-", "").replace(" ", "")
    
    if phone_pattern.search(clean_text):
        print("📞 זוהה ליד ניקיון!")
        alert_text = (
            f"🧹 <b>ליד חדש (ניקיון)!</b>\n"
            f"➖➖➖➖➖➖➖\n"
            f"👤 <b>שם:</b> {user_name}\n"
            f"🔗 <b>יוזר:</b> @{username if username else 'אין'}\n"
            f"📱 <b>הודעה:</b>\n"
            f"<i>{user_text}</i>"
        )
        try:
            if TARGET_CHANNEL_ID:
                await context.bot.send_message(chat_id=TARGET_CHANNEL_ID, text=alert_text, parse_mode='HTML')
            else:
                print("⚠️ לא הוגדר TARGET_CHANNEL_ID בשרת")
        except Exception as e:
            print(f"❌ שגיאה בשליחה לערוץ: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # הגנה מפני הודעות ללא טקסט
    if not update.message or not update.message.text:
        return

    user_text = update.message.text
    user_id = update.effective_user.id
    
    await check_for_lead(update, context)

    if user_id not in chats_history:
        chats_history[user_id] = []

    # בניית היסטוריה קצרה
    history_txt = ""
    for msg in chats_history[user_id][-6:]:
        history_txt += f"{msg['role']}: {msg['text']}\n"

    # חיווי "מקליד..."
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    bot_answer = send_to_google_direct(history_txt, user_text)
    
    # הודעת שגיאה אם ה-AI נכשל
    if not bot_answer:
        bot_answer = "מצטער, אני מבריק דירה כרגע וקצת עמוס. (שגיאת חיבור ל-AI, בדוק לוגים)"

    # שמירה בהיסטוריה
    chats_history[user_id].append({"role": "לקוח", "text": user_text})
    chats_history[user_id].append({"role": "אני", "text": bot_answer})
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_answer)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chats_history[update.effective_user.id] = []
    await context.bot.send_message(chat_id=update.effective_chat.id, text="שלום! אני הבוט של Cleaning Pro IL 🧹. אני כאן כדי לעזור לכם להפוך את הבית למבריק! איך אפשר לעזור?")

if __name__ == '__main__':
    keep_alive()
    
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("🚀 בוט הניקיון יצא לדרך!")
    application.run_polling()
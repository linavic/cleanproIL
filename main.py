import os
import requests
import logging
import re
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from keep_alive import keep_alive

# ==========================================
# ⚙️ הגדרות
# ==========================================
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
ADMIN_ID = 1687054059

MAX_MESSAGES = 3 

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ==========================================
# 🧠 המוח - מכונת מכירות לניקיון
# ==========================================
SYSTEM_PROMPT = """
You are 'Z4U Bot', a sales assistant for a cleaning company.
Goals:
1. Short answers only (Hebrew).
2. Get 3 details: Service Type (Office/Home/Renovation), City, Size (Rooms/Sqm).
3. CRITICAL: After getting basic info, TELL THE USER: "To get an exact price quote, please click the button below 👇".
4. Do NOT give prices yourself.
5. If the user says "Apartment" or "Renovation", ask "How many rooms?".
"""

chats_history = {}

# ==========================================
# 🧠 שליחה ל-AI (גרסה יציבה)
# ==========================================
def send_to_google(history_text, user_text):
    # שימוש במודל המהיר והיציב ביותר כרגע
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": f"{SYSTEM_PROMPT}\n\nChat History:\n{history_text}\nClient: {user_text}\nBot:"}]
        }]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        # בדיקה אם יש תשובה תקינה
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            # הדפסת השגיאה ללוג כדי שנבין מה הבעיה
            print(f"❌ Google Error: {response.status_code} - {response.text}")
            return "כדי לתת הצעת מחיר מדויקת, אנא לחץ על הכפתור למטה 👇 ונציג יחזור אליך מיד."
            
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return "קיבלתי. כדי שנוכל להתקדם להצעת מחיר, אנא לחץ על הכפתור למטה 👇"

# ==========================================
# 📩 לוגיקה וכפתורים
# ==========================================
def get_main_keyboard():
    # כפתור גדול וברור
    return ReplyKeyboardMarkup([[KeyboardButton("📞 קבל הצעת מחיר (לחץ כאן)", request_contact=True)]], resize_keyboard=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    user_text = update.message.text
    user_id = update.effective_user.id
    
    # 1. זיהוי מספר טלפון בתוך הטקסט (למקרה שהלקוח מקליד ידנית)
    phone_pattern = re.compile(r'05\d{1}[- ]?\d{3}[- ]?\d{4}')
    if phone_pattern.search(user_text):
        phone = phone_pattern.search(user_text).group(0)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔥 ליד חם (הקלדה)!\nשם: {update.effective_user.first_name}\nטלפון: {phone}\nהודעה: {user_text}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="תודה! הפרטים נקלטו, נתקשר בדקות הקרובות.", reply_markup=get_main_keyboard())
        return

    # 2. ניהול היסטוריה
    if user_id not in chats_history: chats_history[user_id] = []
    
    # 3. מנגנון קיצור שיחה - אחרי 4 הודעות חותך ישר לכפתור
    if len(chats_history[user_id]) >= 4:
        cut_msg = "יש לי מספיק פרטים. לקבלת המחיר הסופי - לחץ על הכפתור למטה 👇"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=cut_msg, reply_markup=get_main_keyboard())
        # איפוס שיחה כדי לא להיתקע
        chats_history[user_id] = []
        return 

    # בניית היסטוריה לבוט
    history = ""
    for msg in chats_history[user_id][-4:]: history += f"{msg['role']}: {msg['text']}\n"

    # חיווי הקלדה
    if update.effective_chat.type == 'private':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # שליחה לגוגל
    bot_answer = send_to_google(history, user_text)
    
    # שמירה בהיסטוריה
    chats_history[user_id].append({"role": "user", "text": user_text})
    chats_history[user_id].append({"role": "model", "text": bot_answer})
    
    # שליחת תש

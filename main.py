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
ADMIN_ID = 1687054059  # וודא שזה ה-ID שלך לקבלת הלידים

MAX_MESSAGES = 3 

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ==========================================
# 🧠 המוח (מותאם ל-Z4U CLEANING)
# ==========================================
SYSTEM_PROMPT = """
You are the smart representative for 'Z4U CLEANING SERVICES'.
Your Services: Office cleaning, Carpet cleaning, Pre-occupancy cleaning (Deep cleaning before moving in).
Goal: Ask clarifying questions to understand the client's cleaning needs to prepare a quote.
RULES:
1. NEVER ask for a phone number in the first 3 turns.
2. If the user asks for a price, explain that it depends on the size (sqm) and condition, and ask for details.
3. Ask: "What needs cleaning? (Office/Apartment/Carpet)", "How many rooms/sqm?", "Where is the location?".
4. Be short, professional, and Hebrew speaking.
"""

chats_history = {}
current_model_url = ""

# ==========================================
# 🔍 סורק מודלים
# ==========================================
def find_working_model():
    global current_model_url
    possible_urls = [
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
        f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}",
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    ]
    for url in possible_urls:
        try:
            if requests.post(url, json={"contents": [{"parts": [{"text": "."}]}]}, timeout=5).status_code == 200:
                current_model_url = url
                print(f"✅ מודל: {url}")
                return
        except: continue
    current_model_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"

find_working_model()

# ==========================================
# 🧠 שליחה ל-AI
# ==========================================
def send_to_google(history_text, user_text):
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": f"{SYSTEM_PROMPT}\n\nהיסטוריה:\n{history_text}\nלקוח: {user_text}\nאני:"}]
        }]
    }
    try:
        response = requests.post(current_model_url, json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        
        # fallback אם יש שגיאה בגוגל - מותאם לניקיון
        return "רשמתי לפני. איזה סוג ניקיון אתם צריכים? (משרדים / לפני אכלוס / שטיחים)?"
    except:
        return "אני מקשיב. מה גודל הנכס או המשרד שצריך לנקות?"

# ==========================================
# 📩 לוגיקה
# ==========================================
def get_main_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("📞 שלח מספר להצעת מחיר", request_contact=True)]], resize_keyboard=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    if update.effective_user.id == 777000: return

    user_text = update.message.text
    user_id = update.effective_user.id
    
    # זיהוי טלפון
    phone_pattern = re.compile(r'05\d{1}[- ]?\d{3}[- ]?\d{4}')
    if phone_pattern.search(user_text):
        phone = phone_pattern.search(user_text).group(0)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 ליד בטקסט (Z4U)!\n{phone}\n{user_text}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="תודה! הפרטים הועברו לצוות Z4U, נחזור אליך בהקדם.", reply_markup=get_main_keyboard())
        return

    # היסטוריה
    if user_id not in chats_history: chats_history[user_id] = []
    
    # חיתוך לשיחה אנושית
    if len(chats_history[user_id]) >= (MAX_MESSAGES * 2):
        cut_msg = "תודה על הפרטים! כדי שנוכל לתת הצעת מחיר מדויקת ולשריין תאריך, אנא לחץ למטה 👇"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=cut_msg, reply_markup=get_main_keyboard())
        return 

    history = ""
    for msg in chats_history[user_id][-6:]: history += f"{msg['role']}: {msg['text']}\n"

    if update.effective_chat.type == 'private':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    bot_answer = send_to_google(history, user_text)
    
    chats_history[user_id].append({"role": "user", "text": user_text})
    chats_history[user_id].append({"role": "model", "text": bot_answer})
    
    if update.effective_chat.type == 'private':
        await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_answer, reply_markup=get_main_keyboard())
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_answer, reply_to_message_id=update.message.message_id)

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = update.message.contact
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 ליד כפתור (Z4U)!\n{c.phone_number}")
    await context.bot.send_message(chat_id=update.effective_chat.id, text="תודה! הועבר לטיפול צוות הניקיון.", reply_markup=get_main_keyboard())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chats_history[update.effective_user.id] = []
    # הודעת פתיחה מותאמת לניקיון
    welcome_msg = "שלום, אני הבוט של Z4U CLEANING SERVICES 🧹\nאנו מתמחים בניקיון משרדים, ניקוי שטיחים וניקיון לפני אכלוס.\nאיך אוכל לעזור לך היום?"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome_msg, reply_markup=get_main_keyboard())

if __name__ == '__main__':
    keep_alive()
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("✅ הבוט של Z4U מוכן לעבודה...")
    app.run_polling(drop_pending_updates=True)
  


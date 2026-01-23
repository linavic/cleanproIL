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

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ==========================================
# 🧠 מוח גיבוי (עובד גם בלי גוגל!)
# ==========================================
def solve_locally(text):
    # מזהה מילות מפתח ועונה מיד בלי לחכות לגוגל
    t = text.replace("?", "").replace("!", "").strip()
    
    if any(x in t for x in ["משרד", "משרדים", "עסק"]):
        return "מעולה. באיזו עיר המשרד וכמה מטר בערך הוא?"
    
    if any(x in t for x in ["דירה", "בית", "פרטי", "שיפוץ", "טופס 4", "לפני אכלוס"]):
        return "הבנתי. כמה חדרים הדירה? (3, 4, 5?)"
        
    if any(x in t for x in ["שטיח", "ספה", "ריפוד"]):
        return "אנחנו מומחים בזה. תוכל לשלוח תמונה או לתאר את הגודל?"
        
    if any(x in t for x in ["מחיר", "כמה עולה", "עלות"]):
        return "המחיר תלוי בגודל. כדי לתת הצעה מדויקת - לחץ על הכפתור למטה 👇"
        
    return None # אם לא זוהה כלום, ננסה את גוגל

# ==========================================
# 🧠 שליחה ל-AI (עם הגנה כפולה)
# ==========================================
SYSTEM_PROMPT = "You represent Z4U Cleaning. Short answers in Hebrew. Ask for size/location. Always end by asking to click the button for quote."

def send_to_google(history_text, user_text):
    # ניסיון 1: מוח גיבוי מקומי
    local_answer = solve_locally(user_text)
    if local_answer:
        return local_answer

    # ניסיון 2: שליחה לגוגל
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": f"{SYSTEM_PROMPT}\nHistory:\n{history_text}\nUser: {user_text}\nBot:"}]
        }]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            print(f"⚠️ Google Error: {response.status_code}")
            return "כדי לקבל הצעת מחיר מדויקת ומהירה, אנא לחץ על הכפתור למטה 👇"
            
    except Exception as e:
        print(f"⚠️ Connection Error: {e}")
        # הודעה שלא יוצרת לופ
        return "הפרטים נקלטו. להצעת מחיר סופית לחץ על הכפתור למטה 👇"

# ==========================================
# 📩 לוגיקה
# ==========================================
def get_main_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("📞 לחץ כאן להצעת מחיר", request_contact=True)]], resize_keyboard=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    user_text = update.message.text

    # בדיקת ליד מהיר (מספר טלפון בטקסט)
    phone_pattern = re.compile(r'05\d{8}')
    if phone_pattern.search(user_text.replace("-", "")):
        phone = phone_pattern.search(user_text.replace("-", "")).group(0)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔥 ליד בהקלדה!\n{phone}\n{user_text}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="תודה! נחזור אליך מיד.", reply_markup=get_main_keyboard())
        return

    # חיווי הקלדה
    if update.effective_chat.type == 'private':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # שליחה לפונקציה החכמה
    bot_answer = send_to_google("", user_text)
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_answer, reply_markup=get_main_keyboard())

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = update.message.contact
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"💰 ליד כפתור!\n{c.phone_number}\n{c.first_name}")
    await context.bot.send_message(chat_id=update.effective_chat.id, text="תודה! הפנייה הועברה, נתקשר בקרוב.", reply_markup=get_main_keyboard())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_msg = "ברוכים הבאים ל-Z4U! 🧹\nאנחנו מבצעים ניקיון משרדים, דירות לפני אכלוס ושטיחים.\n\nמה תרצו לנקות היום?"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome_msg, reply_markup=get_main_keyboard())

if __name__ == '__main__':
    keep_alive()
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("✅ הבוט (גרסת גיבוי) באוויר!")
    app.run_polling(drop_pending_updates=True)

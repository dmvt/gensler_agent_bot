import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import openai
import os
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Initialize OpenAI client once with async client
client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)

def load_prompt(filename):
    try:
        with open(os.path.join('prompts', filename), 'r') as f:
            return f.read().strip() 
    except Exception as e:
        logger.error(f"Error loading prompt {filename}: {str(e)}")
        return "Error loading prompt"

PERSONAS = {
    "CZ": load_prompt('cz.txt'),
    "SBF": load_prompt('sbf.txt'),
    "GENSLER": load_prompt('gensler.txt')
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data[f'mode_{user_id}'] = 'GENSLER'  # Set default mode for new user
    await update.message.reply_text(
        "I'm your compliance agent. Use /mode [CZ|SBF|GENSLER] to change personas. Default is Gensler."
    )

async def set_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    current_mode = context.user_data.get(f'mode_{user_id}', 'GENSLER')
    
    if not context.args:
        await update.message.reply_text(f"Current mode: {current_mode}\nTo change, specify a mode: CZ, SBF, or GENSLER")
        return
    
    mode = context.args[0].upper()
    if mode not in PERSONAS:
        await update.message.reply_text(f"Invalid mode. Current mode: {current_mode}\nValid options: CZ, SBF, or GENSLER")
        return
        
    context.user_data[f'mode_{user_id}'] = mode
    logger.info(f"User {user_id} set mode to {mode}")
    await update.message.reply_text(f"Mode set to {mode}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mode = context.user_data.get(f'mode_{user_id}', 'GENSLER')
    logger.info(f"Processing message from user {user_id} in {mode} mode: {update.message.text}")
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": PERSONAS[mode]},
                {"role": "user", "content": update.message.text}
            ]
        )
        if mode == 'SBF':
            logger.info(f"Response from OpenAI for user {user_id}: {response.choices[0].message.content}")
            response.choices[0].message.content = '\n\n'.join(response.choices[0].message.content.split('\n\n')[:-1])
            logger.info(f"Response from OpenAI updated for user {user_id}: {response.choices[0].message.content}")
        logger.info(f"Got response from OpenAI for user {user_id}")
        await update.message.reply_text(response.choices[0].message.content)
    except Exception as e:
        logger.error(f"Error processing message for user {user_id}: {str(e)}", exc_info=True)
        await update.message.reply_text("Sorry, I encountered an error processing your message.")

def main():
    try:
        logger.info("Starting bot...")
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("mode", set_mode))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        logger.info("Bot is ready to start polling")
        application.run_polling()
    except Exception as e:
        logger.error(f"Error in main: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main() 
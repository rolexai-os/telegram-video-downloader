"""Example opt-in plugin. Copy/modify only after reviewing its code."""
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text("👋 Hello from the optional plugin system!")


def register(app: Application, bot_module, runner_module) -> None:
    """Called by plugin_manager when ENABLE_PLUGINS=1."""
    app.add_handler(CommandHandler("pluginhello", hello))

from typing import Dict, List
import traceback
import json
import re
import functools
import asyncio
import concurrent
import time
from pytimeparse.timeparse import timeparse
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, Chat, ChatMember, ChatPermissions
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    CallbackContext,
    MessageHandler,
    PicklePersistence,
)
from telegram.ext.filters import Filters

import checker
from handlers import FilteredConversationHandler, ReadHandler
import filters

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG
)

logger = logging.getLogger(__name__)

help_string = """/start - start conversation with bot
/help - print help
/configure - start configuration wizzard"""

def print_help(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(help_string, disable_notification=True)

def start(update: Update, context: CallbackContext) -> None:
    if update.effective_chat.type not in [Chat.GROUP, Chat.SUPERGROUP]:
        update.message.reply_text("Hello, I'm Detoxification bot. I can help you to deal with tox in your chat. You should add me there first.", disable_notification=True)
    else:
        update.message.reply_text("Hello, I'm Detoxification bot. I can help you to deal with tox in this chat." + '\n' + help_string, disable_notification=True)



class Rule():
    def __init__(self, rule: Dict):
        self.warn = str(rule["warn"]) if "warn" in rule else ""
        self.delete = bool(int(rule["delete"])) if "delete" in rule else 0
        self.mute_time = timeparse(rule["mute_time"], "%Hh%Mm%Ss") if "mute_time" in rule else 0
        self.ban_time = timeparse(rule["ban_time"], "%Hh%Mm%Ss") if "ban_time" in rule else 0
        self.reset_time = timeparse(rule["reset_time"], "%Hh%Mm%Ss") if "reset_time" in rule else 0
    def print(self):
        result = dict()
        if self.warn:
            result["warn"] = self.warn
        if self.delete:
            result["delete"] = self.delete
        if self.mute_time:
            result["mute_time"] = self.mute_time
        if self.ban_time:
            result["ban_time"] = self.ban_time
        if self.reset_time:
            result["reset_time"] = self.reset_time
        return result

default_rules = [Rule({"warn": "This is too toxic!"})]
default_tox_level = 0.4

def process_msg(update: Update, context: CallbackContext) -> None:
    message = update.message if update.message else update.edited_message
    score = checker.score(message.text)
    logger.info("Processing message")
    chat = update.effective_chat
    member = chat.get_member(update.effective_user.id)
    is_admin = member.status in [ChatMember.CREATOR, ChatMember.ADMINISTRATOR]
    data = context.chat_data
    rule_name = "rules_" + ("admin" if is_admin else "user")
    rules = data[rule_name] if rule_name in data else default_rules
    state = data[member.user.id] if member.user.id in data else (0, 0) # time and current rule to apply index
    last_time_applied, current_rule = state
    if len(rules) == 0:
        return
    rule = rules[current_rule]
    #score = await score
    tox_level = data["tox_level"] if "tox_level" in data else default_tox_level
    if score < tox_level:
        return

    if time.time() - last_time_applied > rule.reset_time:
        current_rule = 0
    if rule.warn != "":
        message.reply_text(((member.user.username + " ") if rule.delete else "") + rule.warn.replace("{score}", str(int(score * 100))))
    if rule.delete:
        message.delete()
    if rule.mute_time:
        chat.restrict_member(member.user.id, ChatPermissions(can_send_messages=False), until_date=int(time.time()) + rule.mute_time)
    if rule.ban_time:
        chat.ban_member(member, until_date=time.time() + rule.ban_time)
    current_rule = min(current_rule + 1, len(rules) - 1)
    data[member.user.id] = (time.time(), current_rule)

class State:
    (CONFIG,
    CONFIG_LEVEL,
    CONFIG_RULES_USER,
    CONFIG_RULES_ADMIN) = range(4)

def configure(update: Update, context: CallbackContext, quote=None, first=True):
    if update.effective_chat.type not in [Chat.GROUP, Chat.SUPERGROUP]:
        update.message.reply_text("You can configure me only in groups or supergroups.", disable_notification=True)
        return ConversationHandler.END

    chat = update.effective_chat
    member = chat.get_member(update.effective_user.id)
    is_admin = member.status in [ChatMember.CREATOR, ChatMember.ADMINISTRATOR]

    if not is_admin:
        update.message.reply_text("Only administrator can configure bot.")

    keyboard = [
        [InlineKeyboardButton("Tox level", callback_data=str(State.CONFIG_LEVEL))],
        [InlineKeyboardButton("Rules for users", callback_data=str(State.CONFIG_RULES_USER))],
        [InlineKeyboardButton("Rules for admins", callback_data=str(State.CONFIG_RULES_ADMIN))],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message or first:
        update.message.reply_text("What do you want to configure?", reply_markup=reply_markup, quote=quote, disable_notification=True)
    elif update.callback_query:
        update.callback_query.answer()
        update.callback_query.message.edit_text("What do you want to configure?")
        update.callback_query.message.edit_reply_markup(reply_markup)
        #update.callback_query.message.reply_text("What do you want to configure next?", reply_markup=reply_markup, quote=quote, disable_notification=True)
    return State.CONFIG

def set_level(update: Update, context: CallbackContext, cancel_data=None) -> bool:
    msg = None
    text = None
    quote = None
    if update.message:
        msg = update.message
        text = msg.text
    else:
        quote = False
        msg = update.callback_query.message
        text = update.callback_query.data.rsplit('_', 1)[0]
    if text == "cancel" or text.startswith("/cancel"):
        configure(update, context, False, False)
        return True
    if not text.isdigit() or 0 > int(text) or int(text) > 100:
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data=cancel_data)]]) if cancel_data else None
        msg.reply_text("Invalid value. Must be integer from 0 to 100. You may try again.", reply_markup=reply_markup, quote=quote, disable_notification=True)
    else:
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Continue configuration", callback_data=str(State.CONFIG))]])
        context.chat_data["tox_level"] = int(text) / 100
        msg.reply_text("Tox level is now " + text, reply_markup=reply_markup, quote=quote, disable_notification=True)
        return True
    return False

quotes = [
   #Windows codepage 1252
   "\xC2\x82",
   "\xC2\x84",
   "\xC2\x8B",
   "\xC2\x91",
   "\xC2\x92",
   "\xC2\x93",
   "\xC2\x94",
   "\xC2\x9B",

   #Regular Unicode     
   "\xC2\xAB",
   "\xC2\xBB",
   "\xE2\x80\x98",
   "\xE2\x80\x99",
   "\xE2\x80\x9A",
   "\xE2\x80\x9B",
   "\xE2\x80\x9C",
   "\xE2\x80\x9D",
   "\xE2\x80\x9E",
   "\xE2\x80\x9F",
   "\xE2\x80\xB9",
   "\xE2\x80\xBA",
   "“",
   "”",
   "‘",
   "’",
   "'",
]

def parse_rules(text: str) -> List[Rule]:
    try:
        rules = []
        text = ''.join(["\"" if char in quotes else char for char in text])
        text = re.sub("&quot", "\"", text)
        for rule in json.loads(text):
            rules.append(Rule(rule))
        return rules
    except:
        traceback.print_exc()
        return None

def print_rules(rules: List[Rule]) -> str:
    return json.dumps([rule.print() for rule in rules])

def set_rules_user(update: Update, context: CallbackContext, cancel_data=None) -> bool:
    msg = None
    text = None
    quote = None
    if update.message:
        msg = update.message
        text = msg.text
    else:
        quote = False
        msg = update.callback_query.message
        text = update.callback_query.data.rsplit('_', 1)[0]
    if text == "cancel" or text.startswith("/cancel"):
        configure(update, context, False, False)
        return True
    rules = parse_rules(text)
    if rules == None:
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data=cancel_data)]]) if cancel_data else None
        msg.reply_text("Invalid value.", reply_markup=reply_markup, quote=quote, disable_notification=True)
    else:
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Continue configuration", callback_data=str(State.CONFIG))]])
        context.chat_data["rules_user"] = rules
        msg.reply_text("User rules set to " + print_rules(context.chat_data["rules_user"]), reply_markup=reply_markup, quote=quote, disable_notification=True)
        return True
    return False

def set_rules_admin(update: Update, context: CallbackContext, cancel_data=None) -> bool:
    msg = None
    text = None
    quote = None
    if update.message:
        msg = update.message
        text = msg.text
    else:
        quote = False
        msg = update.callback_query.message
        text = update.callback_query.data.rsplit('_', 1)[0]
    if text == "cancel" or text.startswith("/cancel"):
        configure(update, context, False, False)
        return True
    rules = parse_rules(text)
    if rules == None:
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data=cancel_data)]]) if cancel_data else None
        msg.reply_text("Invalid value.", reply_markup=reply_markup, quote=quote, disable_notification=True)
    else:
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Continue configuration", callback_data=str(State.CONFIG))]])
        context.chat_data["rules_admin"] = rules
        msg.reply_text("User rules set to " + print_rules(context.chat_data["rules_admin"]), reply_markup=reply_markup, quote=quote, disable_notification=True)
        return True
    return False


def cancel(update: Update, context: CallbackContext):
    if update.callback_query: update.callback_query.answer()
    configure(update, context, quote=False)
    return State.CONFIG

def empty_handler(update: Update, context: CallbackContext):
    if update.callback_query:
        update.callback_query.answer()

def main() -> None:
    """Run the bot."""
    
    checker.load("./model")
    persistence = PicklePersistence("state")
    # Create the Updater and pass it your bot's token.
    updater = Updater("5011312596:AAGF2Kkc4rFUM-K9Oql1i9nlprCm1HeothQ", persistence=persistence)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher
    #dispatcher.start()

    dispatcher.add_handler(CommandHandler('start', start, run_async=True))
    dispatcher.add_handler(CommandHandler('help', print_help, run_async=True))

    config_handler = FilteredConversationHandler(
        entry_points=[CommandHandler("configure", configure)],
        states={
            State.CONFIG: [
                CallbackQueryHandler(functools.partial(configure, first=False, quote=False), pattern='^' + str(State.CONFIG) + '$'),
                ReadHandler(set_level, lambda update, context: "Current tox level is "
                    + str(int((context.chat_data['tox_level'] if 'tox_level' in context.chat_data else default_tox_level) * 100)) + ". "
                    + "You can now send a new one.", '^' + str(State.CONFIG_LEVEL) + '$',
                    [[10, 20, 30], [40, 50, 60, 70], [80, 90, 100]], State.CONFIG),
                ReadHandler(set_rules_user, lambda update, context: "Current rules are: "
                    + print_rules(context.chat_data["rules_user"] if "rules_user" in context.chat_data else default_rules)
                    + "\nYou can now enter new list of rules in json format. Each rule is represented as dict with the following keys:\n"
                    + "'warn': str - the message which will be sent as reply to toxic messages, you can use {score} to print the score of the message\n"
                    + "'delete': (0|1) - whather bot will delete toxic messages or not\n"
                    + "'mute_time': time(%Hh%Mm%Ss) - time for which author of toxic message will be muted\n"
                    + "'ban_time': time(%Hh%Mm%Ss) - time for which author of toxic message will be banned\n"
                    + "'reset_time': time(%Hh%Mm%Ss) - time after current rule for user will be reset to the first one",
                    '^' + str(State.CONFIG_RULES_USER) + '$', [], State.CONFIG),
                ReadHandler(set_rules_admin, lambda update, context: "Current rules are: "
                    + print_rules(context.chat_data["rules_admin"] if "rules_admin" in context.chat_data else default_rules)
                    + "\nYou can now enter new list of rules in json format. Each rule is represented as dict with the following keys:\n"
                    + "'warn': str - the message which will be sent as reply to toxic messages, you can use {score} to print the score of the message\n"
                    + "'delete': (0|1) - whather bot will delete toxic messages or not\n"
                    + "'mute_time': time(%Hh%Mm%Ss) - time for which author of toxic message will be muted\n"
                    + "'ban_time': time(%Hh%Mm%Ss) - time for which author of toxic message will be banned\n"
                    + "'reset_time': time(%Hh%Mm%Ss) - time after current rule for admin will be reset to the first one",
                    '^' + str(State.CONFIG_RULES_ADMIN) + '$', [], State.CONFIG)
            ],
        },
        fallbacks=[],
        allow_reentry=True,
        per_user=False,
        name="configuration_handler",
        persistent=True,
        run_async=False,
        filters=[filters.AdminFilter],
    )

    dispatcher.add_handler(config_handler)

    dispatcher.add_handler(MessageHandler((Filters.update.message | Filters.update.edited_message) & Filters.text
        & (Filters.chat_type.group | Filters.chat_type.supergroup), process_msg, run_async=False))

    dispatcher.add_handler(CallbackQueryHandler(empty_handler))

    updater.start_polling()

    updater.idle()


if __name__ == '__main__':
    main()

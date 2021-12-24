from typing import Callable, Any, Dict, List, Union, Optional, Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, Chat, ChatMember, ChatPermissions, Message
from telegram.ext import (
    Handler,
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    CallbackContext,
    MessageHandler,
    filters,
)

from telegram.ext.utils.types import CCT
CheckUpdateType = Optional[Tuple[Tuple[int, ...], Handler, object]]

import uuid
import datetime

class FilteredConversationHandler(ConversationHandler):
    def __init__(
        self,
        entry_points: List[Handler[Update, CCT]],
        states: Dict[object, List[Handler[Update, CCT]]],
        fallbacks: List[Handler[Update, CCT]],
        allow_reentry: bool = False,
        per_chat: bool = True,
        per_user: bool = True,
        per_message: bool = False,
        conversation_timeout: Union[float, datetime.timedelta] = None,
        name: str = None,
        persistent: bool = False,
        map_to_parent: Dict[object, object] = None,
        run_async: bool = False,
        filters: List[filters.BaseFilter] = [],
    ):
        self.filters = filters
        super().__init__(
            entry_points,
            states,
            fallbacks,
            allow_reentry,
            per_chat,
            per_user,
            per_message,
            conversation_timeout,
            name,
            persistent,
            map_to_parent,
            run_async,
        )
    def check_update(self, update: object) -> CheckUpdateType:
        for f in self.filters:
            if not f(update):
                return None
        return super().check_update(update)

def ReadHandler(process: Callable[[Update, CallbackContext], Any], gen_query=lambda update, context: "", pattern=None, choices=[], ret=None):
    def callback(update: Update, context: CallbackContext):
        if update.callback_query:
            update.callback_query.answer()
        if process(update, context, "cancel_readhandler"):
            return ConversationHandler.END
    keyboard = []
    for row in choices:
        krow = []
        for choice in row:
            krow.append(InlineKeyboardButton(str(choice), callback_data=str(choice) + "_readhandler"))
        keyboard.append(krow)
    keyboard.append([InlineKeyboardButton("Back", callback_data=str("cancel_readhandler"))])
    def init(update: Update, context: CallbackContext):
        update.callback_query.answer()
        query = gen_query(update, context)
        if query:
            if update.callback_query:
                update.callback_query.message.edit_text(query)
                update.callback_query.message.edit_reply_markup(InlineKeyboardMarkup(keyboard))
            else:
                update.effective_chat.send_message(query, reply_markup=InlineKeyboardMarkup(keyboard))
        return 0
    handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(init, pattern=pattern)],
        states={
            0: [
                MessageHandler(filters.Filters.update.message, callback),
                CommandHandler("cancel", callback),
                CallbackQueryHandler(callback, pattern=lambda msg: msg.endswith("_readhandler")),
                CallbackQueryHandler(init, pattern=pattern)
            ]
        },
        fallbacks=[],
        map_to_parent={
            ConversationHandler.END: ret,
        },
        name="ReadHandler:" + str(pattern if pattern else ""),
        per_user=False,
        persistent=True,
    )
    return handler

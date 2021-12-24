from telegram import Update, Chat, ChatMember

def AdminFilter(update: Update): # Only for use with FilteredConversationHandler
    chat = update.effective_chat
    if chat.type not in [Chat.GROUP, Chat.SUPERGROUP]:
        return True
    member = chat.get_member(update.effective_user.id)
    return member.status in [ChatMember.CREATOR, ChatMember.ADMINISTRATOR]

# models/__init__.py
from .user import User
from .checkin import CheckIn, CheckInItem
from .checkin_file import CheckInFile
from .work_order_draft import WorkOrderDraft
from .chat import ChatSession, ChatMessage
from .embeddings import CustomerEmbedding, WorkOrderEmbedding, ItemEmbedding

# Optional: add the renamed files with spaces if needed
# from .Name_AutoCorrect_Log import NameAutoCorrectLog
# from .Paste_Errors import PasteErrors
# from .Switchboard_Items import SwitchboardItems

__all__ = [
    "User",
    "CheckIn",
    "CheckInItem",
    "CheckInFile",
    "WorkOrderDraft",
    "ChatSession",
    "ChatMessage",
    "CustomerEmbedding",
    "WorkOrderEmbedding",
    "ItemEmbedding",
]

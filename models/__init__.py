# models/__init__.py
from .user import User
from .checkin import CheckIn, CheckInItem

# Optional: add the renamed files with spaces if needed
# from .Name_AutoCorrect_Log import NameAutoCorrectLog
# from .Paste_Errors import PasteErrors
# from .Switchboard_Items import SwitchboardItems

__all__ = ["User", "CheckIn", "CheckInItem"]

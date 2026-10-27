# Log2 Alfa CmdHelp — yardım bilgisi saklar — Pyrogram için sadece yardım bilgisi saklar, hata vermez
from userbot import PATTERNS, CMD_HELP, CMD_HELP_BOT

class CmdHelp:
    FILE = ""
    ORIGINAL_FILE = ""
    FILE_AUTHOR = ""
    IS_OFFICIAL = True
    COMMANDS = {}
    PREFIX = PATTERNS[:1] if PATTERNS else "."
    WARNING = ""
    INFO = ""

    def __init__(self, file: str, official: bool = True, file_name: str = None):
        self.FILE = file
        self.ORIGINAL_FILE = file
        self.IS_OFFICIAL = official
        self.FILE_NAME = file_name if file_name is not None else file + '.py'
        self.COMMANDS = {}
        self.FILE_AUTHOR = ""
        self.WARNING = ""
        self.INFO = ""

    def set_file_info(self, name: str, value: str):
        if name == 'name':
            self.FILE = value
        elif name == 'author':
            self.FILE_AUTHOR = value
        return self

    def add_command(self, command: str, params=None, usage: str = '', example=None):
        self.COMMANDS[command] = {'command': command, 'params': params, 'usage': usage, 'example': example}
        return self

    def add_warning(self, warning):
        self.WARNING = warning
        return self

    def add_info(self, info):
        self.INFO = info
        return self

    def get_result(self):
        result = f"**📗 Dosya:** `{self.FILE}`\n"
        if self.WARNING == '' and self.INFO == '':
            result += f"**⬇️ Official:** {'✅' if self.IS_OFFICIAL else '❌'}\n\n"
        else:
            result += f"**⬇️ Official:** {'✅' if self.IS_OFFICIAL else '❌'}\n"
            if self.INFO == '':
                if not self.WARNING == '':
                    result += f"**⚠️ Uyarı:** {self.WARNING}\n\n"
            else:
                if not self.WARNING == '':
                    result += f"**⚠️ Uyarı:** {self.WARNING}\n"
                result += f"**ℹ️ Info:** {self.INFO}\n\n"
        for command in self.COMMANDS:
            command = self.COMMANDS[command]
            if command['params'] is None:
                result += f"**🛠 Komut:** `{self.PREFIX}{command['command']}`\n"
            else:
                result += f"**🛠 Komut:** `{self.PREFIX}{command['command']} {command['params']}`\n"
            if command['example'] is None:
                result += f"**💬 Açıklama:** `{command['usage']}`\n\n"
            else:
                result += f"**💬 Açıklama:** `{command['usage']}`\n"
                result += f"**⌨️ Örnek:** `{self.PREFIX}{command['example']}`\n\n"
        return result

    def add(self):
        CMD_HELP_BOT[self.FILE] = {'info': {'official': self.IS_OFFICIAL, 'warning': self.WARNING, 'info': self.INFO}, 'commands': self.COMMANDS}
        CMD_HELP[self.FILE] = self.get_result()
        return True

    def getText(self, text: str):
        if text == 'REPLY_OR_USERNAME':
            return '<kullanıcı adı> <kullanıcı adı/yanıtlama>'
        elif text == 'OR':
            return 'veya'
        elif text == 'USERNAMES':
            return '<kullanıcı ad(lar)ı>'

"""
Log2 Alfa uyumluluk shim — Pyrogram için (eski Asena shim'i korunuyor)
Her türlü `from userbot.* import` sorunsuz çalışsın
"""
import os
import sys
import types

PATTERNS = os.getenv("PLUGIN_PATTERN", ".")
CMD_HELP = {}
CMD_HELP_BOT = {}
BOTLOG_CHATID = None
LOGSPAMMER = False
# Bazı eski pluginler bunları da bekler
BOTLOG = False
LOGGING = False
LANG = "TR"
DB_URI = os.getenv("DATABASE_URL") or os.getenv("DB_URI") or "sqlite:///log2alfa.db"
# LOGS için logger
import logging as _logging
LOGS = _logging.getLogger("userbot")
if not LOGS.handlers:
    _logging.basicConfig(level=_logging.INFO)

class _DummyBot:
    def add_event_handler(self, *a, **kw):
        pass
    async def send_message(self, *a, **kw): pass
    async def send_file(self, *a, **kw): pass

class _BotProxy:
    """bot/borg proxy — gerçek Pyrogram app'e yönlendir, yoksa dummy"""
    def _resolve(self):
        # 1) _current_app set edilmişse
        if _current_app is not None:
            return _current_app
        # 2) userbot_core.active_userbots içindeki ilk bağlı app
        try:
            import userbot_core as _uc
            if getattr(_uc, "active_userbots", None):
                for _app in _uc.active_userbots.values():
                    try:
                        if _app and getattr(_app, "is_connected", False):
                            return _app
                    except Exception:
                        continue
                # bağlı yoksa herhangi birini döndür
                for _app in _uc.active_userbots.values():
                    if _app:
                        return _app
        except Exception:
            pass
        return None

    def __getattr__(self, name):
        # Telethon conversation shim — bot.conversation(chat) async context manager
        if name == "conversation":
            # bot.conversation(chat) -> async context manager with send_message, wait_event
            def _conv_factory(chat, **kw):
                # chat can be str username or int
                class _Conv:
                    def __init__(self, chat):
                        self.chat = chat
                        self.chat_id = None
                        # try to resolve chat_id
                        try:
                            # if chat is str like "@DeezerMusicBot", keep as is
                            self._chat_arg = chat
                        except:
                            self._chat_arg = chat
                    async def __aenter__(self):
                        # resolve chat_id when entering
                        try:
                            app = self._resolve_app()
                            if app:
                                try:
                                    c = await app.get_chat(self._chat_arg)
                                    self.chat_id = c.id
                                except:
                                    # fallback: if chat is "@xxx", keep string
                                    self.chat_id = self._chat_arg
                        except:
                            pass
                        return self
                    async def __aexit__(self, exc_type, exc, tb):
                        pass
                    def _resolve_app(self):
                        try:
                            # use _BotProxy's _resolve
                            # create temp proxy to resolve
                            import userbot_core as _uc
                            if getattr(_uc, "active_userbots", None):
                                for _app in _uc.active_userbots.values():
                                    if _app and getattr(_app, "is_connected", False):
                                        return _app
                                for _app in _uc.active_userbots.values():
                                    if _app:
                                        return _app
                        except:
                            pass
                        return None
                    async def send_message(self, text, **kw):
                        app = self._resolve_app()
                        if app and self.chat_id:
                            try:
                                return await app.send_message(self.chat_id, text, **kw)
                            except Exception as e:
                                print(f"conv send_message hata: {e}", flush=True)
                        return None
                    async def wait_event(self, event, **kw):
                        # event is telethon.events.NewMessage(incoming=True, from_users=...)
                        # Extract from_users
                        target_uid = None
                        try:
                            # telethon NewMessage stores from_users
                            target_uid = getattr(event, "from_users", None) or getattr(event, "from_user", None)
                            if isinstance(target_uid, (list, tuple, set)):
                                target_uid = list(target_uid)[0] if target_uid else None
                        except:
                            pass
                        app = self._resolve_app()
                        if not app or not self.chat_id:
                            await asyncio.sleep(2)
                            return None
                        # Poll for new message from target user (max 15s)
                        import asyncio as _asyncio
                        for _ in range(15):
                            try:
                                async for msg in app.get_chat_history(self.chat_id, limit=5):
                                    # check if from target user
                                    try:
                                        f_id = getattr(msg.from_user, "id", None) if msg.from_user else None
                                        if target_uid and f_id == int(target_uid):
                                            return msg
                                        # if no target, return first
                                        if not target_uid and msg:
                                            return msg
                                    except:
                                        pass
                                await _asyncio.sleep(1)
                            except Exception as e:
                                print(f"conv wait_event hata: {e}", flush=True)
                                await _asyncio.sleep(1)
                        return None
                    async def get_response(self, **kw):
                        return await self.wait_event(None)
                return _Conv(chat)
            return _conv_factory
        # Telethon bot.on / borg.on — Asena pending'e ekle (Pyrogram'a çevrilecek)
        if name == "on":
            def _on_decorator(*a, **kw):
                # a[0] genelde events.NewMessage(pattern=..., outgoing=True)
                pat = None
                try:
                    if a:
                        ev = a[0]
                        pat = getattr(ev, "pattern", None)
                        if pat is None:
                            pat = getattr(ev, "_pattern", None)
                        # pattern Regex objesi olabilir
                        if hasattr(pat, "pattern"):
                            try:
                                pat = pat.pattern
                            except:
                                pass
                    # kw'de pattern varsa
                    if not pat and "pattern" in kw:
                        pat = kw.get("pattern")
                        if hasattr(pat, "pattern"):
                            try:
                                pat = pat.pattern
                            except:
                                pass
                except:
                    pat = None
                def _decorator(func):
                    try:
                        # Telethon NewMessage pattern'i direkt regex — Asena pending'e ekle
                        # ChatAction gibi patternsiz event'ler ignore
                        if pat:
                            # pattern string'e çevir
                            pstr = pat if isinstance(pat, str) else str(pat)
                            # Telethon pattern'i r"\\.xxx" olabilir — Pyrogram regex'e çevir
                            # Eğer ^ yoksa başına ^ ekle (komutlar hep ^ ile başlar)
                            # Ama var olanı koru
                            ASENA_PENDING.append((pstr, func, {}))
                        else:
                            # ChatAction vs. — no-op, fonksiyonu döndür
                            pass
                    except Exception as e:
                        print(f"bot.on pending hata: {e}", flush=True)
                    return func
                return _decorator
            return _on_decorator
        # önce gerçek app'e bak
        app = self._resolve()
        if app is not None:
            try:
                attr = getattr(app, name)
                return attr
            except AttributeError:
                pass
        # fallback dummy
        # Telethon uyumu için send_file -> send_document vb. shim de sağlanıyor
        if name in ("send_file", "sendFile"):
            async def _send_file(entity, file, **kw):
                a = self._resolve()
                if a:
                    # _smart_send benzeri cascade — direkt send_document dene
                    try:
                        from userbot.events import _smart_send
                        chat = entity
                        try:
                            if not isinstance(entity, int):
                                chat = getattr(entity, "id", entity)
                        except Exception:
                            pass
                        cap = kw.pop("caption", None)
                        rt = kw.pop("reply_to", None)
                        if hasattr(rt, "id"):
                            rt = rt.id
                        return await _smart_send(a, chat, file, caption=cap, reply_to=rt, **kw)
                    except Exception:
                        pass
                    # fallback
                    try:
                        return await a.send_document(entity if isinstance(entity, int) else getattr(entity, "id", 0), file, caption=kw.get("caption"))
                    except Exception:
                        pass
                return None
            return _send_file
        if name in ("inline_query", "inlineQuery"):
            async def _inline_query(bot_username, query, **kw):
                a = self._resolve()
                if a:
                    try:
                        from utils.inline_shim import inline_query as _iq
                        return await _iq(a, bot_username, query)
                    except Exception as e:
                        print(f"bot.inline_query hata ({bot_username}): {e}", flush=True)
                return []
            return _inline_query
        if name == "send_message":
            async def _send_message(entity, message, **kw):
                a = self._resolve()
                if a:
                    try:
                        chat = entity if isinstance(entity, int) else getattr(entity, "id", 0)
                        return await a.send_message(chat, message, **kw)
                    except Exception:
                        pass
                return None
            return _send_message
        # diğer tüm attribute'lar için dummy callable
        return _DummyCallable()

    def __call__(self, *a, **kw):
        return None

bot = _BotProxy()
# borg, tgbot, etc. aynı proxy
borg = bot
tgbot = bot

_current_app = None
def _set_current_app(app):
    global _current_app
    _current_app = app
def _get_current_app():
    # proxy için de aynı
    if _current_app is not None:
        return _current_app
    try:
        import userbot_core as _uc
        if getattr(_uc, "active_userbots", None):
            for _app in _uc.active_userbots.values():
                if _app:
                    return _app
    except Exception:
        pass
    return None

ASENA_PENDING = []
BOT_ON_PENDING = []  # borg.on / bot.on handlers

# ── Dinamik alt-modül oluşturucu (userbot.language, userbot.utils vs. her import çalışsın)
class _DummyCallable:
    def __call__(self, *a, **kw): return None
    def __getattr__(self, name): return _DummyCallable()
    def __getitem__(self, key): return f"{key}"
    def __setitem__(self, key, value): pass
    def __contains__(self, key): return False
    def __iter__(self): return iter([])
    def __bool__(self): return False
    def __await__(self): 
        async def _d(): return None
        return _d().__await__()

class _DummyLangDict(dict):
    def __getitem__(self, key):
        return f"{key}"
    def get(self, key, default=None):
        return f"{key}"

def _make_dummy_module(name):
    mod = types.ModuleType(name)
    mod.__file__ = f"/tmp/dummy_{name.replace('.', '_')}.py"
    class _Mod(types.ModuleType):
        def __getattr__(self, attr):
            # userbot.main gibi yerlerde PLUGIN_MESAJLAR dict beklenir
            if attr == "PLUGIN_MESAJLAR":
                return {}
            if attr in ("PLUGIN_CHANNEL_ID", "BOTLOG", "BOTLOG_CHATID"):
                return None
            return _DummyCallable()
        def __getitem__(self, key):
            return _DummyCallable()
    dummy = _Mod(name)
    dummy.__dict__.update(mod.__dict__)
    dummy.__file__ = f"/tmp/dummy_{name.replace('.', '_')}.py"
    dummy.__path__ = []
    return dummy

# Bilinen alt modüller için boş ama import edilebilir hale getir
for _sub in ["language", "utils", "main", "events", "cmdhelp", "config", "helpers", "sql_helper", "uniborgConfig"]:
    full = f"userbot.{_sub}"
    if full not in sys.modules:
        if _sub in ("events", "cmdhelp"):
            continue
        m = _make_dummy_module(full)
        if _sub == "language":
            def _get_value(key, *a, **kw): 
                if key == "com_1":
                    return "`İşleniyor...`"
                # get_value("admin") → dict döndür, LANG['PP_TOO_SMOL'] çalışsın
                # get_value("plugin", "key") → string
                if len(a) == 0 and len(kw) == 0:
                    # tek arg: plugin ismi → dict
                    return _DummyLangDict()
                # iki arg veya value varsa → string
                return key
            m.get_value = _get_value
            m.get_string = _get_value
            m.get_lang = _get_value
            m.LANG = _DummyLangDict()
            m.LANGUAGE = "TR"
        if _sub == "main":
            m.PLUGIN_MESAJLAR = {}
            m.CMD_HELP = {}
        sys.modules[full] = m
    else:
        # var olan language modülünü düzelt (get_value dict döndürsün)
        if _sub == "language" and "userbot.language" in sys.modules:
            try:
                _lm = sys.modules["userbot.language"]
                def _get_value2(key, *a, **kw):
                    if key == "com_1":
                        return "`İşleniyor...`"
                    if len(a) == 0 and len(kw) == 0:
                        return _DummyLangDict()
                    return key
                _lm.get_value = _get_value2
                _lm.get_string = _get_value2
                _lm.get_lang = _get_value2
            except Exception:
                pass

# ── addons paketi dummy (Ultroid waifu.deEmojify vs.)
if "addons" not in sys.modules:
    addons_mod = types.ModuleType("addons")
    addons_mod.__path__ = []
    sys.modules["addons"] = addons_mod
    # addons.waifu
    waifu_mod = _make_dummy_module("addons.waifu")
    def _deEmojify(text):
        # emoji temizle — basit
        import re
        try:
            # emoji kütüphanesi varsa kullan
            import emoji
            return emoji.replace_emoji(text, "")
        except Exception:
            return re.sub(r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]", "", text)
    waifu_mod.deEmojify = _deEmojify
    sys.modules["addons.waifu"] = waifu_mod
    addons_mod.waifu = waifu_mod

# ── custom_plugins paketi için get_string / ultroid_cmd dummy
# Pluginler `from . import get_string` yaparsa custom_plugins.get_string lazım
try:
    import importlib, os as _os
    # plugin dizinini bul
    _cp_dir = _os.getenv("PLUGIN_DIR") or ("/data/plugins" if _os.path.isdir("/data") else _os.path.join(_os.getcwd(), "plugins"))
    if "custom_plugins" not in sys.modules:
        cp_mod = types.ModuleType("custom_plugins")
        cp_mod.__path__ = [_cp_dir]
        sys.modules["custom_plugins"] = cp_mod
    else:
        cp_mod = sys.modules["custom_plugins"]
        if not getattr(cp_mod, "__path__", None):
            cp_mod.__path__ = [_cp_dir]
    # get_string ve ultroid_cmd ekle
    if not hasattr(cp_mod, "get_string"):
        def _cp_get_string(key, *a, **kw):
            if key == "com_1":
                return "`İşleniyor...`"
            return key
        cp_mod.get_string = _cp_get_string
    if not hasattr(cp_mod, "ultroid_cmd"):
        # ultroid_cmd -> log2alfa register alias
        def _ultroid_cmd(*a, **kw):
            pat = kw.get("pattern", "")
            from userbot.events import register
            if pat and not pat.startswith("^"):
                pass
            return register(pattern=pat, **{k:v for k,v in kw.items() if k!="pattern"})
        cp_mod.ultroid_cmd = _ultroid_cmd
except Exception as e:
    print(f"custom_plugins dummy hata: {e}", flush=True)

# ── userbot alt modülleri için generic dummy (bilinmeyen importlar için)
def __getattr__(name):
    # Gerçek dosya var mı kontrol et — varsa onu yüklemeye bırak, dummy yapma
    import importlib.util, pathlib
    # userbot.events ve userbot.cmdhelp gerçek dosyalar — onları dummy yapma
    if name in ("events", "cmdhelp"):
        # gerçek modülü yüklemeye çalış
        try:
            return importlib.import_module(f"userbot.{name}")
        except Exception:
            pass
    full = f"userbot.{name}"
    if full in sys.modules:
        return sys.modules[full]
    # dosya var mı?
    p = pathlib.Path(__file__).parent / f"{name}.py"
    if p.exists():
        try:
            return importlib.import_module(full)
        except Exception:
            pass
    # yoksa dummy
    m = _make_dummy_module(full)
    sys.modules[full] = m
    return m

# asena paketi — userbot'a alias
if "asena" not in sys.modules:
    asena_mod = types.ModuleType("asena")
    asena_mod.__path__ = []
    sys.modules["asena"] = asena_mod
    try:
        import importlib
        _ev = importlib.import_module("userbot.events")
        sys.modules["asena.events"] = _ev
        asena_mod.events = _ev
    except Exception as e:
        print(f"asena.events alias hata: {e}", flush=True)
    try:
        import importlib
        _ch = importlib.import_module("userbot.cmdhelp")
        sys.modules["asena.cmdhelp"] = _ch
        asena_mod.cmdhelp = _ch
    except Exception as e:
        print(f"asena.cmdhelp alias hata: {e}", flush=True)
    # diğer asena alt modülleri için dummy
    def _asena_getattr(name):
        full = f"asena.{name}"
        if full in sys.modules:
            return sys.modules[full]
        m = _make_dummy_module(full)
        sys.modules[full] = m
        setattr(asena_mod, name, m)
        return m
    try:
        asena_mod.__getattr__ = _asena_getattr  # type: ignore
    except Exception:
        pass
    # asena için de generic import fallback
    # sys.modules'a ekli kalması yeterli, import asena.events zaten sys.modules'dan gelecek

# telethon dummy — Unvoice gibi pluginlerin import'ları çökmesin
if "telethon" not in sys.modules:
    _tele = _make_dummy_module("telethon")
    _tele_events = _make_dummy_module("telethon.events")
    class _Dummy:
        StopPropagation = Exception
        class NewMessage:
            def __init__(self, *a, **kw):
                self.pattern = kw.get("pattern") or (a[0] if a else None)
                self.outgoing = kw.get("outgoing", None)
                self.incoming = kw.get("incoming", None)
                self.func = kw.get("func", None)
                # pattern Regex olabilir
                try:
                    if hasattr(self.pattern, "pattern"):
                        self.pattern = self.pattern.pattern
                except:
                    pass
                self.Event = self  # Telethon NewMessage.Event için
            def __call__(self, *a, **kw):
                return self
        Event = NewMessage  # alias
        class MessageEdited:
            def __init__(self, *a, **kw): pass
            Event = None
    _tele_events.NewMessage = _Dummy.NewMessage
    _tele_events.MessageEdited = _Dummy.MessageEdited
    _tele_events.StopPropagation = _Dummy.StopPropagation
    _tele.events = _tele_events
    sys.modules["telethon"] = _tele
    sys.modules["telethon.events"] = _tele_events
    # tl alt modülleri dummy
    for _tp in ["telethon.tl", "telethon.tl.types", "telethon.tl.functions", "telethon.tl.custom", "telethon.errors", "telethon.sync", "telethon.sessions"]:
        if _tp not in sys.modules:
            sys.modules[_tp] = _make_dummy_module(_tp)
# Telethon alt fonksiyon paketleri — her import için dummy oluştur (photos, account vb.)
for _tfn in [
    "telethon.tl.functions.photos", "telethon.tl.functions.account", "telethon.tl.functions.channels",
    "telethon.tl.functions.messages", "telethon.tl.functions.contacts", "telethon.tl.functions.users",
    "telethon.tl.functions.help", "telethon.tl.functions.upload", "telethon.tl.functions.auth",
    "telethon.utils", "telethon.sync", "telethon.sessions", "telethon.client", "telethon.tl.custom",
    "telethon.tl.types", "telethon.tl.types.messages", "telethon.tl.types.channels"
]:
    if _tfn not in sys.modules:
        sys.modules[_tfn] = _make_dummy_module(_tfn)
for _tt in ["telethon.tl.types", "telethon.tl.types.messages", "telethon.tl.types.channels"]:
    if _tt not in sys.modules:
        sys.modules[_tt] = _make_dummy_module(_tt)
# telethon.errors.rpcerrorlist shim — her alt import çalışsın
for _tpath in ["telethon.errors.rpcerrorlist", "telethon.errors.common", "telethon.tl.functions.messages", "telethon.tl.functions.channels", "telethon.tl.functions.contacts"]:
    if _tpath not in sys.modules:
        _m = _make_dummy_module(_tpath)
        # common hatalar için dummy exception ekle
        class _RPCError(Exception): pass
        for _n in ["RPCError", "FloodWaitError", "ChatAdminRequiredError", "YouBlockedUserError", "UserAlreadyParticipantError", "InviteHashExpiredError", "MessageNotModifiedError", "AuthKeyError", "SessionPasswordNeededError"]:
            setattr(_m, _n, _RPCError)
        sys.modules[_tpath] = _m
    else:
        # var olan dummy'ye de hataları ekle (tl.types gibi)
        _m = sys.modules[_tpath]
        if not hasattr(_m, "RPCError"):
            class _RPCError(Exception): pass
            for _n in ["RPCError", "FloodWaitError", "ChatAdminRequiredError", "YouBlockedUserError"]:
                setattr(_m, _n, _RPCError)
# telethon.errors ana modülüne rpcerrorlist'i bağla
try:
    _err = sys.modules.get("telethon.errors")
    _rpc = sys.modules.get("telethon.errors.rpcerrorlist")
    if _err is not None and _rpc is not None and not hasattr(_err, "rpcerrorlist"):
        _err.rpcerrorlist = _rpc
except Exception:
    pass

# ── Telethon TL fonksiyonları için gerçek sınıflar (JoinChannelRequest, GetFullUserRequest vb.) ──
# Joker pluginler `await client(JoinChannelRequest("xxx"))` ve `await client(GetFullUserRequest(uid))` yapar
# Bunları Pyrogram'a yönlendirmek için sınıfları düzgün tanımla ve Client.__call__'i patchle
try:
    import types as _types2
    # JoinChannelRequest
    class _JoinChannelRequest:
        def __init__(self, channel):
            self.channel = channel
            self.channel_id = channel
    class _GetFullUserRequest:
        def __init__(self, id):
            self.id = id
            self.user_id = id
            self.target = id
    class _AddContactRequest:
        def __init__(self, *a, **kw): pass
    class _GetContactsRequest:
        def __init__(self, *a, **kw): pass
    class _DeleteContactsRequest:
        def __init__(self, *a, **kw): pass
    # Modüllere enjekte et
    for _mod_path, _cls_name, _cls in [
        ("telethon.tl.functions.channels", "JoinChannelRequest", _JoinChannelRequest),
        ("telethon.tl.functions.users", "GetFullUserRequest", _GetFullUserRequest),
        ("telethon.tl.functions.contacts", "AddContactRequest", _AddContactRequest),
        ("telethon.tl.functions.contacts", "GetContactsRequest", _GetContactsRequest),
        ("telethon.tl.functions.contacts", "DeleteContactsRequest", _DeleteContactsRequest),
    ]:
        try:
            mod = sys.modules.get(_mod_path)
            if mod is not None:
                setattr(mod, _cls_name, _cls)
                # ayrıca dummy'nin __getattr__'ı varsa yine de set etsin
            else:
                mod = _types2.ModuleType(_mod_path)
                setattr(mod, _cls_name, _cls)
                sys.modules[_mod_path] = mod
        except Exception:
            pass
    # telethon.tl.types için de bazı dummy tipler
    for _mod_path in ["telethon.tl.types"]:
        try:
            mod = sys.modules.get(_mod_path)
            if mod is None:
                mod = _types2.ModuleType(_mod_path)
                sys.modules[_mod_path] = mod
            for _n in ["User", "Chat", "Channel", "ChannelParticipantsAdmins", "Message", "MessageService"]:
                if not hasattr(mod, _n):
                    setattr(mod, _n, type(_n, (), {}))
            # ChannelParticipantsAdmins için cp alias
            if not hasattr(mod, "ChannelParticipantsAdmins"):
                setattr(mod, "ChannelParticipantsAdmins", type("ChannelParticipantsAdmins", (), {}))
        except Exception:
            pass
except Exception as e:
    print(f"TL functions patch hata: {e}", flush=True)

# ── Pyrogram Client.__call__ shim — Telethon `await client(Request)` için ──
try:
    import pyrogram.client as _py_client
    import pyrogram as _py
    # pyrogram.Client ve Client class
    _ClientCls = None
    try:
        _ClientCls = _py.Client
    except:
        try:
            _ClientCls = _py_client.Client
        except:
            pass
    if _ClientCls is not None and not hasattr(_ClientCls, "_log2alfa_patched_call"):
        _orig_call = getattr(_ClientCls, "__call__", None)
        async def _patched_call(self, *args, **kwargs):
            # Telethon TL requestleri için
            if args:
                req = args[0]
                # JoinChannelRequest -> join_chat
                try:
                    cname = getattr(req, "__class__", type(req)).__name__ if req else ""
                    if cname == "_JoinChannelRequest" or cname == "JoinChannelRequest":
                        ch = getattr(req, "channel", None) or getattr(req, "channel_id", None)
                        if isinstance(ch, str):
                            try:
                                # Pyrogram join_chat
                                return await self.join_chat(ch)
                            except Exception as e:
                                print(f"JoinChannelRequest join_chat hata {ch}: {e}", flush=True)
                                return None
                        return None
                    if cname == "_GetFullUserRequest" or cname == "GetFullUserRequest":
                        uid = getattr(req, "user_id", None) or getattr(req, "id", None) or getattr(req, "target", None)
                        # uid Pyrogram id veya Peer olabilir
                        try:
                            # Asena'da reply.from_id (int) veya Peer objesi gelebilir
                            # Peer ise id çıkar
                            if hasattr(uid, "user_id"):
                                uid = uid.user_id
                            elif hasattr(uid, "channel_id"):
                                uid = uid.channel_id
                            elif hasattr(uid, "chat_id"):
                                uid = uid.chat_id
                            elif hasattr(uid, "id"):
                                # Eğer obje Message ise?
                                uid = getattr(uid, "id", uid)
                            # int veya string
                            if isinstance(uid, int) or (isinstance(uid, str) and uid.lstrip("@").isdigit()):
                                try:
                                    u = await self.get_users(int(str(uid).lstrip("@")))
                                    # Telethon FullUser objesi: .user içinde User
                                    class _Wrap:
                                        def __init__(self, user):
                                            self.user = user
                                            self.full_user = user
                                            self.users = [user]
                                    return _Wrap(u)
                                except Exception as e:
                                    print(f"GetFullUserRequest get_users hata {uid}: {e}", flush=True)
                                    return None
                            elif isinstance(uid, str):
                                try:
                                    u = await self.get_users(uid)
                                    class _Wrap:
                                        def __init__(self, user):
                                            self.user = user
                                            self.full_user = user
                                    return _Wrap(u)
                                except Exception:
                                    return None
                        except Exception as e:
                            print(f"GetFullUserRequest hata: {e}", flush=True)
                            return None
                    # Diğer TL istekleri: AddContact vs. -> no-op
                    if cname in ("_AddContactRequest", "AddContactRequest", "_GetContactsRequest", "GetContactsRequest", "_DeleteContactsRequest", "DeleteContactsRequest"):
                        return None
                except Exception as e:
                    print(f"Client.__call__ shim hata: {e}", flush=True)
            # Eğer orig_call varsa dene, yoksa None
            if _orig_call is not None:
                try:
                    return await _orig_call(self, *args, **kwargs)
                except TypeError:
                    # orig_call sync olabilir
                    try:
                        return _orig_call(self, *args, **kwargs)
                    except:
                        return None
                except Exception:
                    return None
            return None
        _ClientCls.__call__ = _patched_call
        _ClientCls._log2alfa_patched_call = True
        print("Pyrogram Client.__call__ patchlendi (Telethon uyumu)", flush=True)
except Exception as e:
    print(f"Client.__call__ patch hata: {e}", flush=True)


# ── Eksik pip paketleri için dummy shim (her plugin import edebilsin) ──
for _missing in [
    "speedtest", "spotify_token", "aria2p", "selenium", "twitter_scraper", "coffeehouse",
    "pydub", "hachoir", "lyricsgenius", "pylast", "qrcode", "cowpy", "pySmartDL",
    "git", "pytz", "sqlalchemy", "aiohttp", "numpy", "PIL", "cv2",
    "barcode", "googletrans", "flag", "googleapiclient", "hachoir", "bs4",
    "yt_dlp", "youtube_dl", "heroku3", "pyrogram", "telethon"
]:
    if _missing not in sys.modules:
        try:
            __import__(_missing)
        except Exception:
            sys.modules[_missing] = _make_dummy_module(_missing)
            try:
                sys.modules[f"{_missing}.parser"] = _make_dummy_module(f"{_missing}.parser")
                sys.modules[f"{_missing}.metadata"] = _make_dummy_module(f"{_missing}.metadata")
            except Exception:
                pass
# alt modüller için de dummy (barcode.writer, googletrans.client vb.)
for _sub in [
    "barcode.writer", "googletrans.client", "googletrans.constants",
    "googleapiclient.discovery", "googleapiclient.http", "googleapiclient.errors", "googleapiclient.model",
    "hachoir.parser", "hachoir.metadata",
    "bs4", "PIL.Image",
    "selenium.webdriver", "selenium.webdriver.common", "selenium.webdriver.common.by",
    "selenium.webdriver.chrome", "selenium.webdriver.chrome.options", "selenium.webdriver.support",
    "selenium.webdriver.support.ui", "selenium.webdriver.support.expected_conditions",
    "telegraph", "telegraph.aio", "telethon.utils", "telegraph.utils",
    "wikipedia", "wikipedia.exceptions", "wikipedia.util",
    "coffeehouse.lydia", "coffeehouse.api", "coffeehouse",
    "googleapiclient", "oauth2client", "oauth2client.client", "oauth2client.service_account",
    "oauth2client.file", "oauth2client.tools", "urbandict", "urbandict.urbandict",
    "httplib2", "search_engine_parser", "search_engine_parser.core",
    "gtts", "gtts.lang", "youtube_dl", "youtube_dl.utils", "youtube_dl.extractor"
]:
    if _sub not in sys.modules:
        try:
            __import__(_sub)
        except Exception:
            sys.modules[_sub] = _make_dummy_module(_sub)
for _alias, _real in [("googletrans", "googletrans"), ("barcode", "barcode"), ("flag", "flag")]:
    if _alias not in sys.modules:
        try:
            __import__(_alias)
        except Exception:
            sys.modules[_alias] = _make_dummy_module(_alias)

# ── custom_plugins shazam_helper alias (Asena shazam.py custom_plugins.shazam_helper bekler) ──
try:
    import importlib as _il
    for _cp_alias, _real_mod in [
        ("custom_plugins.shazam_helper", "userbot.modules.shazam_helper"),
        ("custom_plugins.shazam_helper.algorithm", "userbot.modules.shazam_helper.algorithm"),
        ("custom_plugins.shazam_helper.communication", "userbot.modules.shazam_helper.communication"),
        ("custom_plugins.shazam_helper.signature_format", "userbot.modules.shazam_helper.signature_format"),
        ("custom_plugins.shazam_helper.user_agent", "userbot.modules.shazam_helper.user_agent"),
    ]:
        if _cp_alias not in sys.modules:
            try:
                _m = _il.import_module(_real_mod)
                sys.modules[_cp_alias] = _m
            except Exception:
                sys.modules[_cp_alias] = _make_dummy_module(_cp_alias)
except Exception:
    pass

# ── userbot.modules paketi için gerçek dizin mount ──
try:
    import pathlib as _pl
    _mod_path = _pl.Path(__file__).parent / "modules"
    if _mod_path.exists():
        if "userbot.modules" not in sys.modules:
            _mod = types.ModuleType("userbot.modules")
            _mod.__path__ = [str(_mod_path)]
            sys.modules["userbot.modules"] = _mod
        else:
            try:
                cur = getattr(sys.modules["userbot.modules"], "__path__", None)
                if not cur or str(_mod_path) not in list(cur):
                    sys.modules["userbot.modules"].__path__ = [str(_mod_path)]
            except Exception:
                pass
        for _subpkg in ["sql_helper", "shazam_helper"]:
            full = f"userbot.modules.{_subpkg}"
            if full in sys.modules:
                try:
                    mod = sys.modules[full]
                    if not hasattr(mod, "__file__") or not getattr(mod, "__file__", None):
                        del sys.modules[full]
                except Exception:
                    pass
except Exception as e:
    print(f"userbot.modules mount hata: {e}", flush=True)

# ── Genel dummy finder: eksik harici paketlerin her alt modülü için otomatik dummy ──
try:
    import importlib.abc as _abc
    import importlib.machinery as _mach
    _DUMMY_PREFIXES = (
        "telethon", "barcode", "googletrans", "googleapiclient", "hachoir", "selenium",
        "telegraph", "wikipedia", "coffeehouse", "oauth2client", "urbandict", "httplib2",
        "search_engine_parser", "gtts", "youtube_dl", "spotify_token", "aria2p", "pylast",
        "qrcode", "cowpy", "pySmartDL", "git", "pytz", "sqlalchemy", "aiohttp", "numpy",
        "PIL", "cv2", "hachoir", "bs4", "flag", "urbandict", "lyricsgenius", "pylast",
        "ImageDown", "youtubesearchpython", "httplib2", "oauth2client"
    )
    class _AnyDummyLoader(_abc.Loader):
        def create_module(self, spec):
            mod = types.ModuleType(spec.name)
            mod.__spec__ = spec
            mod.__path__ = []
            # her attribute dummy
            mod.__getattr__ = lambda n: _DummyCallable()
            return mod
        def exec_module(self, module):
            module.__getattr__ = lambda n: _DummyCallable()
            if not hasattr(module, "__path__"):
                module.__path__ = []
            # dummy'nin her alt erişimi de dummy
            module.__dict__["__getattr__"] = lambda n: _DummyCallable()

    class _AnyDummyFinder(_abc.MetaPathFinder):
        def find_spec(self, fullname, path, target=None):
            if fullname in sys.modules:
                return None
            for pref in _DUMMY_PREFIXES:
                if fullname == pref or fullname.startswith(pref + "."):
                    try:
                        # eğer gerçek paket varsa (pip ile kurulu) dummy yapma
                        import importlib.util as _iu
                        if _iu.find_spec(fullname) is not None:
                            return None
                    except Exception:
                        pass
                    return _mach.ModuleSpec(fullname, _AnyDummyLoader(), is_package=True)
            return None
    # en başa ekle
    sys.meta_path.insert(0, _AnyDummyFinder())
except Exception as e:
    print(f"dummy finder hata: {e}", flush=True)

# PIL multiline_textsize fix — Pillow 10+ için uyumluluk (stickerfun vb.)
try:
    from PIL import ImageDraw as _ID
    if not hasattr(_ID.ImageDraw, "multiline_textsize"):
        def _fake_multiline_textsize(self, text, font=None, spacing=0, stroke_width=0, **kw):
            try:
                # Pillow 10+: multiline_textbbox kullan
                bbox = self.multiline_textbbox((0, 0), text, font=font, spacing=spacing, stroke_width=stroke_width)
                return (bbox[2] - bbox[0], bbox[3] - bbox[1])
            except Exception:
                try:
                    # fallback: textsize
                    w, h = 0, 0
                    for line in text.split("\n"):
                        lw, lh = self.textsize(line, font=font, stroke_width=stroke_width)
                        w = max(w, lw)
                        h += lh + spacing
                    return (w, h)
                except:
                    return (len(text)*10, 20)
        _ID.ImageDraw.multiline_textsize = _fake_multiline_textsize
    # textsize -> textbbox fallback
    if not hasattr(_ID.ImageDraw, "textsize"):
        def _fake_textsize(self, text, font=None, stroke_width=0, **kw):
            try:
                bbox = self.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
                return (bbox[2]-bbox[0], bbox[3]-bbox[1])
            except:
                return (len(text)*10, 20)
        _ID.ImageDraw.textsize = _fake_textsize
except Exception as e:
    print(f"PIL patch hata: {e}", flush=True)

# sqlite_storage inspect.stack fix — dummy module yüzünden list index hatasını engelle
try:
    import sys as _sys
    import pyrogram.storage.sqlite_storage as _sql
    # Orijinal _get/_set inspect.stack kullanır, onu sys._getframe ile değiştir
    import inspect as _ins
    _orig_get = _sql.SQLiteStorage._get
    _orig_set = _sql.SQLiteStorage._set
    async def _patched_get(self):
        try:
            # inspect.stack()[2].function yerine sys._getframe
            attr = _sys._getframe(2).f_code.co_name
        except:
            attr = "dc_id"
        return await self.loop.run_in_executor(self.executor, self._get_impl, attr)
    async def _patched_set(self, value):
        try:
            attr = _sys._getframe(2).f_code.co_name
        except:
            attr = "dc_id"
        return await self.loop.run_in_executor(self.executor, self._set_impl, attr, value)
    _sql.SQLiteStorage._get = _patched_get
    _sql.SQLiteStorage._set = _patched_set
    # Ayrıca inspect.stack'i de güvenli hale getir (dummy için)
    _orig_stack = _ins.stack
    def _safe_stack(*a, **kw):
        try:
            return _orig_stack(*a, **kw)
        except Exception:
            # En az 3 frame'li fake stack döndür ki [2] hatası olmasın
            class _FakeFrame:
                def __init__(self, func): self.function = func
            return [_FakeFrame("dummy"), _FakeFrame("dummy2"), _FakeFrame("dc_id")]
    _ins.stack = _safe_stack
except Exception as e:
    print(f"sqlite_storage patch hata: {e}", flush=True)

try:
    from . import events as _events  # noqa
    from . import cmdhelp as _cmdhelp  # noqa
except Exception as e:
    print(f"userbot events/cmdhelp import hata: {e}", flush=True)

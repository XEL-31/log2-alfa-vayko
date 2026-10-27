"""Plugin loader — başkalarının .py pluginlerini yükleme
PLUGINS_DIR: /data/plugins (Railway volume) yoksa ./plugins
Her plugin tek dosya: myplugin.py
İçinde register_handlers(app) veya register(app) olmalı
"""
import os
import sys
import time
import traceback
import importlib.util
import pathlib
from pathlib import Path
import re

# Plugin dizini — kalıcı olmalı
def _resolve_dir():
    env = os.getenv("PLUGIN_DIR")
    if env:
        return env
    # Railway volume
    if os.path.isdir("/data"):
        return "/data/plugins"
    return os.path.join(os.getcwd(), "plugins")

# --- Pyrogram Message shims (reply_to_msg_id, download_media, from_id) ---
try:
    from pyrogram.types import Message as _PyMsg
    if not hasattr(_PyMsg, 'reply_to_msg_id'):
        _PyMsg.reply_to_msg_id = property(lambda self: self.reply_to_message.id if self.reply_to_message else None)
    if not hasattr(_PyMsg, 'from_id'):
        _PyMsg.from_id = property(lambda self: self.from_user.id if getattr(self, 'from_user', None) else getattr(self, 'sender_id', None) if hasattr(self, 'sender_id') else getattr(self.from_user, 'id', None) if getattr(self, 'from_user', None) else None)
    # download_media alias for Message.download
    if not hasattr(_PyMsg, 'download_media'):
        async def _dl_media(self, *a, **kw):
            try:
                return await self.download(*a, **kw)
            except Exception as e:
                print(f"download_media shim hata {e}", flush=True)
                return None
        _PyMsg.download_media = _dl_media
    # also alias for .message -> .text for Telethon compatibility
    if not hasattr(_PyMsg, 'message'):
        _PyMsg.message = property(lambda self: self.text or self.caption or "")
except Exception as _e:
    print(f"Message shim hata {_e}", flush=True)
    pass

PLUGIN_DIR = _resolve_dir()
os.makedirs(PLUGIN_DIR, exist_ok=True)
# fallback: ./plugins dosyaları /data/plugins'a kopyala (ilk kurulum)
try:
    alt = pathlib.Path("./plugins")
    if alt.exists() and PLUGIN_DIR != str(alt):
        for f in alt.glob("*.py"):
            dest = pathlib.Path(PLUGIN_DIR) / f.name
            if not dest.exists():
                try:
                    dest.write_bytes(f.read_bytes())
                    print(f"plugin copy {f.name} -> {PLUGIN_DIR}", flush=True)
                except Exception as e:
                    print(f"plugin copy hata {e}", flush=True)
except Exception:
    pass

# Yüklü modüller: name -> module
_loaded = {}

def _sanitize(name: str) -> str:
    # dosya adı temizle: sadece a-z0-9_ -
    import re as _re2
    n = name.strip()
    if n.endswith(".py"):
        n = n[:-3]
    n = _re2.sub(r"[^a-zA-Z0-9_\-]", "_", n)
    if not n:
        n = "plugin"
    return n

def list_plugins():
    out = []
    try:
        for p in Path(PLUGIN_DIR).glob("*.py"):
            try:
                stat = p.stat()
                # boş dosyaları temizle (0 byte → bozuk plugin, sil)
                if stat.st_size < 10:
                    try:
                        p.unlink()
                        print(f"→ bozuk plugin silindi (boş): {p.name}", flush=True)
                    except:
                        print(f"→ plugin atlandı (boş): {p.name}", flush=True)
                    continue
                out.append({
                    "name": p.stem,
                    "file": p.name,
                    "path": str(p),
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                })
            except Exception:
                out.append({"name": p.stem, "file": p.name, "path": str(p), "size": 0, "mtime": 0})
    except Exception as e:
        print(f"plugin list hata: {e}", flush=True)
    return sorted(out, key=lambda x: x["mtime"], reverse=True)

def get_plugin_path(name: str) -> str:
    name = _sanitize(name)
    return os.path.join(PLUGIN_DIR, f"{name}.py")

def _patch_plugin_source(text: str, name: str) -> str:
    """Kod içi düzeltmeler — çalışan komutlarla karşılaştırılarak"""
    orig = text
    # 1) BOM temizle
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
    text = text.replace("\ufeff", "")
    # 2) time.sleep -> asyncio.sleep  (async içinde blocking)
    # `from time import sleep` veya `import time` + `time.sleep` / `sleep(`
    # Hepsini asyncio.sleep yap
    # Önce import asyncio ekle (eğer yoksa)
    if "asyncio.sleep" not in text and ("time.sleep" in text or re.search(r'\bsleep\s*\(', text)):
        # sadece async def barındıran dosyalarda
        if "async def" in text:
            # from time import sleep varsa onu da düzelt
            # sleep( -> asyncio.sleep(
            # time.sleep( -> asyncio.sleep(
            if "import asyncio" not in text:
                # ilk import satırından sonra ekle
                lines = text.splitlines()
                insert_idx = 0
                for i, l in enumerate(lines):
                    if l.strip().startswith("import ") or l.strip().startswith("from "):
                        insert_idx = i+1
                lines.insert(insert_idx, "import asyncio")
                text = "\n".join(lines)
    # Replace time.sleep(
    text = re.sub(r'\btime\.sleep\s*\(', 'asyncio.sleep(', text)
    # Replace from time import sleep -> sleep( (sadece async dosyalarda)
    # sleep(
    # Dikkat: sadece `await asyncio.sleep` olmalı, sleep( tek başına varsa await ekle
    # Biz time.sleep -> asyncio.sleep yaptık ama await yoksa eklememiz lazım
    # Basit: `asyncio.sleep(` varsa önünde await yoksa ekle
    # Fakat plugin kodu zaten `time.sleep(` şeklinde await olmadan kullanıyordu -> blocking
    # Şimdi `asyncio.sleep(` yaptık ama await gerekiyor
    # Örn: `time.sleep(0.5)` inside async def -> `await asyncio.sleep(0.5)` olmalı
    # Bunu regex ile ekle: satırda asyncio.sleep varsa ve await yoksa
    def _await_sleep(m):
        prefix = m.group(1) or ""
        # eğer zaten await varsa bırak
        if "await" in prefix:
            return m.group(0)
        return prefix + "await asyncio.sleep("
    # Satır başı veya ; sonrası sleep
    text = re.sub(r'(^|;\s*|:\s*|\n\s*)(asyncio\.sleep\()', lambda m: m.group(1) + "await asyncio.sleep(" if "await" not in m.group(1) else m.group(0), text)
    # Daha genel: `asyncio.sleep(` önünde await yoksa ekle (satır içi)
    # Her `asyncio.sleep(` için önündeki 30 karakterde await var mı kontrol et, yoksa ekle
    # Basit iterasyon
    new_lines = []
    for line in text.splitlines():
        if "asyncio.sleep(" in line and "await" not in line:
            # sadece async içindeki sleep'leri değiştir
            line = line.replace("asyncio.sleep(", "await asyncio.sleep(")
        new_lines.append(line)
    text = "\n".join(new_lines)
    # 3) await event.get_reply_message().attr -> (await event.get_reply_message()).attr
    # Genelleştir: await <var>.get_reply_message().<attr>
    text = re.sub(r'await\s+(\w+)\.get_reply_message\(\)\.(\w+)', r'(await \1.get_reply_message()).\2', text)
    # 4) JoinChannelRequest — kanal katılımını sessiz atla (hata vermesin)
    # `await event.client(JoinChannelRequest("..."))` -> pass
    text = re.sub(r'await\s+(?:event|e|q|brend|hazmat|fry|client|bot)\.client\s*\(\s*JoinChannelRequest\s*\(.*?\)\s*\)', 'await asyncio.sleep(0)', text)
    text = re.sub(r'await\s+bot\s*\(\s*JoinChannelRequest\s*\(.*?\)\s*\)', 'await asyncio.sleep(0)', text)
    text = re.sub(r'await\s+event\.client\s*\(\s*JoinChannelRequest.*?\)', 'await asyncio.sleep(0)', text)
    # Tüm `JoinChannelRequest` import satırlarını koru ama çağrıları sil
    # Daha agresif: her satırda JoinChannelRequest varsa o satırı yorum yap
    # Yukarıdaki regexler zaten çoğu yakalar, kalanlar için yorum:
    #text = re.sub(r'.*JoinChannelRequest.*\n', '# JoinChannelRequest patched\n', text)  # çok agresif - kapalı
    # 5) event.client.get_messages(event.chat_id, 0, from_user=...) Telethon -> Pyrogram uyumu
    # Biz shim'de GetFullUserRequest vs handle ediyoruz ama `bot.get_messages` de telethon
    # `bot.get_messages(chat, 0, from_user=...)` -> shim zaten var ama çalışsın diye bırakıyoruz
    # 6) Eski `bot.send_read_acknowledge` zaten shim var
    # 7) `event.client.iter_participants` -> `event.client.get_chat_members`
    text = re.sub(r'\.iter_participants\s*\(', '.get_chat_members(', text)
    # 8) `event.client.get_participants` -> get_chat_members
    text = re.sub(r'\.get_participants\s*\(', '.get_chat_members(', text)
    # 9) `download_profile_photo` -> download_media wrapper
    # Shim'de handle ediyoruz, bırak
    # 10) `from telethon.tl.functions.channels import JoinChannelRequest` zaten dummy, sorun yok
    # 11) `while` içinde `time.sleep` zaten düzeltildi
    # 12) Bazı pluginler `sleep` doğrudan import etmiş: `from time import sleep` + `sleep(0.5)` -> asyncio
    # Yukarıda import asyncio ekledik ama sleep( hala kalmışsa
    # `sleep(` -> `await asyncio.sleep(`
    # Sadece `from time import sleep` varsa yapılan sleep çağrılarını değiştir
    if "from time import sleep" in orig or "from time import *" in orig or re.search(r'\bsleep\s*\(', text):
        # Bu dosyalarda sleep( kullanımı asyncio olmalı — sadece standalone sleep, X.sleep değil
        # 1) await sleep( -> await asyncio.sleep(
        text = re.sub(r'\bawait\s+sleep\s*\(', 'await asyncio.sleep(', text)
        # 2) standalone sleep( -> await asyncio.sleep(  (J.sleep / asyncio.sleep içindeki sleep hariç)
        #    Öncesinde . veya harf/rakam/_ olmamalı
        text = re.sub(r'(?<![\w.])sleep\s*\(', 'await asyncio.sleep(', text)
        # Düzeltme sonrası çift await temizle
        text = re.sub(r'await\s+await', 'await', text)
        text = text.replace("await asyncio.await", "await asyncio.")
    # 13) `reply.from_id` zaten shim ile handle, ama Pyrogram'da from_user.id
    # `reply.from_id` -> `getattr(reply, "from_user", reply).id` gibi shim var, bırak
    # 14) `reply.message` -> `reply.text` alias shim var
    # 15) `__pycache__` ile ilgili değil
    # --- Ek patch: edit_delete helper (inlinefun) ---
    if "edit_delete" in text and "def edit_delete" not in text:
        # import asyncio zaten var mı kontrol et, yoksa ekle
        if "import asyncio" not in text:
            lines = text.splitlines()
            insert_idx = 0
            for i, l in enumerate(lines):
                if l.strip().startswith("import ") or l.strip().startswith("from "):
                    insert_idx = i+1
            lines.insert(insert_idx, "import asyncio")
            text = "\n".join(lines)
        # helper fonksiyonu imports sonrası ekle
        text = text.replace("from userbot.cmdhelp import CmdHelp", "from userbot.cmdhelp import CmdHelp\n\nasync def edit_delete(event, text):\n    try:\n        await event.edit(text)\n        await asyncio.sleep(3)\n        try:\n            await event.delete()\n        except: pass\n    except Exception as e:\n        try:\n            await event.edit(str(e))\n        except: pass")

    # --- Ek patch: reply_to_msg_id shim (kuzeytekinoglu etc) ---
    # e.message.reply_to_msg_id -> e.reply_to_msg_id
    text = re.sub(r'(\w+)\.message\.reply_to_msg_id', r'\1.reply_to_msg_id', text)
    # Generic .reply_to_msg_id on Message -> try to map to reply_to_message.id
    # If still .reply_to_msg_id on raw Message object, patch to getattr
    # We also add monkey-patch later, but source patch helps
    # No direct source replace for Message, monkey patch handles

    # --- Ek patch: hipnoz mesaj.edit(file=) -> simple remove file param ---
    if "hipnoz" in name.lower() or ("mesaj.edit" in text and "file=" in text):
        # Simple: remove file= param, keep caption edit only (avoid crash)
        # await mesaj.edit(cap2, file=foto) -> await mesaj.edit(cap2)
        text = re.sub(r'\.edit\(([^)]*),\s*file\s*=\s*[^)]+\)', r'.edit(\1)', text)

    # --- Ek patch: ses (MrTTSbot) conversation not supported -> graceful ---
    # Patch removed to avoid duplication syntax error - handled via Message shim and friendly error
    pass

    # --- Ek patch: .download_media() on Message -> .download() fallback ---
    # Pyrogram Message has download() not download_media, shim added elsewhere but also patch source
    # Keep original, monkey patch will handle at runtime, so no source change needed

    # --- Genel patch: some-random-api.ml -> .com (lgbt, gif, etc) ---
    if "some-random-api.ml" in text:
        text = text.replace("some-random-api.ml", "some-random-api.com")
        print(f"→ patch some-random-api.ml -> .com for {name}", flush=True)

    # --- Genel patch: while sonuc is False infinite loop -> bounded loop ---
    if "while sonuc is False:" in text:
        # Replace with bounded loop + fallback
        # Ensure asyncio imported
        if "import asyncio" not in text:
            lines = text.splitlines()
            insert_idx = 0
            for i, l in enumerate(lines):
                if l.strip().startswith("import ") or l.strip().startswith("from "):
                    insert_idx = i+1
            lines.insert(insert_idx, "import asyncio")
            text = "\n".join(lines)
        text = text.replace("    sonuc = False\n    while sonuc is False:", "    sonuc = False\n    # bounded loop fix: avoid infinite hang\n    for _try in range(20):\n        if not sonuclar:\n            await event.edit(\"**Bot boş sonuç döndürdü, tekrar deneyin!**\")\n            return\n        await asyncio.sleep(0.05)")
        # After the if block that sets sonuc=True, add break
        # Find pattern "            sonuc = True" inside while and add break after
        text = re.sub(r"            sonuc = True\n", "            sonuc = True\n        if sonuc:\n            break\n", text)
        # If not already has fallback after loop, add fallback before next @register or Help
        # Check if fallback already exists (turkcerap has it), so only add if not
        if "Uygun eşleşme bulunamadı" not in text and "Bounded loop" in text:
            # Add fallback before next @register or CmdHelp
            text = re.sub(r"(        if sonuc:\n            break\n)\n\n(@register|CmdHelp|Help)", r"\1\n    if not sonuc:\n        await event.edit(\"**Uygun şarkı bulunamadı, tekrar deneyin!**\")\n        return\n\n\2", text)
        print(f"→ patch while sonuc is False -> bounded for {name}", flush=True)

    # --- Genel patch: reply.from_id -> handled via Message.from_id shim ---
    pass
    # --- Genel patch: download_profile_photo shim ---
    # Handled via Message/client shim in userbot/events.py, no source patch needed (avoid nested ternary syntax error)
    pass
    # --- Telegraph patch kept but handled separately ---
    if "upload_file" in text and "telegraph" in text and "avatar = upload_file(foto)" in text:
        # Only if not already patched
        if "if not avatar:" not in text:
            text = text.replace("avatar = upload_file(foto)", "avatar = upload_file(foto) if foto else None\n    if not avatar:\n        await event.edit('**Profil fotoğrafı Telegrapha yüklenemedi!**')\n        return")
            print(f"→ patch telegraph upload for {name}", flush=True)

    # 16) Syntax hatası JTEMA line 93 -> kontrol et ve düzelt
    if name == "JTEMA":
        # JTEMA.py line 93 civarı `await event.edit(f"{choice(Jokisback)}")` sonrası Jokisback tanımlı değil (sonra tanımlı)
        # Python'da forward reference list için hata değil, ama syntax hatası var
        # Biz dosyayı okuyup düzeltelim: örnek Jokisback listesi önceden tanımlı olmalı
        # En basit: dosyayı tamamen yorumlayıp çalışır bir versiyonla değiştir
        # Eğer hala syntax hatası varsa, minimal çalışan versiyon koy
        try:
            import ast as _ast
            _ast.parse(text)
        except SyntaxError as se:
            print(f"JTEMA syntax düzeltme {se}", flush=True)
            # Minimal fallback
            text = '''
from userbot.events import register
from random import choice
from userbot.cmdhelp import CmdHelp
Jokisback = ["[JOK-TEMA](https://t.me/addtheme/test)"]
@register(outgoing=True, pattern="^.jtema")
async def jokisback(event):
    await event.edit(f"{choice(Jokisback)}")
Help = CmdHelp("jtema")
Help.add_command("jtema", None, "Tema")
Help.add()
'''
    # Ek: syntax kontrol - eğer hala hata varsa düzeltmeye çalış
    try:
        import ast as _ast
        _ast.parse(text)
    except SyntaxError as se:
        # Ortak hata: `invalid escape sequence` uyarısı değil, gerçek syntax
        print(f"patch sonrası syntax hata {name}: {se} line {se.lineno}", flush=True)
        # Dosyayı olduğu gibi bırak, yükleme sırasında hata verecek ve atlanacak
        pass
    if text != orig:
        print(f"→ plugin patch uygulandı: {name} ({len(orig)}->{len(text)} bytes)", flush=True)
    return text

def _load_module_from_path(path: str, mod_name: str):
    # Patch uygula ve exec et (spec yerine compile)
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        raise ImportError(f"dosya okunamadı {path}: {e}")
    # Patch
    try:
        patched = _patch_plugin_source(raw, mod_name)
    except Exception as e:
        print(f"patch hata {mod_name}: {e}", flush=True)
        patched = raw
    # Eğer patch değişiklik yaptıysa, dosyayı diske de yaz (kalıcı)
    if patched != raw:
        try:
            p.write_text(patched, encoding="utf-8")
        except Exception:
            pass
        raw = patched
    spec = importlib.util.spec_from_file_location(f"custom_plugins.{mod_name}", path)
    if not spec or not spec.loader:
        # Fallback: manuel module oluştur ve exec
        import types
        mod = types.ModuleType(f"custom_plugins.{mod_name}")
        mod.__file__ = path
        sys.modules[f"custom_plugins.{mod_name}"] = mod
        code = compile(raw, path, "exec")
        exec(code, mod.__dict__)
        return mod
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    # exec_module yerine patched code ile çalıştır (dosya zaten patched yazıldı, spec loader patched dosyayı okuyacak)
    # Ama güvende olmak için compile + exec de yapabiliriz
    try:
        spec.loader.exec_module(mod)
    except SyntaxError as se:
        # Eğer hala syntax hatası varsa, fallback: patched code'u compile et
        print(f"exec_module syntax hata {mod_name}: {se} -> compile exec fallback", flush=True)
        code = compile(raw, path, "exec")
        # mod'u temizle ve yeniden exec
        mod.__dict__.clear()
        mod.__dict__["__name__"] = f"custom_plugins.{mod_name}"
        mod.__dict__["__file__"] = path
        exec(code, mod.__dict__)
    return mod

def _register_module(app, mod):
    # Önce Asena pending handlerlarını Pyrogram'a çevir (userbot.events shim)
    asena_reg = None
    try:
        from userbot import ASENA_PENDING
        from userbot.events import AsenaEvent
        from pyrogram import filters as _filters
        from pyrogram.handlers import MessageHandler as _MH
        import re as _re
        # ASENA_PENDING o anda bu plugin için doldurulmuş olmalı
        # Kopyala ve temizle
        pending = list(ASENA_PENDING)
        # --- FIX earth pollution: admin importlarıyla gelen userbot.modules.* handlerlarını filtrele ---
        _orig_len = len(pending)
        _filtered_by_module = []
        _kept = []
        for _pat, _fn, _a in pending:
            modname = getattr(_fn, "__module__", "")
            if modname and not modname.startswith("custom_plugins."):
                _filtered_by_module.append(getattr(_fn, "__name__", str(_fn)) + f"[{modname}]")
                continue
            if not _pat:
                fname = getattr(_fn, "__name__", "").lower()
                if fname in ("gbanmsg", "gmutemsg", "gban", "gmute", "gbanmsg"):
                    _filtered_by_module.append(fname + "(pat=None)")
                    continue
            _kept.append((_pat, _fn, _a))
        if _filtered_by_module:
            pending = _kept
            print(f"→ _register_module pollution filtered for {mod.__name__}: orig={_orig_len} kept={len(pending)} dropped={_filtered_by_module}", flush=True)
        else:
            print(f"→ _register_module pending={len(pending)} for {mod.__name__}", flush=True)
        # Temizle (sonraki plugin için)
        ASENA_PENDING.clear()
        for pattern, func, args in pending:
            try:
                # filtre oluştur — pattern string veya compiled Regex olabilir
                # Sadece hesabında userbot kurulu olan kişi tetikleyebilir (outgoing/me)
                flt = _filters.me | _filters.outgoing
                if pattern:
                    try:
                        # Pattern objesi ise string'e çevir
                        if hasattr(pattern, "pattern"):
                            try:
                                pattern = pattern.pattern
                            except:
                                pattern = str(pattern)
                        # Asena ^. -> ^[.] ve ^\. -> ^[.] normalizasyonu (lazy PATTERNS)
                        if isinstance(pattern, str):
                            try:
                                from userbot import PATTERNS as _PAT
                            except:
                                _PAT = "."
                            _pat_char = _PAT[:1] if _PAT else "."
                            if "^." in pattern:
                                pattern = pattern.replace("^.", "^[" + _re.escape(_pat_char) + "]")
                            elif pattern.startswith("\\."):
                                # Telethon r"\\.xxx" -> "^[.]xxx" (komutlar hep ^ ile başlar, ekle)
                                pattern = "^[" + _re.escape(_pat_char) + "]" + pattern[2:]
                            elif pattern.startswith(".") and not pattern.startswith("^["):
                                # nadir: ".xxx" -> "^[.]xxx"
                                pattern = "^[" + _re.escape(_pat_char) + "]" + pattern[1:]
                        # Asena pattern zaten ^[.] şeklinde, regex olarak kullan
                        # Robust: regex + fallback simple prefix (dosya ismi değil komut bazlı)
                        try:
                            flt = flt & _filters.regex(pattern)
                        except Exception as e:
                            print(f"regex filter hata {pattern}: {e}", flush=True)
                            flt = flt
                    except Exception as e:
                        print(f"pattern regex hata {pattern}: {e}", flush=True)
                        try:
                            flt = flt & _filters.regex(_re.escape(str(pattern)))
                        except:
                            pass
                # groups_only varsa ekle (Asena'da groups_only argümanı vardı ama biz pop etmiştik)
                # Şimdilik sadece me+regex
                async def _asena_wrapper(client, message, _func=func, _pat=pattern):
                    # DEBUG: her tetiklemeyi logla
                    try:
                        txt = (message.text or message.caption or "")[:80]
                        print(f"🔥 WRAPPER tetiklendi: {getattr(_func,'__name__',str(_func))} pat={_pat} text={repr(txt)} from={getattr(message.from_user,'id',0)} chat={getattr(message.chat,'id',0)} out={getattr(message,'outgoing',False)} is_self={getattr(getattr(message,'from_user',None),'is_self',None)}", flush=True)
                    except: pass
                    ev = AsenaEvent(client, message, _pat)
                    try:
                        # Signature kontrolü: tek arg mı iki arg mı? (ayrı try - func hatasını yutma)
                        import inspect as _ins
                        n_params = 1
                        try:
                            sig = _ins.signature(_func)
                            n_params = len(list(sig.parameters.values()))
                        except (ValueError, TypeError):
                            n_params = 1
                        if n_params == 1:
                            await _func(ev)
                        elif n_params >= 2:
                            try:
                                await _func(ev)
                            except TypeError as te:
                                msg_te = str(te)
                                if "positional" in msg_te or "missing" in msg_te or "takes" in msg_te or "too many" in msg_te:
                                    await _func(client, message)
                                else:
                                    raise
                        else:
                            await _func(ev)
                    except BaseException as e:
                        err_str = str(e)
                        err_low = err_str.lower()
                        # Mesaj silindiyse — spam yapma, sessizce dur (tüm animasyon pluginleri: .surf vb için)
                        if "message_id_invalid" in err_low or "message to edit not found" in err_low or "message not found" in err_low or "msg_id_invalid" in err_low or e.__class__.__name__ == "MessageDeletedError":
                            print(f"🛑 plugin durduruldu — mesaj silindi: {getattr(_func,'__name__',str(_func))} chat={getattr(message.chat,'id',0)}", flush=True)
                            return
                        if "FloodWait" in err_str:
                            try:
                                import re as _re2
                                sec = int(_re2.search(r'(\d+)', err_str).group(1)) if _re2.search(r'(\d+)', err_str) else 5
                                print(f"handler FloodWait {sec}s {getattr(_func,'__name__',str(_func))}", flush=True)
                                import asyncio as _aio
                                await _aio.sleep(sec+1)
                            except:
                                pass
                            return
                        if not isinstance(e, Exception):
                            print(f"handler base hata {getattr(_func,'__name__',str(_func))}: {e}\n{traceback.format_exc()}", flush=True)
                            return
                        print(f"handler hata {getattr(_func,'__name__',str(_func))}: {e}\n{traceback.format_exc()}", flush=True)
                        try:
                            await message.reply_text("hata verdim @")
                        except:
                            pass
                app.add_handler(_MH(_asena_wrapper, flt))
                asena_reg = (asena_reg or 0) + 1
                print(f"→ handler eklendi: {getattr(func,'__name__',str(func))} pattern={pattern}", flush=True)
            except Exception as e:
                print(f"register hata {pattern}: {e}\n{traceback.format_exc()}", flush=True)
        if asena_reg:
            return f"{asena_reg} komut"
    except Exception as e:
        # shim yoksa veya hata olursa sessiz geç
        # print(f"asena shim hatası: {e}", flush=True)
        pass

    # farklı isimleri dene (Pyrogram native) — sadece modülün kendi tanımladığı fonksiyonlar
    for fn_name in ("register_handlers", "setup", "init", "register"):
        if fn_name in mod.__dict__:
            fn = mod.__dict__[fn_name]
            if callable(fn):
                # Asena'nın `from userbot.events import register` importini atla — o dekoratör, entry point değil
                if fn_name == "register" and getattr(fn, "__module__", "") == "userbot.events":
                    continue
                try:
                    fn(app)
                    return fn_name
                except Exception as e:
                    print(f"plugin {mod.__name__} {fn_name} hata: {e}\n{traceback.format_exc()}", flush=True)
                    raise
    # hiçbiri yoksa, modülün kendisi handler eklemiş olabilir (import sırasında)
    # o yüzden başarılı say ama uyar
    if asena_reg:
        return f"{asena_reg} komut"
    print(f"plugin {mod.__name__} uyarı: register_handlers bulunamadı, dosya import edildi ama handler eklememiş olabilir", flush=True)
    return None

def load_plugin(app, name: str):
    """Tek plugin yükle (dosyadan)"""
    path = get_plugin_path(name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"plugin yok: {name}")
    # Asena pending temizle (önceki plugin artığı kalmasın)
    try:
        from userbot import ASENA_PENDING
        ASENA_PENDING.clear()
    except Exception:
        pass
    # önceki varsa temizle
    mod_key = f"custom_plugins.{_sanitize(name)}"
    if mod_key in sys.modules:
        try:
            del sys.modules[mod_key]
        except:
            pass
    # telethon shim — Asena pluginleri `from telethon import events` yaparsa hata vermesin
    try:
        import sys as _sys
        if "telethon" not in _sys.modules:
            import types as _types
            _tele = _types.ModuleType("telethon")
            _tele_events = _types.ModuleType("telethon.events")
            class _Dummy:
                StopPropagation = Exception
                class NewMessage:
                    def __init__(self, *a, **kw): pass
                class MessageEdited:
                    def __init__(self, *a, **kw): pass
            _tele_events.NewMessage = _Dummy.NewMessage
            _tele_events.MessageEdited = _Dummy.MessageEdited
            _tele_events.StopPropagation = _Dummy.StopPropagation
            _tele.events = _tele_events
            _sys.modules["telethon"] = _tele
            _sys.modules["telethon.events"] = _tele_events
    except Exception:
        pass
    # emoji get_emoji_regexp shim — emoji==2.x için uyumluluk
    try:
        import emoji as _emoji
        if not hasattr(_emoji, "get_emoji_regexp"):
            import re as _re
            def _get_emoji_regexp():
                try:
                    # emoji 2.x: EMOJI_DATA
                    emojis = sorted(getattr(_emoji, "EMOJI_DATA", {}).keys(), key=len, reverse=True)
                    if emojis:
                        pattern = "(" + "|".join(_re.escape(e) for e in emojis) + ")"
                        return _re.compile(pattern)
                except Exception:
                    pass
                return _re.compile(r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]+")
            _emoji.get_emoji_regexp = _get_emoji_regexp
    except Exception:
        pass
    mod = _load_module_from_path(path, _sanitize(name))
    _loaded[name] = mod
    try:
        reg = _register_module(app, mod)
        print(f"→ plugin yüklendi: {name} ({reg or 'import-only'})", flush=True)
        return mod, reg
    except Exception as e:
        _loaded.pop(name, None)
        raise

# Log2 Alfa sade mod — native komutlarla çakışan ağır Asena pluginleri atlanır
_NATIVE_COVERED = {"admin","afk","www","chat","whois","profile","purge","tagall","locks","warn","filter","notes","snips","welcomes","pmpermit","blacklist"}
_DISABLE_HEAVY = os.getenv("DISABLE_ASENA_HEAVY", "1").lower() in ("1","true","yes")

def load_all_plugins(app):
    """Başlangıçta tüm pluginleri yükle — sade: native olanlar atlanır, ağır Telethon pluginler opsiyonel"""
    plugins = list_plugins()
    if not plugins:
        print("→ plugin batch: 0 plugin (volume boş)", flush=True)
        return 0, 0, []
    ok, fail, skipped = 0, 0, 0
    errs = []
    for p in plugins:
        name = p["name"]
        # boş dosya kontrolü (list'te zaten filtrelendi ama double-check)
        try:
            if p.get("size", 0) < 10:
                print(f"→ plugin atlandı (boş): {name}", flush=True)
                continue
        except Exception:
            pass
        # sade mod: native Log2 Alfa zaten bu komutları sağlıyor → atla, çakışma/karmaşa olmasın
        if _DISABLE_HEAVY and name.lower() in _NATIVE_COVERED:
            print(f"→ plugin atlandı (native Log2 Alfa var): {name}", flush=True)
            skipped += 1
            continue
        # ağır Telethon/scraper pluginler — env ile kapatılabilir
        if _DISABLE_HEAVY and name.lower() in {"scrapers","scrapers_bot","gdrive","spotify","lyrics","lastfm","aria","galeri","autopp","deepfry"}:
            # bu liste opsiyonel, ama sade modda atlıyoruz (API anahtarı gerektirir)
            print(f"→ plugin atlandı (ağır/API): {name} → sade mod", flush=True)
            skipped += 1
            continue
        try:
            load_plugin(app, name)
            ok += 1
        except Exception as e:
            fail += 1
            errs.append(f"{name}: {e}")
            print(f"plugin load fail {name}: {e}", flush=True)
    if ok or fail or skipped:
        print(f"→ plugin batch: {ok} ok, {fail} fail, {skipped} atlandı(Log2 Alfa sade) / {len(plugins)}", flush=True)
    return ok, fail, errs

def install_from_temp(app, temp_path: str, original_name: str):
    """Temp dosyayı plugin dizinine kopyala ve yükle (userbot .pal) — tüm aktif userbotlara yükle"""
    if not original_name.endswith(".py"):
        raise ValueError("sadece .py dosyası")
    # isim sanitize ama orijinali koru
    base = os.path.basename(original_name)
    if not base.endswith(".py"):
        base += ".py"
    safe = _sanitize(base[:-3]) + ".py"
    dest = os.path.join(PLUGIN_DIR, safe)
    import shutil
    shutil.copy(temp_path, dest)
    # yükle — önce gönderen app'e
    name = safe[:-3]
    try:
        mod, reg = load_plugin(app, name)
        # diğer aktif userbotlara da yükle (her hesap aynı plugin'i görsün)
        try:
            import userbot_core as _uc
            for oid, other_app in list(getattr(_uc, "active_userbots", {}).items()):
                if other_app is app:
                    continue
                try:
                    if other_app and getattr(other_app, "is_connected", False):
                        load_plugin(other_app, name)
                        print(f"→ plugin {name} diğer userbot {oid} için de yüklendi", flush=True)
                except Exception as e2:
                    print(f"plugin {name} diğer bot {oid} yükleme hatası: {e2}", flush=True)
        except Exception:
            pass
        return dest, name, reg
    except Exception as e:
        raise

def delete_plugin(name: str):
    path = get_plugin_path(name)
    existed = os.path.exists(path)
    if existed:
        os.remove(path)
    # modülü temizle
    key = f"custom_plugins.{_sanitize(name)}"
    sys.modules.pop(key, None)
    _loaded.pop(_sanitize(name), None)
    _loaded.pop(name, None)
    return existed

def get_plugin_code(name: str) -> str | None:
    path = get_plugin_path(name)
    if not os.path.exists(path):
        return None
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None

# ── Otomatik plugin izleyici — yeni .py eklendiğinde otomatik yükle (restart gerekmesin)
_plugin_watcher_task = None
_watched_files = set()

async def _plugin_watcher_loop():
    import asyncio
    print("🔍 Plugin watcher başlatıldı — yeni .py dosyaları otomatik yüklenecek", flush=True)
    while True:
        try:
            await asyncio.sleep(10)
            # PLUGIN_DIR'deki yeni dosyaları tara
            try:
                current = set(p.name for p in Path(PLUGIN_DIR).glob("*.py") if p.stat().st_size >= 10)
            except:
                current = set()
            new_files = current - _watched_files
            if new_files:
                for fname in new_files:
                    name = fname[:-3]
                    # zaten atlanan native/heavy ise yine dene ama load_all mantığı ile atlanacak
                    try:
                        import userbot_core as _uc
                        for oid, app in list(getattr(_uc, "active_userbots", {}).items()):
                            try:
                                if app and getattr(app, "is_connected", False):
                                    # eğer zaten yüklü ise atla
                                    key = f"custom_plugins.{_sanitize(name)}"
                                    if key in sys.modules:
                                        continue
                                    load_plugin(app, name)
                                    print(f"🔍 watcher: {name} yüklendi (userbot {oid})", flush=True)
                            except Exception as e:
                                print(f"watcher yükleme hata {name}: {e}", flush=True)
                    except Exception as e:
                        print(f"watcher hata: {e}", flush=True)
                _watched_files.update(new_files)
            # silinen dosyalar için set'i güncelle
            _watched_files.intersection_update(current)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"plugin watcher loop hata: {e}", flush=True)
            await asyncio.sleep(10)

def start_plugin_watcher(app=None):
    global _plugin_watcher_task, _watched_files
    try:
        import asyncio
        # ilk taramada mevcut dosyaları kaydet (tekrar yüklememek için)
        try:
            _watched_files = set(p.name for p in Path(PLUGIN_DIR).glob("*.py") if p.stat().st_size >= 10)
        except:
            _watched_files = set()
        loop = asyncio.get_event_loop()
        if _plugin_watcher_task is None or _plugin_watcher_task.done():
            _plugin_watcher_task = loop.create_task(_plugin_watcher_loop())
            print(f"watcher task oluşturuldu", flush=True)
    except Exception as e:
        print(f"watcher start hata: {e}", flush=True)

"""
Tanılama — userbot'un GÖRDÜĞÜ her mesajı logla.
seen_out sayacı: gelen kendi (OUT) mesajlarını sayar — hesap koruması için.
"""
import time
import re
from pyrogram import Client, filters
from pyrogram.types import Message

# Kendi hesabından gelen (OUT) mesaj sayısı — hesap karışıklığı koruması
seen_out = 0
seen_all = 0

async def debug_all(c: Client, m: Message):
    global seen_out, seen_all
    try:
        seen_all += 1
        txt = (m.text or m.caption or "")[:120].replace("\n", " ")
        src = m.from_user.id if m.from_user else "?"
        is_self = getattr(m.from_user, "is_self", None) if m.from_user else None
        kind = "OUT" if m.outgoing else "IN "
        chat = m.chat.id if m.chat else "?"
        chat_type = getattr(m.chat, "type", "?")
        if m.outgoing:
            seen_out += 1
        print(f"[MSG] {time.strftime('%H:%M:%S')} {kind} chat={chat}({chat_type}) from={src} is_self={is_self} out={m.outgoing} txt={repr(txt)}", flush=True)
        if txt.startswith("."):
            print(f"[CMD] {time.strftime('%H:%M:%S')} {repr(txt)} (out={m.outgoing} is_self={is_self} from={src})", flush=True)
        # Ayrıca regex testi
        if txt.startswith(".afro"):
            print(f"[REGEX-TEST] .afro text matched? {bool(re.search(r'^[.]afro', txt))} txt={repr(txt)}", flush=True)
        # Manual dispatcher check for kritik komutlar — hangi handler match ediyor?
        if txt.startswith(".afro") or txt.startswith(".türküm") or txt.startswith(".hidra") or txt.startswith(".phandler") or txt.startswith(".twt") or txt.startswith(".stag"):
            try:
                hit = 0
                miss = 0
                for group, handlers in sorted(c.dispatcher.groups.items()):
                    for h in handlers:
                        try:
                            fname = getattr(getattr(h, 'callback', None), '__name__', str(getattr(h, 'callback', '')))
                            # skip self
                            if fname in ('debug_all','debug_outgoing','debug_regex','handler_list','afro_test','afro_regex_test'):
                                continue
                            # Only evaluate filters that contain relevant pattern or for afro test all in group 0 limited
                            flt = getattr(h, 'filters', None)
                            # Try handler.check
                            try:
                                ok = await h.check(c, m)
                            except Exception as ce:
                                ok = f"check_err:{ce}"
                            if ok is True:
                                print(f"[MANUAL-CHECK] ✅ MATCH group={group} cb={fname} filter={flt} txt={repr(txt[:30])}", flush=True)
                                hit += 1
                            else:
                                # For afro/turkum/hidra specifically log their own miss
                                if any(k in fname.lower() for k in ('afro','turkum','hidra','stag','twt','phandler')) or any(k in str(flt).lower() for k in ('afro','turkum','hidra','stag','twt')):
                                    print(f"[MANUAL-CHECK] ❌ NO-MATCH group={group} cb={fname} filter={flt} txt={repr(txt[:30])} ok={ok}", flush=True)
                                    miss += 1
                            if hit+miss>20:
                                break
                        except Exception as ie:
                            print(f"[MANUAL-CHECK] inner err {ie}", flush=True)
                    if hit+miss>20:
                        break
                if hit==0:
                    print(f"[MANUAL-CHECK] >>> NO handler matched for {repr(txt[:30])} — groups={list(c.dispatcher.groups.keys())} total={sum(len(v) for v in c.dispatcher.groups.values())}", flush=True)
                else:
                    print(f"[MANUAL-CHECK] >>> {hit} handler(s) matched for {repr(txt[:30])}", flush=True)
            except Exception as e:
                import traceback
                print(f"[MANUAL-CHECK] hata {e}\n{traceback.format_exc()}", flush=True)
    except Exception as e:
        import traceback
        print(f"[MSG] debug hatası: {e}\n{traceback.format_exc()}", flush=True)

async def debug_outgoing(c: Client, m: Message):
    """Sadece outgoing/me için ek log — plugin filtreleriyle aynı"""
    try:
        txt = (m.text or m.caption or "")[:80]
        print(f"[OUT-FILTER] {time.strftime('%H:%M:%S')} txt={repr(txt)} out={m.outgoing} is_self={getattr(getattr(m,'from_user',None),'is_self',None)}", flush=True)
    except: pass

async def debug_regex(c: Client, m: Message):
    try:
        txt = (m.text or m.caption or "") or ""
        import re
        from pyrogram import filters as _f
        # Test a few critical patterns
        for pat, name in [(r"^[.]afro", "afro"), (r"^[.]ping", "ping"), (r"^\.help", "help"), (r"^[.]help", "help2")]:
            try:
                # Re
                re_match = bool(re.search(pat, txt))
                # Pyrogram filter
                flt = _f.regex(pat)
                # Need to call filter with real Message type? Use re directly for now
                # Also test me|outgoing
                me = bool(m.from_user and m.from_user.is_self or getattr(m, "outgoing", False))
                out = bool(getattr(m, "outgoing", False))
                combo = (me or out) and re_match
                if txt.startswith("."):
                    print(f"[REGEX-DEBUG] {time.strftime('%H:%M:%S')} pat={repr(pat):15} name={name:6} txt={repr(txt[:30]):20} re={re_match} me={me} out={out} combo={combo}", flush=True)
            except Exception as e:
                print(f"[REGEX-DEBUG] hata {e}", flush=True)
    except Exception as e:
        import traceback
        print(f"[REGEX-DEBUG] genel hata {e}\n{traceback.format_exc()}", flush=True)


def register_handlers(app: Client):
    from pyrogram.handlers import MessageHandler
    # Her türlü mesajı logla — grup -1 en önce
    try:
        app.add_handler(MessageHandler(debug_all, filters.all), group=-1)
        print("Debug handler -1 (all) eklendi", flush=True)
    except Exception as e:
        print(f"Debug -1 hata {e}", flush=True)
    # OUT filtresiyle de logla
    try:
        app.add_handler(MessageHandler(debug_outgoing, (filters.me | filters.outgoing)), group=-1)
        print("Debug handler -1 (me|outgoing) eklendi", flush=True)
    except Exception as e:
        print(f"Debug out hata {e}", flush=True)
    # Eskisi de kalsın
    try:
        app.add_handler(MessageHandler(debug_all, filters.text | filters.document), group=2)
        print("Debug handler 2 (text|doc) eklendi", flush=True)
    except: pass
    # Regex debug her outgoing için
    try:
        app.add_handler(MessageHandler(debug_regex, (filters.me | filters.outgoing) & filters.regex(r"^\." )), group=0)
        print("Debug regex handler eklendi", flush=True)
    except Exception as e:
        print(f"Debug regex handler hata {e}", flush=True)
    # Handler list debug
    try:
        async def handler_list(c, m):
            try:
                txt = (m.text or "")[:20]
                if txt == ".phandler":
                    from pyrogram.handlers import MessageHandler as MH
                    out = []
                    for group, handlers in sorted(c.dispatcher.groups.items()):
                        out.append(f"Group {group}: {len(handlers)} handlers")
                        for h in handlers[:5]:
                            try:
                                f = getattr(h, 'filters', None)
                                fname = getattr(getattr(h, 'callback', None), '__name__', str(h.callback))[:30]
                                out.append(f"  - {fname} filter={f}")
                            except: pass
                    # Also count total handlers
                    total = sum(len(v) for v in c.dispatcher.groups.values())
                    out.append(f"Total handlers: {total}")
                    # Check afro specifically
                    found_afro = False
                    for group, handlers in c.dispatcher.groups.items():
                        for h in handlers:
                            try:
                                fname = getattr(h.callback, '__name__', '')
                                if 'afro' in str(fname).lower() or 'afro' in str(getattr(h, 'filters', '')):
                                    out.append(f"Found afro in group {group}: {h.callback.__name__} {h.filters}")
                                    found_afro = True
                            except: pass
                    if not found_afro:
                        out.append("Afro handler NOT FOUND in dispatcher!")
                        # List all handler names
                        for group, handlers in c.dispatcher.groups.items():
                            for h in handlers:
                                try:
                                    out.append(f"  handler: {h.callback.__name__} group={group}")
                                except: pass
                                if len(out) > 30: break
                            if len(out) > 30: break
                    await m.reply_text("\n".join(out[:30]))
            except Exception as e:
                import traceback
                print(f"handler_list hata {e}\n{traceback.format_exc()}", flush=True)
        # phandler with both regex and command for robustness
        try:
            app.add_handler(MessageHandler(handler_list, (filters.me | filters.outgoing) & filters.command("phandler", prefixes=".")), group=0)
            print("Debug phandler command eklendi", flush=True)
        except Exception as e:
            print(f"phandler command hata {e}", flush=True)
        app.add_handler(MessageHandler(handler_list, (filters.me | filters.outgoing) & filters.regex(r"^\.phandler")), group=0)
        print("Debug phandler eklendi", flush=True)
        # Afro direct test — filtreli ve filtresiz
        try:
            async def afro_test(c, m):
                print(f"✅ AFRO-TEST tetiklendi: {repr((m.text or '')[:30])}", flush=True)
                try:
                    await m.reply_text("✅ afro-test ok — filtre çalışıyor")
                except: pass
            # Custom filter that definitely should match .afro
            def afro_filter(_, __, m):
                txt = (m.text or m.caption or "")
                return txt.startswith(".afro")
            app.add_handler(MessageHandler(afro_test, (filters.me | filters.outgoing) & filters.create(afro_filter)), group=0)
            print("Afro-test handler eklendi (custom filter)", flush=True)
            # also command variant
            try:
                app.add_handler(MessageHandler(afro_test, (filters.me | filters.outgoing) & filters.command("afro", prefixes=".")), group=0)
                print("Afro-test command eklendi", flush=True)
            except: pass
            # Also with regex
            async def afro_regex_test(c, m):
                print(f"✅ AFRO-REGEX-TEST tetiklendi: {repr((m.text or '')[:30])}", flush=True)
                try:
                    await m.reply_text("✅ afro-regex-test ok")
                except: pass
            app.add_handler(MessageHandler(afro_regex_test, (filters.me | filters.outgoing) & filters.regex(r"^[.]afro")), group=0)
            print("Afro-regex-test handler eklendi", flush=True)
        except Exception as e:
            print(f"afro-test hata {e}", flush=True)
    except Exception as e:
        print(f"phandler hata {e}", flush=True)
    print(f"Debug handler yüklendi (seen_all={seen_all})", flush=True)

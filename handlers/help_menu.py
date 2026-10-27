from pyrogram import Client, filters
from utils.helpers import HELP_TEXT, respond
from utils.security import rate_limit
from utils.fonts import smalls
from userbot import CMD_HELP, CMD_HELP_BOT
from utils.plugin_loader import list_plugins
import re
import pathlib

# Sade Log2 Alfa help — komut bazlı (dosya adı değil)
_DETAILS = {
    "ping": "• .ping → hız + uptime gösterir",
    "log2alfa": "• .log2alfa/.alive → bot durumu + uptime",
    "alive": "• .log2alfa/.alive → bot durumu + uptime",
    "afk": "• .afk <sebep> → afk moda geç, mention/DM gelirse otomatik cevap. Tekrar .afk veya düz yazınca kapanır.",
    "ban": "• .ban (yanıtla veya .ban @user) → gruptan banlar. Yönetici yetkisi gerekir.",
    "unban": "• .unban → banı kaldırır",
    "kick": "• .kick → gruptan atar (ban+unban)",
    "mute": "• .mute → susturur (mesaj engelle)",
    "unmute": "• .unmute → susturmayı kaldırır",
    "promote": "• .promote → yönetici yapar",
    "demote": "• .demote → yöneticilikten alır",
    "pin": "• .pin (mesaja yanıtla) → mesajı sabitler",
    "purge": "• .purge/.del (mesaja yanıtla) → o mesajdan bulunduğun yere kadar siler",
    "del": "• .del/.purge → aynı",
    "tagall": "• .tagall [yazı] → gruptaki herkesi tek tek etiketler. .dur ile durdur.",
    "dur": "• .dur → tagall’ı durdurur",
    "id": "• .id (yanıtla veya boş) → kullanıcı/chat id verir",
    "info": "• .info/.whois (yanıtla/@) → kişi bilgisi (id, isim, username)",
    "whois": "• .whois/.info → aynı",
    "chatinfo": "• .chatinfo → grup bilgisi",
    "hava": "• .hava <şehir> → hava durumu (wttr.in)",
    "hesap": "• .hesap 2+2*3 → matematik",
    "plist": "• .plist → plugin listesi",
    "pal": "• .pal (py dosyaya yanıtla) → plugin yükle",
    "psil": "• .psil <isim> → plugin sil",
    "pget": "• .pget <isim> → plugin dosyasını gönder",
    "efekt": "• .efekt <ad> (fotoğrafa yanıtla)\n• .efekt rastgele\n• .efekt liste",
    "fx": "• .fx <efekt> <metin>\n• .fx liste\n• (mesaja yanıtla) .fx <efekt>",
    "py": "• .py (mesaja yanıtla)\n• .py dosyaadi.py (mesaja yanıtla)\n• .py <kod>",
    "nsave": "• .nsave <ad> (mesaja yanıtla) — not kaydet\n• .not <ad> — göster\n• .notlar — liste\n• .notsil <ad|hepsi> — sil",
    "kaydet": "• .nsave <ad> (mesaja yanıtla) — not kaydet\n• .not <ad> — göster\n• .notlar — liste\n• .notsil <ad|hepsi> — sil",
    "not": "• .nsave <ad> (mesaja yanıtla) — not kaydet\n• .not <ad> — göster\n• .notlar — liste\n• .notsil <ad|hepsi> — sil",
    "gban": "• .gban (yanıtla/@) [sebep] — global yasak (gruptan atar)\n• .ungban — kaldır\n• .gbanlar — liste",
    "gmute": "• .gmute (yanıtla/@) [sebep] — global sustur (mesajları silinir)\n• .ungmute — kaldır\n• .gmutelar — liste",
    "save": "• .save <t.me/link> — linkteki medyayı kaydet\n• .save (medyaya yanıtla) — medyayı kaydet",
    "help": "• .help → bu menü  • .help <komut> → detay (ör: .help ban)  • .help efekt / .help fx",
}

def _extract_cmd_from_pattern(pat: str):
    """Pattern string'den komut adını çıkar — örn '^\\.afk(?: |$)' -> 'afk', '^log2alfa$' -> 'log2alfa', '^.aşk' -> 'aşk' (unicode)"""
    try:
        m = re.search(r'\^[^\w]*(\w{2,})', pat, re.UNICODE)
        if m:
            cand = m.group(1).lower()
            if cand not in ('register','event','pattern','outgoing','incoming','true','false','none','handler','command'):
                return cand
        m2 = re.search(r'(\w{2,})', pat, re.UNICODE)
        if m2:
            cand = m2.group(1).lower()
            if cand not in ('register','event','pattern','true','false'):
                return cand
    except:
        pass
    return None

def _all_commands():
    """Tüm komutları CMD_HELP ve CMD_HELP_BOT'tan + plugin dosyalarından tara — dosya değil komut bazlı"""
    cmds = {}
    # 1) CMD_HELP_BOT daha yapısal: file -> {'commands': {cmd: {...}}}
    try:
        for file, data in CMD_HELP_BOT.items():
            try:
                commands = data.get('commands', {}) if isinstance(data, dict) else {}
                for cmd, info in commands.items():
                    if cmd not in cmds:
                        cmds[cmd] = file
            except: pass
    except: pass
    # 2) CMD_HELP string'lerinden de regex ile çıkar (fallback)
    try:
        for file, txt in CMD_HELP.items():
            try:
                for m in re.finditer(r"`\.(\w+)", txt):
                    cmd = m.group(1).lower()
                    if cmd not in cmds:
                        cmds[cmd] = file
                for m in re.finditer(r"•\s*\.(\w+)", txt):
                    cmd = m.group(1).lower()
                    if cmd not in cmds:
                        cmds[cmd] = file
            except: pass
    except: pass
    # 3) Plugin dosyalarından pattern tarama — her plugin için garanti (çalışmayanlar da)
    try:
        for p in list_plugins():
            name = p['name']
            path = p['path']
            try:
                text = pathlib.Path(path).read_text(encoding='utf-8', errors='ignore')
                # 3a) pattern="..."
                for m in re.finditer(r'pattern\s*=\s*[r]?["\']([^"\']+)["\']', text):
                    pat = m.group(1)
                    cmd = _extract_cmd_from_pattern(pat)
                    if cmd and cmd not in cmds:
                        cmds[cmd] = name
                # 3b) Help.add_command("komut"
                for m in re.finditer(r'\.add_command\s*\(\s*["\'](\w+)["\']', text):
                    cmd = m.group(1).lower()
                    if cmd and cmd not in cmds:
                        cmds[cmd] = name
            except:
                continue
    except:
        pass
    return cmds

@rate_limit(2)
async def help_handler(client: Client, message):
    txt = (message.text or message.caption or "").strip()
    print(f"🔍 HELP tetiklendi: {repr(txt)} from={getattr(message.from_user,'id',0)} chat={getattr(message.chat,'id',0)}", flush=True)
    parts = txt.split()
    if len(parts) >= 2:
        q = parts[1].lstrip(".").lower().strip()
        q = q.split()[0] if q else ""
        if not q:
            q = ""
        print(f"🔍 HELP sorgu: {repr(q)}", flush=True)
        if q in _DETAILS:
            await respond(client, message, smalls(_DETAILS[q]))
            return
        for k,v in _DETAILS.items():
            if q == k.lower():
                await respond(client, message, smalls(v))
                return
        try:
            all_cmds = _all_commands()
            if q in all_cmds:
                file = all_cmds[q]
                help_txt = CMD_HELP.get(file) or CMD_HELP.get(file+".py") or ""
                if help_txt:
                    await respond(client, message, help_txt)
                    return
                data = CMD_HELP_BOT.get(file, {})
                if data:
                    try:
                        cmds = data.get('commands', {})
                        if q in cmds:
                            info = cmds[q]
                            usage = info.get('usage','')
                            params = info.get('params')
                            example = info.get('example')
                            out = f"**📗 Dosya:** `{file}`\n**🛠 Komut:** `.{q}"
                            if params: out += f" {params}"
                            out += "`\n"
                            if usage: out += f"**💬 Açıklama:** `{usage}`\n"
                            if example: out += f"**⌨️ Örnek:** `.{example}`\n"
                            await respond(client, message, out)
                            return
                    except: pass
        except Exception as e:
            print(f"help cmd aramada hata {e}", flush=True)
        q_low = q.lower()
        for k, v in CMD_HELP.items():
            try:
                if q_low == k.lower() or q_low in k.lower():
                    await respond(client, message, v)
                    return
                if f".{q_low}" in v.lower() or f"`{q_low}" in v.lower():
                    await respond(client, message, v)
                    return
            except: pass
        try:
            for p in list_plugins():
                if q_low == p["name"].lower() or q_low in p["name"].lower():
                    help_txt = CMD_HELP.get(p["name"]) or CMD_HELP.get(p["name"]+".py") or ""
                    if help_txt:
                        await respond(client, message, help_txt)
                    else:
                        all_cmds = _all_commands()
                        file_cmds = [c for c,f in all_cmds.items() if f==p["name"]]
                        if file_cmds:
                            cmd_list = ", ".join(f".{c}" for c in file_cmds[:10])
                            await respond(client, message, smalls(f"• {p['name']} → {cmd_list}\n→ .help <komut> ile detay"))
                        else:
                            # son fallback: dosyadan direkt pattern çıkar
                            try:
                                text = pathlib.Path(p["path"]).read_text(encoding='utf-8', errors='ignore')
                                found = []
                                for m in re.finditer(r'pattern\s*=\s*[r]?["\']([^"\']+)["\']', text):
                                    cmd = _extract_cmd_from_pattern(m.group(1))
                                    if cmd:
                                        found.append(cmd)
                                if found:
                                    cmd_list = ", ".join(f".{c}" for c in found[:8])
                                    await respond(client, message, smalls(f"• {p['name']} → {cmd_list}\n→ kullanım: {cmd_list}"))
                                else:
                                    await respond(client, message, smalls(f"• .{p['name']} → plugin yüklü\n→ kullanım: .{p['name']} / .help {p['name']}"))
                            except:
                                await respond(client, message, smalls(f"• .{p['name']} → plugin yüklü\n→ kullanım: .{p['name']} / .help {p['name']}"))
                    return
        except Exception as e:
            print(f"help plugin aramada hata {e}", flush=True)
        await respond(client, message, smalls(f"→ bulunamadı: {q}\n→ .help ile listeye bak\n→ .plist ile plugin listesi"))
        return
    try:
        await message.edit_text(HELP_TEXT)
        print(f"🔍 HELP sade gönderildi len={len(HELP_TEXT)}", flush=True)
    except Exception as e:
        print(f"help hata: {e}", flush=True)
        import traceback; traceback.print_exc()
        await respond(client, message, HELP_TEXT)


@rate_limit(2)
async def phelp_handler(client: Client, message):
    """ .phelp — tüm pluginler ve komutları profesyonel liste (her plugin garanti, Asena yok) — 50/sayfa """
    try:
        txt = (message.text or message.caption or "").strip()
        print(f"🔍 PHELP tetiklendi: {repr(txt)} from={getattr(message.from_user,'id',0)}", flush=True)
        parts = txt.split()
        arg = parts[1] if len(parts) > 1 else ""
        arg = arg.strip().lstrip(".").lower()

        plugins = list_plugins()
        all_cmds = _all_commands()
        from collections import defaultdict
        grouped = defaultdict(list)
        for cmd, file in all_cmds.items():
            grouped[file].append(cmd)
        total_plugins = len(plugins)
        total_cmds = len(all_cmds)

        if arg and not arg.isdigit():
            for p in plugins:
                if p['name'].lower() == arg:
                    name = p['name']
                    cmds = grouped.get(name, [])
                    if not cmds:
                        try:
                            text = pathlib.Path(p['path']).read_text(encoding='utf-8', errors='ignore')
                            extra = []
                            for m in re.finditer(r'pattern\s*=\s*[r]?[\"\']([^\"\']+)[\"\']', text):
                                cmd = _extract_cmd_from_pattern(m.group(1))
                                if cmd and cmd not in extra:
                                    extra.append(cmd)
                            if extra:
                                cmds = extra
                            if not cmds:
                                for m in re.finditer(r'\.add_command\s*\(\s*[\"\'](\w+)[\"\']', text):
                                    c = m.group(1).lower()
                                    if c not in cmds:
                                        cmds.append(c)
                        except:
                            pass
                    if cmds:
                        uniq = sorted(set(cmds))
                        cmd_str = ", ".join(f".{c}" for c in uniq)
                        out = smalls(f"✦ {name} → {len(uniq)} komut\n━━━━━━━━━━━━━━━━\n{cmd_str}\n━━━━━━━━━━━━━━━━\n→ .help <komut> ile detay")
                    else:
                        out = smalls(f"✦ {name}\n→ komut bulunamadı — dosya: {p['path']}")
                    await respond(client, message, out)
                    return
            if arg in all_cmds:
                file = all_cmds[arg]
                help_txt = CMD_HELP.get(file) or CMD_HELP.get(file+".py") or ""
                if help_txt:
                    await respond(client, message, help_txt)
                    return
                await respond(client, message, smalls(f"• .{arg} → dosya: {file}\n→ .help {arg} ile detay"))
                return

        per = 50
        page = 1
        if arg.isdigit():
            try:
                page = int(arg)
            except:
                page = 1
        sorted_plugins = sorted(plugins, key=lambda x: x['name'].lower())
        total_pages = (total_plugins + per - 1)//per if total_plugins else 1
        page = max(1, min(page, total_pages))
        start = (page-1)*per
        chunk_plugins = sorted_plugins[start:start+per]

        lines = []
        lines.append(smalls(f"✦ Pluginler ({total_plugins}) • Komutlar ({total_cmds}) — Log2Alfa"))
        lines.append(smalls(f"━ Sayfa {page}/{total_pages} (50/sayfa) ━━━━━━━━━━━━━━━━"))
        for p in chunk_plugins:
            name = p['name']
            cmds = grouped.get(name, [])
            if not cmds:
                try:
                    text = pathlib.Path(p['path']).read_text(encoding='utf-8', errors='ignore')
                    extra = []
                    for m in re.finditer(r'pattern\s*=\s*[r]?[\"\']([^\"\']+)[\"\']', text):
                        cmd = _extract_cmd_from_pattern(m.group(1))
                        if cmd and cmd not in extra:
                            extra.append(cmd)
                    if extra:
                        cmds = extra
                    if not cmds:
                        for m in re.finditer(r'\.add_command\s*\(\s*[\"\'](\w+)[\"\']', text):
                            c = m.group(1).lower()
                            if c not in cmds:
                                cmds.append(c)
                except:
                    pass
            if cmds:
                uniq = sorted(set(cmds))[:8]
                cmd_str = ", ".join(f".{c}" for c in uniq)
                if len(cmds) > 8:
                    cmd_str += f" +{len(set(cmds))-8}"
                lines.append(smalls(f"• {name} → {cmd_str}"))
            else:
                lines.append(smalls(f"• {name}"))
        lines.append(smalls("━━━━━━━━━━━━━━━━"))
        lines.append(smalls(f"→ .phelp 1 / .phelp 2 ... ile sayfa değiştir"))
        lines.append(smalls(f"→ .help <komut> ile detay — örnek: .help afk"))
        text = "\n".join(lines)
        await respond(client, message, text)
        print(f"🔍 PHELP gönderildi page={page}/{total_pages} plugins={total_plugins} cmds={total_cmds}", flush=True)
    except Exception as e:
        print(f"phelp hata: {e}", flush=True)
        import traceback; traceback.print_exc()
        await respond(client, message, smalls(f"phelp hata: {e}"))

def register_handlers(app: Client):
    from pyrogram.handlers import MessageHandler
    app.add_handler(MessageHandler(help_handler, filters.command(["help","yardim","menu"], prefixes=".") & (filters.me | filters.outgoing)))
    app.add_handler(MessageHandler(help_handler, filters.regex(r"^\.help(?:\s|$|@)") & (filters.me | filters.outgoing)))
    app.add_handler(MessageHandler(phelp_handler, filters.command(["phelp","ph","pluginhelp","chelp"], prefixes=".") & (filters.me | filters.outgoing)))
    app.add_handler(MessageHandler(phelp_handler, filters.regex(r"^\.phelp(?:\s|$|@)") & (filters.me | filters.outgoing)))
    print("✅ help_menu handler eklendi (command + regex) + phelp", flush=True)

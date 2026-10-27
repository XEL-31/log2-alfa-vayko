"""
Log2 Alfa CLI doğrulama (sade set) — her komut tek tek:
1) handler kayıtlı mı  2) filtre eşleşiyor mu  3) handler çalışıyor mu
"""
import asyncio, os, sys, types, re, json
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def fake_urlopen(url, timeout=None, *a, **k):
    u = getattr(url, "full_url", None) or str(url)
    class R:
        def read(self):
            if "openrouter.ai" in u or "groq.com" in u:
                return json.dumps({"choices":[{"message":{"content":"Merhaba! Ben Log2Alfa."}}]}).encode()
            if "loader.to" in u and "download.php" in u:
                return json.dumps({
                    "success": True,
                    "title": "test şarkı",
                    "info": {"title": "test şarkı"},
                    "progress_url": "https://lto2.affadaffa.com/api/progress?id=fake",
                }).encode()
            if "progress" in u and ("affadaffa" in u or "savenow" in u or "lto2" in u):
                return json.dumps({
                    "success": 1,
                    "progress": 1000,
                    "download_url": "https://example.com/fake.mp3",
                }).encode()
            if "example.com/fake.mp3" in u:
                return b"fakeaudio" * 500
            if "youtube.com/results" in u:
                return b'"videoId":"dQw4w9WgXcQ","title":{"runs":[{"text":"test sarki"}]'
            return json.dumps({"current_condition":[{"temp_C":"22","FeelsLikeC":"23","humidity":"50","windspeedKmph":"5","weatherDesc":[{"value":"Sunny"}]}]}).encode()
        def __enter__(self): return self
        def __exit__(self, *a): return False
        headers = {}
    return R()

async def fake_sleep(t): pass

class FakeYDL:
    def __init__(self, opts): self.opts = opts
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def extract_info(self, url, download=False):
        path = self.opts["outtmpl"].replace("%(title)s", "test").replace("%(ext)s", "m4a")
        with open(path, "wb") as f: f.write(b"fakeaudio" * 200)  # >1KB
        return {"title": "test şarkı"}

class FakeClient:
    def __init__(self):
        self.handlers = []
        self.me = types.SimpleNamespace(id=0, username="rahmetizm", first_name="rahmet")
        self.is_connected = True
        self.name = "fake"
    def add_handler(self, h, group=0): self.handlers.append(h)
    async def get_me(self): return self.me
    async def invoke(self, *a, **k):
        # mock: GetFullUser -> (UserFull, User, contacts)
        return (types.SimpleNamespace(about="mock bio"), None, [])
    async def get_chat(self, cid): return types.SimpleNamespace(id=cid, title="Test", type="private", username=None)
    async def get_users(self, *a, **k):
        return [types.SimpleNamespace(id=111, first_name="Test", last_name="", username="test", is_bot=False)]
    async def get_chat_member(self, *a, **k):
        return types.SimpleNamespace(user=types.SimpleNamespace(id=111, first_name="Test"))
    async def download_media(self, *a, **k): return None
    async def send_message(self, *a, **k): return types.SimpleNamespace(id=1, delete=AsyncMock())
    async def send_document(self, *a, **k): return types.SimpleNamespace(id=1)
    async def send_audio(self, *a, **k): return types.SimpleNamespace(id=1)
    async def delete_messages(self, *a, **k): pass

def make_msg(text, outgoing=True, reply=None, chat_id=1, from_id=0):
    m = MagicMock()
    m.text = text; m.caption = None; m.outgoing = outgoing; m.id = 42
    m.command = text.split() if text else []
    m.reply_to_message = reply
    ctype = "group" if (text or "").startswith((".tagall", ".dur", ".tag ", ".stop")) else "private"
    if ctype == "group":
        chat_id = chat_id if chat_id < 0 else -1001998351208
    m.chat = types.SimpleNamespace(id=chat_id, type=ctype, title="TestGroup", username=None)
    m.from_user = types.SimpleNamespace(id=from_id, first_name="rahmet", last_name="", username="rahmetizm", is_bot=False, is_self=outgoing)
    m.document = None; m.photo = None; m.entities = []; m.edited = None
    async def edit(t, *a, **k):
        m.edited = t
        return m
    m.edit_text = edit
    m.reply_text = AsyncMock(return_value=types.SimpleNamespace(id=43, delete=AsyncMock()))
    m.delete = AsyncMock(); m.copy = AsyncMock(return_value=types.SimpleNamespace(id=44))
    return m

def main():
    client = FakeClient()
    import handlers.alive as alive_h
    import handlers.help_menu as help_h
    import handlers.tools as tools_h
    import handlers.weather as weather_h
    import handlers.calculator as calc_h
    import handlers.ai as ai_h
    import handlers.music as music_h
    import handlers.tagall as tagall_h
    import handlers.debug as dbg_h
    for r in (alive_h, help_h, tools_h, weather_h, calc_h, ai_h, music_h, tagall_h, dbg_h):
        r.register_handlers(client)

    print(f"Toplam handler: {len(client.handlers)}")

    # Çift kayıt kontrolü
    from collections import Counter
    cnt = Counter()
    for h in client.handlers:
        s = str(h.filters)
        if "command" in s:
            part = s.split("prefixes")[0]
            for cc in re.findall(r"'([^']+)'", part) + re.findall(r'"([^"]+)"', part):
                if cc and cc != ".":
                    cnt[cc.strip()] += 1
    dups = {k: v for k, v in cnt.items() if v > 1}
    print("ÇİFT KAYIT:", dups if dups else "YOK ✓")

    TESTS = [".ping", ".help", ".log2alfa", ".afk deneme",
             ".hava Gaziantep", ".hesap 25*4+10", ".ai merhaba",
             ".indir https://youtu.be/test", ".indir tarkan kuzu kuzu", ".tagall test", ".dur"]

    async def run_tests():
        results = []
        for cmd_text in TESTS:
            msg = make_msg(cmd_text)
            matched, errors, ran = 0, [], []
            for h in client.handlers:
                try:
                    fmatch = await h.filters(client, msg)
                except Exception as e:
                    errors.append(f"filter:{e}")
                    continue
                if fmatch:
                    matched += 1
                    try:
                        with patch("time.sleep", lambda *a, **k: None), patch("urllib.request.urlopen", fake_urlopen), patch("asyncio.sleep", fake_sleep), patch("yt_dlp.YoutubeDL", FakeYDL):
                            await h.callback(client, msg)
                        ran.append(getattr(h.callback, "__name__", "?"))
                    except Exception as e:
                        errors.append(f"{getattr(h.callback,'__name__','?')}:{type(e).__name__}:{str(e)[:60]}")
            errors = [e for e in errors if "Regex filter doesn't work" not in e]
            status = "✓" if (matched >= 1 and not errors) else "✗"
            results.append((cmd_text, matched, errors, ran, msg.edited))
            extra = f"  → {','.join(ran)}" if ran else ""
            err = f"  HATA: {'; '.join(errors[:3])}" if errors else ""
            print(f"{status} {cmd_text:16s} eşleşen:{matched}  edit:{'evet' if msg.edited else 'hayır'}{extra}{err}")
        return results

    loop = asyncio.new_event_loop()
    results = loop.run_until_complete(run_tests())
    ok = sum(1 for _, m, e, _, _ in results if m >= 1 and not e)
    print(f"\n=== SONUÇ: {ok}/{len(results)} komut AKTİF ===")

main()

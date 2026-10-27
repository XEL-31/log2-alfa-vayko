import importlib, sys
mods = ["requests","aiosqlite","pyrogram","PIL","dotenv"]
missing=[]
for m in mods:
    try:
        importlib.import_module(m)
        print(f"✅ {m}")
    except Exception as e:
        print(f"❌ {m}: {e}")
        missing.append(m)
if missing:
    print("\nEksik modüller:", missing)
    print("Çözüm: .\\venv\\Scripts\\python.exe -m pip install -r requirements_windows.txt")
else:
    print("\nHepsi hazır, python main.py ile başlat")

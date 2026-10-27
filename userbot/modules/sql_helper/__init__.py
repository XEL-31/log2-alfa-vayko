# Asena sql_helper shim — Pyrogram Log2 Alfa için dummy sqlalchemy
# Gerçek DB işlemleri yok, sadece import hatasını önlemek için
try:
    from sqlalchemy import create_engine
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import sessionmaker, scoped_session
    from userbot import DB_URI
    BASE = declarative_base()
    def start():
        try:
            engine = create_engine(DB_URI or "sqlite:///log2alfa.db")
            BASE.metadata.bind = engine
            BASE.metadata.create_all(engine)
            return scoped_session(sessionmaker(bind=engine, autoflush=False))
        except Exception as e:
            print(f"sql_helper start dummy fallback: {e}")
            class _Dummy:
                def __call__(self, *a, **kw): return self
                def __getattr__(self, n): return _Dummy()
                def add(self, *a, **kw): pass
                def commit(self): pass
                def query(self, *a, **kw): return self
                def filter(self, *a, **kw): return self
                def all(self): return []
                def first(self): return None
                def delete(self, *a, **kw): pass
            return _Dummy()
    SESSION = start()
except Exception as e:
    print(f"sql_helper dummy init: {e}")
    # Dummy BASE that can be subclassed (like declarative_base)
    class _DummyBase:
        metadata = type('obj', (), {'bind': None, 'create_all': lambda x: None})()
        def __init__(self, *a, **kw): pass
    BASE = _DummyBase
    class _DummySession:
        def __call__(self, *a, **kw): return self
        def __getattr__(self, n): return _DummySession()
        def add(self, *a, **kw): pass
        def commit(self): pass
        def query(self, *a, **kw): return self
        def filter(self, *a, **kw): return self
        def all(self): return []
        def first(self): return None
        def delete(self, *a, **kw): pass
        def close(self): pass
    SESSION = _DummySession()

"""Matematik — .hesap <ifade> (güvenli ast tabanlı)"""
import ast, operator
from pyrogram import Client, filters
from utils.security import rate_limit
from utils.helpers import respond

_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv, ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def safe_eval(expr: str):
    """Sadece + - * / // % ** ve ( ) — başka hiçbir şey çalışmaz"""
    try:
        node = ast.parse(expr, mode="eval")

        def ev(n):
            if isinstance(n, ast.Expression):
                return ev(n.body)
            if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
                return n.value
            if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
                return _OPS[type(n.op)](ev(n.left), ev(n.right))
            if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
                return _OPS[type(n.op)](ev(n.operand))
            raise ValueError("izinsiz ifade")

        return ev(node)
    except ZeroDivisionError:
        return "sıfıra bölünemez"
    except Exception:
        return None


@rate_limit(2)
async def calc_handler(client: Client, message):
    expr = " ".join(message.command[1:]).strip()
    if not expr:
        await respond(client, message, "kullanım: `.hesap 25*4+10`")
        return
    result = safe_eval(expr)
    if result is None:
        await respond(client, message, "ifade okunamadı — sadece `+ - * / // % **` ve `()` kullan")
    else:
        if isinstance(result, float) and result == int(result):
            result = int(result)
        await respond(client, message, f"= `{result}`")


def register_handlers(app: Client):
    from pyrogram.handlers import MessageHandler
    app.add_handler(MessageHandler(calc_handler, filters.command(["hesap", "math", "matematik"], prefixes=".") & (filters.me | filters.outgoing)))

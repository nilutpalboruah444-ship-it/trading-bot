import os
import hmac
import hashlib
import time
import json
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

load_dotenv()

TELEGRAM_TOKEN = os.getenv(8796352082:AAF8dHX-V5k_vAVfSuUE2UQ2J6Sao6mtqYM)
DELTA_API_KEY  = os.getenv(TvcLRzxO9juy43VkqNBN3zXa9BsxuP)
DELTA_SECRET   = os.getenv(0IGK7aaJsMwN72XyGICikgkeH5LLsnD6AjlGTE2lAHsrwhJ1kAk8pn9GKKyE)
)
BASE_URL = "https://cdn-ind.testnet.deltaex.org"

ALLOWED_USER_IDS = [123456789]  # Replace with your Telegram user ID

def get_headers(method, path, body=""):
    timestamp = str(int(time.time()))
    message   = method + timestamp + path + body
    signature = hmac.new(
        DELTA_SECRET.encode(), message.encode(), hashlib.sha256
    ).hexdigest()
    return {
        "api-key":      DELTA_API_KEY,
        "timestamp":    timestamp,
        "signature":    signature,
        "Content-Type": "application/json",
    }

def get_product_id(symbol):
    r = requests.get(f"{BASE_URL}/v2/products").json()
    return next((p["id"] for p in r["result"] if p["symbol"] == symbol), None)

def place_order(symbol, side, size, order_type="market_order", limit_price=None):
    path = "/v2/orders"
    product_id = get_product_id(symbol)
    if not product_id:
        return {"error": f"Symbol {symbol} not found"}
    payload = {"product_id": product_id, "size": size, "side": side, "order_type": order_type}
    if limit_price:
        payload["limit_price"] = limit_price
    body = json.dumps(payload)
    r = requests.post(BASE_URL + path, headers=get_headers("POST", path, body), data=body)
    return r.json()

def get_positions():
    path = "/v2/positions/margined"
    r = requests.get(BASE_URL + path, headers=get_headers("GET", path))
    return r.json()

def get_balance():
    path = "/v2/wallet/balances"
    r = requests.get(BASE_URL + path, headers=get_headers("GET", path))
    return r.json()

def is_authorized(update):
    return update.effective_user.id in ALLOWED_USER_IDS

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): return
    await update.message.reply_text(
        "🤖 Delta Exchange Trading Bot\n\n"
        "/buy BTCUSD 10\n"
        "/sell BTCUSD 10\n"
        "/limit buy BTCUSD 10 60000\n"
        "/positions\n"
        "/balance"
    )

async def buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): return
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /buy SYMBOL SIZE")
        return
    symbol, size = args[0].upper(), int(args[1])
    await update.message.reply_text(f"⏳ Placing BUY {size}x {symbol}...")
    result = place_order(symbol, "buy", size)
    if result.get("success"):
        o = result["result"]
        await update.message.reply_text(f"✅ BUY placed!\nOrder ID: {o['id']}\nStatus: {o['state']}")
    else:
        await update.message.reply_text(f"❌ Failed: {result}")

async def sell(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): return
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /sell SYMBOL SIZE")
        return
    symbol, size = args[0].upper(), int(args[1])
    await update.message.reply_text(f"⏳ Placing SELL {size}x {symbol}...")
    result = place_order(symbol, "sell", size)
    if result.get("success"):
        o = result["result"]
        await update.message.reply_text(f"✅ SELL placed!\nOrder ID: {o['id']}\nStatus: {o['state']}")
    else:
        await update.message.reply_text(f"❌ Failed: {result}")

async def limit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): return
    args = ctx.args
    if len(args) < 4:
        await update.message.reply_text("Usage: /limit buy BTCUSD 10 60000")
        return
    side, symbol, size, price = args[0], args[1].upper(), int(args[2]), args[3]
    result = place_order(symbol, side, size, "limit_order", price)
    if result.get("success"):
        await update.message.reply_text(f"✅ Limit {side.upper()} placed @ {price}")
    else:
        await update.message.reply_text(f"❌ Failed: {result}")

async def positions(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): return
    data = get_positions()
    open_pos = [p for p in data.get("result", []) if float(p.get("size", 0)) != 0]
    if not open_pos:
        await update.message.reply_text("No open positions.")
        return
    msg = "📊 Open Positions:\n\n"
    for p in open_pos:
        msg += f"• {p['product_symbol']}: {p['size']} @ {p['entry_price']} | PnL: {p.get('unrealized_pnl','N/A')}\n"
    await update.message.reply_text(msg)

async def balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): return
    data = get_balance()
    msg = "💰 Wallet Balance:\n\n"
    for a in data.get("result", []):
        if float(a.get("balance", 0)) > 0:
            msg += f"• {a['asset_symbol']}: {a['balance']}\n"
    await update.message.reply_text(msg)

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start",     start))
app.add_handler(CommandHandler("buy",       buy))
app.add_handler(CommandHandler("sell",      sell))
app.add_handler(CommandHandler("limit",     limit))
app.add_handler(CommandHandler("positions", positions))
app.add_handler(CommandHandler("balance",   balance))

print("Bot running...")
app.run_polling()

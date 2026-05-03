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

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DELTA_API_KEY  = os.getenv("DELTA_API_KEY")
DELTA_SECRET   = os.getenv("DELTA_SECRET")

BASE_URL = "https://cdn-ind.testnet.deltaex.org"

ALLOWED_USER_IDS = [your_user_id_here]  # replace with your real ID

# ── Delta Helpers ────────────────────────────────────
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

def get_xrp_price():
    r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ripple&vs_currencies=usd&include_24hr_change=true&include_market_cap=true")
    return r.json().get("ripple", {})

def is_authorized(update):
    return update.effective_user.id in ALLOWED_USER_IDS

# ── XRP Commands ─────────────────────────────────────
async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 Available Commands:\n\n"
        "📊 XRP Signals:\n"
        "/signal - Get XRP buy/sell/neutral signal\n"
        "/price  - Live XRP price snapshot\n"
        "/stats  - XRP market stats and ATH\n\n"
        "💹 Delta Trading:\n"
        "/buy BTCUSD 10\n"
        "/sell BTCUSD 10\n"
        "/limit buy BTCUSD 10 60000\n"
        "/positions\n"
        "/balance"
    )

async def price_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = get_xrp_price()
    if not data:
        await update.message.reply_text("Could not fetch XRP price.")
        return
    price  = data.get("usd", "N/A")
    change = data.get("usd_24h_change", 0)
    emoji  = "🟢" if change > 0 else "🔴"
    await update.message.reply_text(
        f"💰 XRP Price\n\n"
        f"Price: ${price}\n"
        f"{emoji} 24h Change: {change:.2f}%"
    )

async def signal_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = get_xrp_price()
    change = data.get("usd_24h_change", 0)
    price  = data.get("usd", "N/A")
    if change > 2:
        signal = "🟢 BUY"
        reason = "Strong upward momentum"
    elif change < -2:
        signal = "🔴 SELL"
        reason = "Strong downward momentum"
    else:
        signal = "🟡 NEUTRAL"
        reason = "Low volatility, wait for clearer signal"
    await update.message.reply_text(
        f"📡 XRP Signal\n\n"
        f"Signal: {signal}\n"
        f"Price:  ${price}\n"
        f"Reason: {reason}\n"
        f"24h:    {change:.2f}%"
    )

async def stats_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = get_xrp_price()
    price  = data.get("usd", "N/A")
    mcap   = data.get("usd_market_cap", "N/A")
    change = data.get("usd_24h_change", 0)
    await update.message.reply_text(
        f"📊 XRP Market Stats\n\n"
        f"Price:      ${price}\n"
        f"Market Cap: ${mcap:,.0f}\n"
        f"24h Change: {change:.2f}%\n"
        f"ATH:        $3.84 (Jan 2018)"
    )

# ── Trading Commands ─────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): return
    await update.message.reply_text(
        "🤖 XRP Signals + Delta Trading Bot\n\n"
        "📊 /signal /price /stats /help\n"
        "💹 /buy /sell /limit /positions /balance"
    )

async def buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): return
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /buy SYMBOL SIZE\nExample: /buy BTCUSD 10")
        return
    symbol, size = args[0].upper(), int(args[1])
    await update.message.reply_text(f"Placing BUY {size}x {symbol}...")
    result = place_order(symbol, "buy", size)
    if result.get("success"):
        o = result["result"]
        await update.message.reply_text(f"BUY placed!\nOrder ID: {o['id']}\nStatus: {o['state']}")
    else:
        await update.message.reply_text(f"Failed: {result}")

async def sell(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): return
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /sell SYMBOL SIZE")
        return
    symbol, size = args[0].upper(), int(args[1])
    await update.message.reply_text(f"Placing SELL {size}x {symbol}...")
    result = place_order(symbol, "sell", size)
    if result.get("success"):
        o = result["result"]
        await update.message.reply_text(f"SELL placed!\nOrder ID: {o['id']}\nStatus: {o['state']}")
    else:
        await update.message.reply_text(f"Failed: {result}")

async def limit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): return
    args = ctx.args
    if len(args) < 4:
        await update.message.reply_text("Usage: /limit buy BTCUSD 10 60000")
        return
    side, symbol, size, price = args[0], args[1].upper(), int(args[2]), args[3]
    result = place_order(symbol, side, size, "limit_order", price)
    if result.get("success"):
        await update.message.reply_text(f"Limit {side.upper()} placed @ {price}")
    else:
        await update.message.reply_text(f"Failed: {result}")

async def positions(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): return
    data = get_positions()
    open_pos = [p for p in data.get("result", []) if float(p.get("size", 0)) != 0]
    if not open_pos:
        await update.message.reply_text("No open positions.")
        return
    msg = "📊 Open Positions:\n\n"
    for p in open_pos:
        msg += f"{p['product_symbol']}: {p['size']} @ {p['entry_price']} | PnL: {p.get('unrealized_pnl','N/A')}\n"
    await update.message.reply_text(msg)

async def balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): return
    data = get_balance()
    msg = "💰 Wallet Balance:\n\n"
    for a in data.get("result", []):
        if float(a.get("balance", 0)) > 0:
            msg += f"{a['asset_symbol']}: {a['balance']}\n"
    await update.message.reply_text(msg)

# ── Run ──────────────────────────────────────────────
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start",     start))
app.add_handler(CommandHandler("help",      help_cmd))
app.add_handler(CommandHandler("price",     price_cmd))
app.add_handler(CommandHandler("signal",    signal_cmd))
app.add_handler(CommandHandler("stats",     stats_cmd))
app.add_handler(CommandHandler("buy",       buy))
app.add_handler(CommandHandler("sell",      sell))
app.add_handler(CommandHandler("limit",     limit))
app.add_handler(CommandHandler("positions", positions))
app.add_handler(CommandHandler("balance",   balance))

print("Bot running...")
app.run_polling()

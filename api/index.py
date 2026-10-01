import os
import json
import requests
from http.server import BaseHTTPRequestHandler


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL = os.getenv("TELEGRAM_CHANNEL", "@steamtopdeals")


def telegram_send(text):
    if not TELEGRAM_BOT_TOKEN:
        return {
            "success": False,
            "error": "TELEGRAM_BOT_TOKEN is not configured"
        }

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    response = requests.post(
        url,
        json={
            "chat_id": TELEGRAM_CHANNEL,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        },
        timeout=15
    )

    return response.json()


def get_game(appid, country):
    url = "https://store.steampowered.com/api/appdetails"

    response = requests.get(
        url,
        params={
            "appids": appid,
            "cc": country,
            "l": "english",
            "filters": "price_overview"
        },
        headers={
            "User-Agent": "Mozilla/5.0"
        },
        timeout=15
    )

    data = response.json()
    game = data.get(str(appid), {})

    if not game.get("success"):
        return None

    return game.get("data", {}).get("price_overview")


def format_price(price):
    if not price:
        return "N/A"

    return price.get("final_formatted", "N/A")


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        result = {
            "success": True,
            "service": "Steam Deals Bot",
            "status": "online"
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        self.wfile.write(
            json.dumps(result).encode("utf-8")
        )

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)

            data = json.loads(body) if body else {}

            appid = str(data.get("appid", "")).strip()

            if not appid:
                raise ValueError("appid is required")

            us = get_game(appid, "US")
            eu = get_game(appid, "DE")
            india = get_game(appid, "IN")
            ukraine = get_game(appid, "UA")

            if not us:
                raise ValueError("Game not found or no price available")

            name = data.get("name", f"Steam Game {appid}")

            message = (
                f"🎮 <b>{name}</b>\n\n"
                f"🔥 تخفیف: <b>{us.get('discount_percent', 0)}%</b>\n\n"
                f"🇺🇸 آمریکا: {format_price(us)}\n"
                f"🇪🇺 اروپا: {format_price(eu)}\n"
                f"🇮🇳 هند: {format_price(india)}\n"
                f"🇺🇦 اوکراین: {format_price(ukraine)}\n\n"
                f"🔗 <a href=\"https://store.steampowered.com/app/{appid}/\">مشاهده در Steam</a>"
            )

            telegram = telegram_send(message)

            result = {
                "success": True,
                "appid": appid,
                "telegram": telegram
            }

        except Exception as e:
            result = {
                "success": False,
                "error": str(e)
            }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        self.wfile.write(
            json.dumps(result, ensure_ascii=False).encode("utf-8")
        )

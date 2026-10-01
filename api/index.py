import os
import json
import requests
from http.server import BaseHTTPRequestHandler


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL = os.getenv("TELEGRAM_CHANNEL", "@steamtopdeals")


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    response = requests.post(
        url,
        json={
            "chat_id": TELEGRAM_CHANNEL,
            "text": message,
            "parse_mode": "HTML"
        },
        timeout=15
    )

    return response.json()


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
            json.dumps(result).encode()
        )

    def do_POST(self):

        try:

            result = send_telegram(
                "🎮 <b>SteamTopDeals</b>\n\n"
                "🔥 ربات با موفقیت به کانال متصل شد!\n\n"
                "سیستم تخفیف‌های Steam به‌زودی فعال می‌شود."
            )

            response = {
                "success": True,
                "telegram": result
            }

        except Exception as e:

            response = {
                "success": False,
                "error": str(e)
            }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        self.wfile.write(
            json.dumps(
                response,
                ensure_ascii=False
            ).encode()
        )

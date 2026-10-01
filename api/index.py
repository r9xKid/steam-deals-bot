import os
import json
import requests
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlencode


BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL = os.getenv("TELEGRAM_CHANNEL", "@steamtopdeals")

STEAM_SEARCH = "https://store.steampowered.com/search/results/"
STEAM_DETAILS = "https://store.steampowered.com/api/appdetails"

HEADERS = {
    "User-Agent": "Mozilla/5.0 SteamTopDeals/1.0"
}


def steam_search():
    params = {
        "start": 0,
        "count": 20,
        "specials": 1,
        "category1": 998,
        "json": 1,
        "l": "english",
        "cc": "us"
    }

    r = requests.get(
        STEAM_SEARCH,
        params=params,
        headers=HEADERS,
        timeout=20
    )

    r.raise_for_status()
    return r.json()


def get_details(appid, country):
    params = {
        "appids": appid,
        "cc": country,
        "filters": "price_overview",
        "l": "english"
    }

    r = requests.get(
        STEAM_DETAILS,
        params=params,
        headers=HEADERS,
        timeout=20
    )

    r.raise_for_status()

    data = r.json().get(str(appid), {})

    if not data.get("success"):
        return None

    return data.get("data", {}).get("price_overview")


def telegram_send(text):
    if not BOT_TOKEN:
        raise Exception("TELEGRAM_BOT_TOKEN is missing")

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    r = requests.post(
        url,
        json={
            "chat_id": CHANNEL,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        },
        timeout=20
    )

    return r.json()


def format_price(price):
    if not price:
        return "ناموجود"

    return price.get("final_formatted", "ناموجود")


def get_deals():
    data = steam_search()

    items = data.get("items", [])

    deals = []

    for item in items[:20]:

        appid = item.get("id") or item.get("appid")

        if not appid:
            continue

        us = get_details(appid, "US")

        if not us:
            continue

        discount = us.get("discount_percent", 0)

        if discount <= 0:
            continue

        eu = get_details(appid, "DE")
        india = get_details(appid, "IN")
        ukraine = get_details(appid, "UA")

        deals.append({
            "appid": appid,
            "name": item.get("name", "Unknown"),
            "discount": discount,
            "us": us,
            "eu": eu,
            "india": india,
            "ukraine": ukraine
        })

    return deals


def make_message(game):

    appid = game["appid"]

    return (
        f"🔥 <b>{game['name']}</b>\n\n"

        f"🏷 تخفیف: <b>{game['discount']}%</b>\n\n"

        f"🇺🇸 آمریکا: "
        f"{format_price(game['us'])}\n"

        f"🇪🇺 اروپا: "
        f"{format_price(game['eu'])}\n"

        f"🇮🇳 هند: "
        f"{format_price(game['india'])}\n"

        f"🇺🇦 اوکراین: "
        f"{format_price(game['ukraine'])}\n\n"

        f"🛒 <a href="
        f"\"https://store.steampowered.com/app/{appid}/\">"
        f"مشاهده در Steam</a>"
    )


class handler(BaseHTTPRequestHandler):

    def do_GET(self):

        try:

            deals = get_deals()

            result = {
                "success": True,
                "count": len(deals),
                "deals": deals
            }

        except Exception as e:

            result = {
                "success": False,
                "error": str(e)
            }

        self.send_response(200)

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8"
        )

        self.end_headers()

        self.wfile.write(
            json.dumps(
                result,
                ensure_ascii=False
            ).encode("utf-8")
        )

    def do_POST(self):

        try:

            deals = get_deals()

            sent = 0

            for game in deals[:5]:

                message = make_message(game)

                result = telegram_send(message)

                if result.get("ok"):
                    sent += 1

            response = {
                "success": True,
                "found": len(deals),
                "sent": sent
            }

        except Exception as e:

            response = {
                "success": False,
                "error": str(e)
            }

        self.send_response(200)

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8"
        )

        self.end_headers()

        self.wfile.write(
            json.dumps(
                response,
                ensure_ascii=False
            ).encode("utf-8")
        )

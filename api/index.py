import os
import json
import requests
from http.server import BaseHTTPRequestHandler


BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL = os.getenv("TELEGRAM_CHANNEL", "@steamtopdeals")

STEAM_SEARCH_URL = "https://store.steampowered.com/search/results/"
STEAM_DETAILS_URL = "https://store.steampowered.com/api/appdetails"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/154.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


def steam_search():
    """
    دریافت بازی‌های تخفیف‌خورده از Steam Store.
    """

    params = {
        "start": 0,
        "count": 50,
        "specials": 1,
        "infinite": 1,
        "category1": 998,
        "cc": "us",
        "l": "english",
        "json": 1,
    }

    response = requests.get(
        STEAM_SEARCH_URL,
        params=params,
        headers=HEADERS,
        timeout=25,
    )

    return {
        "status_code": response.status_code,
        "url": response.url,
        "content_type": response.headers.get("content-type"),
        "text": response.text[:5000],
    }


def get_game_details(appid, country):
    """
    دریافت قیمت یک بازی در یک ریجن مشخص.
    """

    params = {
        "appids": str(appid),
        "cc": country,
        "l": "english",
        "filters": "price_overview",
    }

    response = requests.get(
        STEAM_DETAILS_URL,
        params=params,
        headers=HEADERS,
        timeout=20,
    )

    if response.status_code != 200:
        return None

    try:
        data = response.json()
    except Exception:
        return None

    game = data.get(str(appid), {})

    if not game.get("success"):
        return None

    game_data = game.get("data", {})

    return game_data.get("price_overview")


def format_price(price):
    if not price:
        return "ناموجود"

    return price.get("final_formatted", "ناموجود")


def send_telegram(message):
    """
    ارسال پیام به کانال تلگرام.
    """

    if not BOT_TOKEN:
        return {
            "ok": False,
            "error": "TELEGRAM_BOT_TOKEN is missing"
        }

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    response = requests.post(
        url,
        json={
            "chat_id": CHANNEL,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=20,
    )

    try:
        return response.json()
    except Exception:
        return {
            "ok": False,
            "error": response.text[:1000]
        }


def extract_items(search_data):
    """
    تبدیل پاسخ Steam Search به لیست بازی‌ها.
    """

    try:
        raw_text = search_data.get("text", "")

        data = json.loads(raw_text)

        items = data.get("items", [])

        if isinstance(items, list):
            return items

    except Exception:
        pass

    return []


def get_deals():
    """
    دریافت تخفیف‌های واقعی.
    """

    search_data = steam_search()

    items = extract_items(search_data)

    deals = []

    for item in items:

        appid = (
            item.get("id")
            or item.get("appid")
            or item.get("appID")
        )

        if not appid:
            continue

        name = item.get("name", "Unknown")

        us = get_game_details(appid, "US")

        if not us:
            continue

        discount = int(
            us.get("discount_percent", 0)
        )

        if discount <= 0:
            continue

        eu = get_game_details(appid, "DE")
        india = get_game_details(appid, "IN")
        ukraine = get_game_details(appid, "UA")

        deals.append({
            "appid": appid,
            "name": name,
            "discount": discount,
            "us": us,
            "eu": eu,
            "india": india,
            "ukraine": ukraine,
        })

    return deals


def make_message(game):

    appid = game["appid"]

    name = game["name"]
    discount = game["discount"]

    steam_link = (
        f"https://store.steampowered.com/app/{appid}/"
    )

    return (
        f"🔥 <b>{name}</b>\n\n"
        f"🏷 تخفیف: <b>{discount}%</b>\n\n"

        f"🇺🇸 آمریکا: "
        f"{format_price(game['us'])}\n"

        f"🇪🇺 اروپا: "
        f"{format_price(game['eu'])}\n"

        f"🇮🇳 هند: "
        f"{format_price(game['india'])}\n"

        f"🇺🇦 اوکراین: "
        f"{format_price(game['ukraine'])}\n\n"

        f"🛒 <a href=\"{steam_link}\">"
        f"مشاهده در Steam</a>"
    )


class handler(BaseHTTPRequestHandler):

    def send_json(self, data):

        body = json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")

        self.send_response(200)

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8",
        )

        self.send_header(
            "Content-Length",
            str(len(body)),
        )

        self.end_headers()

        self.wfile.write(body)

    def do_GET(self):

        try:

            search_data = steam_search()

            items = extract_items(search_data)

            self.send_json({
                "success": True,
                "steam_status": search_data["status_code"],
                "steam_content_type": search_data["content_type"],
                "items_found": len(items),
                "steam_url": search_data["url"],
                "sample_items": items[:5],
                "raw_response_start": search_data["text"][:2000],
            })

        except Exception as e:

            self.send_json({
                "success": False,
                "error": str(e),
            })

    def do_POST(self):

        try:

            deals = get_deals()

            sent = 0
            errors = []

            # فعلاً فقط 5 بازی برای تست
            for game in deals[:5]:

                message = make_message(game)

                result = send_telegram(message)

                if result.get("ok"):
                    sent += 1
                else:
                    errors.append({
                        "appid": game["appid"],
                        "telegram": result,
                    })

            self.send_json({
                "success": True,
                "found": len(deals),
                "sent": sent,
                "errors": errors,
                "deals": deals[:5],
            })

        except Exception as e:

            self.send_json({
                "success": False,
                "error": str(e),
            })

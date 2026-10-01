import os
import json
import re
import html
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

    response.raise_for_status()

    return response.json()


def extract_games(search_response):
    """
    استخراج AppID و نام بازی‌ها از results_html
    """

    results_html = search_response.get("results_html", "")

    if not results_html:
        return []

    games = []

    # هر ردیف بازی یک data-ds-appid دارد
    pattern = re.compile(
        r'data-ds-appid="(\d+)"'
        r'.*?'
        r'<span class="title">(.*?)</span>',
        re.S
    )

    matches = pattern.findall(results_html)

    for appid, raw_name in matches:

        name = html.unescape(
            re.sub(r"<.*?>", "", raw_name)
        ).strip()

        if not name:
            continue

        games.append({
            "appid": appid,
            "name": name,
        })

    # حذف موارد تکراری
    unique = {}
    for game in games:
        unique[game["appid"]] = game

    return list(unique.values())


def get_game_details(appid, country):
    """
    دریافت قیمت بازی در یک کشور/ریجن.
    """

    params = {
        "appids": str(appid),
        "cc": country,
        "l": "english",
        "filters": "price_overview",
    }

    try:

        response = requests.get(
            STEAM_DETAILS_URL,
            params=params,
            headers=HEADERS,
            timeout=20,
        )

        if response.status_code != 200:
            return None

        data = response.json()

        game = data.get(str(appid), {})

        if not game.get("success"):
            return None

        game_data = game.get("data", {})

        return game_data.get("price_overview")

    except Exception:
        return None


def format_price(price):

    if not price:
        return "ناموجود"

    return price.get(
        "final_formatted",
        "ناموجود"
    )


def send_telegram(message):

    if not BOT_TOKEN:
        return {
            "ok": False,
            "error": "TELEGRAM_BOT_TOKEN is missing"
        }

    url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )

    try:

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

        return response.json()

    except Exception as e:

        return {
            "ok": False,
            "error": str(e)
        }


def get_deals():

    search_response = steam_search()

    games = extract_games(
        search_response
    )

    deals = []

    # فعلاً فقط 10 بازی برای تست
    for game in games[:10]:

        appid = game["appid"]

        us = get_game_details(
            appid,
            "US"
        )

        if not us:
            continue

        discount = int(
            us.get(
                "discount_percent",
                0
            )
        )

        if discount <= 0:
            continue

        eu = get_game_details(
            appid,
            "DE"
        )

        india = get_game_details(
            appid,
            "IN"
        )

        ukraine = get_game_details(
            appid,
            "UA"
        )

        deals.append({
            "appid": appid,
            "name": game["name"],
            "discount": discount,
            "us": us,
            "eu": eu,
            "india": india,
            "ukraine": ukraine,
        })

    return deals


def make_message(game):

    appid = game["appid"]

    steam_link = (
        f"https://store.steampowered.com/app/"
        f"{appid}/"
    )

    return (
        f"🔥 <b>{game['name']}</b>\n\n"

        f"🏷 تخفیف: "
        f"<b>{game['discount']}%</b>\n\n"

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
            indent=2
        ).encode("utf-8")

        self.send_response(200)

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8"
        )

        self.send_header(
            "Content-Length",
            str(len(body))
        )

        self.end_headers()

        self.wfile.write(body)

    def do_GET(self):

        try:

            search_response = steam_search()

            games = extract_games(
                search_response
            )

            self.send_json({
                "success": True,
                "steam_status": 200,
                "games_found": len(games),
                "games": games[:20],
            })

        except Exception as e:

            self.send_json({
                "success": False,
                "error": str(e)
            })

    def do_POST(self):

        try:

            deals = get_deals()

            sent = 0
            errors = []

            # فقط 5 پست برای تست
            for game in deals[:5]:

                message = make_message(
                    game
                )

                result = send_telegram(
                    message
                )

                if result.get("ok"):
                    sent += 1
                else:
                    errors.append({
                        "appid": game["appid"],
                        "telegram": result
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
                "error": str(e)
            })

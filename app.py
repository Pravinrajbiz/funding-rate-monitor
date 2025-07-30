import requests
import time
import threading
import csv
from datetime import datetime
from flask import Flask, render_template
from zoneinfo import ZoneInfo

app = Flask(__name__)

# Store last 3 results in memory
latest_results = []

# CSV file for history
CSV_FILE = "funding_data.csv"

# Timezone
IST = ZoneInfo("Asia/Kolkata")

previous_rates = {}
previous_mark_price = {}

def fetch_and_store():
    url = "https://fapi.binance.com/fapi/v1/premiumIndex"
    while True:
        try:
            response = requests.get(url, timeout=5)
            data = response.json()

            changes = []
            for item in data:
                symbol = item["symbol"]
                if not symbol.endswith("USDT"):
                    continue
                funding_rate = float(item["lastFundingRate"]) * 100
                mark_price = float(item["markPrice"])
                prev_rate = previous_rates.get(symbol, funding_rate)
                prev_mark = previous_mark_price.get(symbol, mark_price)
                delta_funding = funding_rate - prev_rate
                delta_mark = mark_price - prev_mark
                previous_rates[symbol] = funding_rate
                previous_mark_price[symbol] = mark_price
                changes.append((symbol, funding_rate, delta_funding, mark_price, delta_mark))

            top_positive = sorted(changes, key=lambda x: x[2], reverse=True)[:5]
            top_negative = sorted(changes, key=lambda x: x[2])[:5]

            ist_time = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC")).astimezone(IST)
            timestamp = ist_time.strftime('%Y-%m-%d %H:%M:%S %Z')

            result = {"time": timestamp, "top_positive": top_positive, "top_negative": top_negative}

            latest_results.insert(0, result)
            if len(latest_results) > 3:
                latest_results.pop()

            with open(CSV_FILE, "a", newline="") as f:
                writer = csv.writer(f)
                for sym, rate, d_funding, mark, d_mark in top_positive + top_negative:
                    writer.writerow([timestamp, sym, rate, d_funding, mark, d_mark])
        except Exception as e:
            print("Error:", e)
        time.sleep(180)  # every 3 minutes

@app.route("/")
def index():
    return render_template("index.html", results=latest_results)

# Start background thread
threading.Thread(target=fetch_and_store, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

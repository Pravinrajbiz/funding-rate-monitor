import requests
import time
import threading
import csv
from datetime import datetime, timezone
from flask import Flask, render_template, send_file
from zoneinfo import ZoneInfo

app = Flask(__name__)

# In-memory storage (last 3 results)
latest_results = []

# CSV file to store history
CSV_FILE = "funding_data.csv"

# Timezone
IST = ZoneInfo("Asia/Kolkata")

# Previous values for delta
previous_rates = {}
previous_mark_price = {}

# Occurrence tracking
positive_occurrence = {}
negative_occurrence = {}

def update_occurrence(top_list, occurrence_dict):
    updated = []
    current_symbols = [s[0] for s in top_list]

    for sym, rate, delta_funding, mark_price, delta_mark in top_list:
        if sym in occurrence_dict:
            occurrence_dict[sym] += 1
        else:
            occurrence_dict[sym] = 1
        updated.append((sym, rate, delta_funding, mark_price, delta_mark, occurrence_dict[sym]))

    # Reset tokens not present in this cycle
    for sym in list(occurrence_dict.keys()):
        if sym not in current_symbols:
            occurrence_dict.pop(sym, None)

    return updated

def process_data(url):
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

        # Add occurrence counts
        top_positive_with_occ = update_occurrence(top_positive, positive_occurrence)
        top_negative_with_occ = update_occurrence(top_negative, negative_occurrence)

        timestamp = datetime.now(timezone.utc).astimezone(IST).strftime('%Y-%m-%d %H:%M:%S %Z')

        result = {
            "time": timestamp,
            "top_positive": top_positive_with_occ,
            "top_negative": top_negative_with_occ
        }

        # Store last 3 in memory
        latest_results.insert(0, result)
        if len(latest_results) > 3:
            latest_results.pop()

        # Append to CSV
        with open(CSV_FILE, "a", newline="") as f:
            writer = csv.writer(f)
            for sym, rate, d_funding, mark, d_mark, occ in top_positive_with_occ + top_negative_with_occ:
                writer.writerow([timestamp, sym, rate, d_funding, mark, d_mark, occ])

    except Exception as e:
        print("Error fetching data:", e)

def fetch_and_store():
    url = "https://fapi.binance.com/fapi/v1/premiumIndex"

    # Initial baseline + quick second fetch to get deltas immediately
    process_data(url)
    time.sleep(5)
    process_data(url)

    # Regular loop
    while True:
        process_data(url)
        time.sleep(180)

@app.route("/")
def index():
    # Force fetch on every page load to prevent blank page
    process_data("https://fapi.binance.com/fapi/v1/premiumIndex")
    return render_template("index.html", results=latest_results)

@app.route("/history")
def download_history():
    try:
        return send_file(CSV_FILE, as_attachment=True)
    except FileNotFoundError:
        return "No history file found yet. Please wait for data collection."

# Start background thread
threading.Thread(target=fetch_and_store, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

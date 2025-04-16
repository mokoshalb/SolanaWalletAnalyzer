import os
import csv
import sys
import json
import time
import asyncio
import aiohttp
import threading
import dateutil.parser
from collections import defaultdict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
API_KEY = os.getenv('BIRDEYE_API_KEY')  # Load API key from environment variables
BASE_URL = "https://public-api.birdeye.so"
PATH = os.path.dirname(os.path.abspath(__file__))
LOCK = threading.Lock()

# API Headers
HEADERS = {
    "accept": "application/json",
    "x-chain": "solana",
    "X-API-KEY": API_KEY
}

# Output file configuration
output_file = f"solana_wallets_results_{int(time.time())}.csv"

# User input for analysis parameters
minimum_wallet_capital = float(input("Enter minimum wallet capital to analyze: "))
mimimum_average_holding_period = int(input("Enter minimum average holding period to analyze in seconds: "))
minimum_total_pnl = float(input("Enter minimum total PnL to analyze: "))
minimum_win_rate = float(input("Enter minimum winrate to analyze (1-100%): "))
timeframe = input("Enter timeframe to analyze (1h, 4h, 1d, 1w, 1m): ")

def load_data(file_name="data.json", empty=[]):
    """
    Load data from a JSON file
    Args:
        file_name: Name of the file to load
        empty: Default value if file doesn't exist
    Returns:
        Loaded data or empty list if file doesn't exist
    """
    f = os.path.join(PATH, file_name)
    if os.path.exists(f):
        with open(f, 'r', encoding='utf-8') as file:
            data = json.load(file)
        return data
    else:
        with open(f, 'w', encoding='utf-8') as file:
            json.dump(empty, file)
        return empty

# Load token prices from cache
token_prices = load_data("token_prices.json", {})

def save_data(data, file_name="data.json"):
    """
    Save data to a JSON file
    Args:
        data: Data to save
        file_name: Name of the file to save to
    """
    f = os.path.join(PATH, file_name)
    with LOCK:
        with open(f, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=4)

def convert_to_decimal(number: int, decimal_places: int) -> float:
    """
    Convert a number to decimal format
    Args:
        number: Number to convert
        decimal_places: Number of decimal places
    Returns:
        Converted decimal number
    """
    return number / (10 ** decimal_places)

def convert_to_unix_timestamp(iso_time: str) -> int:
    """
    Convert ISO time to Unix timestamp
    Args:
        iso_time: ISO format time string
    Returns:
        Unix timestamp
    """
    dt = dateutil.parser.isoparse(iso_time)
    return int(dt.timestamp())

def timeframe_to_seconds(timeframe: str) -> int:
    """
    Convert timeframe string to seconds
    Args:
        timeframe: Timeframe string (1h, 4h, 1d, 1w, 1m)
    Returns:
        Timeframe in seconds
    """
    time_units = {'s': 1, 'mi': 60, 'h': 3600, 'd': 86400, 'w': 604800, 'm': 2592000, 'y': 31536000}
    return int(time.time()) if timeframe == "all" else int(timeframe[:-1]) * time_units.get(timeframe[-1], 0)

async def fetch(session, url):
    """
    Fetch data from API
    Args:
        session: aiohttp session
        url: URL to fetch from
    Returns:
        JSON response or None if request fails
    """
    async with session.get(url, headers=HEADERS, ssl=False) as response:
        return await response.json() if response.status == 200 else None

async def wallet_balance(session, wallet):
    """
    Get wallet balance in USD
    Args:
        session: aiohttp session
        wallet: Wallet address
    Returns:
        Wallet balance in USD
    """
    url = f"{BASE_URL}/v1/wallet/token_list?wallet={wallet}"
    data = await fetch(session, url)
    try:
        return data["data"].get("totalUsd", 0) if data and data.get("success") else 0
    except:
        return 0

async def token_price(session, timestamp, token="So11111111111111111111111111111111111111112"):
    """
    Get token price at specific timestamp
    Args:
        session: aiohttp session
        timestamp: Unix timestamp
        token: Token address
    Returns:
        Token price at given timestamp
    """
    global token_prices
    timestamp = str(timestamp)
    price = 0
    if token not in token_prices:
        token_prices[token] = {}
        save_data(token_prices, "token_prices.json")
    if timestamp in token_prices[token]:
        price = token_prices[token][timestamp]
    else:
        url = f"{BASE_URL}/defi/historical_price_unix?address={token}&unixtime={timestamp}"
        data = await fetch(session, url)
        try:
            if data and data.get("success"):
                price = data["data"].get("value", 0)
                token_prices[token][timestamp] = price
                save_data(token_prices, "token_prices.json")
            else:
                price = 0
        except:
            price = 0
    return price

async def wallet_history(session, wallet):
    """
    Get wallet transaction history
    Args:
        session: aiohttp session
        wallet: Wallet address
    Returns:
        Calculated wallet metrics
    """
    txs, eol, limit, lastTx = [], False, 1000, None
    while not eol:
        url = f"{BASE_URL}/v1/wallet/tx_list?wallet={wallet}&limit={limit}" + (f"&before={lastTx}" if lastTx else "")
        data = await fetch(session, url)
        if not data or not data.get("success"): break
        transactions = data["data"].get("solana", [])
        lastTx = transactions[-1]["txHash"] if transactions else None
        for tx in transactions:
            try:
                timestamp = convert_to_unix_timestamp(tx["blockTime"])
                if timestamp < time.time() - timeframe_to_seconds(timeframe):
                    eol = True
                    break
                if tx["mainAction"] == "unknown" and len(tx["balanceChange"]) == 2:
                    txs.append({
                        "name": tx["balanceChange"][1]["name"],
                        "token": tx["balanceChange"][1]["address"],
                        "timestamp": timestamp,
                        "token_amount": convert_to_decimal(tx["balanceChange"][1]["amount"], tx["balanceChange"][1]["decimals"]),
                        "solana_amount": convert_to_decimal(tx["balanceChange"][0]["amount"], tx["balanceChange"][0]["decimals"])
                    })
            except:
                pass
        if len(transactions) < limit:
            eol = True
    return await calculate(session, reversed(txs), wallet)

async def calculate(session, transactions, wallet):
    """
    Calculate wallet metrics from transactions
    Args:
        session: aiohttp session
        transactions: List of transactions
        wallet: Wallet address
    Returns:
        Dictionary containing wallet metrics
    """
    holdings, realized_pnl, unrealized_pnl, pnl_records, total_profit_usd, wins, total_sales, total_holding_time = defaultdict(list), 0, 0, [], 0, 0, 0, 0
    
    for tx in transactions:
        try:
            token, timestamp, token_amount = tx["token"], tx["timestamp"], tx["token_amount"]
            name, token, timestamp, token_amount = tx["name"], tx["token"], tx["timestamp"], tx["token_amount"]
            if token_amount > 0:
                usd_value = await token_price(session, timestamp, token)
                if usd_value > 0:
                    holdings[token].append((token_amount, usd_value, timestamp))
                    print(f"Adding {name} to holdings: {usd_value} USD for {token_amount} at {timestamp}")
            elif token_amount < 0:
                amount_to_sell, original_amount_to_sell, pnl_usd, holding_time = abs(token_amount), abs(token_amount), 0, 0
                token_price_usd_sell = await token_price(session, timestamp, token)
                total_sales += 1
                while amount_to_sell > 0 and holdings[token]:
                    print(f"Sold {name}: {token_price_usd_sell} USD for {amount_to_sell} at {timestamp}")
                    buy_amount, buy_price_usd, buy_time = holdings[token].pop(0)
                    sell_amount = min(amount_to_sell, buy_amount)
                    pnl_usd += (token_price_usd_sell - buy_price_usd) * sell_amount
                    holding_time += (timestamp - buy_time) * (sell_amount / original_amount_to_sell)
                    amount_to_sell -= sell_amount
                    if buy_amount > sell_amount:
                        holdings[token].insert(0, (buy_amount - sell_amount, buy_price_usd, buy_time))
                realized_pnl += pnl_usd
                pnl_records.append(pnl_usd)
                total_profit_usd += pnl_usd
                total_holding_time += holding_time
                if pnl_usd > 0:
                    wins += 1
                    print(f"Winning trade: {pnl_usd}")
                else:
                    print(f"Losing trade: {pnl_usd}")
        except Exception as e:
            print("Error on line {}: {}".format(sys.exc_info()[-1].tb_lineno, e))
    for token, buys in holdings.items():
        current_price = await token_price(session, int(time.time()), token)
        for amount, buy_price, _ in buys:
            unrealized_pnl += (current_price - buy_price) * amount

    print(f"Wins: {wins}, Total Sales: {total_sales}")

    return {
        "wallet": wallet,
        "total_pnl_usd": realized_pnl + unrealized_pnl,
        "realized_pnl": realized_pnl,
        "unrealized_pnl": unrealized_pnl,
        "win_rate": (wins / total_sales * 100) if total_sales else 0,
        "average_holding_time_seconds": (total_holding_time / total_sales) if total_sales else 0
    }

async def main():
    """
    Main function to analyze wallets
    """
    wallets = []
    with open("solana_wallets.csv", "r", encoding="utf-8") as file:
        wallets = [row[0].strip() for row in csv.reader(file) if row]
    async with aiohttp.ClientSession(ssl_context=False) as session:
        results = await asyncio.gather(*[wallet_balance(session, w) for w in wallets])
        qualified_wallets = [w for w, b in zip(wallets, results) if b > minimum_wallet_capital]
        final_results = await asyncio.gather(*[wallet_history(session, w) for w in qualified_wallets])
        sorted_results = sorted([r for r in final_results if r["win_rate"] >= minimum_win_rate and r["average_holding_time_seconds"] >= mimimum_average_holding_period and r["total_pnl_usd"] >= minimum_total_pnl], key=lambda x: x["total_pnl_usd"], reverse=True)
        with open(output_file, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=["wallet", "total_pnl_usd", "realized_pnl", "unrealized_pnl", "win_rate", "average_holding_time_seconds"])
            writer.writeheader()
            writer.writerows(sorted_results)
        print(f"Exported {len(sorted_results)} wallets to {output_file}")

if __name__ == "__main__":
    asyncio.run(main())
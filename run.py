live_trade = True
enable_scheduler = True
use_fixed_margin = False

# You can select the coins that you want to trade here
base = ["LINK", "FLOKI", "PEPE"]
core = [5]

# Optimal value, do not change these
quote = ["USDT"]
# margin_percentage = 1.5
# Initial user-defined margins

initial_margins = {
    "LINKUSDT": 2.0,
    "FLOKIUSDT": 1.5,
    "PEPEUSDT": 1.8
}

import logging
import os
import requests
import socket
import urllib3
from datetime import datetime

import json

from binance.client import Client
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv
from termcolor import colored

load_dotenv()

# Get environment variables
api_key = os.getenv('BINANCE_KEY')
api_secret = os.getenv('BINANCE_SECRET')
client = Client(api_key, api_secret)

# Initialize logging
logging.basicConfig(level=logging.INFO,
                    format='%(message)s',
                    handlers=[
                        logging.FileHandler("log.txt"),
                        logging.StreamHandler()
                    ])

# Trading Setup
pair, round_off = [], []
for i in range(len(base)):
    if len(quote) > 1:
        my_quote_asset = quote[i]
    else:
        my_quote_asset = quote[0]
    pair.append(base[i] + quote[0])

for coin in quote:
    if coin == "USDT":
        decimal = 2
    elif coin == "BTC":
        decimal = 6
    elif coin == "ETH":
        decimal = 5
    elif coin == "BNB":
        decimal = 3
    else:
        decimal == 4
    round_off.append(decimal)

# Load or initialize margin percentages
margin_file = "margin_percentages.txt"
if os.path.exists(margin_file):
    with open(margin_file, 'r') as file:
        margin_percentages = json.load(file)
else:
    margin_percentages = initial_margins.copy()


def get_min_notional_in_usdt(symbol):
    try:
        min_notional = 0.0
        info = client.get_symbol_info(symbol)
        info_json = json.loads(json.dumps(info))  # Parse info to JSON
        min_notional = 0.0

        for filter in info_json['filters']:
            if filter['filterType'] == 'NOTIONAL':
                min_notional = float(filter['minNotional'])
                break

        print(min_notional, 'min_notional')

        # Fetch the current price of the symbol
        current_price = float(client.get_symbol_ticker(symbol=symbol)['price'])
        print(current_price, 'current_price')
        # Calculate the minimum notional value in USDT
        min_notional_usdt = min_notional * current_price
        print(min_notional_usdt, 'min_notional_usdt')
        return min_notional_usdt
    except BinanceAPIException as e:
        logging.error(f"Error fetching minimum notional in USDT for {symbol}: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")


def adjust_margin_for_min_notional(traded_symbol, current_margin_percentage):
    if use_fixed_margin:
        return current_margin_percentage
    min_notional = get_min_notional_in_usdt(traded_symbol)
    # Get the current price of the traded symbol against USDT
    traded_symbol_price = float(client.get_symbol_ticker(symbol=traded_symbol)['price'])
    # Calculate the minimum notional in USDT
    min_notional_usdt = min_notional * traded_symbol_price
    # Fetch the balance of the core currency (USDT)
    core_balance = float(client.get_asset_balance(asset="USDT").get("free"))
    # Calculate the equivalent of the core currency (USDT) in USDT
    core_balance_usdt = core_balance
    # Calculate the required margin percentage in terms of USDT
    required_margin_percentage = (min_notional_usdt / core_balance_usdt) * 100
    required_margin_percentage = required_margin_percentage * 1.05  # Add a 5% buffer
    # Return the higher of the calculated margin percentage and the current margin percentage
    print(required_margin_percentage, 'required_margin_percentage')
    return required_margin_percentage


def buy_low_sell_high():
    for i in range(len(pair)):
        # Auto Adjust FIXED or DYNAMIC variable
        if len(quote) > 1:
            my_quote_asset = quote[i]
        else:
            my_quote_asset = quote[0]
        if len(core) > 1:
            my_core_number = core[i]
        else:
            my_core_number = core[0]
        if len(round_off) > 1:
            my_round_off = round_off[i]
        else:
            my_round_off = round_off[0]

        # Retrieve Current Asset INFO
        asset_info = client.get_symbol_ticker(symbol=pair[i])
        asset_price = float(asset_info.get("price"))
        asset_balance = float(client.get_asset_balance(asset=base[i]).get("free"))

        current_holding = round(asset_balance * asset_price, my_round_off)

        # Adjust margin percentage based on min notional
        current_margin_percentage = margin_percentages[pair[i]]
        adjusted_margin_percentage = adjust_margin_for_min_notional(pair[i], current_margin_percentage)
        margin_percentages[pair[i]] = adjusted_margin_percentage

        change_percent = round(((current_holding - my_core_number) / my_core_number * 100), 4)
        trade_amount = round(abs(current_holding - my_core_number), my_round_off)

        log_message = ""
        # Output Console and Placing Order
        if (current_holding > my_core_number) and (abs(change_percent) > current_margin_percentage):
            if live_trade:
                client.order_market_sell(symbol=pair[i], quoteOrderQty=trade_amount)
            log_message = (
                    colored(asset_info, "green") + "\n" +
                    colored("Created at           : " + str(datetime.today().strftime("%d-%m-%Y @ %H:%M:%S")),
                            "green") + "\n" +
                    colored("Prefix Core          : " + str(my_core_number) + " " + my_quote_asset, "green") + "\n" +
                    colored("Current Core         : " + str(current_holding) + " " + my_quote_asset, "green") + "\n" +
                    colored("Percentage Changed   : " + str(change_percent) + " %", "green") + "\n" +
                    colored("Action               : SELL " + str(trade_amount) + " " + my_quote_asset + "\n", "green")
            )
        elif (current_holding < my_core_number) and (abs(change_percent) > current_margin_percentage):
            if live_trade:
                client.order_market_buy(symbol=pair[i], quoteOrderQty=trade_amount)
            log_message = (
                    colored(asset_info, "red") + "\n" +
                    colored("Created at           : " + str(datetime.today().strftime("%d-%m-%Y @ %H:%M:%S")),
                            "red") + "\n" +
                    colored("Prefix Core          : " + str(my_core_number) + " " + my_quote_asset, "red") + "\n" +
                    colored("Current Core         : " + str(current_holding) + " " + my_quote_asset, "red") + "\n" +
                    colored("Percentage Changed   : " + str(change_percent) + " %", "red") + "\n" +
                    colored("Action               : BUY " + str(trade_amount) + " " + my_quote_asset + "\n", "red")
            )
        else:
            log_message = (
                    colored(asset_info, "green") + "\n" +
                    colored("Created at           : " + str(datetime.today().strftime("%d-%m-%Y @ %H:%M:%S")),
                            "green") + "\n" +
                    colored("Prefix Core          : " + str(my_core_number) + " " + my_quote_asset, "green") + "\n" +
                    colored("Current Core         : " + str(current_holding) + " " + my_quote_asset, "green") + "\n" +
                    colored("Percentage Changed   : " + str(change_percent) + " %", "green") + "\n" +
                    colored("Action               : Do Nothing\n", "green")
            )

        # Print to console and log to file
        print(log_message)
        logging.info(log_message)

        # Save adjusted margins
    with open(margin_file, 'w') as file:
        json.dump(margin_percentages, file)


try:
    # if live_trade and enable_scheduler:
    # print(colored("The program is running.\n", "green"))
    # scheduler = BlockingScheduler()
    # scheduler.add_job(buy_low_sell_high, 'interval', seconds=5)
    # scheduler.start()
    # else:
    buy_low_sell_high()

except (KeyError,
        socket.timeout,
        BinanceAPIException,
        ConnectionResetError,
        urllib3.exceptions.ProtocolError,
        urllib3.exceptions.ReadTimeoutError,
        requests.exceptions.ConnectionError,
        requests.exceptions.ConnectTimeout,
        requests.exceptions.ReadTimeout) as e:

    with open("Error_Message.txt", "a") as error_message:
        error_message.write("[!] Created at : " + datetime.today().strftime("%d-%m-%Y @ %H:%M:%S") + "\n")
        error_message.write(str(e) + "\n\n")

except KeyboardInterrupt:
    print("\n\nAborted.\n")

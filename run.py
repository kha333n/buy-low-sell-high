live_trade = True
enable_scheduler = True

# You can select the coins that you want to trade here
base = ["LINK"]
core = [10]

# Optimal value, do not change these
quote = ["USDT"]
margin_percentage = 2

import os, socket, requests, urllib3, openai
from datetime import datetime
from termcolor import colored
from binance.client import Client
from binance.exceptions import BinanceAPIException
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv
import logging
from datetime import datetime
from termcolor import colored

load_dotenv()

# Get environment variables
api_key = os.getenv('BINANCE_KEY')
api_secret = os.getenv('BINANCE_SECRET')
client = Client(api_key, api_secret)
openai.api_key = os.getenv('OPENAI_KEY')

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


def analyze_market(asset_price, asset_balance):
    # Make a call to OpenAI to get the adjusted trading amount
    prompt = f"""
    Given the current asset price of {asset_price}, and asset balance of {asset_balance},
    suggest the trading action to maximize USDT balance. Indicate if we should buy, sell, or hold,
    and the amount to trade.
    """
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=50
    )
    action_suggestion = response.choices[0].text.strip().lower()
    return action_suggestion


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

        # Computing for Trade Quantity
        current_holding = round(asset_balance * asset_price, my_round_off)
        change_percent = round(((current_holding - my_core_number) / my_core_number * 100), 4)
        trade_amount = round(abs(current_holding - my_core_number), my_round_off)

        # Output Console and Placing Order
        if (current_holding > my_core_number) and (abs(change_percent) > margin_percentage):
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

        elif (current_holding < my_core_number) and (abs(change_percent) > margin_percentage):
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

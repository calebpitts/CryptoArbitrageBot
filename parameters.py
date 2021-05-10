# Get API credentials for each exchange you want to use
# NOTE: For Kucoin, provide the api credentials for the sub-account or main-account you created the api credentials in.
EXCHANGE_CREDENTIALS = {
    "BINANCE.US": {
        "PUBLIC_KEY": "",
        "SECRET_KEY": ""
    },
    "BINANCE": {
        "PUBLIC_KEY": "",
        "SECRET_KEY": ""
    },
    "KUCOIN": {
        "PUBLIC_KEY": "",
        "SECRET_KEY": "",
        "PASSPHRASE": ""
    }
}

# Record your account fees in decimal percent (e.g 0.08% -> 0.0008)
TRADING_FEES = {
    "BINANCE.US": {
        "maker": 0.00075,
        "taker": 0.00075
    },
    "BINANCE": {
        "maker": 0.00075,
        "taker": 0.00075
    },
    "KUCOIN": {
        "maker": 0.00040,  # 0.0008,
        "taker": 0.00064   # 0.0008
    }
}

# specify what asset you want to pay trading fees with. *use exchange-specific assets for lower fees
FEE_ASSETS = {
    "BINANCE.US": "BNB",
    "BINANCE": "BNB",
    "KUCOIN": "KCS"
}

#############################
# # FUNCTIONAL PARAMETERS # #
#############################
TARGET_ASSET = "USDT"         # asset you want more of (ideally a stablecoin or common trading asset)
TARGET_STOP = 0.10            # decimal percent of TARGET_ASSET you are willing to lose
TARGET_MIN_LIQUIDITY = 0.50   # decimal percent of TARGET_ASSET you do not want the bot to touch/use
FEE_MIN_LIQUIDITY = 0.20      # decimal percent of FEE_ASSET you do not want the bot to touch/use (needs to be above 0 for exchange discounts to apply)
MIN_PROFIT = 0.0010           # decimal percent of min profit you want to make for each arbitrage

NUM_SCANS = 1000              # number of scans you want the bot to make before exiting  # 24 hrs = 86400 secs
SCAN_LENGTH_SECONDS = 1       # number of seconds you want to space each scan to avoid exceeding api limits

# path to where you want csv output data to be stored (e.g "/path/to/savefile/")
SAVE_PATH = "/path/to/save/"

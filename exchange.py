from kucoin.client import Market as KucoinMarket
from kucoin.client import Trade as KucoinTrade
from kucoin.client import User as KucoinUser
from binance.client import Client as BinanceClient

import parameters
import market
import helper
import log

import pandas as pd
import sys


class Exchange():
    def __init__(self, exchange_name, target_asset, api_public, api_secret, passphrase):
        self.name = exchange_name
        self.target_asset = target_asset

        self.api_public = api_public
        self.api_secret = api_secret
        self.passphrase = passphrase

        self.establish_connections()
        self.assets_info = self.get_assets_info()
        self.valid_pairs = self.get_valid_pairs()
        self.trading_target_qty, self.reserve_target_qty = self.update_target_qty_partitions()
        self.total_starting_target_qty = self.trading_target_qty + self.reserve_target_qty

    def establish_connections(self):
        '''
        Establishes clients for each API function (market, trade, user)
        '''
        if self.name == "BINANCE.US":
            self.market = BinanceClient(self.api_public, self.api_secret, tld='us')
            self.trade = self.market
            self.user = self.market
        elif self.name == "BINANCE":
            self.market = BinanceClient(self.api_public, self.api_secret)
            self.trade = self.market
            self.user = self.market
        elif self.name == "KUCOIN":
            self.market = KucoinMarket()
            self.trade = KucoinTrade(self.api_public, self.api_secret, self.passphrase)
            self.user = KucoinUser(self.api_public, self.api_secret, self.passphrase)
        else:
            log.print_status(self.name, "exchange not supported.")
            sys.exit()

    def extrapolate_binance_info(self, exchange_info):
        '''
        '''
        assets_info = []
        for i in range(len(exchange_info)):
            filters = pd.DataFrame(exchange_info.iloc[i]["filters"]).set_index("filterType")
            asset_info = {
                "name": exchange_info.iloc[i]["baseAsset"] + exchange_info.iloc[i]["quoteAsset"],
                "baseAsset": exchange_info.iloc[i]["baseAsset"],
                "quoteAsset": exchange_info.iloc[i]["quoteAsset"],
                "baseMinQty": float(filters.loc["LOT_SIZE"]["minQty"]),
                "baseMaxQty": float(filters.loc["LOT_SIZE"]["maxQty"]),
                "baseQtyPrecision": helper.get_precision(filters.loc["LOT_SIZE"]["stepSize"]),  # TODO: add "quoteQtyPrecision" later....
                "basePricePrecision": helper.get_precision(filters.loc["PRICE_FILTER"]["tickSize"]),
                "baseMinNotional": float(filters.loc["MIN_NOTIONAL"]["minNotional"])
            }

            assets_info.append(asset_info)

        return pd.DataFrame(assets_info).set_index("name")

    def extrapolate_kucoin_info(self, exchange_info):
        assets_info = []
        for i in range(len(exchange_info)):
            asset_info = {
                "name": exchange_info.iloc[i]["name"].replace("-", ""),
                "baseAsset": exchange_info.iloc[i]["baseCurrency"],
                "quoteAsset": exchange_info.iloc[i]["quoteCurrency"],
                "baseMinQty": float(exchange_info.iloc[i]["baseMinSize"]),
                "baseMaxQty": float(exchange_info.iloc[i]["baseMaxSize"]),
                "baseQtyPrecision": int(helper.get_precision(exchange_info.iloc[i]["baseIncrement"])),
                "quoteQtyPrecision": int(helper.get_precision(exchange_info.iloc[i]["quoteIncrement"])),
                "basePricePrecision": int(helper.get_precision(exchange_info.iloc[i]["priceIncrement"])),
                "baseMinNotional": ""
            }

            assets_info.append(asset_info)

        return pd.DataFrame(assets_info).set_index("name")

    def get_assets_info(self):
        '''
        '''
        if self.name == "BINANCE" or self.name == "BINANCE.US":
            return self.extrapolate_binance_info(pd.DataFrame(self.market.get_exchange_info()["symbols"]))
        elif self.name == "KUCOIN":
            return self.extrapolate_kucoin_info(pd.DataFrame(self.market.get_symbol_list()))

    def get_valid_pairs(self):
        '''
        Gets valid pairs that can be used in arbitrage trades.
        '''
        valid_pairs = []
        unwinded_assets_info = self.assets_info.reset_index()
        for i in range(len(unwinded_assets_info)):
            asset_info = unwinded_assets_info.iloc[i]
            try:
                self.assets_info.loc[asset_info["baseAsset"] + self.target_asset]
                self.assets_info.loc[asset_info["quoteAsset"] + self.target_asset]
                orderbook = market.get_pair_orderbook(self, asset_info["baseAsset"], asset_info["quoteAsset"])

                if orderbook is not None:
                    if len(orderbook["bids"]) != 0 and len(orderbook["asks"]) != 0:  # doesn't mark pair valid if no bids or asks for pair
                        valid_pairs.append(asset_info["name"])
            except KeyError:
                pass  # not a valid asset pair for arbitrage, not added to valid pairs list

        log.print_status("Found {} valid pairs on {}.".format(len(valid_pairs), self.name))

        return valid_pairs

    def update_target_qty_partitions(self):
        '''
        Get starting target quantity and compute the amount of tradeable target qty and reserve target qty.
        '''
        if self.name == "BINANCE.US" or self.name == "BINANCE":
            starting_target_qty = float(self.user.get_asset_balance(asset=parameters.TARGET_ASSET)['free'])  # ** API CALL **
        elif self.name == "KUCOIN":
            starting_target_qty = float(pd.DataFrame(self.user.get_account_list()).set_index("currency").loc[parameters.TARGET_ASSET]["available"])  # ** API CALL **

        trading_target_qty = starting_target_qty * (1 - parameters.TARGET_MIN_LIQUIDITY)
        reserve_target_qty = starting_target_qty - trading_target_qty

        log.print_status("NEW PRT -> {} / {}".format(trading_target_qty, reserve_target_qty))

        return trading_target_qty, reserve_target_qty

    def get_balances(self):
        '''
        Gets exchange current balance of all assets.
        '''
        log.print_status("Collecting balances...")
        if self.name == "BINANCE" or self.name == "BINANCE.US":
            # TODO

            balances = "TODO LATER"  # TODO

        elif self.name == "KUCOIN":
            balances = pd.DataFrame(self.user.get_account_list())
            balances = balances.rename(columns={"currency": "asset"})
            balances["balance"] = balances["balance"].astype(float)

        return balances[balances["balance"] > 0]  # only return assets with an available balance over zero.

    def check_stop_loss(self, balances):
        '''
        Check to see if stop loss for specified base stablcoin was exceeded.
        '''
        if balances.set_index("asset").loc[parameters.TARGET_ASSET]["balance"] < (self.total_starting_target_qty * (1 - parameters.TARGET_STOP)):
            return True

        return False

    def rebalance_portfolio(self):
        '''
        '''
        # rebalance portfolio when conditions met
                    #     make sure a 1% qty total for these -> {'BTC', 'DAI', 'ETH', 'KCS', 'PAX', 'TRX', 'TUSD', 'USDC', 'USDT', 'UST'}
                    #     make sure most qty in USDT (95%)
                    #     make sure KCS at 4%
                    #     record additional fees incurred to rebalance portfolio
        return


def get_exchange(user_input):
    '''
    Creates user-specified exchange object. If none is specified by the user, KUCOIN exchange is selected.
    '''
    while True:
        if len(user_input) == 1:
            exchange_name = "KUCOIN"  # default exchange
        else:
            exchange_name = user_input[1].upper().strip()

        if exchange_name not in parameters.EXCHANGE_CREDENTIALS.keys():
            log.print_status("Invalid exchange name specified. Exchange name must be in this list: ", list(parameters.EXCHANGE_CREDENTIALS.keys()))
            log.print_status("Enter exchange name (press enter for default exchange selection): ", end="")
            user_input = input()
        else:
            break

    # get passphrase for select exchanges that require it
    try:
        passphrase = parameters.EXCHANGE_CREDENTIALS[exchange_name]["PASSPHRASE"]
    except KeyError:
        passphrase = ""

    log.print_status("Establishing exchange connections...")

    return Exchange(exchange_name,
                    parameters.TARGET_ASSET,
                    parameters.EXCHANGE_CREDENTIALS[exchange_name]["PUBLIC_KEY"],
                    parameters.EXCHANGE_CREDENTIALS[exchange_name]["SECRET_KEY"],
                    passphrase)

import arbitrage
import parameters
import log

import pandas as pd
import time


def take_orderbook_snapshot(exchange, max_tries=30):
    '''
    Gets current orderbook for all pairs in given exchange
    '''
    for i in range(max_tries + 1):
        try:
            if exchange.name == "BINANCE.US" or exchange.name == "BINANCE":
                orderbook = pd.DataFrame(exchange.market.get_orderbook_tickers())
                return orderbook.set_index("symbol").astype(float)[["bidPrice", "askPrice"]]
            elif exchange.name == "KUCOIN":
                orderbook = pd.DataFrame(exchange.market.get_all_tickers()['ticker'])
                orderbook = orderbook[["symbolName", "buy", "sell"]].rename(columns={"symbolName": "symbol", "buy": "bidPrice", "sell": "askPrice"})
                orderbook["symbol"] = orderbook["symbol"].str.replace("-", "")
                return orderbook.set_index("symbol").astype(float)
        except OSError:
            print("OS ERROR. API Connection issue. Trying again in 120 secs ({}/{})...".format(i, max_tries))
            time.sleep(120)

    print("Failed to connect to API after {} retries. Stopping scans.".format(max_tries))
    return None


def scan_exchange(exchange, scan_id):
    '''
    Scan exchange asset pairs for arbitrage oppurtunities.
    '''
    start = time.time()
    orderbook = take_orderbook_snapshot(exchange)  # ** API CALL **
    timestamp = time.strftime("%H:%M:%S", time.localtime())

    if orderbook is None:
        log.print_status("Could not access exchange market data. Waiting 2mins before proceeding...")
        time.sleep(120)
        return {}

    scan = []
    for pair in exchange.valid_pairs:
        pair_scan = {}
        net_forward, forward_rates = arbitrage.get_net_forward_arbitrage(exchange, orderbook, pair)
        net_reverse, reverse_rates = arbitrage.get_net_reverse_arbitrage(exchange, orderbook, pair)

        pair_scan["exchange"] = exchange.name
        pair_scan["target"] = exchange.target_asset
        pair_scan["pair"] = pair
        pair_scan["net_forward"] = net_forward
        pair_scan["net_reverse"] = net_reverse
        pair_scan["timestamp"] = timestamp

        if net_forward >= net_reverse:
            pair_scan["best_direction"] = "forward"
            pair_scan["left_x_target_rate"] = forward_rates[0]
            pair_scan["right_x_target_rate"] = forward_rates[1]
            pair_scan["pair_rate"] = forward_rates[2]
        else:
            pair_scan["best_direction"] = "reverse"
            pair_scan["left_x_target_rate"] = reverse_rates[0]
            pair_scan["right_x_target_rate"] = reverse_rates[1]
            pair_scan["pair_rate"] = reverse_rates[2]

        scan.append(pair_scan)

    scan = pd.DataFrame(scan)
    scan["scan_time_secs"] = round(time.time() - start, 5)
    scan["scan_id"] = scan_id

    return scan  # .set_index(["exchange", "pair"])


def get_max_profit_trade(scan):
    '''
    Looks at total 'scan' df of all pairs and their prices,
    then determines the best possible arbitrage trade.
    @Returns
    dict of row from 'scan' dataframe representing the best trade.
    '''
    if len(scan) == 0:
        return None  # meant that scan wasn't able to be taken

    max_forward_proposal_index = scan['net_forward'].idxmax()
    max_reverse_proposal_index = scan['net_reverse'].idxmax()

    max_forward_proposal = scan.iloc[max_forward_proposal_index]
    max_reverse_proposal = scan.iloc[max_reverse_proposal_index]

    if max_forward_proposal['net_forward'] >= max_reverse_proposal["net_reverse"]:
        max_profit_trade = dict(scan.iloc[max_forward_proposal_index])
        max_profit_trade["max_profit_percent"] = max_forward_proposal['net_forward']
    else:
        max_profit_trade = dict(scan.iloc[max_reverse_proposal_index])
        max_profit_trade["max_profit_percent"] = max_reverse_proposal['net_reverse']

    return max_profit_trade


def is_profitable(exchange, trade_template):
    '''
    Determines whether arbitrage opportunity is profitable (depends on trading fees).
    @Returns
    bool 'True' if profitable, 'False' otherwise
    '''
    if trade_template is None:
        return False

    total_trading_fee = parameters.TRADING_FEES[exchange.name]["maker"] * 3  # 3 trades required for arbitrage hence *3

    try:
        max_profit_percent = trade_template["end_profit_percent"]  # profit percent after trade plan generation
        log.print_status("New profit percent after trade plan generation = {}%".format(round(max_profit_percent, 5)))
    except KeyError:
        max_profit_percent = trade_template["net_{}".format(trade_template["best_direction"])]  # initial profit percent

    if max_profit_percent / 100 > total_trading_fee + parameters.MIN_PROFIT:
        return True

    return False


def get_pair_orderbook(exchange, base_asset, quote_asset):
    '''
    '''
    try:
        if exchange.name == "BINANCE.US" or exchange.name == "BINANCE":
            pair_symbol = base_asset + quote_asset
            return exchange.market.get_order_book(symbol=pair_symbol)
        elif exchange.name == "KUCOIN":
            pair_symbol = base_asset + "-" + quote_asset
            return exchange.market.get_part_order(20, pair_symbol)
    except:
        log.print_status("A problem occurred getting {} orderbook. Pair might be untradeable on {}.".format(base_asset + "-" + quote_asset, exchange.name))
        return None


def get_trade_set_orderbooks(exchange, trade_template):
    '''
    Gets up-to-date orderbooks for corresponding trade pairs needed to execute arbitrage oppurtunity.
    @Returns
    list of JSON orderbook responses for the respective 'exchange' object
    '''
    base_asset = exchange.assets_info.loc[trade_template["pair"]]["baseAsset"]
    quote_asset = exchange.assets_info.loc[trade_template["pair"]]["quoteAsset"]

    orderbooks = [get_pair_orderbook(exchange, base_asset, trade_template["target"]),
                  get_pair_orderbook(exchange, base_asset, quote_asset),
                  get_pair_orderbook(exchange, quote_asset, trade_template["target"])]

    pairs = [base_asset + trade_template["target"], base_asset + quote_asset, quote_asset + trade_template["target"]]

    for orderbook in orderbooks:
        if orderbook is None or len(orderbook["bids"]) == 0 or len(orderbook['asks']) == 0:
            log.record_status("At least one orderbook was not available.")
            return None, None  # orderbook not available (pair not tradeable, only observable)

    return orderbooks, pairs

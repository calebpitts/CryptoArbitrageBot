import parameters
import arbitrage
import market
import helper
import log

import pandas as pd
pd.options.mode.chained_assignment = None
import time


'''
::: NOTES :::
=============
EX: left_x_right
Want left = 1/Ask
Want right = Bid

FORWARD ARBITRAGE (EX: ETHBTC) -> left = ETH, right = BTC, target = USDT
========================================================================
# 1. buy BTCUSDT   - ask  <- pay for lowest asking price (faster)
# 2. buy ETHBTC    - ask  <- pay for lowest asking price (faster)
# 3. sell ETHUSDT  - bid  <- sell to top bid price (faster)

REVERSE ARBITRAGE (EX: ETHBTC) -> left = ETH, right = BTC, target = USDT
========================================================================
# 1. buy ETHUSDT   - ask  <- pay for lowest asking price (faster)
# 2. sell ETHBTC   - bid  <- sell to top bid price (faster)
# 3. sell BTCUSDT  - bid  <- sell to top bid price (faster)
'''


class TradePlan():
    def __init__(self, ex, scan_id, trade_template):
        self.exchange = ex
        self.trade_template = trade_template
        self.trade_set = self.build_trade_set(self.exchange, self.trade_template)
        self.max_quantities = self.calculate_max_quantities(self.trade_set)
        self.trade_plan = self.generate_trade_plan(self.exchange, self.trade_set, self.max_quantities)

        if self.trade_plan is not None:
            self.trade_plan["scan_id"] = scan_id

    def optimize_orderbook_depths(self, exchange, orderbooks, pairs, trade_template):
        '''
        Grid searches optimal orderbook depths that maximizes the profit with the most volume.
        '''
        if trade_template["best_direction"] == "forward":
            sides = ["ask", "ask", "bid"]  # rename variable to 'side'
        else:
            sides = ["ask", "bid", "bid"]

        orderbook_depths = []
        for i in range(3):
            orderbook_side = orderbooks[i][sides[i] + "s"]
            for depth_level, offering in enumerate(orderbook_side):
                # price = float(offering[0])
                qty = float(offering[1])

                base_min_qty = exchange.assets_info.loc[pairs[i]]["baseMinQty"]
                base_max_qty = exchange.assets_info.loc[pairs[i]]["baseMaxQty"]

                if qty > base_min_qty and qty < base_max_qty:
                    print("Found valid qty! Appending index", depth_level)
                    orderbook_depths.append(depth_level)
                    # log.print_status("Depth {} chosen".format(depth_level))
                    break

            print(orderbook_side)  # temp

        if len(orderbook_depths) != 3:
            log.print_status("Entire part orderbook has invalid volumes.")
            return [0, 0, 0]

        return orderbook_depths

    def build_trade_set(self, exchange, trade_template):
        '''
        Gets up-to-date orderbooks for each arbitrage pair, then records each qty and price/rate.
        Orderbook qty is optimized so that profit and trading volume are both maximized.
        @Returns
        dict with optimal qty and prices for each arbitrage pair
        '''
        orderbooks, pairs = market.get_trade_set_orderbooks(exchange, trade_template)
        orderbook_depths = self.optimize_orderbook_depths(exchange, orderbooks, pairs, trade_template)

        print(orderbook_depths)  # temp

        trade_set = trade_template.copy()
        if trade_set["best_direction"] == "forward":
            trade_set["left_x_target_rate"] = float(orderbooks[0]["bids"][orderbook_depths[0]][0])
            trade_set["left_x_right_rate"] = float(orderbooks[1]["asks"][orderbook_depths[1]][0])
            trade_set["right_x_target_rate"] = float(orderbooks[2]["asks"][orderbook_depths[2]][0])
            trade_set["left_x_target_qty"] = float(orderbooks[0]["bids"][orderbook_depths[0]][1])
            trade_set["left_x_right_qty"] = float(orderbooks[1]["asks"][orderbook_depths[1]][1])
            trade_set["right_x_target_qty"] = float(orderbooks[2]["asks"][orderbook_depths[2]][1])
            trade_set["end_profit_percent"] = arbitrage.calculate_forward_arbitrage((trade_set["left_x_target_rate"], trade_set["right_x_target_rate"], trade_set["left_x_right_rate"]))
        else:
            trade_set["left_x_target_rate"] = float(orderbooks[0]["asks"][orderbook_depths[0]][0])
            trade_set["left_x_right_rate"] = float(orderbooks[1]["bids"][orderbook_depths[1]][0])
            trade_set["right_x_target_rate"] = float(orderbooks[2]["bids"][orderbook_depths[2]][0])
            trade_set["left_x_target_qty"] = float(orderbooks[0]["asks"][orderbook_depths[0]][1])
            trade_set["left_x_right_qty"] = float(orderbooks[1]["bids"][orderbook_depths[1]][1])
            trade_set["right_x_target_qty"] = float(orderbooks[2]["bids"][orderbook_depths[2]][1])
            trade_set["end_profit_percent"] = arbitrage.calculate_reverse_arbitrage((trade_set["left_x_target_rate"], trade_set["right_x_target_rate"], trade_set["left_x_right_rate"]))

        if market.is_profitable(exchange, trade_set):
            return trade_set

        return None

    def calculate_max_quantities(self, trade_set):
        '''
        Calculates the max quantities that can be traded for each pair in arbitrage trade based on the orderbook volume.
        @Returns
        dict with max allowable trade qty for each arbitrage pair.
        '''
        if trade_set is None:
            return None

        max_quantities = {}

        # normalize orderbook quantities to stablecoin value
        trade_one_max_qty = trade_set['right_x_target_qty'] * trade_set['right_x_target_rate']
        trade_two_max_qty = trade_set['left_x_right_qty'] * trade_set['left_x_right_rate'] * trade_set['right_x_target_rate']
        trade_three_max_qty = trade_set['left_x_target_qty'] * trade_set['left_x_target_rate']

        max_target_trading_qty = min(trade_one_max_qty, trade_two_max_qty, trade_three_max_qty)

        # convert max qty from stablecoin to each trading pair
        if trade_set["best_direction"] == "forward":
            max_right_x_target_qty = max_target_trading_qty / trade_set['right_x_target_rate']
            max_left_x_right_qty = max_right_x_target_qty / trade_set['left_x_right_rate']
            max_left_x_target_qty = max_left_x_right_qty
        else:
            max_left_x_target_qty = max_target_trading_qty / trade_set['left_x_target_rate']
            max_left_x_right_qty = max_left_x_target_qty
            max_right_x_target_qty = max_target_trading_qty / trade_set['right_x_target_rate']

        max_quantities["max_left_x_target_qty"] = max_left_x_target_qty
        max_quantities["max_left_x_right_qty"] = max_left_x_right_qty
        max_quantities["max_right_x_target_qty"] = max_right_x_target_qty

        return max_quantities

    def generate_trade_plan(self, exchange, trade_set, max_quantities):
        '''
        Generates instructions for executing identified arbitrage oppurtunity.
        @Returns
        dataframe with sequential triset of projected trades to be made.
        '''
        if trade_set is None or max_quantities is None:
            log.print_status("MSG: Arbitrage no longer profitable while generating trade plan.")
            return None

        base_asset = exchange.assets_info.loc[trade_set["pair"]]["baseAsset"]
        quote_asset = exchange.assets_info.loc[trade_set["pair"]]["quoteAsset"]
        tradeable_target_qty = exchange.trading_target_qty

        trade_plan = []
        for i in range(3):  # triangular arbitrage has 3 trades
            trade = {}
            trade["exchange"] = trade_set["exchange"]
            trade["timestamp"] = trade_set["timestamp"]
            if trade_set["best_direction"] == "forward":
                trade["direction"] = "forward"

                if i == 0:  # trade 1
                    trade["order_type"] = "buy"
                    trade["side"] = "ask"
                    trade["pair"] = quote_asset + "-" + trade_set["target"]  # right_x_target
                    trade["price"] = trade_set["right_x_target_rate"]

                    trade["qty"] = tradeable_target_qty / trade_set["right_x_target_rate"]
                    trade["max_trading_qty"] = max_quantities["max_right_x_target_qty"]

                    if trade["qty"] > max_quantities["max_right_x_target_qty"]:  # check if quantity exceeds max quantity offered in order book
                        trade["qty"] = max_quantities["max_right_x_target_qty"]

                elif i == 1:  # trade 2
                    trade["order_type"] = "buy"
                    trade["side"] = "ask"
                    trade["pair"] = base_asset + "-" + quote_asset  # left_x_right
                    trade["price"] = trade_set["pair_rate"]

                    trade["qty"] = trade_plan[i - 1]["qty"] / trade_set["pair_rate"]  # BEFORE -> trade_item["pair_rate"] * trade_plan[i - 1]["qty"]
                    trade["max_trading_qty"] = max_quantities["max_left_x_right_qty"]

                    if trade["qty"] > max_quantities["max_left_x_right_qty"]:  # check if quantity exceeds max quantity offered in order book
                        trade["qty"] = max_quantities["max_left_x_right_qty"]

                else:  # trade 3
                    trade["order_type"] = "sell"
                    trade["side"] = "bid"
                    trade["pair"] = base_asset + "-" + trade_set["target"]  # left_x_target
                    trade["price"] = trade_set["left_x_target_rate"]

                    trade["qty"] = trade_plan[i - 1]["qty"]
                    trade["max_trading_qty"] = max_quantities["max_left_x_target_qty"]

                    if trade["qty"] > max_quantities["max_left_x_target_qty"]:  # check if quantity exceeds max quantity offered in order book
                        trade["qty"] = max_quantities["max_left_x_target_qty"]
            else:
                trade["direction"] = "reverse"

                if i == 0:  # trade 1
                    trade["order_type"] = "buy"
                    trade["side"] = "ask"
                    trade["pair"] = base_asset + "-" + trade_set["target"]  # left_x_target
                    trade["price"] = trade_set["left_x_target_rate"]

                    trade["qty"] = tradeable_target_qty / trade_set["left_x_target_rate"]
                    trade["max_trading_qty"] = max_quantities["max_left_x_target_qty"]

                    if trade["qty"] > max_quantities["max_left_x_target_qty"]:  # check if quantity exceeds max quantity offered in order book
                        trade["qty"] = max_quantities["max_left_x_target_qty"]

                elif i == 1:  # trade 2
                    trade["order_type"] = "sell"
                    trade["side"] = "bid"
                    trade["pair"] = base_asset + "-" + quote_asset  # left_x_right
                    trade["price"] = trade_set["pair_rate"]

                    trade["qty"] = trade_plan[i - 1]["qty"]
                    trade["max_trading_qty"] = max_quantities["max_left_x_right_qty"]
                    # check if quantity exceeds max quantity offered in order book
                    if trade["qty"] > max_quantities["max_left_x_right_qty"]:
                        trade["qty"] = max_quantities["max_left_x_right_qty"]

                else:  # trade 3
                    trade["order_type"] = "sell"
                    trade["side"] = "bid"
                    trade["pair"] = quote_asset + "-" + trade_set["target"]  # right_x_target
                    trade["price"] = trade_set["right_x_target_rate"]

                    trade["qty"] = trade_set["pair_rate"] * trade_plan[i - 1]["qty"]
                    trade["max_trading_qty"] = max_quantities["max_right_x_target_qty"]
                    # check if quantity exceeds max quantity offered in order book
                    if trade["qty"] > max_quantities["max_right_x_target_qty"]:
                        trade["qty"] = max_quantities["max_right_x_target_qty"]

            trade_plan.append(prep_trade(exchange, trade, trade_set))  # prep and add trade to trade plan

        return pd.DataFrame(trade_plan)


class Trade():
    def __init__(self, exchange, trade, trade_num):
        self.exchange = exchange
        self.trade = trade
        self.trade_num = trade_num

        self.orig_trade_qty = trade["qty"]  # save to compare end resulting qty with original trading qty intent
        self.orig_trade_price = float(trade["price"])
        self.unused_qty = exchange.trading_target_qty - (trade["qty"] * float(trade["price"]))
        self.trading_target_qty = exchange.trading_target_qty  # starting target qty
        self.ending_target_qty = 0
        self.orderbook_depth = 0

        self.partially_filled = False
        self.invalid_order_qty = -1
        self.trade_complete = False
        self.arbitrage_lost = False
        self.order_mostly_filled = False

    def update_order_details(self, order):
        '''
        Extract order details from exchange-specific limit order placement api response.
        '''
        if self.exchange.name == "BINANCE" or self.exchange.name == "BINANCE.US":
            return order  # TODO ## <- edit so that it matches kucoin revised order details
        elif self.exchange.name == "KUCOIN":
            order_details = self.exchange.trade.get_order_details(order["orderId"])  # API CALL ##
            revised_order_details = {"scan_id": self.trade["scan_id"],
                                     "trade_num": self.trade_num,
                                     "orderId": order_details["id"],
                                     "order_type": self.trade["order_type"],
                                     "pair": order_details["symbol"],
                                     "pending": bool(order_details["isActive"]),
                                     "price": float(order_details["price"]),
                                     "original_qty": float(order_details["size"]),
                                     "filled_qty": float(order_details["dealSize"]),
                                     "result_qty": float(order_details["dealFunds"]),
                                     "fee": float(order_details["fee"]),
                                     "fee_currency": order_details["feeCurrency"]}

        return revised_order_details

    def extract_available_qty(self, balances, asset_to_adjust):
        '''
        '''
        try:
            available_qty = float(balances.set_index("asset").loc[asset_to_adjust]["available"])
        except KeyError:
            log.print_status("WARNING: You do not have any {} available in your account.".format(asset_to_adjust))
            return 0

        return available_qty

    def execute_limit_trade(self):
        '''
        Executes individual limit orders. Adjusts qty to current available qty in account if there is a problem executing the trade.
        '''
        start = time.time()
        reduced_qty = False
        adj_factor = 1

        while True:
            try:
                if self.exchange.name == "BINANCE" or self.exchange.name == "BINANCE.US":
                    if self.trade["order_type"] == "buy":
                        order = self.exchange.trade.order_limit_buy(symbol=self.trade["pair"], quantity=self.trade["qty"], price=self.trade["price"])  # API CALL ##
                        break
                    else:
                        order = self.exchange.trade.order_limit_sell(symbol=self.trade["pair"], quantity=self.trade["qty"], price=self.trade["price"])  # API CALL ##
                        break
                elif self.exchange.name == "KUCOIN":
                    order = self.exchange.trade.create_limit_order(self.trade["pair"], self.trade["order_type"], self.trade["qty"], self.trade["price"])  # API CALL ##
                    break
            except Exception as e:
                log.print_status("API RESPONSE ->" + str(e))
                if not reduced_qty:
                    log.print_status("Attempting to execute trade with current balance quantity...")
                    balances = self.exchange.get_balances()

                    if self.trade["order_type"] == "sell":
                        asset_to_adjust = self.exchange.assets_info.loc[self.trade["pair"].replace("-", "")]["baseAsset"]
                        self.trade["qty"] = self.extract_available_qty(balances, asset_to_adjust)
                    elif self.trade["order_type"] == "buy":
                        asset_to_adjust = self.exchange.assets_info.loc[self.trade["pair"].replace("-", "")]["quoteAsset"]
                        self.trade["qty"] = self.extract_available_qty(balances, asset_to_adjust) / float(self.trade["price"])

                    if asset_to_adjust == parameters.TARGET_ASSET:
                        adj_factor = (1 - parameters.TARGET_MIN_LIQUIDITY)
                    elif asset_to_adjust in parameters.FEE_ASSETS.values():
                        adj_factor = (1 - parameters.FEE_MIN_LIQUIDITY)
                    elif asset_to_adjust in ["BTC", "ETH", "USDC"]:  # leave a small amount of wiggle room for transitory fees if needed
                        # TODO -> change before discount fee rate acording to exchange-specific fee schedules
                        before_discount_fee_rate = 0.005  # this is the rate that is initially charged in the quote currency (BTC or ETH) before any discounted fee rate applies
                        adj_factor = (1 - before_discount_fee_rate)  # (self.trade["qty"] * self.trade["price"]) * (1 - before_discount_fee_rate)

                    if adj_factor != 1:
                        self.trade["qty"] *= adj_factor

                    adjusted_trade_qty_precision = int(self.exchange.assets_info.loc[self.trade["pair"].replace("-", "")]["baseQtyPrecision"])
                    self.trade["qty"] = helper.round_decimals_down(float(self.trade["qty"]), adjusted_trade_qty_precision)

                    if self.trade["qty"] == 0:
                        return None  # nothing available in account, fail to execute limit trade

                    log.print_status("New trade qty: {}".format(self.trade["qty"]))
                    reduced_qty = True
                else:
                    if "Order size below the minimum requirement" in str(e):
                        log.print_status("Order size below the minimum requirement. Continue with trade plan.")
                        # create artificial order to indicate to override order filled checking requiremnt
                        order = {}  # create dummy order to let program know to continue trade plan
                        order["filled_qty"] = -1
                        order["original_qty"] = -1
                        order["result_qty"] = 0
                        return order
                    else:
                        log.print_status("WARNING: Reduction in qty failed.")
                        return None

        order = self.update_order_details(order)
        order["execution_time_secs"] = str(round(time.time() - start, 5))

        return order

    # def execute_market_trade(self):
    #     '''
    #     Handles invalid trade by attempting a market order. This prevents infinite loops in the 'handle_order_behavior' function.
    #     @Returns
    #     dictionary of executed market order details
    #     '''
    #     start = time.time()

    #     if self.exchange.name == "BINANCE" or self.exchange.name == "BINANCE.US":
    #         if self.trade["order_type"] == "buy":
    #             order = self.exchange.trade.order_market_buy(symbol=self.trade["pair"], quantity=self.trade["qty"])  # API CALL ##
    #         else:
    #             order = self.exchange.trade.order_market_sell(symbol=self.trade["pair"], quantity=self.trade["qty"])  # API CALL ##
    #     elif self.exchange.name == "KUCOIN":
    #         order = self.exchange.trade.create_market_order(self.trade["pair"], self.trade["order_type"], self.trade["qty"])  # API CALL ##

    #     for i in range(31):
    #         order_details = self.update_order_details(self.exchange, order)
    #         order_details["order_num"] = self.order_num

    #         if order_details["pending"]:
    #             log.print_status("Market order still pending ({}/30).".format(i))
    #             time.sleep(1)  # check status of market order every 1 sec 10 times
    #         else:
    #             order_details["execution_time_secs"] = str(round(time.time() - start, 5))

    #             return order_details

    #     log.print_status("Market order failed to completely fill in 30 secs.")

    #     return order_details

    def cancel_trade(self, order):
        '''
        Attempts to cancel order. If it fails to cancel order then its most likely completed.
        @Returns
        bool indicating 'True' if cancel order succeeded, 'False' otherwise.
        '''
        try:
            if self.exchange.name == "BINANCE.US" or self.exchange.name == "BINANCE":
                if self.exchange.trade.cancel_order(symbol=order["pair"], orderId=order["order_id"])["orderId"] == order["orderId"]:
                    log.print_status("MSG: Order canceled.")
                    return True
            elif self.exchange.name == "KUCOIN":
                if self.exchange.trade.cancel_order(order["orderId"])["cancelledOrderIds"][0] == order["orderId"]:
                    log.print_status("MSG: Order canceled.")
                    return True
        except Exception as e:
            log.print_status("MSG: Failed to cancel order. API Reason -> " + str(e))  # if failed to cancel order, then order most likely completed
            return False

    def get_resulting_qty(self, order):
        '''
        Updates the total resulting qty from what was filled during order execution.
        '''
        if self.trade["order_type"] == "buy":
            return order["filled_qty"]
        else:
            return order["result_qty"]

    def handle_order(self, order):
        '''
        Handles incomplete orders, failures, and edge cases related to orders.
        '''
        additional_orders = []
        partially_filled, override = False, False
        remainder_qty = 0

        if order is None:  # case where reduction in qty from prior order handle failed
            log.print_status("MSG: Arbitrage trade lost. Returning to scanning...")
            self.arbitrage_lost = True
            return additional_orders, self.trading_target_qty

        resulting_qty = self.get_resulting_qty(order)  # account for any initial qty result

        while True:
            if self.trade_num == 0 and order["filled_qty"] == 0 and not partially_filled:
                log.print_status("No quantity filled during first limit order. Waiting 1 second before returning to scanning...")
                time.sleep(1)
                if self.cancel_trade(order):
                    log.print_status("MSG: Arbitrage trade lost. Returning to scanning...")
                    self.arbitrage_lost = True
                    return additional_orders, self.trading_target_qty  # no additional trades needed, b/c lost arbitrage oppurtunity

                order = self.update_order_details(order)
                resulting_qty += self.get_resulting_qty(order)

            elif (order["filled_qty"] >= 0 and order["filled_qty"] < order["original_qty"]) or override:
                partially_filled = True
                log.print_status("Incomplete limit order during TRADE {}. Waiting 1 second before attempting to complete limit order...".format(self.trade_num))
                time.sleep(1)
                #  if order["pending"]:  # added
                if not self.cancel_trade(order):
                    print("XXX:", remainder_qty)
                    order = self.update_order_details(order)
                    additional_orders.append(order)
                    resulting_qty += self.get_resulting_qty(order)  # save qty that actually executed after waiting 1 sec
                    if remainder_qty == 0:
                        log.print_status("Order completed while cancelling, and no remainder qty is left. Continuing with trade plan.")
                        return additional_orders, resulting_qty  # no additional trades needed, still continuing with trade plan
                    else:
                        log.print_status("Order completed while cancelling, but remainder qty still exists ({} {})".format(remainder_qty, self.trade["pair"]))
                        self.trade["qty"] = remainder_qty  # update quantity since there is more qty to fill
                        if not helper.check_qty(self.exchange, self.trade, self.trade["pair"].replace("-", "")):
                            log.print_status("Remainder qty too low to execute (qty={}). Continuing with trade plan.".format(self.trade["qty"]))
                            return additional_orders, resulting_qty  # remainder qty too low to execute, continue with trade plan

                if not override:
                    self.trade["qty"] = order["original_qty"] - order["filled_qty"]  # get unfilled qty

                base_asset = self.exchange.assets_info.loc[self.trade["pair"].replace("-", "")]["baseAsset"]
                quote_asset = self.exchange.assets_info.loc[self.trade["pair"].replace("-", "")]["quoteAsset"]

                # update pair orderbook
                new_pair_orderbook = market.get_pair_orderbook(self.exchange, base_asset, quote_asset)
                # orderbook_depth = 0  # <- update later with optimal trade volume depth ......................................
                self.trade["price"] = float(new_pair_orderbook[self.trade["side"] + "s"][self.orderbook_depth][0])
                available_qty = float(new_pair_orderbook[self.trade["side"] + "s"][self.orderbook_depth][1])

                # get new trading qty, update remainder qty
                if self.invalid_order_qty != available_qty:  # prevents infinite loop prior invalid order
                    if self.trade["qty"] > available_qty:                   # not enough qty to fill full order
                        remainder_qty += self.trade["qty"] - available_qty  # increase remainder qty by the qty that can't be filled now
                        self.trade["qty"] = available_qty                   # set new trading qty to what is available to trade
                        log.print_status("Not enough quantity to fill. Remainder qty = {}".format(remainder_qty))
                    else:
                        if available_qty >= self.trade["qty"] + remainder_qty:  # can fill all of remainder qty + trade qty
                            self.trade["qty"] += remainder_qty
                            log.print_status("Can fully fill remainder qty + trade qty. Remainder qty set to 0.".format(remainder_qty))
                            remainder_qty = 0
                        else:                                              # can partially fill remainder qty + trade qty
                            available_qty_diff = available_qty - self.trade["qty"]
                            remainder_qty -= available_qty_diff
                            self.trade["qty"] += available_qty_diff
                            log.print_status("Can partially fill trade qty. Remainder qty = {}".format(remainder_qty))

                    # prep additional trade specs for execution
                    print("A", remainder_qty)
                    self.trade = prep_trade(self.exchange, self.trade)
                    print("B", remainder_qty)

                    if not self.trade["valid"]:
                        log.print_status("Invalid trade -> (likely) due to remainder qty being to low to execute.")
                        self.invalid_order_qty = self.trade["qty"]
                        if remainder_qty == 0:
                            log.print_status("Remainder qty is 0. Continuing with trade plan.")
                            return additional_orders, resulting_qty
                    else:
                        log.print_status("TRADE + -> {} {} {} at price {}".format(self.trade["order_type"], self.trade["qty"], self.trade["pair"], self.trade["price"]))
                        order = self.execute_limit_trade()

                        if order is None:
                            break

                        print("C", remainder_qty)

                        resulting_qty += self.get_resulting_qty(order)
                        additional_orders.append(order)

                        print("F", remainder_qty)
                else:
                    log.print_status("Last order was invalid and same qty available. Incrementing orderbook depth to {}".format(self.orderbook_depth + 1))
                    self.orderbook_depth += 1

            else:  # order was fully filled
                if remainder_qty > 0:  # if remainder still exist, fill remainder in new order override
                    log.print_status("Filling remainder qty. Override set.")
                    self.trade["qty"] = remainder_qty
                    remainder_qty = 0
                    override = True
                else:
                    break  # limit order completed, no remainder qty left

        return additional_orders, resulting_qty


def prep_trade(exchange, trade, trade_set={}):
    '''
    Preps trade specs for trade execution. Determines if trade is valid and conforms floats to required precisions.
    '''
    stripped_symbol = trade["pair"].replace("-", "")

    # change pair formatting for exchanges other than KUCOIN
    if exchange.name == "BINANCE" or exchange.name == "BINANCE.US":
        trade["pair"] = stripped_symbol

    # adhere to rounding / max decimal exchange requirements
    base_qty_precision = int(exchange.assets_info.loc[stripped_symbol]["baseQtyPrecision"])
    trade["qty"] = helper.round_decimals_down(trade["qty"], base_qty_precision)

    # check if notional value adheres to exchange rules and if quantity >= min and quantity <= max
    if helper.check_min_notional(exchange, trade, stripped_symbol) and helper.check_qty(exchange, trade, stripped_symbol):
        trade["valid"] = True
    else:
        trade["valid"] = False

    # convert all prices to string representation to avoid scientific notation issues when placing limit orders
    base_price_precision = exchange.assets_info.loc[stripped_symbol]["basePricePrecision"]
    trade["price"] = '{:0.0{}f}'.format(trade["price"], base_price_precision)

    # save profit percent that indicates what profit is yielded after executing all three arbitrage trades
    try:
        trade["end_profit_percent"] = trade_set["end_profit_percent"]
    except KeyError:
        trade["end_profit_percent"] = "NA"

    return trade


def compare_resulting_qty(exchange, t, actual_resulting_qty):
    '''
    Checks to see if the resulting qty is what was expected from the trading plan.
    @Returns
    factor that is multiplied by the qty of the next trade to adjust it and align with what the actual resulting qty is
    '''
    base_qty_precision = int(exchange.assets_info.loc[t.trade["pair"].replace("-", "")]["baseQtyPrecision"])
    quote_qty_precision = int(exchange.assets_info.loc[t.trade["pair"].replace("-", "")]["quoteQtyPrecision"])

    if t.trade["order_type"] == "buy":
        expected_resulting_qty = helper.round_decimals_down(t.orig_trade_qty, base_qty_precision)  # helps avoid small rounding miscompares
    else:
        expected_resulting_qty = helper.round_decimals_down(t.orig_trade_qty * float(t.orig_trade_price), quote_qty_precision)  # helps avoid small rounding miscompares

    if actual_resulting_qty != expected_resulting_qty:
        qty_reduction_factor = actual_resulting_qty / expected_resulting_qty
        log.print_status("Unexpected result qty difference. Expected {} {} but received {} {} from last trade.\nAdjusting next trade qty by a factor of {}.".format(expected_resulting_qty, t.trade["pair"], actual_resulting_qty, t.trade["pair"], qty_reduction_factor))
        return qty_reduction_factor

    return 1


def execute_trade_plan(exchange, trade_plan):
    '''
    Executes trading plan contained in trade_plan dict with a variety of corner cases dealing with
    partially filled limit orders, failed orders, and recomputing old orderbook statistics and arbitrage.
    Returns dataframe of executed orders.
    '''
    # ** TODO ** (req) rebalance portfolio to hold 0.1% of each asset to avoid rounding insufficient balance issues
    # ** TODO ** (maybe) handle partially filled first trade instances
    log.print_status("\nARBITRAGE AVAILABLE!\nBEG BAL -> {} {}".format(exchange.trading_target_qty, parameters.TARGET_ASSET))

    executed_orders = []
    qty_reduction_factor = 1
    for trade_num, trade in trade_plan.iterrows():
        if qty_reduction_factor != 1:
            trade["qty"] *= qty_reduction_factor
            base_qty_precision = int(exchange.assets_info.loc[trade["pair"].replace("-", "")]["baseQtyPrecision"])
            trade["qty"] = helper.round_decimals_down(trade["qty"], base_qty_precision)

        log.print_status("TRADE {} -> {} {} {} at price {}".format(trade_num, trade["order_type"], trade["qty"], trade["pair"], trade["price"]))

        t = Trade(exchange, trade, trade_num)
        order = t.execute_limit_trade()
        executed_orders.append(order)  # append initial order attempt
        additional_orders, resulting_qty = t.handle_order(order)
        executed_orders += additional_orders  # append any additional orders needed to complete trade (could be 0 additional trades)

        if t.arbitrage_lost:
            raw_profit = {}
            raw_profit["scan_id"] = trade_plan["scan_id"][0]
            raw_profit["profit"] = 0
            if executed_orders is None:
                return pd.DataFrame(), raw_profit
            else:
                return pd.DataFrame(executed_orders), raw_profit

        if trade_num == 0 or trade_num == 1:
            qty_reduction_factor = compare_resulting_qty(exchange, t, resulting_qty)

    raw_profit = {}
    raw_profit["scan_id"] = trade_plan["scan_id"][0]
    raw_profit["starting_qty"] = exchange.trading_target_qty
    raw_profit["ending_qty"] = resulting_qty + t.unused_qty
    raw_profit["profit"] = raw_profit["ending_qty"] - raw_profit["starting_qty"]
    raw_profit["asset"] = parameters.TARGET_ASSET

    log.print_status("==============================\nEND BAL -> {} {}".format(round(raw_profit["ending_qty"], 5), parameters.TARGET_ASSET))
    log.print_status("PROFIT  -> {} {}".format(round(raw_profit["profit"], 5), parameters.TARGET_ASSET))

    return pd.DataFrame(executed_orders), raw_profit


# TODO ## <- revise this
# def rebalance_portfolio(exchange, original_total_account_value, target_stop_loss_percent):
#     '''
#     Record balances, determine if stop loss exceeded, and reblance assets if necessary
#     Return balances and True if stop loss exceeded, False otherwise.
#     '''
#     balances = pd.DataFrame(exchange.client.get_account()["balances"])  # API CALL ##
#     balances["free"] = balances["free"].astype(float)
#     balances["time"] = datetime.now().strftime("%Y:%m:%d %H:%M:%S")

#     total_account_value = 0
#     for i, asset in enumerate(balances["asset"]):
#         item = balances[balances["asset"] == asset]
#         asset_bal = item["free"][i]
#         try:
#             asset_price_in_usdt = float(exchange.client.get_order_book(symbol=asset + 'USD')['asks'][0][0])  # API CALL ##
#             total_account_value += asset_bal * asset_price_in_usdt
#         except:
#             pass

#     balances = balances.append([{'asset': 'TOTAL ACCT VALUE (USDT)', 'free': total_account_value}])
#     balances = balances.pivot_table(index=["time"], columns='asset', values='free').reset_index()

#     # check if BNB balance at 1% of portfolio, buy more to get to 3%
#     bnb_price_in_usdt = float(exchange.client.get_order_book(symbol='BNBUSDT')['asks'][0][0])  # API CALL ##
#     if (balances["BNB"].values[0] * bnb_price_in_usdt) / total_account_value < 0.01:
#         print("Rebalancing BNB to 2 percent of portfolio.")
#         bnb_to_buy_with_usdt = total_account_value * 0.03 - ((balances["BNB"].values[0] * bnb_price_in_usdt) / total_account_value)
#         precision = int(round(-math.log(float(exchange.step_sizes["BNBUSDT"]), 10), 0))
#         bnb_qty_to_buy = round_decimals_down(bnb_to_buy_with_usdt / bnb_price_in_usdt, precision)
#         order = exchange.client.order_market_buy(symbol='BNBUSDT', quantity=bnb_qty_to_buy)

#     # check if all other arbitrage assets at 0.2% of total portfolio, remainder goes to TARGET ASSET
#     pass  # <- TODO

#     if total_account_value < original_total_account_value * (1 - (target_stop_loss_percent / 100)):
#         return balances, True

#     return balances, False


'''
## NOTES ##

# updated trade_set example
exchange                  KUCOIN
target                      USDT
pair                      FTMETH
net_forward            -0.776712
net_reverse              0.45594
timestamp               01:04:24
best_direction           reverse
left_x_target_rate       0.38577
right_x_target_rate      2469.91
pair_rate              0.0001569
scan_time_secs           0.69398
scan_id                        0
max_profit_percent      0.501086
left_x_right_rate      0.0001569
left_x_target_qty        2701.84
left_x_right_qty          0.0001
right_x_target_qty     0.0826969

# trade_plan example
{'symbol': 'VETUSDT', 'orderId': 60790476, 'orderListId': -1, 'clientOrderId': 'XmRDmS7UriPkWpBJZw3Qx0', 'transactTime': 1617444519735, 'price': '0.00000000', 'origQty': '894.00000000', 'executedQty': '894.00000000', 'cummulativeQuoteQty': '83.04723600', 'status': 'FILLED', 'timeInForce': 'GTC', 'type': 'MARKET', 'side': 'BUY', 'fills': [{'price': '0.09289400', 'qty': '894.00000000', 'commission': '0.00018324', 'commissionAsset': 'BNB', 'tradeId': 1113091}]}
'''

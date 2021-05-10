import exchange
import market
import trade
import parameters
import log

from datetime import datetime
import pandas as pd
import time
import sys


def main():
    all_exchange_scans = pd.DataFrame()
    all_projected_trades = pd.DataFrame()
    all_executed_trades = pd.DataFrame()
    all_asset_balances = pd.DataFrame()
    all_raw_profits = []

    ex = exchange.get_exchange(sys.argv)
    genisis_target_qty = ex.total_starting_target_qty

    for scan_id in range(parameters.NUM_SCANS + 1):
        scan = market.scan_exchange(ex, scan_id)
        max_trade_template = market.get_max_profit_trade(scan)

        all_exchange_scans = all_exchange_scans.append(scan)  # record scan
        log.print_scan_info(scan_id, scan, max_trade_template)  # print scan info to console

        if market.is_profitable(ex, max_trade_template):
            execute_start_time = time.time()

            tp = trade.TradePlan(ex, scan_id, max_trade_template)

            if tp.trade_plan is not None:
                all_projected_trades = all_projected_trades.append(tp.trade_plan)  # record projected trades
                if tp.trade_plan["valid"].all():
                    executed_trades, raw_profit = trade.execute_trade_plan(ex, tp.trade_plan)
                    all_executed_trades = all_executed_trades.append(executed_trades)  # record executed trades
                    # ex.trading_target_qty = raw_profit["ending_qty"]  # may not be needed b/c we have ex.update_target_qty_partitions()

                    raw_profit["total_arbitrage_time_secs"] = round(scan["scan_time_secs"][0] + (time.time() - execute_start_time), 5)
                    all_raw_profits.append(raw_profit)  # record raw profit

                    log.print_status("TIME    -> {} secs.\n".format(raw_profit["total_arbitrage_time_secs"]))

                    if raw_profit != 0:
                        balances = ex.get_balances()
                        balances["scan_id"] = scan_id
                        all_asset_balances = all_asset_balances.append(balances)  # record current balance sheet

                        # TODO:
                        # ** KEEP TRACK OF FEES INCURRED pre and post fee discount **
                        # ** KEEP TRACK OF CRYPTO DUST COLLECTED **

                        ex.rebalance_portfolio()  # TODO

                        if ex.check_stop_loss(balances):
                            log.print_status("WARNING: STOP LOSS FOR TARGET ASSET EXCEEDED! Exiting scan loop early...")
                            break
                        else:
                            ex.update_target_qty_partitions()  # update target tradeable and liquid qty

        time.sleep(parameters.SCAN_LENGTH_SECONDS)

    log.print_status("Saving runtime history...")
    save_time = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

    all_exchange_scans.set_index("scan_id").to_csv("{}scan_history_{}.csv".format(parameters.SAVE_PATH, str(save_time)))

    if len(all_projected_trades) > 0:
        all_projected_trades.set_index("scan_id").to_csv("{}projected_trades_history_{}.csv".format(parameters.SAVE_PATH, str(save_time)))

    if len(all_executed_trades) > 0:
        all_executed_trades.set_index(["scan_id", "trade_num"]).to_csv("{}executed_trades_history_{}.csv".format(parameters.SAVE_PATH, str(save_time)))
        pd.DataFrame(all_raw_profits).set_index(["scan_id"]).to_csv("{}raw_profits_history_{}.csv".format(parameters.SAVE_PATH, str(save_time)))
        all_asset_balances.set_index(["scan_id"]).to_csv("{}balances_history_{}.csv".format(parameters.SAVE_PATH, str(save_time)))

    # ending messages
    total_runtime_mins = round((time.time() - runtime_start) / 60, 2)
    final_trading_target_qty, final_reserve_target_qty = ex.update_target_qty_partitions()
    target_asset_accumulation_amount = (final_trading_target_qty + final_reserve_target_qty) - genisis_target_qty
    target_asset_accumulation_percent = round((target_asset_accumulation_amount / genisis_target_qty) * 100, 5)
    log.print_status("\nDone! In {} mins, the bot accumulated {} {} which is a {} percent difference.".format(total_runtime_mins, target_asset_accumulation_amount, parameters.TARGET_ASSET, target_asset_accumulation_percent))


if __name__ == '__main__':
    runtime_start = time.time()
    main()
    total_runtime_mins = round((time.time() - runtime_start) / 60, 2)
    log.print_status("Total runtime was {} mins.".format(total_runtime_mins))

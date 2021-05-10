import parameters

from datetime import date
import pandas as pd


def print_scan_info(scan_id, scan, max_trade_template):
    '''
    Writes max profit for each scan to log file and prints to console.
    '''
    time_secs = scan["scan_time_secs"][0]
    message_str = ">>>  Scan {}/{} took {} secs. MAX PROFIT = {}%".format(scan_id, parameters.NUM_SCANS, f'{time_secs:.5f}', f'{max_trade_template["max_profit_percent"]:.5f}')

    today_date = date.today()

    with open(parameters.SAVE_PATH + "console_log_{}_{}_{}.txt".format(today_date.year, today_date.month, today_date.day), "a") as log_file:
        log_file.write(message_str + "\n")  # save to logfile
        print(message_str)  # print to console


def save_scan_history(path, save_time, scan_history):
    scan_history.to_excel(path + "scan_history_{}.xlsx".format(str(save_time)))


def print_status(status_str):
    '''
    Writes 'status_str' string to log file and prints the string to console.
    '''
    today_date = date.today()

    with open(parameters.SAVE_PATH + "console_log_{}_{}_{}.txt".format(today_date.year, today_date.month, today_date.day), "a") as log_file:
        log_file.write(status_str + "\n")  # save to logfile
        print(status_str)  # print to console


def print_end_trade_status():
    '''
    '''
    print("TODO")
    return


def save_trading_plan_history(path, save_time, projected_trades_history):
    projected_trades_history.to_excel(path + "projected_trades_history_{}.xlsx".format(str(save_time)))


def save_executed_trades_history(path, save_time, executed_trades_history):
    executed_trades_history.to_excel(path + "executed_trades_history_{}.xlsx".format(str(save_time)))


def save_current_balances(path, save_time, current_balances):
    current_balances.to_excel(path + "balances_history_{}.xlsx".format(str(save_time)))

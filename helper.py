import log
import math


def get_precision(step_size):
    '''
    step_size: 0.00100
    returns 3
    '''
    return int(round(-math.log(float(step_size), 10), 0))


def round_decimals_down(number, decimals):
    """
    Returns a value rounded down to a specific number of decimal places.
    """
    if not isinstance(decimals, int):
        raise TypeError("decimal places must be an integer")
    elif decimals < 0:
        raise ValueError("decimal places has to be 0 or more")
    elif decimals == 0:
        return math.floor(number)

    factor = 10 ** decimals
    return math.floor(number * factor) / factor


def check_min_notional(exchange, trade, stripped_symbol):
    '''
    Returns True if the pair quantity satisfies the min notional requirement.
    '''
    min_notional = exchange.assets_info.loc[stripped_symbol]["baseMinNotional"]
    if min_notional == "":  # no min notional for this exchange
        return True

    if trade["price"] * trade["qty"] >= min_notional:  # notional = price * quantity
        return True

    log.print_status("MSG: {} pair trade notional ({}*{}) below min_notional ({}).".format(trade["pair"], str(trade["price"]), str(trade["qty"]), str(min_notional)))
    return False


def check_qty(exchange, trade, stripped_symbol):
    '''
    Checks if proposed trade quantity is above the min qty required and below the max qty allowed.
    '''
    base_min_qty = exchange.assets_info.loc[stripped_symbol]["baseMinQty"]
    base_max_qty = exchange.assets_info.loc[stripped_symbol]["baseMaxQty"]

    if trade["qty"] >= base_min_qty and trade["qty"] <= base_max_qty:
        return True

    log.print_status("MSG: {} {} not within ({},{}) required.".format(trade["qty"], stripped_symbol, base_min_qty, base_max_qty))
    return False

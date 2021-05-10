def calculate_forward_arbitrage(forward_rates):
    '''
    '''
    return ((1 / forward_rates[1]) * (1 / forward_rates[2]) * forward_rates[0] - 1) * 100


def calculate_reverse_arbitrage(reverse_rates):
    '''
    '''
    return (reverse_rates[1] * reverse_rates[2] * (1 / reverse_rates[0]) - 1) * 100


def get_net_forward_arbitrage(exchange, orderbook, pair):
    '''
    Calculates forward arbitrage profit. Returns float showing profit in percent.
    '''
    # extract target pair symbols
    pair_left_target_symbol = exchange.assets_info.loc[pair]["baseAsset"] + exchange.target_asset
    pair_right_target_symbol = exchange.assets_info.loc[pair]["quoteAsset"] + exchange.target_asset

    # collect asset exchange rates
    forward_rates = (orderbook.loc[pair_left_target_symbol]['bidPrice'],
                     orderbook.loc[pair_right_target_symbol]['askPrice'],
                     orderbook.loc[pair]['askPrice'])

    return calculate_forward_arbitrage(forward_rates), forward_rates


def get_net_reverse_arbitrage(exchange, orderbook, pair):
    '''
    Calculates potential reverse arbitrage profit. Returns float showing profit in percent.
    '''
    # extract target pair symbols
    pair_left_target_symbol = exchange.assets_info.loc[pair]["baseAsset"] + exchange.target_asset
    pair_right_target_symbol = exchange.assets_info.loc[pair]["quoteAsset"] + exchange.target_asset

    # collect asset exchange rates
    reverse_rates = (orderbook.loc[pair_left_target_symbol]['askPrice'],
                     orderbook.loc[pair_right_target_symbol]['bidPrice'],
                     orderbook.loc[pair]['bidPrice'])

    return calculate_reverse_arbitrage(reverse_rates), reverse_rates

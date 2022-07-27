
from binance.client import Client
import config
import pandas as pd
import pandas_ta as pta
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np


client = Client(config.API_KEY, config.API_SECRET, tld='us')



def get_historic_data(symbol='BNBBTC', interval='1h', back=10):

    interval_units = ''.join([i for i in interval if not i.isdigit()])
    if interval_units == 'm':
        long_interval_unit = 'minutes'
    elif interval_units == 'h':
        long_interval_unit = 'hours'
    elif interval_units == 'd':
        long_interval_unit = 'days'
    else:
        print('Time interval not recognised!!')
        return None
    
    response = client.get_historical_klines(symbol=symbol, interval = interval, start_str = f'{back} {long_interval_unit} ago UTC')
    df = pd.DataFrame(response)
    df = df.iloc[:,:5]
    df.columns = ['time', 'open', 'high', 'low', 'close']
    df[['open', 'high', 'low', 'close']] = df[['open', 'high', 'low', 'close']].astype(float)
    df.time = pd.to_datetime(df.time, unit='ms')
    #df['day'] = df.time.hour
    df = df.sort_values('time', ascending = False).reset_index(drop=True)
    return df


def get_macd(stream, ma_big_period, ma_small_period, n=2):
    ma_big = pd.DataFrame(stream).ewm(span=ma_big_period, adjust=False, min_periods=12).mean()
    ma_big = ma_big.loc[ma_big.index[-n]:ma_big.index[-1]].reset_index(drop=True)
    ma_small = pd.DataFrame(stream).ewm(span=ma_small_period, adjust=False, min_periods=12).mean()
    ma_small = ma_small.loc[ma_small.index[-n]:ma_small.index[-1]].reset_index(drop=True)
    ma_small.columns = ['small']
    ma_big.columns = ['big']
    mas = ma_small.join(ma_big)
    return mas



def on_open(ws):
    print('opened connection')

def on_close(ws):
    print('closed connection')
    
def get_balance(coin='USDT'):
    info = client.get_account()
    balances = pd.DataFrame(info["balances"])
    balance = balances[balances['asset'] == coin]['free']
    balance = float(balance.values[0])
    
    return math.floor(balance * 1000)/1000.0



def rsi_tester(
    tld = 'us',
    symbol = 'BNBUSDT',
    interval = '1h',
    back = 24*30,
    sell_limit_per = 0.5,
    investment_dollar = 100,
    rsi_period = 14,
    rsi_low = 30,
    rsi_high = 70
):
    client = Client(config.API_KEY, config.API_SECRET, tld=tld)
    data = get_historic_data(symbol=symbol, interval=interval, back=back).sort_values('time').reset_index(drop=True)
    data['rsi'] = pta.rsi(data['close'], length = rsi_period)   
    
    position = 'out'

    colnames = data.columns.values.tolist() 
    colnames.append('move')
    data_movements = pd.DataFrame(columns=colnames)

    for index, row in data.iterrows():
        if position == 'out':
            if row['rsi'] < rsi_low:
                buy_price = row['close']
                limit_price = buy_price - (buy_price * sell_limit_per/100)
                position = 'in'
                
                to_append = data.iloc[index].copy()
                to_append['move'] = 'BUY'
                data_movements = data_movements.append(to_append)
                            
        elif position == 'in':
            if (row['close'] < limit_price) or row['rsi'] > rsi_high:
                position = 'out'
                
                to_append = data.iloc[index].copy()
                to_append['move'] = 'SELL'
                data_movements = data_movements.append(to_append)
        else:
            pass
        
    data_movements.reset_index(drop=True, inplace=True)
    
    dollar = investment_dollar
    crypto = 0

    data_movements['dollar'] = float(0)
    data_movements['crypto'] = float(0)

    for index, row in data_movements.iterrows():
        if row['move'] == 'BUY':
            crypto = dollar / row['close']
            dollar = 0
            data_movements.loc[index, 'crypto'] = crypto
            data_movements.loc[index, 'dollar'] = 0
        else:
            dollar = crypto * row['close']
            crypto = 0
            data_movements.loc[index:, 'dollar'] = dollar
            data_movements.loc[index:, 'crypto'] = 0


    data = data.merge(data_movements[['time', 'move', 'dollar', 'crypto']], on='time', how='left')
    data[['dollar', 'crypto']] = data[['dollar', 'crypto']].fillna(method='ffill')
    data['dollar'] = data['dollar'].fillna(investment_dollar)
    data['crypto'] = data['crypto'].fillna(0)
    data['move'] = data['move'].fillna('')
    data['value_dollar'] = data['dollar'] + (data['crypto'] * data['close'])
    data['balance'] = data['value_dollar'] - investment_dollar
    last_value_dollars = data.loc[max(data.index), 'value_dollar']
    profit = last_value_dollars - investment_dollar
    profit_per = profit / investment_dollar * 100
    
    
    fig, axes = plt.subplots(2, 1, figsize=(15, 7))
    axes = axes.flatten()
    fig.suptitle(f'Balance: {round(last_value_dollars, 1)} $ | Profit: {round(profit, 1)} |  Profit %: {round(profit_per, 1)} | RSI period: {rsi_period} |Low: {rsi_low} | High: {rsi_high}', fontsize=20) 

    plot_stock_value = sns.lineplot(x="time", y="close", data=data, ax=axes[0], color = 'grey')


    plot_wallet = sns.lineplot(x="time", y="balance", data=data, ax=axes[1], color = 'cyan')
    plot_wallet.axhline(0, color = 'salmon')
    
    return plt.show()
            
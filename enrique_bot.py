from binance.client import Client
import config
import pandas as pd
import websocket
import json
import pandas_ta as pta
import math
from binance.enums import *
from my_funcs import get_historic_data


#### SETTINGS #####
pair = 'bnbusdt' # No capital letters
pair_cripto = 'bnb'
interval = '1m'
rsi_interval = 14
rsi_low = 30
rsi_high = 70
position = 'out'
stoch_high = 80
for_real = True
back_hist = 60 * 24 * 30 * 12 * 2
###################################


pair_no_cripto = pair.replace(pair_cripto, '').upper()
pair_cripto = pair_cripto.upper()


client = Client(api_key = config.API_KEY, api_secret = config.API_SECRET, tld='com')
SOCKET = f'wss://stream.binance.com:9443/ws/{pair}@kline_{interval}'

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


# to convert into 5 min klines
ohlc = {
    'high': 'max',
    'low': 'min',
    'close': 'last',
}

stream = get_historic_data(symbol=pair.upper(), interval=interval, back=back_hist)
stream = stream.sort_values('time').reset_index(drop=True)
stream = stream[['time', 'high', 'low', 'close']]
stream.index = stream['time']
stream.drop(['time'], axis = 1, inplace=True)
stream.index = pd.to_datetime(stream.index, unit = 'ns', utc=True).tz_convert('US/Eastern')
stream['ended'] = True


def on_message(ws, message):
    global stream, position, pair, ohlc
    
    json_message = json.loads(message)
    candle = json_message['k']
    is_candle_closed = candle['x']
    close = float(candle['c'])
    high = float(candle['h'])
    low = float(candle['l'])
    time = pd.to_datetime(float(candle['T']), unit='ms', utc=True).tz_convert('US/Eastern')
    to_append = pd.DataFrame({'high':[high], 'low':[low], 'close': close, 'time':time, 'ended': is_candle_closed})
    to_append = to_append.set_index('time')
    stream = stream.append(to_append, ignore_index=False)
    
    if position == 'out':
        stream_5min = stream.resample('5min', label='right').apply(ohlc)
        stream_5min['rsi'] = pta.rsi(stream_5min['close'], length = rsi_interval)
        rsi = stream_5min.loc[stream_5min.index[-1], 'rsi']
        round_close = stream_5min.loc[stream_5min.index[-1], 'close']
        round_time = stream_5min.index[-1]
        
        print(f'Position: {position} | Price: {round_close} | RSI: {rsi} | Time: {round_time}', end = "\r")
        
        if rsi < rsi_low:
            no_cripto_balance = get_balance(pair_no_cripto)
            quant = round(no_cripto_balance / close * 0.99, 3)
            if for_real:
                order = client.create_order(
                             symbol=pair.upper(),
                             side=SIDE_BUY,
                             type=ORDER_TYPE_MARKET,
                             quantity = quant 
                             )
            
            position = 'in'
            print('BOUGHT!!!!')
        
        
    else:
        stream_1min = stream.resample('1min', label='right').apply(ohlc)
        stream_1min.ta.stoch(high='high', low='low', k=14, d=3, append=True)
        stoch = stream_1min.loc[stream_1min.index[-1], 'STOCHk_14_3_3']
        round_close = stream_1min.loc[stream_1min.index[-1], 'close']
        round_time = stream_1min.index[-1]
        
        print(f'Position: {position} | Price: {round_close} | STOCH: {stoch} | Time: {round_time}', end = "\r")
        
        if stoch > stoch_high:
            crypto_balance = get_balance(pair_cripto)
            if for_real:
                order = client.create_order(
                             symbol=pair.upper(),
                             side=SIDE_SELL,
                             type=ORDER_TYPE_MARKET,
                             quantity = round(crypto_balance*0.99, 3)
                             )
                
            position = 'out'
            print('SOLD!!!!')


    stream = stream[stream.ended == True]
    
    if stream.shape[0] > back_hist:
        stream = stream.iloc[1:]
         
    
  
ws = websocket.WebSocketApp(SOCKET, on_open=on_open, on_close=on_close, on_message=on_message)
ws.run_forever()




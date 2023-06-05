from kucoin.client import Client
from kucoin_futures.client import Trade
from kucoin_futures.client import User
from dotenv import load_dotenv
from ta.trend import ema_indicator
from ta.momentum import stochrsi_k, stochrsi_d
import pandas as pd
from datetime import datetime
from datetime import timezone
import traceback
import time
import os

# Load environment variables from .env file
load_dotenv()

# Market API, get candlesticks for indicators
marketClient = Client(os.getenv('API_KEY_FUTURES'), os.getenv('API_SECRET_FUTURES'), os.getenv('API_PASSPHRASE_FUTURES'))

# ----- FUTURES API -----
api_key = os.getenv('API_KEY_FUTURES')
api_secret = os.getenv('API_SECRET_FUTURES')
api_passphrase = os.getenv('API_PASSPHRASE_FUTURES')

# Create trade and user endpoints, used for executing futures trades and getting user account details
tradeClient = Trade(key = api_key, secret = api_secret, passphrase = api_passphrase, is_sandbox = False)
userClient = User(api_key, api_secret, api_passphrase)

# Modifiable leverage parameter
leverage = 1

# Keep track of current position details
class currentPosition:
    inPositionLONG = False
    inPositionSHORT = False
    buyPrice = 0
    amtLots = 0

# Establish previous state in the event of a crash/restart
if(tradeClient.get_order_list()['items'][0]['side'] == 'buy'):
    currentPosition.inPositionLONG = True
if(tradeClient.get_order_list()['items'][0]['side'] == 'sell'):
    currentPosition.inPositionSHORT = True

# Buy conditions
def kupwardLONG(rsi_k_current, rsi_k_trailing, rsi_d_current):
    return (((rsi_k_current - rsi_k_trailing) > 0.05) and 
            (rsi_k_current > rsi_d_current) and 
            (rsi_k_current > 0.5))
def kupwardSHORT(rsi_k_current, rsi_k_trailing, rsi_d_current):
    return (((rsi_k_trailing - rsi_k_current) > 0.05) and 
            (rsi_k_current < rsi_d_current) and 
            (rsi_k_current < 0.5))

def smaupwardLONG(sma_9_current, sma_9_trailing): 
    return (sma_9_current - sma_9_trailing) > 1.5
def smaupwardSHORT(sma_9_current, sma_9_trailing):
    return (sma_9_trailing - sma_9_current) > 1.5

def priceupLONG(price_current, sma_9_current):
    return (price_current > sma_9_current)
def priceupSHORT(price_current, sma_9_current):
    return (price_current < sma_9_current)

# Execute a buy
def executeLONG():
    while True:
        try:
            # Get account balance and price in USDT
            balance = userClient.get_account_overview('USDT')['availableBalance']
            currentPrice = marketClient.get_ticker('ETH-USDT')['price']
            # Get buy amount in lots (0.01 ETH) * leverage
            buyAmt = int((balance/float(currentPrice))/0.01) * leverage
            # Place a ETH-USDT market order with calculated parameters
            tradeClient.create_market_order('ETHUSDTM', 'buy', '1', 'UUID', size=1)
            currentPosition.amtLots = buyAmt
            break
        except:
            time.sleep(11)
            traceback.print_exc()
            pass
    if(currentPosition.inPositionSHORT == False):
        currentPosition.inPositionLONG = True
    else:
        currentPosition.inPositionSHORT = False

# Execute a sell
def executeSHORT():
    while True:
        try:
            # size=currentPosition.amtLots
            tradeClient.create_market_order('ETHUSDTM', 'sell', '1', 'UUID', size=1)
            break
        except:
            time.sleep(1)
            traceback.print_exc()
            pass
    if(currentPosition.inPositionLONG == False):
        currentPosition.inPositionSHORT = True
    else:
        currentPosition.inPositionLONG = False

frameLen = 0

# Bot loop
while True:
    while True:
        try:
            # Request large enough data set for accurate indicators and create dataframe
            df = pd.DataFrame(marketClient.get_kline_data('ETH-USDT', 
                                            '4hour', 
                                            round(datetime(2023, 3, 5).replace(tzinfo=timezone.utc).timestamp()), 
                                            round(time.time())), 
                                            columns=['timestamp', 'open', 'close', 'high', 'low', 'tx amt', 'tx vol'])
            break
        except:
            time.sleep(11)
            traceback.print_exc()
            pass
    
    # Indicators
    price_current = pd.to_numeric(df.iloc[::-1]['close'])[0]
    ema_200_current = ema_indicator(pd.to_numeric(df.iloc[::-1]['close']), 200, False)[0]
    sma_9_current = ema_indicator(pd.to_numeric(df.iloc[::-1]['close']), 17, False)[0]
    sma_9_trailing = ema_indicator(pd.to_numeric(df.iloc[::-1]['close']), 17, False)[1]
    rsi_k_current = stochrsi_k(pd.to_numeric(df.iloc[::-1]['close']), 14, 4, 4, True)[0]
    rsi_d_current = stochrsi_d(pd.to_numeric(df.iloc[::-1]['close']), 14, 4, 4, True)[0]
    rsi_k_trailing = stochrsi_k(pd.to_numeric(df.iloc[::-1]['close']), 14, 4, 4, True)[1]

    # Buying conditions
    if(kupwardLONG(rsi_k_current, rsi_k_trailing, rsi_d_current) and
        smaupwardLONG(sma_9_current, sma_9_trailing) and 
        priceupLONG(price_current, sma_9_current) and
        currentPosition.inPositionLONG == False and 
        (frameLen != len(df) and frameLen != 0)):
        # Execute a buy
        executeLONG()
    elif(kupwardSHORT(rsi_k_current, rsi_k_trailing, rsi_d_current) and
        smaupwardSHORT(sma_9_current, sma_9_trailing) and 
        priceupSHORT(price_current, sma_9_current) and
        currentPosition.inPositionSHORT == False and 
        (frameLen != len(df) and frameLen != 0)):
        # Execute a buy
        executeSHORT()

    # Selling conditions, can sell on the same tick as buy
    if(rsi_k_trailing - rsi_k_current > 0 and currentPosition.inPositionLONG == True and (frameLen != len(df) and frameLen != 0)):
        # Execute a short sell
        executeSHORT()
    elif(rsi_k_current - rsi_k_trailing > 0 and currentPosition.inPositionSHORT == True and (frameLen != len(df) and frameLen != 0)):
        # Execute a long buy
        executeLONG()

    print(price_current)
    print(kupwardLONG(rsi_k_current, rsi_k_trailing, rsi_d_current), smaupwardLONG(sma_9_current, sma_9_trailing), priceupLONG(price_current, sma_9_current))
    print(kupwardSHORT(rsi_k_current, rsi_k_trailing, rsi_d_current), smaupwardSHORT(sma_9_current, sma_9_trailing), priceupSHORT(price_current, sma_9_current))
    print(ema_200_current, sma_9_current, rsi_k_current, rsi_k_trailing)
    print((frameLen != len(df) and frameLen != 0))
    if(currentPosition.inPositionLONG == True or currentPosition.inPositionSHORT == True):
        print("---IN POSITION---")
    frameLen = len(df)
    time.sleep(5)
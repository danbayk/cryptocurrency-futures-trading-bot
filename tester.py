import backtrader as bt
from backtrader.feeds import GenericCSVData
import pandas as pd
from ta.trend import ema_indicator
from ta.momentum import stochrsi_k, stochrsi_d
from math import floor
import datetime

#1h TP: 25, SL: 15
# Variable values for testing

# Interchange with any chart with the same column format
chart = 'largeDataSetETH.csv'
# Starting capital
initialCapital = 1000
# Set take profit (dollars)
takeprofit = 25
# Set stop loss (dollars)
stoploss = 15
# Futures leverage amount (ex. '5' --> 5x leverage)
leverage = 5

cerebro = bt.Cerebro()
feed = GenericCSVData(dataname=chart,
                      dtformat = ('%Y-%m-%d'),
                      fromdate = datetime.datetime(2023, 1, 5),
                      date = 0,
                      open = 1,
                      high = 2,
                      low = 3,
                      close = 4,
                      volume = 5,
                      openinterest = -1)

df = pd.DataFrame(columns=['close'])
df_open = pd.DataFrame(columns=['open'])

class positionStats:
    startingCapital = initialCapital
    capital = startingCapital
    wins = 0
    losses = 0
    fees = 0

class currentPosition:
    inPosition = False
    buyPrice = 0

class TestStrategy(bt.Strategy):

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print('%s, %s' % (dt.isoformat(), txt))

    def __init__(self):
        self.dataclose = self.datas[0].close
        self.datahigh = self.datas[0].high
        self.dataopen = self.datas[0].open
        self.datavolume = self.datas[0].volume
        self.datalow = self.datas[0].low

    def next(self):
        global positionStats

        df.loc[len(df.index)] = [self.dataclose[0]]
        df_open.loc[len(df_open.index)] = [self.dataopen[0]]
        price_current = pd.to_numeric(df['close'])[len(df) - 1]
        price_previous_open = pd.to_numeric(df_open['open'])[0 if len(df) == 1 else len(df) - 2]
        ema_200_current = ema_indicator(pd.to_numeric(df['close']), 200, False)[0 if len(df) == 1 else len(df) - 2]
        if(price_current < ema_200_current):
            return
        price_current_high = self.datahigh[0]
        price_current_open = self.dataopen[0]
        price_current_low = self.datalow[0]
        price_volume = self.datavolume[0]
        sma_9_current = ema_indicator(pd.to_numeric(df['close']), 17, False)[0 if len(df) == 1 else len(df) - 2]
        sma_9_trailing = ema_indicator(pd.to_numeric(df['close']), 17, False)[0 if ((len(df) == 1) or (len(df) == 2)) else len(df) - 3]
        rsi_k_current = stochrsi_k(pd.to_numeric(df['close']), 14, 3, 3, True)[0 if len(df) == 1 else len(df) - 2]
        rsi_d_current = stochrsi_d(pd.to_numeric(df['close']), 14, 3, 3, True)[0 if len(df) == 1 else len(df) - 2]
        rsi_k_trailing = stochrsi_k(pd.to_numeric(df['close']), 14, 3, 3, True)[0 if ((len(df) == 1) or (len(df) == 2)) else len(df) - 3]
        rsi_d_trailing = stochrsi_d(pd.to_numeric(df['close']), 14, 3, 3, True)[0 if ((len(df) == 1) or (len(df) == 2)) else len(df) - 3]

        # Buying conditions
        def kupward():
            return (((rsi_k_current - rsi_k_trailing) > 0.05) and (rsi_k_current > rsi_d_current) and (rsi_k_current > 0.5))

        def smaupward():
            return (sma_9_current - sma_9_trailing) > 0.9

        def priceup():
            return ((price_current > ema_200_current) and (price_current > sma_9_current) and (sma_9_current > ema_200_current))

        if(kupward() and smaupward() and priceup() and currentPosition.inPosition == False):
            currentPosition.inPosition = True
            currentPosition.buyPrice = (price_current_open + price_previous_open)/2
            positionStats.fees = positionStats.fees + ((positionStats.capital * leverage)/100)*0.06
            # print(price_current, ema_200_current, sma_9_current, rsi_k_current)
            print('--------------------')
            self.log('BUY')
            print(currentPosition.buyPrice)
            print(price_volume)
            print('--------------------')
            self.buy()

        # Option to sell on buy tick
        if(((price_current_high > (currentPosition.buyPrice + takeprofit)) or (price_current_low < (currentPosition.buyPrice - stoploss))) and currentPosition.inPosition == True):
            self.log('SELL')
            # Win
            if(price_current_high > (currentPosition.buyPrice + takeprofit)):
                positionStats.wins += 1
                positionStats.capital = positionStats.capital + ((((positionStats.capital * leverage)/currentPosition.buyPrice)*(currentPosition.buyPrice + takeprofit)) - (positionStats.capital * leverage))
                positionStats.fees = positionStats.fees + (((positionStats.capital * leverage) + takeprofit)/100)*0.06
                print(currentPosition.buyPrice + takeprofit)
            # Loss
            elif(price_current_low < (currentPosition.buyPrice - stoploss)):
                positionStats.losses += 1
                positionStats.capital = positionStats.capital = positionStats.capital + ((((positionStats.capital * leverage)/currentPosition.buyPrice)*(currentPosition.buyPrice - stoploss)) - (positionStats.capital * leverage))
                positionStats.fees = positionStats.fees + (((positionStats.capital * leverage) - stoploss)/100)*0.06
                print(currentPosition.buyPrice - stoploss)
            print(price_volume)
            currentPosition.inPosition = False
            currentPosition.buyPrice = 0
            self.sell()

cerebro.addstrategy(TestStrategy)
cerebro.adddata(feed)   
cerebro.run()
print('\n')
print('-----RESULTS-----')
print('Starting capital:')
print(positionStats.startingCapital)
print('--------------------')
print('Ending capital:')
print(floor(positionStats.capital))
print('--------------------')
print('PnL:')
print(floor(positionStats.capital - positionStats.startingCapital))
print('--------------------')
print('Wins:')
print(positionStats.wins)
print('--------------------')
print('Losses:')
print(positionStats.losses)
print('--------------------')
print('Win rate:')
print((positionStats.wins)/(positionStats.wins + positionStats.losses))
print('--------------------')
print('Fees:')
print(positionStats.fees)
print('--------------------')
print('Final profit:')
print(floor((positionStats.capital - positionStats.startingCapital) - positionStats.fees))
print('--------------------')
# cerebro.plot()
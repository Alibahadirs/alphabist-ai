import pandas as pd
import yfinance as yf

def yahoo_symbol(symbol):
    symbol = symbol.strip().upper()
    return symbol if symbol.endswith('.IS') else symbol + '.IS'

def get_quote(symbol):
    history = yf.Ticker(yahoo_symbol(symbol)).history(period='5d', interval='1d', auto_adjust=False)
    if history.empty:
        raise RuntimeError('Fiyat verisi bulunamadı')
    closes = history['Close'].dropna()
    last = float(closes.iloc[-1])
    previous = float(closes.iloc[-2]) if len(closes) > 1 else None
    return {'last': last, 'previous': previous, 'change': None if previous is None else last-previous, 'change_percent': None if not previous else (last-previous)/previous*100}

def get_history(symbol, period='1y'):
    frame = yf.download(yahoo_symbol(symbol), period=period, interval='1d', auto_adjust=False, progress=False, threads=False)
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    frame = frame[['Open','High','Low','Close','Volume']].dropna(subset=['Close'])
    frame['SMA_20'] = frame['Close'].rolling(20).mean()
    frame['SMA_50'] = frame['Close'].rolling(50).mean()
    frame['SMA_200'] = frame['Close'].rolling(200).mean()
    delta = frame['Close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    rs = gain.ewm(alpha=1/14, adjust=False).mean() / loss.ewm(alpha=1/14, adjust=False).mean().replace(0, pd.NA)
    frame['RSI_14'] = 100 - (100/(1+rs))
    fast = frame['Close'].ewm(span=12, adjust=False).mean()
    slow = frame['Close'].ewm(span=26, adjust=False).mean()
    frame['MACD'] = fast - slow
    frame['MACD_SIGNAL'] = frame['MACD'].ewm(span=9, adjust=False).mean()
    return frame

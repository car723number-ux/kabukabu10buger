import yfinance as yf
import pandas as pd

def get_company_name(ticker):
    # 企業名は返さず、常に空文字またはTickerのみを返す
    return ""

def generate_sample_data(ticker, period="1y"):
    if not ticker:
        return None
    full_ticker = f"{ticker}.T"
    try:
        df = yf.download(full_ticker, period=period, interval="1d")
        if df.empty:
            return None
        return df
    except:
        return None
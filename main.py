import decimal
import json
import requests
import websocket
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
from binance.client import Client

import config

API_URL = "https://api.binance.com/api/v3/klines"
WS_URL = "wss://stream.binance.com:9443/ws/{symbol}@kline_{interval}"


class BinanceCandlestickAnalyzer:
    def __init__(self, symbol, period, interval, limit):
        self.symbol = symbol
        self.period = period
        self.interval = interval
        self.limit = limit
        self.close_prices = []
        self.candle_count = 0
        self.data = []
        self.notification_container = st.empty()  # Container for notifications
        self.chart_container = st.empty()  # Container for the chart

    def calculate_sma(self, prices, n):
        if len(prices) < n:
            return None
        sma = sum(prices[-n:]) / n
        return sma

    def get_historical_candles(self):
        params = {
            "symbol": self.symbol,
            "interval": self.interval,
            "limit": self.limit
        }
        response = requests.get(API_URL, params=params)
        if response.status_code == 200:
            candles = json.loads(response.text)
            closing_prices = [decimal.Decimal(candle[4]) for candle in candles]
            return closing_prices
        else:
            st.error("Failed to retrieve historical candles from Binance API.")
            return []

    def on_message(self, ws, message):
        json_message = json.loads(message)
        candles = json_message["k"]
        if candles["x"]:
            close_price = decimal.Decimal(candles["c"])
            self.close_prices.append(close_price)

            if len(self.close_prices) > self.period:
                self.close_prices.pop(0)

            sma_value = self.calculate_sma(self.close_prices, self.period)

            if close_price < sma_value:
                self.candle_count += 1
                if self.candle_count >= self.limit:
                    timestamp = datetime.fromtimestamp(int(candles['T']) / 1000).strftime('%Y-%m-%d %H:%M:%S')
                    self.notification_container.warning(
                        f"Number of candles with Close Price < SMA ("
                        f"{self.candle_count}) exceeds the limit ({self.limit})! Timestamp: {timestamp}"
                    )
            else:
                self.candle_count = 0

            timestamp = pd.to_datetime(candles['T'], unit='ms') + timedelta(hours=3)
            self.data.append((timestamp, close_price, sma_value))
            self.update_graph()

    def on_close(self, ws):
        st.write("WebSocket connection closed.")

    def update_graph(self):
        df = pd.DataFrame(self.data, columns=["Timestamp", "Close Price", "SMA Value"])

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["Timestamp"], y=df["Close Price"], mode='lines', name='Close Price'))
        fig.add_trace(go.Scatter(x=df["Timestamp"], y=df["SMA Value"], mode='lines', name='SMA Value'))

        chart = self.chart_container.plotly_chart(fig, use_container_width=True)

    def analyze_candlesticks(self):
        closing_prices = self.get_historical_candles()
        if closing_prices:
            self.close_prices = closing_prices[-self.period:]

        self.data = []
        self.candle_count = 0

        socket = WS_URL.format(symbol=self.symbol.lower(), interval=self.interval)
        ws = websocket.WebSocketApp(socket, on_message=self.on_message, on_close=self.on_close)
        ws.run_forever()

        # Update the graph after receiving all the data
        self.update_graph()


def main():
    st.title("Binance Candlestick Analysis")

    client = Client(config.API_KEY, config.SECRET_KEY)

    symbols = [symbol['symbol'] for symbol in client.get_exchange_info()['symbols']]

    symbol = st.sidebar.selectbox("Symbol", symbols, index=symbols.index("BNBUSDT"))

    intervals = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"]
    interval = st.sidebar.selectbox("Interval", intervals, index=intervals.index("30m"))

    period = st.sidebar.number_input("Period", min_value=1, value=8)
    limit = st.sidebar.number_input("Limit", min_value=1, value=3)

    if st.sidebar.button("Start Analysis"):
        analyzer = BinanceCandlestickAnalyzer(symbol, period, interval, limit)
        analyzer.analyze_candlesticks()


if __name__ == "__main__":
    main()

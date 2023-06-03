import decimal
import json
import requests
import websocket
import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go

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

        close_price = decimal.Decimal(candles["c"])
        self.close_prices.append(close_price)

        if len(self.close_prices) > self.period:
            self.close_prices.pop(0)

        sma_value = self.calculate_sma(self.close_prices, self.period)

        if close_price < sma_value:
            self.candle_count += 1
            if self.candle_count >= self.limit:
                timestamp = datetime.fromtimestamp(int(candles['t']) / 1000).strftime('%Y-%m-%d %H:%M:%S')
                self.notification_container.warning(
                    f"Number of candles with Close Price < SMA ({self.candle_count}) exceeds the limit ({self.limit})! Timestamp: {timestamp}")
        else:
            self.candle_count = 0

        self.data.append((len(self.data), close_price, sma_value))
        self.update_graph()

    def on_close(self, ws):
        st.write("WebSocket connection closed.")

    def update_graph(self):
        df = pd.DataFrame(self.data, columns=["Index", "Close Price", "SMA Value"])
        df.set_index("Index", inplace=True)

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df.index, y=df["Close Price"], mode='lines', name='Close Price'))
        fig.add_trace(go.Scatter(x=df.index, y=df["SMA Value"], mode='lines', name='SMA Value'))

        chart = self.chart_container.plotly_chart(fig, use_container_width=True)

        # Mutate the chart with new data
        chart.data[0].x = df.index
        chart.data[0].y = df["Close Price"]
        chart.data[1].x = df.index
        chart.data[1].y = df["SMA Value"]

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

    symbol = st.sidebar.text_input("Symbol", "BNBUSDT")
    period = st.sidebar.number_input("Period", min_value=1, value=8)
    interval = st.sidebar.selectbox("Interval",
                                    ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d",
                                     "1w", "1M"], index=4)
    limit = st.sidebar.number_input("Limit", min_value=1, value=3)

    if st.sidebar.button("Start Analysis"):
        analyzer = BinanceCandlestickAnalyzer(symbol, period, interval, limit)
        analyzer.analyze_candlesticks()


if __name__ == "__main__":
    main()

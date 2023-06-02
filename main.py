import decimal
import json
import requests
import websocket
import streamlit as st

S = "BNBUSDT"
N = 8
T = "30m"
L = 3

close_prices = []
candle_count = 0
data = []
sma_values = []


def calculate_sma(prices, n):
    if len(prices) < n:
        return None
    sma = sum(prices[-n:]) / n
    return sma


def get_historical_candles(symbol, interval, limit):
    api_url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    response = requests.get(api_url, params=params)
    if response.status_code == 200:
        candles = json.loads(response.text)
        closing_prices = [decimal.Decimal(candle[4]) for candle in candles]
        return closing_prices
    else:
        st.error("Failed to retrieve historical candles from Binance API.")
        return []


def on_message(ws, message):
    global candle_count, data, sma_values

    json_message = json.loads(message)
    candles = json_message["k"]

    close_price = decimal.Decimal(candles["c"])
    close_prices.append(close_price)

    if len(close_prices) > N:
        close_prices.pop(0)

    sma_value = calculate_sma(close_prices, N)

    if close_price < sma_value:
        candle_count += 1
        if candle_count >= L:
            st.warning(f"Number of candles with Close Price < SMA ({candle_count}) exceeds the limit ({L})!")
    else:
        candle_count = 0

    data.append((len(data), close_price))  # Add the close price to the graph data with the corresponding time index
    sma_values.append((len(sma_values), sma_value))  # Add the SMA value to the sma_values list with the corresponding time index

    update_graph()


def on_close(ws):
    st.write("WebSocket connection closed.")


def update_graph():
    global data, sma_values

    chart_data = list(zip(*data))  # Unzip the data list into separate x and y coordinate lists
    chart_sma = list(zip(*sma_values))  # Unzip the sma_values list into separate x and y coordinate lists

    chart.line_chart(chart_data[1], use_container_width=True, key="close_price")  # Display the close prices on the chart
    chart.line_chart(chart_sma[1], use_container_width=True, key="sma")  # Display the SMA values on the chart


def main():
    global S, N, T, L, close_prices, data, sma_values, chart

    st.title("Binance Candlestick Analysis")

    st.sidebar.header("User Input")
    S = st.sidebar.text_input("Symbol", S)
    N = st.sidebar.number_input("Period", min_value=1, value=N)
    T = st.sidebar.selectbox("Interval", ["1m", "5m", "30m", "1h", "1d"], index=2)
    L = st.sidebar.number_input("Limit", min_value=1, value=L)

    chart = st.empty()

    if st.sidebar.button("Start Analysis"):
        closing_prices = get_historical_candles(S, T, N)
        if closing_prices:
            close_prices = closing_prices[-N:]

        socket = f"wss://stream.binance.com:9443/ws/{S.lower()}@kline_{T}"
        ws = websocket.WebSocketApp(socket, on_message=on_message, on_close=on_close)
        ws.run_forever()


if __name__ == "__main__":
    main()

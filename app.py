from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import yfinance as yf

# 頁面基本設定
st.set_page_config(
    page_title="盤中訊號總覽與走勢分析雲端版 (互動圖表)", layout="wide"
)

# 自訂 CSS 樣式
st.markdown(
    """
    <style>
    .stDataFrame {
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
    }
    </style>
""",
    unsafe_allow_html=True,
)

st.title("📈 盤中訊號總覽與走勢分析工具 (互動縮放版)")

# 1. 檔案上傳區塊
uploaded_file = st.file_uploader(
    "選擇盤中訊號 Excel 檔案", type=["xlsx", "xls"]
)

if uploaded_file is not None:
  @st.cache_data
  def load_data(file):
    return pd.read_excel(file)

  df_all_signals = load_data(uploaded_file)

  # 欄位檢查
  required_cols = [
      "標的名稱",
      "監控點",
      "高亮類型",
      "開始時間",
      "結束時間",
      "持續秒數",
  ]
  if not all(col in df_all_signals.columns for col in required_cols):
    st.error(f"Excel 缺少必要的欄位，請確認包含：{required_cols}")
  else:
    df_all_signals["標的名稱"] = df_all_signals["標的名稱"].astype(str)
    df_all_signals["監控點"] = df_all_signals["監控點"].astype(str)
    df_all_signals["高亮類型"] = df_all_signals["高亮類型"].astype(str)

    # 2. 側邊欄：選擇標的與參數
    st.sidebar.header("查詢設定")
    tickers = sorted(df_all_signals["標的名稱"].unique().tolist())
    selected_ticker_base = st.sidebar.selectbox("🔍 選擇查詢標的", tickers)

    period = st.sidebar.selectbox("期間", ["1d", "5d"], index=0)
    interval = st.sidebar.selectbox("間隔", ["1m", "5m", "15m"], index=1)

    # 過濾下方表格資料
    filtered_df = df_all_signals[
        df_all_signals["標的名稱"] == selected_ticker_base
    ]

    # 3. 顯示訊號總覽表格 (支援互動縮放、固定高度捲動)
    st.subheader(f"📋 {selected_ticker_base} 訊號列表")
    st.dataframe(filtered_df, use_container_width=True, height=300)

    # 4. 繪圖按鈕
    if st.sidebar.button("📊 繪製互動式走勢圖", type="primary"):
      with st.spinner("正在從 Yahoo Finance 抓取資料並繪製互動圖表..."):
        df = pd.DataFrame()
        success_ticker = ""
        for suffix in [".TW", ".TWO"]:
          ticker = f"{selected_ticker_base}{suffix}"
          try:
            stock = yf.Ticker(ticker)
            temp_df = stock.history(period=period, interval=interval)
            if not temp_df.empty:
              df = temp_df
              success_ticker = ticker
              break
          except Exception:
            continue

        if df.empty:
          st.warning(
              f"查無 {selected_ticker_base}"
              " 的資料！請確認代號是否正確或時間間隔是否支援。"
          )
        else:
          if df.index.tz is not None:
            df.index = (
                df.index.tz_convert("Asia/Taipei").tz_localize(None)
            )

          today_date = df.index[-1].strftime("%Y-%m-%d")
          ticker_signals = filtered_df

          # 建立訊號時間與價格的對應記錄
          green_high_times, green_high_prices = [], []
          lian_c_times, lian_c_prices = [], []
          lian_v_times, lian_v_prices = [], []

          for _, row in ticker_signals.iterrows():
            monitor_point = str(row["監控點"])
            highlight_type = str(row["高亮類型"])
            start_time_str = str(row["開始時間"])
            try:
              signal_dt = pd.to_datetime(f"{today_date} {start_time_str}")
              idx = df.index.get_indexer([signal_dt], method="nearest")[0]
              if idx != -1:
                match_time = df.index[idx]
                target_price = df.loc[match_time, "High"] * 1.002

                if "綠色高亮" in highlight_type:
                  green_high_times.append(match_time)
                  green_high_prices.append(target_price)
                elif "連次" in monitor_point:
                  lian_c_times.append(match_time)
                  lian_c_prices.append(target_price)
                elif "連量" in monitor_point:
                  lian_v_times.append(match_time)
                  lian_v_prices.append(target_price)
            except Exception as ex:
              print(f"解析時間失敗: {ex}")

          # 使用 Plotly 建立上下子圖（上圖：K線，下圖：成交量）
          fig = make_subplots(
              rows=2,
              cols=1,
              shared_xaxes=True,
              vertical_spacing=0.03,
              row_heights=[0.75, 0.25],
          )

          # 1. 繪製 K 線圖 (Candlestick)
          fig.add_trace(
              go.Candlestick(
                  x=df.index,
                  open=df["Open"],
                  high=df["High"],
                  low=df["Low"],
                  close=df["Close"],
                  name="K線",
              ),
              row=1,
              col=1,
          )

          # 2. 繪製成交量圖 (Volume)，依漲跌顯示紅綠柱
          colors = [
              "red" if c >= o else "green"
              for c, o in zip(df["Close"], df["Open"])
          ]
          fig.add_trace(
              go.Bar(
                  x=df.index,
                  y=df["Volume"],
                  name="成交量",
                  marker_color=colors,
              ),
              row=2,
              col=1,
          )

          # 3. 疊加訊號標記
          # 綠色高亮 (綠色向上箭頭)
          if green_high_times:
            fig.add_trace(
                go.Scatter(
                    x=green_high_times,
                    y=green_high_prices,
                    mode="markers",
                    name="綠色高亮",
                    marker=dict(
                        symbol="triangle-up", size=14, color="green"
                    ),
                ),
                row=1,
                col=1,
            )

          # 橘色連次 (橘色向下箭頭)
          if lian_c_times:
            fig.add_trace(
                go.Scatter(
                    x=lian_c_times,
                    y=lian_c_prices,
                    mode="markers",
                    name="連次",
                    marker=dict(
                        symbol="triangle-down", size=14, color="orange"
                    ),
                ),
                row=1,
                col=1,
            )

          # 紅色連量 (紅色向上箭頭，尺寸較小)
          if lian_v_times:
            fig.add_trace(
                go.Scatter(
                    x=lian_v_times,
                    y=lian_v_prices,
                    mode="markers",
                    name="連量",
                    marker=dict(
                        symbol="triangle-up", size=8, color="red"
                    ),  # 尺寸調小
                ),
                row=1,
                col=1,
            )

          # 設定圖表互動與排版屬性
          fig.update_layout(
              title=f"<b>{success_ticker} 盤中訊號互動走勢圖</b>",
              xaxis_rangeslider_visible=False,  # 關閉預設下方滑桿，讓畫面更清爽
              height=650,
              template="plotly_white",
              hovermode="x unified",
          )

          # 渲染到 Streamlit 網頁中 (st.plotly_chart 支援互動拖曳、縮放與全螢幕)
          st.plotly_chart(fig, use_container_width=True)
else:
  st.info("👋 請先在上方上傳您的盤中訊號 Excel 檔案以開始使用。")

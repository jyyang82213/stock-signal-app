from datetime import datetime
import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
import streamlit as st
import yfinance as yf

# 頁面基本設定
st.set_page_config(
    page_title="盤中訊號總覽與走勢分析雲端版", layout="wide"
)

st.title("📈 盤中訊號總覽與走勢分析工具 (雲端版)")

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

    # 2. 側邊欄或上方控制列：選擇標的與參數
    st.sidebar.header("查詢設定")
    tickers = sorted(df_all_signals["標的名稱"].unique().tolist())
    selected_ticker_base = st.sidebar.selectbox("🔍 選擇查詢標的", tickers)

    period = st.sidebar.selectbox("期間", ["1d", "5d"], index=0)
    interval = st.sidebar.selectbox("間隔", ["1m", "5m", "15m"], index=1)

    # 過濾下方表格資料
    filtered_df = df_all_signals[
        df_all_signals["標的名稱"] == selected_ticker_base
    ]

    # 顯示訊號總覽表格
    st.subheader(f"📋 {selected_ticker_base} 訊號列表")
    st.dataframe(filtered_df, use_container_width=True)

    # 3. 繪圖按鈕
    if st.sidebar.button("📊 繪製該標的全部訊號圖", type="primary"):
      with st.spinner("正在從 Yahoo Finance 抓取資料並繪圖..."):
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

          lian_c_series = pd.Series(float("nan"), index=df.index)
          lian_v_series = pd.Series(float("nan"), index=df.index)

          for _, row in ticker_signals.iterrows():
            monitor_point = str(row["監控點"])
            start_time_str = str(row["開始時間"])
            try:
              signal_dt = pd.to_datetime(f"{today_date} {start_time_str}")
              idx = df.index.get_indexer([signal_dt], method="nearest")[0]
              if idx != -1:
                match_time = df.index[idx]
                target_price = df.loc[match_time, "High"] * 1.002
                if "連次" in monitor_point:
                  lian_c_series.loc[match_time] = target_price
                elif "連量" in monitor_point:
                  lian_v_series.loc[match_time] = target_price
            except Exception:
              pass

          plots = []
          if lian_c_series.notna().any():
            plots.append(
                mpf.make_addplot(
                    lian_c_series,
                    type="scatter",
                    marker="v",
                    markersize=120,
                    color="orange",
                )
            )
          if lian_v_series.notna().any():
            plots.append(
                mpf.make_addplot(
                    lian_v_series,
                    type="scatter",
                    marker="^",
                    markersize=120,
                    color="red",
                )
            )

          # 繪製 mplfinance 圖表並轉換給 Streamlit 顯示
          fig, axes = mpf.plot(
              df,
              type="candle",
              volume=True,
              style="yahoo",
              addplot=plots if plots else None,
              title=f"\n{success_ticker} Intraday Signals (橙:連次 / 紅:連量)",
              ylabel="Price",
              ylabel_lower="Volume",
              returnfig=True,
          )

          st.pyplot(fig)
else:
  st.info("👋 請先在上方上傳您的盤中訊號 Excel 檔案以開始使用。")
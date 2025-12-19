import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from scanner import Scanner
from data_manager import DataManager
from backtester import Backtester

# Page Config
st.set_page_config(page_title="BIST Alpha Filter", layout="wide")

# Title
st.title("📈 BIST Alpha Filter & Yatırım Asistanı")
st.markdown("⚠️ **Bu uygulama yatırım tavsiyesi değildir.** Sadece teknik analiz ve filtreleme amacı taşır.")

# Sidebar - Settings
st.sidebar.header("⚙️ Strateji Ayarları")
# Timeframe Selection
interval_option = st.sidebar.selectbox("Periyot", ["Günlük (1d)", "Haftalık (1wk)"])
interval_map = {"Günlük (1d)": "1d", "Haftalık (1wk)": "1wk"}
selected_interval = interval_map[interval_option]

# Index Selection
index_option = st.sidebar.selectbox("Hisse Grubu", ["BIST 30", "BIST 100"])

ema_len = st.sidebar.number_input("Kısa Vade EMA", min_value=1, value=9)
wma_len = st.sidebar.number_input("Uzun Vade WMA", min_value=1, value=30)
index_sma_len = st.sidebar.number_input("Endeks Filtresi (SMA)", min_value=1, value=50)

st.sidebar.markdown("---")
st.sidebar.header("🔍 Tarama")

# Initialize Scanner
@st.cache_resource
def get_scanner():
    return Scanner()

scanner = get_scanner()

# Display BIST Status (Based on selected interval)
# If weekly, use longer period for index data
idx_period = "2y" if selected_interval == "1wk" else "6mo"
index_data = scanner.data_manager.fetch_ohlcv("XU100.IS", period=idx_period, interval=selected_interval)
if not index_data.empty:
    current_idx_val = index_data['close'].iloc[-1]
    last_sma50 = index_data['close'].rolling(index_sma_len).mean().iloc[-1]
    is_positive = current_idx_val > last_sma50
    status_color = "green" if is_positive else "red"
    status_text = "POZİTİF" if is_positive else "NEGATİF"
    
    st.sidebar.metric("BIST 100 Durumu", f"{current_idx_val:.2f}", delta=f"{current_idx_val - last_sma50:.2f} (vs SMA{index_sma_len})")
    st.sidebar.markdown(f"**Piyasa Genel Görünümü:** :{status_color}[{status_text}]")
else:
    st.sidebar.warning("BIST verisi alınamadı.")

# Tabs
tab1, tab2 = st.tabs(["🔍 Tarama (Scanner)", "🔙 Geçmiş Test (Backtest)"])

with tab1:
    # Run Scan Logic
    if st.button("Taramayı Başlat", key="btn_scan"):
        with st.spinner("Piyasa taranıyor... Veriler indiriliyor..."):
            # Update Strategy Params
            scanner.strategy_engine.ema_len = ema_len
            scanner.strategy_engine.wma_len = wma_len
            scanner.strategy_engine.index_sma_len = index_sma_len
            
            # Scan
            target_tickers = scanner.get_bist_tickers(index_option)
            results = scanner.scan_market(tickers=target_tickers, interval=selected_interval) 
            
            if not results.empty:
                st.session_state['scan_results'] = results
                st.success(f"{len(results)} hisse tarandı.")
            else:
                st.warning("Sonuç bulunamadı veya veri hatası.")

    # Display Results Logic
    if 'scan_results' in st.session_state:
        df = st.session_state['scan_results']
        
        # Quick Summary Metrics
        buy_signals = df[df['Buy Signal'] == True]
        st.metric("Al Sinyali Verenler", len(buy_signals))
        
        # Filter View
        show_only_buy = st.checkbox("Sadece AL Sinyallerini Göster", value=True)
        
        display_df = buy_signals if show_only_buy else df
        
        # Format for display
        # Rename columns for TR
        display_df_tr = display_df.rename(columns={
            "Ticker": "Hisse", "Price": "Fiyat", "Trend Up": "Trend Yukarı", 
            "Market Pos": "Piyasa Pozitif", "Buy Signal": "AL Sinyali", "Exit Signal": "Çıkış Sinyali"
        })
        
        st.dataframe(
            display_df_tr.style.background_gradient(subset=['Fiyat'], cmap="Blues")
            .background_gradient(subset=['RSI'], cmap="Reds", vmin=30, vmax=70)
            .format({"Fiyat": "{:.2f}", "RSI": "{:.2f}", "EMA9": "{:.2f}", "WMA30": "{:.2f}"}),
            use_container_width=True
        )
        
        # Detail View
        st.markdown("### 📊 Detaylı Analiz")
        selected_ticker = st.selectbox("İncelenecek Hisse Seçin:", display_df['Ticker'].unique())
        
        if selected_ticker:
            st.subheader(f"{selected_ticker} Teknik Görünüm")
            
            # Fetch data again for plotting full history
            dman = DataManager()
            stock_df = dman.fetch_ohlcv(selected_ticker, period="6mo")
            stock_df = scanner.strategy_engine.calculate_indicators(stock_df, index_data)
            
            # Create Plotly Chart
            fig = go.Figure()
            
            # Candlestick
            fig.add_trace(go.Candlestick(x=stock_df.index,
                            open=stock_df['open'], high=stock_df['high'],
                            low=stock_df['low'], close=stock_df['close'], name='Fiyat'))
            
            # Indicators
            fig.add_trace(go.Scatter(x=stock_df.index, y=stock_df['ema_9'], line=dict(color='blue', width=1), name=f'EMA {ema_len}'))
            fig.add_trace(go.Scatter(x=stock_df.index, y=stock_df['wma_30'], line=dict(color='red', width=2), name=f'WMA {wma_len}'))
            
            # Layout
            fig.update_layout(title=f"{selected_ticker} - EMA/WMA Stratejisi", xaxis_title="Tarih", yaxis_title="Fiyat", template="plotly_dark")
            
            st.plotly_chart(fig, use_container_width=True)
            
        # AI Assistant Section (Placeholder)
        with st.expander("🤖 Yapay Zeka Asistanı Görüşü"):
            # Safe logic for 'status condition' text
            is_buy = not buy_signals[buy_signals['Ticker'] == selected_ticker].empty if selected_ticker else False
            st.write(f"**{selected_ticker if selected_ticker else 'Seçili Hisse'}** için analiz: Stratejiye göre şu an {'AL konumunda' if is_buy else 'İzleme konumunda'}. Piyasa genel trendi {status_text}.")

with tab2:
    st.header("🔙 Geçmiş Performans Testi (Backtest)")
    st.info("Bu modül, stratejiyi geçmiş verilere (son 1 yıl) uygulayarak, 'Eğer bu stratejiyi uygulasaydım ne kazanırdım?' sorusuna cevap arar.")
    
    backtester = Backtester()
    
    col_bt1, col_bt2 = st.columns([1,3])
    with col_bt1:
        if st.button("🚀 Testi Başlat (Son 1 Yıl)", key="btn_backtest"):
            with col_bt2:
                with st.spinner("Zaman makinesi çalışıyor... ⏳ (BIST 100 testi 1-2 dk sürebilir)"):
                     # Get tickers based on selection in sidebar
                    bt_tickers = scanner.get_bist_tickers(index_option)
                    
                    bt_results = backtester.backtest_tickers(bt_tickers, period="1y", interval=selected_interval)
                    
                    if not bt_results.empty:
                        st.session_state['bt_results'] = bt_results
                        st.balloons()
                    else:
                        st.error("Test sonucu alınamadı.")

    if 'bt_results' in st.session_state:
        bt_results = st.session_state['bt_results']
        
        # Summary Metrics
        avg_win_rate = bt_results['Win Rate'].mean() * 100
        avg_return = bt_results['Total Return'].mean() * 100
        best_stock = bt_results.loc[bt_results['Total Return'].idxmax()]
        worst_stock = bt_results.loc[bt_results['Total Return'].idxmin()]

        st.markdown("### 🏆 Performans Özeti")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Ortalama Kazanma Oranı", f"%{avg_win_rate:.1f}")
        m2.metric("Ortalama Getiri", f"%{avg_return:.1f}")
        m3.metric("En İyi Hisse", f"{best_stock['Ticker']}", f"%{best_stock['Total Return']*100:.1f}")
        m4.metric("En Kötü Hisse", f"{worst_stock['Ticker']}", f"%{worst_stock['Total Return']*100:.1f}")
        
        st.subheader("Detaylı Sonuçlar (En İyiden Kötüye)")
        
        # Sort by Return
        bt_results_sorted = bt_results.sort_values(by="Total Return", ascending=False)
        
        # Format
        st.dataframe(
            bt_results_sorted[['Ticker', 'Total Trades', 'Win Rate', 'Total Return']]
            .style.format({'Win Rate': "{:.0%}", 'Total Return': "{:.1%}"})
            .background_gradient(subset=['Total Return'], cmap="RdYlGn"),
            use_container_width=True
        )

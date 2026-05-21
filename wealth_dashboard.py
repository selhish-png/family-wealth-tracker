import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import time
import google.generativeai as genai
import requests
import io
import datetime

st.set_page_config(page_title="私人財富指揮中心", layout="wide", initial_sidebar_state="expanded")

# --- UI 樣式設定 (保持 Fashion) ---
st.markdown("""
<style>
    .fashion-title {
        background: -webkit-linear-gradient(45deg, #2c3e50, #3498db);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 2.5rem;
        padding-bottom: 10px;
    }
    div[data-testid="metric-container"] {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(128, 128, 128, 0.2);
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border-radius: 15px;
        padding: 15px;
        backdrop-filter: blur(10px);
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="fashion-title">✨ 全自動資產追蹤 </div>', unsafe_allow_html=True)
# -----------------------------------------------------------------------------
# 1. 系統安全：密碼鎖機制
# -----------------------------------------------------------------------------
def check_password():
    """驗證使用者密碼是否正確"""
    def password_entered():
        # 核對輸入的密碼是否與 secrets 中的密碼相符
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # 驗證成功後清除輸入框內的密碼紀錄
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # 第一次進入，顯示密碼輸入框
        st.title("🔒 系統已鎖定")
        st.text_input("請輸入專屬密碼以解鎖系統：", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        # 密碼錯誤，顯示錯誤提示
        st.title("🔒 系統已鎖定")
        st.text_input("請輸入專屬密碼以解鎖系統：", type="password", on_change=password_entered, key="password")
        st.error("😕 密碼錯誤，請再試一次。")
        return False
    else:
        # 密碼正確，放行
        return True

# 如果密碼驗證未通過，就停止執行後續的所有程式碼
if not check_password():
    st.stop()

# ==========================================
# 1. 自動抓取匯率
# ==========================================
@st.cache_data(ttl=3600)
def fetch_stable_exchange_rates():
    rates = {"TWD": 1.0}
    try:
        usd_twd = yf.download("USDTWD=X", period="5d")['Close'].dropna().iloc[-1]
        rates["USD"] = float(usd_twd)

        jpy_twd = yf.download("JPYTWD=X", period="5d")['Close'].dropna().iloc[-1]
        rates["JPY"] = float(jpy_twd)
    except Exception:
        rates["USD"], rates["JPY"] = 32.5, 0.21
    return rates


LIVE_RATES = fetch_stable_exchange_rates()

with st.sidebar:
    st.header("💱 即時外匯基準")
    st.metric("USD / TWD", f"{LIVE_RATES['USD']:.2f}")
    st.metric("JPY / TWD", f"{LIVE_RATES['JPY']:.4f}")


# ==========================================
# 1.5 全球宏觀指標 (原油、黃金、BTC、VIX、恐懼貪婪)
# ==========================================
@st.cache_data(ttl=300)
def fetch_macro_indicators():
    macro_results = {}

    # 1. 使用 yfinance 抓取常規市場指標
    tickers = {
        "🛢️ WTI 原油 (USD)": "CL=F",
        "🪙 黃金期貨 (USD)": "GC=F",
        "₿ 比特幣 (USD)": "BTC-USD",
        "😨 VIX 恐慌指數": "^VIX"
    }

    for name, ticker in tickers.items():
        try:
            # 🌟 關鍵修正 1：改用 yf.Ticker().history，對單一標的抓取更穩定
            # 🌟 關鍵修正 2：period="5d" 確保跨週末也能抓到上週五的價格
            history_data = yf.Ticker(ticker).history(period="5d")

            if not history_data.empty:
                # dropna() 會把週末沒交易產生的 NaN 清掉，再拿最後一筆有效價格
                price = history_data['Close'].dropna().iloc[-1]
                macro_results[name] = float(price)
            else:
                macro_results[name] = 0.0

        except Exception as e:
            # st.sidebar.error(f"抓取 {name} 失敗: {e}") # Debug 時可解開這行
            macro_results[name] = 0.0

    # 2. 爬取 CNN 恐懼與貪婪指數 (Fear & Greed Index)
    try:
        # 偽裝成正常的瀏覽器連線
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        response = requests.get(url, headers=headers, timeout=5)

        if response.status_code == 200:
            data = response.json()
            score = round(data['fear_and_greed']['score'])
            rating = data['fear_and_greed']['rating'].lower()

            # 將英文情緒翻譯為專業中文
            rating_tw = rating.replace("extreme fear", "極度恐懼") \
                .replace("fear", "恐懼") \
                .replace("neutral", "中立") \
                .replace("extreme greed", "極度貪婪") \
                .replace("greed", "貪婪")

            macro_results["🧭 恐懼與貪婪指數"] = f"{score} ({rating_tw})"
        else:
            macro_results["🧭 恐懼與貪婪指數"] = "暫時無法取得"
    except Exception:
        macro_results["🧭 恐懼與貪婪指數"] = "連線逾時"

    return macro_results


# --- 側邊欄：顯示宏觀指標 UI ---
with st.sidebar:
    st.markdown("---")  # 畫一條分隔線
    st.header("🌍 全球宏觀與情緒指標")

    macro_data = fetch_macro_indicators()

    # 排版顯示
    st.metric("🛢️ WTI 原油 (桶)", f"${macro_data.get('🛢️ WTI 原油 (USD)', 0):.2f}")
    st.metric("🪙 黃金期貨 (盎司)", f"${macro_data.get('🪙 黃金期貨 (USD)', 0):,.2f}")
    st.metric("₿ 比特幣 (BTC)", f"${macro_data.get('₿ 比特幣 (USD)', 0):,.0f}")

    # 將情緒指標分兩欄並排顯示，節省垂直空間
    col_vix, col_fg = st.columns(2)
    col_vix.metric("😨 VIX", f"{macro_data.get('😨 VIX 恐慌指數', 0):.2f}")
    col_fg.metric("🧭 CNN 指數", str(macro_data.get('🧭 恐懼與貪婪指數', 'N/A')))

# ==========================================
# 2. 雲端讀取靜態資產 (直接抓取您的 Spreadsheet)
# ==========================================
@st.cache_data(ttl=600)
def fetch_static_assets_from_gsheet():
    sheet_url = st.secrets["SHEET"]
    try:
        df = pd.read_excel(sheet_url, sheet_name='工作表1')

        # 讀取現金總額 (保守抓取 F 欄)
        cash_total = df.iloc[1:10, 5].fillna(0).apply(pd.to_numeric, errors='coerce').sum()
        if cash_total == 0: cash_total = 999

        # 讀取黃金與基金 (C 欄與 F 欄)
        gold_value = df.iloc[48:50, 2].fillna(0).apply(pd.to_numeric, errors='coerce').sum()
        if gold_value == 0: gold_value = 999

        fund_value = df.iloc[48:50, 5].fillna(0).apply(pd.to_numeric, errors='coerce').sum()
        if fund_value == 0: fund_value = 999

        # 讀取負債 (J 欄與 K 欄)
        deposit = df.iloc[48:50, 9].fillna(0).apply(pd.to_numeric, errors='coerce').sum()
        loan = df.iloc[48:50, 10].fillna(0).apply(pd.to_numeric, errors='coerce').sum()
        total_debt = deposit + loan
        if total_debt == 0: total_debt = -999

        return {"銀行現金": cash_total, "黃金": gold_value, "基金": fund_value, "總負債": total_debt}
    except Exception as e:
        return {"銀行現金": 999, "黃金": 999, "基金": 999, "總負債": -999}


STATIC_ASSETS = fetch_static_assets_from_gsheet()


# ==========================================
# 3. 動態持股陣列 (🌟 修正語法，改為直接輸入「總成本 Total_Cost」)
# ==========================================


@st.cache_data(ttl=300)
def fetch_dynamic_stocks_from_gsheet():
    # 🌟 請家人將他們自己的 Google Sheets 網址 (發布為 xlsx 格式) 貼在這裡
    sheet_url = st.secrets["SHEET"]


    try:
        df_stocks = pd.read_excel(sheet_url, sheet_name='持股明細')

        # 移除任何欄位名稱的空白，確保讀取精準
        df_stocks.columns = df_stocks.columns.str.strip()

        # 直接轉換為字典陣列
        return df_stocks.to_dict(orient='records')

    except Exception as e:
        st.sidebar.error(f"⚠️ 無法讀取持股資料，請確認 Excel 分頁名稱為 '持股明細'。")
        # 逃生機制：回傳預設的台積電，讓網頁不會當機，也方便測試
        return [
            {"Sector": "系統測試", "Name": "載入失敗(預設顯示)", "Ticker": "2330.TW", "Shares": 1, "Currency": "TWD",
             "Total_Cost": 1000}]


DYNAMIC_STOCKS = fetch_dynamic_stocks_from_gsheet()
with st.sidebar:
    st.header("🏦 雲端同步狀態")
    st.success("Google Sheets 靜態資產同步完成")
    st.write(f"抓取現金總額: NT$ {STATIC_ASSETS['銀行現金']:,.0f}")


# ==========================================
# 4. 報酬率計算報價引擎 (🌟 欄位精準對位版)
# ==========================================
@st.cache_data(ttl=300)
def fetch_all_prices_with_roi(stocks, rates):
    data = []

    if not stocks:
        return pd.DataFrame()

    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, stock in enumerate(stocks):
        # 🌟 修正 1：將 'Name' 改為 Excel 裡的 '標的名稱'
        # 使用 .get() 可以多加一層防護，萬一欄位填錯也不會直接當機
        stock_name = stock.get('標的名稱', '未知標的')
        stock_ticker = stock.get('Ticker', '未知代號')

        status_text.text(f"🚀 正在連線交易所，抓取報價: {stock_name} ({stock_ticker})...")

        try:
            # 獨立抓取單一股票的歷史報價
            hist_data = yf.Ticker(stock_ticker).history(period="5d")

            if not hist_data.empty:
                # 取得最新一筆收盤價
                price = float(hist_data['Close'].dropna().iloc[-1])

                # 計算原幣
                original_cost = float(stock.get("Total_Cost", 0))
                original_value = price * float(stock.get("Shares", 0))
                original_pnl = original_value - original_cost

                # 計算台幣
                currency = stock.get("Currency", "TWD")
                twd_total_cost = original_cost * rates.get(currency, 1.0)
                twd_current_value = original_value * rates.get(currency, 1.0)
                unrealized_pnl = twd_current_value - twd_total_cost
                roi_percent = (original_pnl / original_cost) * 100 if original_cost > 0 else 0

                data.append({
                    "板塊分類": stock.get("板塊分類", "未分類"),  # 🌟 修正 2：改為 '板塊分類'
                    "標的名稱": stock_name,  # 🌟 修正 3：改為 '標的名稱'
                    "幣別": currency,
                    "投入成本(原幣)": round(original_cost, 2),
                    "即時市值(原幣)": round(original_value, 2),
                    "未實現損益(原幣)": round(original_pnl, 2),
                    "即時現價": round(price, 2),
                    "投入總成本(TWD)": round(twd_total_cost),
                    "即時總市值(TWD)": round(twd_current_value),
                    "未實現損益(TWD)": round(unrealized_pnl),
                    "報酬率(%)": round(roi_percent, 2)
                })
        except Exception as e:
            pass

        progress_bar.progress(int((i + 1) / len(stocks) * 100))

    time.sleep(0.5)
    status_text.empty()
    progress_bar.empty()

    return pd.DataFrame(data)
df_dynamic = fetch_all_prices_with_roi(DYNAMIC_STOCKS, LIVE_RATES)

# ==========================================
# 5. 繪製真實熱力圖與報酬率儀表板
# ==========================================
total_securities_value = df_dynamic['即時總市值(TWD)'].sum() if not df_dynamic.empty else 0
total_securities_cost = df_dynamic['投入總成本(TWD)'].sum() if not df_dynamic.empty else 0
total_pnl = total_securities_value - total_securities_cost
total_roi = (total_pnl / total_securities_cost) * 100 if total_securities_cost > 0 else 0

net_worth = total_securities_value + STATIC_ASSETS["銀行現金"] + STATIC_ASSETS["黃金"] + STATIC_ASSETS["基金"] + \
            STATIC_ASSETS["總負債"]

col1, col2, col3, col4 = st.columns(4)
col1.metric("💎 總即時淨資產", f"NT$ {net_worth:,.0f}")
col2.metric("📈 證券總市值", f"NT$ {total_securities_value:,.0f}")
col3.metric("🎯 證券總損益", f"NT$ {total_pnl:,.0f}", f"{total_roi:.2f}%")
col4.metric("🛡️ 儲備資產(現金/黃金)", f"NT$ {(STATIC_ASSETS['銀行現金'] + STATIC_ASSETS['黃金']):,.0f}")

st.markdown("<br>", unsafe_allow_html=True)
if not df_dynamic.empty:
    st.subheader("🗺️ 資產熱力圖 ")

    # 🌟 頂級戰術改裝：數學斷層色階法
    # 比例尺基準：range_color=[-40, 40]
    # 0.00 = -40%, 0.25 = -20%, 0.375 = -10%, 0.625 = +10%, 0.75 = +20%, 1.00 = +40%

    fig = px.treemap(
        df_dynamic,
        path=['板塊分類', '標的名稱'],
        values='即時總市值(TWD)',
        color='報酬率(%)',
        # 🌟 顏色調整：0% 變成深灰色 (更符合 Finviz 的暗黑風格)
        color_continuous_scale=[[0, '#ff4d4d'], [0.5, '#414554'], [1, '#2ecc71']],
        color_continuous_midpoint=0,
        range_color=[-40, 40],
        custom_data=['報酬率(%)', '未實現損益(TWD)', '即時總市值(TWD)']
    )

    # 🌟 修改 1：文字置中、自訂顯示格式與大小
    fig.update_traces(
        hovertemplate="<b>%{label}</b><br>市值: NT$ %{customdata[2]:,.0f}<br>損益: NT$ %{customdata[1]:,.0f}<br>報酬率: %{customdata[0]:.2f}%<extra></extra>",
        # 強制指定顯示內容：標的名稱 (換行) 報酬率%
        texttemplate="<b>%{label}</b><br>%{customdata[0]:.2f}%",
        # 設定字體大小為 16、白色，並且強制垂直與水平置中
        textfont=dict(size=16, color='white'),
        textposition="middle center",
        marker=dict(line=dict(color='#000000', width=1.5))  # 黑色細邊框切割區塊
    )

    # 🌟 修改 2：將背景改為深灰色，消除原本的淺色漸層
    fig.update_layout(
        margin=dict(t=30, l=0, r=0, b=0),  # 縮小邊距讓熱力圖更大
        paper_bgcolor="#1e1e1e",  # 整個圖表外框背景改為深灰
        plot_bgcolor="#1e1e1e",  # 圖表內部背景改為深灰
        height=850
    )
    st.plotly_chart(fig, use_container_width=True)

# ==========================================
# 6. AI 財富管家即時洞察 (Gemini API)
# ==========================================
st.markdown("---")
st.subheader("🤖 AI 財富分析師即時洞察")

# 檢查系統是否有設定 API Key
if "GEMINI_API_KEY" in st.secrets:
    try:
        # 設定金鑰與模型
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-2.5-flash')
        macro_info = fetch_macro_indicators()
        macro_summary = "\n".join([f"- {k}: {v}" for k, v in macro_info.items()])
        # 將現在的投資數據轉換為文字，餵給 AI
        portfolio_summary = df_dynamic[['板塊分類', '標的名稱', '即時總市值(TWD)', '報酬率(%)']].to_string(index=False)

        # 打造給 AI 的終極指令 (Prompt)
        prompt = f"""
        你是一位頂尖的華爾街「全天候資產配置大師」，語氣專業、銳利、客觀，且帶有精準的策略思維。
        
        現在全球的【市場宏觀情緒指標】如下：
        {macro_summary}
        
        以下是我目前的全球資產配置即時數據（單位為台幣）：
        總淨資產：{net_worth:,.0f} 元
        證券總損益：{total_pnl:,.0f} 元 (報酬率 {total_roi:.2f}%)

        各項資產明細：
        {portfolio_summary}

        請根據上述真實數據，為我寫一份 300 字以內的精簡「今日資產健檢與行動建議」。
        重點包含：
        1. 當周政治經濟局勢的全球經濟的影響。
        2. 點出跌幅最重（報酬率最低）的標的，並給予冷靜的應對建議（例如：耐心等候、考慮停損或逢低加碼）。
        3. 整體資金佈局的安全感評估。
        請結合當前的「市場宏觀情緒（例如 VIX 是否過高、CNN 指數是否處於極度恐懼或極度貪婪、黃金/原油暗示的通膨避險情緒）」以及我的「持倉賺賠現況」，為我寫一份 400 字以內的「全球宏觀策略健檢報告」。
        
        重點包含：
        1. 【市場局勢解讀】：用一句話點破當前全球市場的情緒狀態。
        2. 【持倉汰弱留強】：點出跌幅最重或面臨宏觀風險的標的，給予具體的應對戰術（加碼/停損/觀望）。
        3. 【風控與資金建議】：綜合當前 VIX 與 CNN 指數，告訴我現在應該「保留現金、防禦至上」，還是「勇敢分批逆向加碼」？
        4. 【全球重要金融大事】當周政治經濟局勢的全球經濟的影響。
        
        請用 Markdown 格式輸出，重點文字與標題可加粗，條理要清晰。        
        請用 Markdown 格式輸出，重點文字可加粗。
        """

        # 加入一個按鈕，讓你不必每次重整網頁都消耗 API，想看報告時再點擊

        if st.button("✨ 點此生成今日 AI 專屬財富報告"):
            with st.spinner("🧠 正在分析全球市場與您的持倉數據..."):
                try:
                    # 🥇 第一關：優先嘗試呼叫最強的 Pro 旗艦大腦
                    model = genai.GenerativeModel('gemini-2.5-pro')
                    response = model.generate_content(prompt)
                    used_model = "💎 Gemini 2.5 Pro "

                except Exception as e_pro:
                    # 🥈 第二關：如果 Pro 額度用盡或報錯，自動啟動 Fallback 切換至 Flash
                    try:
                        model = genai.GenerativeModel('gemini-2.5-flash')
                        response = model.generate_content(prompt)
                        used_model = "⚡ Gemini 2.5 Flash "
                        # 顯示小提示告知使用者發生了降級切換
                        st.info("💡 提示：Pro 旗艦版伺服器忙碌或額度暫滿，系統已自動無縫切換至 Flash 版完成本次分析。")

                    except Exception as e_flash:
                        # 💀 第三關：如果兩個大腦都連不上，才宣告真正的連線失敗
                        st.error(f"雙引擎連線皆發生異常，請確認網路或 API 狀態。")
                        st.stop()  # 終止程式避免後續報錯

                # 🌟 結果展示：明確標示出本次立功的是哪顆 AI 大腦
                st.success(f"分析完成！(本次運算核心：{used_model})")
                st.markdown(f"> {response.text}")

    except Exception as e:
        st.error(f"系統設定發生異常。錯誤訊息: {e}")

else:
    st.warning("尚未設定 GEMINI_API_KEY，請至 Streamlit Secrets 後台設定以啟用 AI 洞察功能。")

# ==========================================
# 7. 一鍵匯出 Excel (每月記帳專用版 - 頂級原幣會計格式)
# ==========================================
st.markdown("---")
st.subheader("📥 資料匯出中心")


@st.cache_data(show_spinner=False)
def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='每月資產記帳明細')
        worksheet = writer.sheets['每月資產記帳明細']

        # 讀取標題列，用來判斷每一欄該用什麼數字格式
        headers = [cell.value for cell in worksheet[1]]

        # 自動調整欄寬
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            worksheet.column_dimensions[column_letter].width = max(max_length + 2, 12)

        # 會計級數字格式處理 (原幣需要小數點來呈現美分的精準度)
        for row in worksheet.iter_rows(min_row=2, max_row=worksheet.max_row):
            for cell in row:
                if isinstance(cell.value, (int, float)):
                    header_name = headers[cell.column - 1]
                    if "報酬率" in header_name:
                        cell.number_format = '0.00'
                    elif "原幣" in header_name or "現價" in header_name:
                        cell.number_format = '#,##0.00'  # 加入小數點與千分位
                    else:
                        cell.number_format = '#,##0'

    return output.getvalue()


if not df_dynamic.empty:
    # 🌟 關鍵戰術：在這裡「過濾」欄位！把台幣相關的欄位全部剔除，只保留記帳需要的
    export_columns = [
        "板塊分類", "標的名稱", "幣別", "即時現價",
        "投入成本(原幣)", "即時市值(原幣)", "未實現損益(原幣)", "報酬率(%)"
    ]
    df_export = df_dynamic[export_columns]  # 只把乾淨的資料交給 Excel

    # 產生 Excel 檔案
    excel_data = convert_df_to_excel(df_export)
    today_str = datetime.datetime.now().strftime("%Y%m%d")
    export_filename = f"記帳明細{today_str}.xlsx"

    st.download_button(
        label="📊 點擊下載今日資產 Excel",
        data=excel_data,
        file_name=export_filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
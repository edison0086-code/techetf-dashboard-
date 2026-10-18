# 科技 ETF 進場監控儀表板

QQQM／SMH／00935 每日價格、近 52 週回撤、完整週線 J 值、CNN Fear & Greed 指數，以及 30／40／30 的進場條件檢查。

> 完整可執行的 Streamlit 網頁程式，資料來源為線上免費／非官方端點。**需有網路並執行 Python 伺服器才能更新**；直接雙擊 `app.py` 不是打開網頁。未部署前，沒有可供外網存取的永久網址。

## 方法 A：Windows 本機開啟（比較容易）

1. 安裝 [Python 3.11 或 3.12](https://www.python.org/downloads/)（安裝時勾選 **Add Python to PATH**）。
2. 將 ZIP 解壓縮後，雙擊 `啟動儀表板.bat`。首次啟動會下載 Streamlit、pandas、requests、plotly。
3. 瀏覽器打開 `http://localhost:8501`；若未自動打開請手動輸入。
4. 每天開啟網址或重新整理，即看到最新可得資料。網站為避免限流，快取最多 15 分鐘；按「強制重新抓取市場資料」會跳過快取。
5. 使用完關掉黑色命令視窗即可結束伺服器。下次要看請再次雙擊 `.bat`。

也能使用命令列：

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## 方法 B：部署成手機、電腦都能開的網址

1. 將這個資料夾的 `app.py`、`data_sources.py`、`strategy.py`、`requirements.txt`、`.streamlit/config.toml` 放入 GitHub repository（**不要**上傳 `my_trade_state.json`）。
2. 到 [Streamlit Community Cloud](https://share.streamlit.io/) 登入 GitHub → **Create app** → 選擇 repository、分支與入口 `app.py` → Deploy。
3. 它會建立一個 `https://你的名稱.streamlit.app` 網址。每天開啟即可檢視。
4. 個人買進紀錄檔在免費雲端可能因重建消失，建議自行留正式交易記錄；必要時改接永久資料庫。公開部署前注意是否設定隱私權限。

官方部署教學：https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy

## 已實作

- 兩套候選權重：QQQM／SMH／00935 = **50/25/25**（預設）或 **40/30/30**。
- CNN F&G 分數、前次讀數、資料日期與原始來源；CNN 暫時無法讀取時嘗試第三方備援，明確標示。
- 三檔 ETF 收盤價、交易日、近 52 週最高收盤價回撤（盡可能採用調整後收盤價）、已完成的 **週 K 線** J 值與上週 J 值。
- 第 1 批 **30%**：任一指定 ETF 自近 52 週最高收盤回檔 ≥10%，或 **CNN <25 且該 ETF 的完整週 J<25**。
- 個別標的觸發不等同整體組合必然觸發；儀表板特別標註 QQQM 的組合級基準與其他標的個別訊號。
- 第 2 批 **40%**：第一批買入後，QQQM 再跌至少 8%（此處採 8% 門檻），或 CNN<15 且 QQQM 週 J<15；必須已經過至少一個完整週線收盤。
- 第 3 批 **30%**：第一批買入後，QQQM 週 J **向上穿越** 20，或 CNN 讀數**由 ≤30 向上突破 30**；亦要經過至少一個完整週線收盤。
- 第 2／3 批需要在網頁上記錄實際第一批日期／QQQM 成交參考價，沒有填就不憑空發出買進訊號。
- 無股災、未提前買完的年度資金：**00935 9 月除息交易日，QQQM、SMH、00935 同一台灣日曆日買入**。日期以野村正式公告為準，需在側邊欄手動設定，無公告不臆測日期。
- 資料過期、無法取得、或市場休市均顯示日期與待確認，不用 0 或捏造數字替代。

## 仍需注意

1. 非即時報價：Yahoo Finance 的 Chart API 不是保證可用的正式行情服務；CNN 也不提供穩定、明確承諾的公開 API。網頁**無法保證永遠抓得到資料**，遇錯誤顯示待確認。更高可靠性需付費或官方授權資料 API。
2. J 值公式採 RSV 9 週、K/D 1/3 平滑、初值 50，不同券商週線與調整方式可能略有差異；不要拿日線 J 直接比較。
3. 認定第二批前需第一批實際買進資料。以 QQQM 為組合級進場基準是此版本的實作決策；如果你決定要「SMH／00935 任何一檔亮燈，整組就買」，應在使用前明確變更程式規則。
4. 在 2027 年正式開始投入前，2026 年先視為觀察期。
5. 只顯示條件，**不會替你下單**；也不會用歷史回測未驗證的參數聲稱有獲利保證。
6. `my_trade_state.json` 只存第一批的日期、QQQM 參考成交價及已執行批次等狀態，儲存在**本機程式目錄**；不要放上公開 GitHub。

## 驗證程式

```bash
python -m pip install pytest pandas
python -m pytest tests -q
```

# 科技 ETF 15 年進場監控 V3｜Massive + FinMind + TWSE + CNN

本程式可直接部署在 Streamlit Community Cloud。QQQM 和 SMH 使用 Massive 股票日終 Aggregate API，00935 使用 FinMind，失敗時再使用臺灣證交所月資料；不依賴 Yahoo 或 Tiingo。

## 部署方法

1. 將壓縮包內的 `app.py`、`strategy.py`、`data_sources.py`、`cnn_sources.py`、`requirements.txt`、`.streamlit/config.toml` 放在 GitHub 專案相同的資料夾層級；請一次替換舊版，避免 import/signature 不相容。
2. 在 Streamlit Cloud 對現有 App 開啟 **Settings → Secrets**，填入：

```toml
MASSIVE_API_KEY = "你已申請的 Massive API key"
FINMIND_TOKEN = ""
```

請勿在 GitHub 原始碼、截圖或對話中公開 API Key；也不要將實際 secrets.toml 上傳 GitHub。
3. 重新啟動／等待自動部署，按「強制更新日收盤行情」。App 網址保留不變。

## 指標與策略

- 最新可得的日終收盤價、日 J、本週未完成週 J 估算、已完成週 J、52 週最高收盤回檔。
- KDJ(9,3,3)，K/D 從 50 開始遞迴計算；與第三方指標可能略有不同。
- CNN 官方網頁未文件化端點自動讀取（可能失效），失敗可切換手動核對；過期不觸發訊號。
- 第一批 30%：單一 ETF 回檔至少 10%，或 CNN <25 與該 ETF 已完成週 J <25（候選訊號）。請勿把單一標的訊號直接視為整體三檔觸發。
- 第二批 40% 與第三批 30% 須輸入第一批實際買進日期及 QQQM 參考成交價；只顯示候選訊號，不下單。
- 比例：QQQM/SMH/00935 可選 50/25/25、40/30/30。年度未提前買入的餘額，00935 九月官方除息交易日三檔同日買進。

## 注意

Massive Basic 為個人用途，使用與展示權限依供應商授權；建議使用私人 Streamlit App。
免費 Stocks Basic 提供日終行情與兩年歷史、每分鐘 5 次 API 請求；首次上線需在你的 Streamlit 環境驗證 QQQM、SMH 的實際回傳。程式內不含任何真實金鑰。
FinMind / TWSE 或 CNN 有可能因限制、限流而顯示無資料；顯示原因但不推測數值。所有資訊非投資建議。

## 測試

`python -m pytest -q tests`

## V3.1 更新：本週暫估 J 與上週 J

- 網頁原本的「已完成週 J」改名「上週 J」（指最後一根已完成週 K）。
- 本週未出現新日 K 時，「本週暫估 J」顯示「尚無本週資料」，不沿用上週 J。
- 本週已有新日 K，才用最新日 K 計算暫估週 J；標出各欄所使用的日期。
- 正式 30／40／30 進場判定仍以已完成週 J 為準，不使用本週暫估值。
- 週線預設以星期五為結束日。遇交易所特殊假期而提前結束的週，需人工核對交易所日曆；也需留意行情商資料更新延遲。
- 安裝方式：將 ZIP 內相同資料夾中的 `app.py`、`strategy.py`、`data_sources.py`、`cnn_sources.py`、`requirements.txt` 全部一併更新，不能混用其他版本；Secrets 不要放入 GitHub。

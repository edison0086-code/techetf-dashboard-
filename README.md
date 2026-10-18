# 科技 ETF 監控網頁 v2（Tiingo／FinMind／TWSE）

用於 QQQM 50%、SMH 25%、00935 25% 的 15 年買進策略；亦可切換 40/30/30。不自動下單。

## 1. 不需重新建立網站，更新現有 GitHub

GitHub `edison0086-code/techetf-dashboard-` 專案：將本 ZIP 內的 `app.py`、`data_sources.py`、`strategy.py`、`requirements.txt`、`README.md`、`.streamlit/config.toml` 上傳或取代原有同名檔案。**不要把 ZIP 整包放上去**。檔案應位於根目錄，只有 `config.toml` 放在 `.streamlit/` 資料夾。

## 2. 取得 API Key

* Tiingo https://www.tiingo.com/ 註冊、查找 API Token。需要給 QQQM、SMH 使用。請確認個人用途及展示授權。
* FinMind https://finmind.github.io/ 的 `TaiwanStockPrice` 可嘗試不填 token；若有 Token，可提高額度。
* TWSE 公開日交易資料作 00935 的備援，無金鑰，但需要多個按月 API 請求，備援使用時可能較慢且被限流。

## 3. 設定 Streamlit Secrets（不可放 GitHub）

在 https://share.streamlit.io/ 進入 App → Settings → Secrets，貼入：

```toml
TIINGO_TOKEN = "你的Tiingo金鑰"
FINMIND_TOKEN = ""
```

取得 FinMind Token 時才填第二項。儲存後重新啟動網站。注意：**不要上傳 `.streamlit/secrets.toml`** 到 GitHub，亦不要公開貼出 token。

## 4. 公開／私人權限

建議 Streamlit App 設為私人，GitHub Repo 也設為私人。私人不代表免除行情商條款；Tiingo 的個人方案與資料展示規範須自行確認。確保 Streamlit 仍有讀取私人 GitHub repo 的權限。

## 5. 指標和更新

- 股價：各資料來源回傳的最近完整日 K 收盤價，**非盤中價**。Tiingo EOD 更新常晚於交易所收盤，應看「行情日期」。
- 日 J：最新日 K 對 KDJ(9,3,3) 的計算。
- 估算週 J：包含本週最新日 K 的尚未結束週線。
- 已完成週 J：按交換市場週收盤時間判斷，正式訊號只用已完成週線。J = 3K − 2D，K、D 初值 50，RSV 以 9 根 K 棒計算。不同平台的初始化和還原方式可能不同。
- 52 週回檔：原始收盤價（不計配息與拆分還原），**ETF 除息本身可能造成技術性下跌**，重大除息與拆分需手動核實。這不是總報酬回撤。
- CNN 指數：此版採**人工查核並輸入**，避免不穩定的非官方 API 假訊號。未輸入時，情緒複合條件待確認，但價格條件可獨立檢查。
- 資料快取 1 小時，側欄可強制更新。週末或不同市場假期會出現較舊的最近收盤價，超過期限時不作正式觸發。

## 6. 重要限制

本 App 不儲存交易紀錄；重新整理需再次輸入，這避免私人紀錄儲存在不持久的 Streamlit 雲端檔案中。第二、第三批判斷依實際第一批日期和成交參考價，並需要人工核對執行狀態。不提供自動推播或券商下單。

## 7. 如果顯示「待確認」

- QQQM/SMH 沒有數字：確認 `TIINGO_TOKEN`、Tiingo 使用權限與 Cloud 日誌。
- 00935 沒有數字：FinMind 限流或未涵蓋；TWSE 後備資料請求可能過多，查看錯誤文字。
- CNN 待確認：需手動核對並輸入 CNN 數字。
- 第二批／第三批待確認：尚未記錄實際第一批成交狀態。

公開端點、供應商定價與授權可能改變；本版本在本地做靜態及模擬資料測試，**尚未用你的 Tiingo Token 在 Streamlit 雲端端到端驗證**。

## v2.1 新增：CNN 網頁數據自動抓取

- 預設「自動（優先）」：嘗試讀取 CNN 網頁背後使用的 `production.dataviz.cnn.io` JSON 端點，取出 score、rating、timestamp、previous_close；快取 30 分鐘。**這不是 CNN 授權保證可用的公開 API，可能遭封鎖、限流或結構更改。** 如相關使用條款禁止此用途，請停止使用自動模式。
- 自動讀取失敗時不會填假資料，也不會錯把未取得數據當「未符合」；請在側欄改選「手動核對」，並依據 https://edition.cnn.com/markets/fear-and-greed 的數值輸入。
- 資料時間超過 5 曆日視為過期，不能觸發 CNN 相關訊號；個別 ETF 價格回檔訊號依然分開判斷。
- 網站仍須自行將實際執行批次、成交日期記錄在外部，不會永久保存個人交易紀錄。

**更新原有 v2**：替換 `app.py`、`README.md`，新增 `cnn_sources.py`；其他程式可保留原樣。整包替換亦可。已進行模擬測試；尚未在使用者的 Streamlit 主機驗證 CNN 端點連線及商業授權。

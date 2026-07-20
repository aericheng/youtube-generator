# YouTube API 全自動上傳：你要做的 4 個步驟

> 程式端已全部就緒（`pipeline/yt_auth.py`、`pipeline/upload_queue.py`，排程已整合）。
> 以下步驟涉及你的 Google 帳號，必須本人操作，約 15 分鐘。做完回報即可。

## 步驟 1：建 Google Cloud 專案＋啟用 API（約 5 分鐘）

1. 開 https://console.cloud.google.com/ → 登入你要經營頻道的那個 Google 帳號。
2. 上方專案選單 →「新增專案」→ 名稱隨意（例：`yt-shorts-uploader`）→ 建立。
3. 開 https://console.cloud.google.com/apis/library/youtube.googleapis.com → 確認左上角是剛建的專案 → 點「啟用」。

## 步驟 2：OAuth 同意畫面（約 3 分鐘）

1. 開 https://console.cloud.google.com/apis/credentials/consent
2. User Type 選 **External** → 建立。
3. App 名稱隨意、支援 email 填自己 → 完成必填欄位（其餘留空）→ 儲存。
4. **重要**：回到同意畫面總覽，把發布狀態從「Testing」改為 **「In production」**（按 Publish app）。
   - 原因：Testing 狀態的授權 token 有效期極短（約 7 天），全自動排程會一直斷線。
   - 發布後會顯示「未經驗證」——沒關係，只有你自己授權自己用，警告畫面點「進階」→「前往（不安全）」即可。

## 步驟 3：建 OAuth 憑證並下載（約 2 分鐘）

1. 開 https://console.cloud.google.com/apis/credentials
2. 「建立憑證」→「OAuth 用戶端 ID」→ 應用程式類型選 **「電腦版應用程式」** → 建立。
3. 點下載 JSON，把檔案存到（檔名要改成 client_secret.json）：
   `C:\Users\user\Desktop\dev\youtube generator\secrets\client_secret.json`

## 步驟 4：跑一次授權（約 1 分鐘）

在這個對話輸入：

```
! cd "C:\Users\user\Desktop\dev\youtube generator" && .venv/Scripts/python.exe pipeline/yt_auth.py
```

瀏覽器會跳出 Google 授權頁 → 選你的頻道帳號 → 未驗證警告點「進階」→「前往」→ 勾選允許上傳權限 → 完成。看到 `OK: token saved` 就成功了。

---

## 之後會發生什麼（我的部分）

- 我先用一支測試影片驗證 API 上傳全流程（**不會動 queue 裡的正式成品**——未過審前 API 上傳的影片會被永久鎖 private，正式影片要等過審後才走 API）。
- 帶你送「YouTube API compliance audit」表單（過審後 API 上傳才能公開；等待期數週）。
- 過審前的過渡期：排程照常每天產片進 queue，你手動上傳（每支 2 分鐘）；過審後把 `upload_privacy` 切成 `public`，全線無人化。

## 送審表單（步驟 4 之後一起做）

表單：https://support.google.com/youtube/contact/yt_api_form
要點：用途填「上傳自有頻道原創的 AI 輔助製作氛圍影片，工具僅本人使用，不涉及第三方資料存取」。細節到時我幫你擬。

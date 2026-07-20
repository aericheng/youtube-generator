# 執行手冊：YouTube API 全自動上傳的雲端設定（給 Claude agent）

> **讀者**：具備瀏覽器操作能力的 Claude agent（Claude Cowork、Claude in Chrome 等）。
> **委託人**：本機使用者（頻道擁有者本人）。
> **目標**：完成 Google Cloud 專案設定 → 取得 OAuth 憑證 → 完成一次性授權 → 填妥 YouTube API 合規審核（audit）表單待使用者確認送出。
> **語言**：與使用者互動一律繁體中文。

---

## 0. 背景（先讀完再動手）

使用者有一套本機全自動 YouTube Shorts 產製系統（專案路徑：`C:\Users\user\Desktop\dev\youtube generator`），影片已在每日排程產出。缺最後一環：**YouTube Data API 的上傳授權**。程式端（`pipeline/yt_auth.py`、`pipeline/upload_queue.py`）已寫好並測試過，只差 Google Cloud 端的人工設定，即本手冊的任務。

**關鍵背景知識**（決定了本手冊的安全規則）：
- 未通過 YouTube compliance audit 的 API 專案，上傳的影片會被**永久鎖成 private 且不可申訴**。因此在過審之前，絕不可用 API 上傳 `output/queue/` 裡的任何正式影片。
- OAuth 同意畫面若停留在「Testing」狀態，refresh token 約 7 天過期，全自動排程會斷線。所以任務 2 必須把應用程式**發布為 In production**。

## 1. 硬性規則（違反任何一條即停止並回報）

1. **帳號憑證絕不經手**：遇到 Google 登入頁、密碼輸入、兩步驟驗證（2FA）、手機確認——立即暫停，把控制權交還使用者，等使用者完成登入後再繼續。絕不代輸入密碼。
2. **送出前必須人工確認**：任務 6 的 audit 表單填妥後**不可自行按送出**——截圖或列出全部填寫內容給使用者過目，取得明確同意後才送出（或請使用者自己按）。
3. **絕不用 API 上傳正式影片**：`output/queue/` 內的 mp4 一律不碰。驗證上傳流程只能用 `--dry-run`。
4. **機密檔案不外流**：`secrets/client_secret.json` 與 `secrets/token.json` 的內容絕不貼進對話、log 或任何外部服務。
5. **不修改專案程式**：`pipeline/` 下的檔案是已驗收的生產程式，本手冊的任務不需要動它們。
6. 每完成一個任務，向使用者回報一行結果再進下一個。

## 2. 前提檢查（開始前確認）

- [ ] Chrome 已登入**要經營 YouTube 頻道的那個 Google 帳號**（問使用者確認是哪個帳號）。
- [ ] 能存取本機路徑 `C:\Users\user\Desktop\dev\youtube generator\secrets\`（資料夾已存在）。若你在雲端 VM 無法寫入本機檔案，改為：完成瀏覽器端任務，檔案下載類步驟指導使用者手動放置，並驗證他放對了。
- [ ] 若你能執行本機指令：確認 `C:\Users\user\Desktop\dev\youtube generator\.venv\Scripts\python.exe` 存在。不能執行也沒關係，任務 4 改請使用者跑一條指令。

## 3. 任務清單

### 任務 1：建立 Google Cloud 專案＋啟用 API

1. 開 https://console.cloud.google.com/projectcreate
2. 專案名稱：`yt-shorts-uploader`（如被占用，加數字後綴）。位置維持「無機構」。按「建立」。
3. 等待專案建立完成，確認頁面右上通知或專案選單已切到新專案。
4. 開 https://console.cloud.google.com/apis/library/youtube.googleapis.com （確認左上角專案選單顯示的是剛建立的專案）→ 按「啟用」（Enable）。
5. **驗證**：啟用後頁面會跳轉到該 API 的總覽頁，顯示「API 已啟用」或「管理」按鈕。
6. **記下**：專案 ID（project ID）與專案編號（project number）——任務 6 表單會用到。可在 https://console.cloud.google.com/home/dashboard 查看。

### 任務 2：OAuth 同意畫面（含發布到 production）

1. 開 https://console.cloud.google.com/apis/credentials/consent
2. User Type 選 **External**（外部）→ 建立。
3. 必填欄位：App 名稱填 `yt-shorts-uploader`；使用者支援電子郵件選使用者的 email；開發人員聯絡資訊填同一 email。其餘留空，逐頁「儲存並繼續」到完成。
4. Scopes（範圍）頁可直接跳過（程式會在授權時動態請求 `youtube.upload`）。
5. 回到同意畫面總覽（OAuth consent screen），找到發布狀態（Publishing status），按 **「發布應用程式」（Publish app）** 把狀態從 Testing 改為 **In production**。確認對話框直接確認（不需要提交驗證審查——「未經驗證」狀態可接受，因為只有使用者本人授權使用）。
6. **驗證**：總覽頁 Publishing status 顯示「In production」。

### 任務 3：建立 OAuth 用戶端憑證＋下載

1. 開 https://console.cloud.google.com/apis/credentials
2. 「建立憑證」（Create credentials）→「OAuth 用戶端 ID」（OAuth client ID）。
3. 應用程式類型選 **「電腦版應用程式」（Desktop app）**，名稱 `uploader-desktop` → 建立。
4. 建立完成的彈窗按「下載 JSON」。
5. 把下載的檔案改名為 `client_secret.json`，放到：
   `C:\Users\user\Desktop\dev\youtube generator\secrets\client_secret.json`
   （若你無法操作本機檔案：請使用者從瀏覽器下載列把檔案移過去，給他完整目標路徑。）
6. **驗證**：該路徑檔案存在，且 JSON 內容含 `"installed"` 這個 key（用讀檔工具驗，不要把內容貼出來）。若你無法讀本機檔案：請使用者自己用記事本開啟該檔，確認開頭是 `{"installed":` 後告訴你即可。

### 任務 4：一次性 OAuth 授權

1. 執行（若你有本機終端機能力，否則請使用者在他的終端機貼上執行；指令是免 cd 的單一指令。**cmd 可直接貼上；PowerShell 必須照下方指引在行首加 `&`**）：
   ```
   "C:\Users\user\Desktop\dev\youtube generator\.venv\Scripts\python.exe" "C:\Users\user\Desktop\dev\youtube generator\pipeline\yt_auth.py"
   ```
   （PowerShell 貼上時若整行以引號開頭會被當字串，前面加 `&` 一個字元即可：`& "C:\...python.exe" "..."`。）
2. 指令會自動開瀏覽器到 Google 授權頁。流程：
   - 選擇帳號 → **交還使用者選擇/登入**（規則 1）。
   - 出現「Google 尚未驗證這個應用程式」警告 → 點「進階」（Advanced）→「前往 yt-shorts-uploader（不安全）」。
   - 權限頁勾選/同意「管理您的 YouTube 影片」上傳權限 → 繼續。
3. **驗證**：終端機輸出 `OK: token saved to secrets/token.json`，且該檔案存在。
4. 最終驗證（不會真的上傳）：
   ```
   "C:\Users\user\Desktop\dev\youtube generator\.venv\Scripts\python.exe" "C:\Users\user\Desktop\dev\youtube generator\pipeline\upload_queue.py" --dry-run
   ```
   預期輸出：`would upload [private]: ...` 開頭的待傳清單。

### 任務 5：（可選，建議做）API 煙霧測試

用一支**拋棄式測試影片**（絕不是 queue 裡的正式成品）驗證 API 上傳鏈路通暢。專用腳本已備好：
1. 產生 10 秒黑畫面測試片：
   ```
   ffmpeg -y -f lavfi -i color=c=black:s=1080x1920:d=10 -f lavfi -i anullsrc=r=48000:cl=stereo -t 10 -c:v libx264 -pix_fmt yuv420p -c:a aac "C:\Users\user\Desktop\dev\youtube generator\secrets\apitest.mp4"
   ```
2. 執行專用煙霧測試腳本（它拒收路徑含 queue 的檔案，防呆已內建；免 cd 單一指令）：
   ```
   "C:\Users\user\Desktop\dev\youtube generator\.venv\Scripts\python.exe" "C:\Users\user\Desktop\dev\youtube generator\pipeline\yt_smoketest.py" "C:\Users\user\Desktop\dev\youtube generator\secrets\apitest.mp4"
   ```
3. 成功輸出 `OK videoId=...`。回報 videoId 給使用者，提醒他日後可在 Studio 刪除這支測試片。此影片會被鎖 private——正常且無所謂，它就是消耗品。

**注意**：正式的 queue 自動上傳有安全閘——`upload_privacy` 不是 `"public"` 時 `upload_queue.py` 會直接拒絕動 queue 影片（防止過審前把正式影片鎖死）。這是設計，不是 bug，不要試圖繞過。

### 任務 6：填寫 audit 表單（填妥→停→等使用者確認）

1. 開 https://support.google.com/youtube/contact/yt_api_form
2. 逐欄填寫。以下是預擬草稿（可依表單實際欄位調整措辭，維持相同事實）：
   - **API Client 用途說明**（英文）：
     > This is a single-user desktop tool (Python script using the OAuth installed-app flow) operated exclusively by me, the owner of the YouTube channel it uploads to. Its sole function is to upload my own original relaxation/ambience videos (about one 60-90 second video per day) to my own channel. The visuals and audio are original content produced by my local creation pipeline, and every upload sets the containsSyntheticMedia disclosure flag. The tool uses only the youtube.upload scope. It does not access, collect, or store any third-party or viewer data; no user other than myself can access it. It does not scrape YouTube data and does not download any YouTube content. Expected API usage is well within default quota (about 1-2 videos/insert calls per day).
   - **要求的配額**：不需要增加（default quota is sufficient）。表單若問每日用量，**照實描述而不要自己換算 units**：每日 1-2 次 `videos.insert` 呼叫（約 1-2 支影片）。units 的官方計價曾多次改版，寫呼叫次數最不會出錯。
   - 專案 ID / 專案編號：用任務 1 記下的值。
   - 聯絡 email：使用者的 email。
3. **全部填好後停止**（規則 2）：把每個欄位的填寫內容完整列給使用者過目，等他說「送出」才送（或讓他自己按）。
4. 送出後回報：確認頁面截圖或確認訊息文字。

## 4. 完成回報格式

全部任務結束後，用下列格式回報：

```
任務 1 Cloud 專案：完成（專案 ID: xxx）/ 失敗（原因）
任務 2 同意畫面：完成（已 In production）/ ...
任務 3 憑證：完成（client_secret.json 已就位）/ ...
任務 4 授權：完成（token.json 已存在，dry-run 通過）/ ...
任務 5 煙霧測試：完成（videoId: xxx）/ 跳過
任務 6 audit 表單：已送出（日期）/ 已填妥待使用者確認
```

## 5. 常見狀況處理

| 狀況 | 處理 |
|------|------|
| Google 要求登入或 2FA | 規則 1：暫停交還使用者，完成後續跑 |
| 找不到「發布應用程式」按鈕 | Google Console 改版常見。到 OAuth consent screen 總覽找 Publishing status 區塊；新版介面可能在「目標對象」（Audience）分頁 |
| 下載的 JSON 檔名是 client_secret_xxxx.json | 改名成 client_secret.json 再放入 secrets/ |
| yt_auth.py 報 missing client_secret.json | 檔案沒放對路徑，重做任務 3 第 5 步 |
| 授權頁沒有出現「進階」連結 | 應用程式可能還在 Testing 狀態（任務 2 第 5 步沒完成），或使用者被加為測試使用者。回去確認 In production |
| audit 表單欄位與本手冊描述不符 | 表單會改版。維持草稿的事實內容，對應到最接近的欄位；不確定的欄位列出來問使用者 |
| 表單要求提供 demo 影片或截圖 | 請使用者提供（或協助錄一段 upload_queue.py --dry-run 的畫面）；不要憑空捏造 |

## 6. 你完成後，本機系統會接手的事（背景資訊，不用執行）

- 排程 `LofiShortsDaily` 每日 03:30 產片＋呼叫 `upload_queue.py --max 1`（token 就位後自動生效，過審前維持 private 模式所以不會動正式影片——`upload_privacy` 設定在 `pipeline/pool/config.json`）。
- audit 過審通知送達後，使用者把 `upload_privacy` 改為 `"public"`，全線無人化完成。

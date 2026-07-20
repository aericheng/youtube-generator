# YouTube Shorts 自動化製作技術路線調查（2026-07-11）

> 調查目的：為自動化短影音系統選擇製作管線。目標規格：直式 1080x1920、15-60 秒。
> 使用者環境：Windows 11，本機已有 ffmpeg、yt-dlp、Python 3.x、Node.js。
> 查證方法：所有價格與可用性以官方頁面（WebFetch/WebSearch）為準，每項附來源 URL 與查證日期；查不到的標「未查證」。本報告不含法律建議。

---

## 總覽表

| 路線 | 30 秒單支成本 | 品質上限 | 自動化可行度 |
|------|--------------|----------|--------------|
| 1. 素材拼接型（免費圖庫＋edge-tts＋ffmpeg） | ~$0.00 | 中：素材與旁白語意匹配是瓶頸 | 半自動（合成全自動，素材選擇建議人工複核） |
| 2. AI 圖生影片型（AI 圖＋Ken Burns＋TTS） | API 生圖 $0.2-0.4；本機 SD $0 | 中高：畫面精緻但只有鏡頭運動 | 全自動 |
| 3. AI 文生影片型（Veo/Sora/Runway/Kling/Pika） | $1.2（最便宜 720p）～ $45（4K 最貴）；主流高品質 $12-21 | 高：真動態畫面＋原生音訊 | 全自動（Veo/Sora 官方 API；Kling/Runway 存取待確認） |
| 4. 字幕：TTS 時間戳 或 whisper 本機 | $0 | — | 全自動 |
| 5. 組裝：ffmpeg / moviepy / Remotion | ffmpeg 與 moviepy $0；Remotion 商用可能觸發授權費 | — | 全自動 |
| 6. 風格分析（yt-dlp＋LLM） | 近 $0（LLM 分析費用另計） | — | 全自動（有 ToS 注意事項） |

---

## 路線 1：素材拼接型（免費圖庫/影片庫 API ＋ TTS 旁白 ＋ ffmpeg 合成字幕）

### 免費素材庫 API

**Pexels API**（圖片＋影片皆有）
- 免費額度：200 requests/hour、20,000 requests/month；符合使用條款可申請提高至無上限。
- 授權：允許商業使用、允許用於 YouTube 影片；不強制掛名（"Attribution is not required"），但 API 使用要求在頁面層級顯示 Pexels 連結。
- 有獨立影片庫端點：`GET /v1/videos/search`、`/v1/videos/popular`。
- 來源：https://www.pexels.com/api/documentation/ 、https://www.pexels.com/license/ （查證日期 2026-07-11）

**Pixabay API**（圖片＋影片皆有）
- 免費額度：約 100 requests/60 秒（≈6,000/hour；另有來源稱 5,000/hour）。**注意：Pixabay 官方 `/api/docs/` 頁 WebFetch 被 403 擋下，此數字來自 WebSearch 摘要，標記「未完全查證」，建議實作前用 API key 實測 response headers 確認實際額度。**
- 授權（Pixabay Content License）：允許商用、免付費、免強制掛名；但不可將素材未經加工轉售或另建圖庫平台。來源：https://pixabay.com/service/license-summary/ （WebSearch 摘要，2026-07-11；官方頁 fetch 被擋）
- 有獨立影片 API：`https://pixabay.com/api/videos/`。來源：https://pixabay.com/blog/posts/search-for-videos-with-our-updated-api-76/ （查證日期 2026-07-11）

**Unsplash API**（只有圖片，**沒有影片庫**）
- 免費額度：Demo 狀態 50 requests/hour；申請 Production 後 1,000 requests/hour（免費，需簡單審核），無月上限。
- 授權：允許商用，不強制掛名但建議標註攝影師。
- 來源：https://unsplash.com/documentation 、https://unsplash.com/license （查證日期 2026-07-11）

### TTS 選項比較

**edge-tts（rany2/edge-tts，非官方開源專案）**
- 完全免費、GPL-3.0 授權，呼叫 Microsoft Edge 瀏覽器背後的線上 Neural TTS，不需 API key。
- **支援繁體中文（zh-TW），確認 3 個語音**：`zh-TW-HsiaoChenNeural`（女）、`zh-TW-HsiaoYuNeural`（女）、`zh-TW-YunJheNeural`（男）。（來源為兩份社群 voice list 交叉比對一致，非 Microsoft 官方頁：https://gist.github.com/BettyJJ/17cbaa1de96235a7f5773b8690a20462 、https://github.com/bytectlgo/edge-tts/blob/main/voice-list.md ，查證日期 2026-07-11）
- 維護狀態：最新版 7.2.8，發布於 2026-03-22（PyPI 官方頁確認），2026 年仍在維護。來源：https://pypi.org/project/edge-tts/ 、https://github.com/rany2/edge-tts （查證日期 2026-07-11）
- **風險**：這是逆向工程 Microsoft 未公開 API 的專案，端點隨時可能變動導致管線中斷（歷史上發生過多次，repo 有修復紀錄）。長期自動化需監控與備援（例如失敗時 fallback 到 OpenAI TTS）。

**OpenAI TTS API**（官方定價，developers.openai.com）
- tts-1：$15.00 / 1M characters
- tts-1-hd：$30.00 / 1M characters
- gpt-4o-mini-tts：文字輸入 $0.60/1M tokens、音訊輸出 $12.00/1M tokens（token 計價，較新型號）
- 來源：https://developers.openai.com/api/docs/models/tts-1 、https://developers.openai.com/api/docs/models/tts-1-hd 、https://developers.openai.com/api/docs/models/gpt-4o-mini-tts （查證日期 2026-07-11）
- 30 秒中文旁白約 100-150 字元，tts-1 成本約 $0.002-0.005，近乎可忽略。

**ElevenLabs**（官方 pricing 頁）
- Free：$0/月 10,000 credits；Starter $6/月 30k；Creator $22/月 121k；Pro $99/月 600k；Scale $299/月 1.8M；Business $990/月 6M credits。多數模型 1 字元 ≈ 1 credit（部分 Flash/Turbo 模型 0.5 credit/字元）。官方頁未列明確超額逐字元價格（未查證）。
- 中文支援：Multilingual v2 支援 29 語言含 Mandarin；Eleven v3 支援 70+ 語言含 Mandarin（cmn）。**此語言資訊來自 ElevenLabs 輔助頁面（help.elevenlabs.io），非 pricing 官方頁直接驗證。**
- 來源：https://elevenlabs.io/pricing （查證日期 2026-07-11）

### 路線 1 結論
- **(a) 30 秒單支成本**：≈ **$0.00**（edge-tts 免費＋圖庫免費額度內＋本機 ffmpeg；改用 OpenAI tts-1 也僅約 $0.005/支）。
- **(b) 品質評語**：edge-tts 音質為 Microsoft Neural TTS 等級（優於傳統合成，遜於 ElevenLabs 的情感表現）；最大瓶頸是免費圖庫素材與旁白內容的語意匹配——純自動關鍵字檢索容易出現「畫面與旁白對不上」。
- **(c) 自動化可行度**：**半自動**。TTS 與 ffmpeg 合成可全自動；素材檢索與畫面-文案匹配要達到可上架水準，通常需人工審核或人工設定關鍵字映射規則。另 edge-tts 有端點失效風險，需備援。

---

## 路線 2：AI 圖生影片型（AI 靜態圖 ＋ Ken Burns 動態 ＋ TTS）

### 圖片生成 API 價格

**OpenAI（gpt-image 系列）**
- 產品線現況：`gpt-image-1`（2025-04，將於 2026-10-23 淘汰）、`gpt-image-1.5`（2025-12，目前 API 預設主推）、`gpt-image-2`（2026-04 發布的旗艦）。來源：https://developers.openai.com/api/docs/models/gpt-image-2 （查證日期 2026-07-11）
- `gpt-image-1.5` 每張圖官方定價（1024×1024）：低品質 $0.009、中品質 $0.034、高品質 $0.133；1024×1536／1536×1024 略貴（低 $0.013、中 $0.050、高 $0.200）——直式 Shorts 用 1024×1536 較合適。來源：https://developers.openai.com/api/docs/guides/image-generation （官方 per-image 表，查證日期 2026-07-11）
- `gpt-image-2` 官方 pricing 頁只列 token 制費率（標準 input $8 / output $30 每百萬 tokens），**官方頁未直接列 per-image 美元數字**；第三方換算約 1024² 中品質 $0.053、高品質 $0.211（**非官方一手數字，標記為第三方估算**）。來源：https://developers.openai.com/api/docs/pricing （查證日期 2026-07-11）

**Google Gemini API（Imagen 系列與替代方案）**
- Imagen 4 三檔位：Fast $0.02/張、Standard $0.04/張、Ultra $0.06/張。
- **重要**：官方頁明確標註 Imagen 系列進入淘汰程序，**2026-08-17 關閉**（距查證日約 5 週），官方建議改用 Gemini 原生圖片生成（"Nano Banana" 家族）。**新管線不應選 Imagen。**
- 替代方案官方定價：`gemini-2.5-flash-image` 約 $0.039/張（1024²）；`gemini-3.1-flash-image` 約 $0.045-0.151/張（視解析度）；`gemini-3-pro-image` 約 $0.134/張（1K-2K）、$0.24/張（4K）。
- 來源：https://ai.google.dev/gemini-api/docs/pricing 、https://ai.google.dev/gemini-api/docs/imagen （查證日期 2026-07-11）

**Stable Diffusion 本機（免費，無 API 費）**
- 硬體門檻（社群共識彙整，非廠商官方保證值）：SD 1.5 最低 4GB VRAM；SDXL 至少 8GB、建議 12GB+；FLUX.1 量化版 6-8GB、全精度 12-16GB；ComfyUI 整體甜蜜點 16GB VRAM。
- 來源：https://www.synpixcloud.com/blog/stable-diffusion-gpu-requirements-guide 、https://comfylab.dev/blog/guides-pro/best-gpu-for-comfyui/ 、https://forums.developer.nvidia.com/t/recommended-hardware-for-running-comfyui-stable-diffusion-locally/367632 （查證日期 2026-07-11）
- 邊際成本趨近 $0，適合量產；代價是一次性硬體投資（若無 GPU 約 US$300-700）與環境維護（模型下載、ComfyUI/A1111 安裝、prompt 調校）。

### Ken Burns 效果
- ffmpeg 內建 `zoompan` filter 原生支援（官方 filter 文件明述其動機即 "Apply Ken Burns effect"），參數含 `z`（zoom）、`x`/`y`（平移）、`d`（持續影格）、`s`（輸出尺寸）、`fps`。完全免費、無需 API。
- 來源：https://ffmpeg.org/ffmpeg-filters.html#zoompan （官方文件，查證日期 2026-07-11）

### 成本估算（30 秒，每 3-5 秒換一張圖 → 6-10 張，中位 8 張）

| 服務/機型 | 品質 | 單價 | 6 張 | 10 張 |
|---|---|---|---|---|
| OpenAI gpt-image-1.5 | 低 | $0.009 | $0.05 | $0.09 |
| OpenAI gpt-image-1.5 | 中 | $0.034 | $0.20 | $0.34 |
| OpenAI gpt-image-1.5 | 高 | $0.133 | $0.80 | $1.33 |
| Google Imagen 4 Fast（8/17 停用） | — | $0.02 | $0.12 | $0.20 |
| Google gemini-2.5-flash-image（官方建議替代） | 1024² | $0.039 | $0.23 | $0.39 |

### 路線 2 結論
- **(a) 30 秒單支成本**：付費 API（中品質）約 **$0.2-0.4**；本機 Stable Diffusion **$0**（需 GPU ≥8GB VRAM）。
- **(b) 品質評語**：畫面精緻度高且可完全客製，但只有鏡頭模擬運動（縮放平移），敘事張力弱於真動態影片——適合知識型/敘事型內容，不適合強視覺衝擊的娛樂類。
- **(c) 自動化可行度**：**全自動**。腳本→TTS→生圖→zoompan→拼接整條可無人工介入，是六條路線中最容易端到端全自動化的一條。

---

## 路線 3：AI 文生影片型（text-to-video API）

### Google Veo（Gemini API / Vertex AI）
- 最新版本：**Veo 3.1**（Veo 3、Veo 2 已標 deprecated，2026-06-30 終止服務）。
- **有官方 API**（Gemini API 與 Vertex AI 均可程式呼叫）。
- 官方定價（Gemini Developer API）：
  - Veo 3.1 Standard：**$0.40/秒**（720p/1080p，含 audio）、$0.60/秒（4K）
  - Veo 3.1 Fast：$0.10/秒（720p）～ $0.30/秒（4K）
  - Veo 3.1 Lite：**$0.05/秒**（720p）、$0.08/秒（1080p）
- 來源：https://ai.google.dev/gemini-api/docs/pricing （查證日期 2026-07-11）
- 未完全查證：Vertex AI 專屬頁面未直接列 Veo 費率明細；二手來源稱 Veo 2 on Vertex AI 達 $0.50/秒，非官方一手確認。

### OpenAI Sora
- **有官方 API**（非僅 ChatGPT app 內功能）。
- 官方定價：sora-2 **$0.10/秒**（720p）；sora-2-pro $0.30/秒（720p）、$0.50/秒（1024p）、**$0.70/秒**（1080p）。Batch API 半價（sora-2 $0.05/秒）。
- 來源：https://developers.openai.com/api/docs/pricing （查證日期 2026-07-11）
- **未查證（二手來源，官方頁未見）**：「需先儲值 ≥US$10 才解鎖 Sora」「Sora 2 API 將於 2026-09-24 sunset」——後者若屬實對長期管線是重大風險，導入前務必向官方再確認。

### Runway
- 計費：credits 制，**$0.01/credit**。換算每秒：Gen-4 Turbo 5 credits/秒 = **$0.05/秒**（最便宜）；透過 Runway 呼叫 Veo 3.1 為 $0.20-0.40/秒；Seedance 2.0 $0.36-1.50/秒（480p-4K）。
- 來源：https://docs.dev.runwayml.com/guides/pricing/ （查證日期 2026-07-11）
- **API 存取層級有矛盾訊號（未完全查證）**：官方文件描述像自助式購買 credits，但有第三方報導稱 2026 年 1 月起 API 僅開放 Enterprise。正式導入前需向 Runway 確認，否則有淪為「需人工洽談合約」的風險。

### Kling AI（快手可靈）
- **官方頁面查證受阻**：kling.ai/dev/pricing 與 klingai.com/global/dev/pricing 均回傳 HTTP 446（疑似地區/反爬蟲阻擋），**費率未達官方一手查證標準**。
- 二手來源（宣稱引用官方 developer guide）：Prepaid API 方案 Trial $9.80/100 units 起；換算約 $0.084/秒（1080p 標準）至 $0.42/秒（4K）。API 與 web credits 是分開的計費系統。
- 判定：大概率有 REST API，但費率與存取門檻需人工二次查證（例如實際註冊 developer 帳號）才能定案。

### Pika
- **沒有第一方 API**。官方 https://pika.art/api 明確將程式化存取導向合作夥伴 **Fal.ai** 代管。
- 官方訂閱（網頁版）：Free $0、Standard $8/月、Pro $28/月、Fancy $76/月（年繳價）。來源：https://pika.art/pricing （查證日期 2026-07-11）
- 程式呼叫實際費率（Fal.ai）：720p 5 秒 $0.20（= **$0.04/秒**）、1080p 5 秒 $0.45（= $0.09/秒）。來源：https://fal.ai/models/fal-ai/pika/v2.2/text-to-video （查證日期 2026-07-11）

### 30 秒 Shorts 成本估算
多數服務單次生成僅數秒到約 25 秒（此 duration 數字多為二手來源），30 秒成片需多段生成＋ffmpeg 拼接；計費按總秒數線性計算，拆段不會顯著增加 API 費用，但跨段落角色/場景一致性是品質風險。

| 選項 | 每秒 | 30 秒 |
|------|------|-------|
| Pika 720p（經 Fal.ai） | $0.04 | **$1.20**（最便宜） |
| Runway Gen-4 Turbo / Veo 3.1 Lite 720p | $0.05 | $1.50 |
| Sora-2 720p | $0.10 | $3.00 |
| Veo 3.1 Standard 720p/1080p（含音訊） | $0.40 | $12.00 |
| Sora-2-pro 1080p | $0.70 | $21.00 |
| Runway Seedance 2.0 4K | $1.50 | **$45.00**（最貴） |

### 路線 3 結論
- **(a) 30 秒單支成本**：**$1.2（最便宜）～ $45（最貴）**；主流「高品質含音訊」等級約 **$12-21**。
- **(b) 品質評語**：鏡頭運動、畫面自然度與（Veo 3.1/Sora-2-pro）原生同步音訊明顯優於其他路線，是品質上限最高的一條；但 30 秒須拼接多段生成，跨段一致性是最大品質風險。
- **(c) 自動化可行度**：Veo/Sora **全自動**（官方 API）；Pika 經 Fal.ai 亦可全自動（依賴第三方託管）；Runway、Kling 的 API 存取門檻未定案，暫列「需人工確認後才能全自動」。

---

## 路線 4：字幕/逐字稿

### 方案 A：TTS 生成時直接拿時間戳（推薦，若管線本來就用 TTS 配音）
- **edge-tts**：原始碼 `communicate.py` 明確支援 `WordBoundary` 與 `SentenceBoundary` 事件，生成語音同時取得逐字時間戳，免費且與音檔同源（零辨識誤差）。來源：https://github.com/rany2/edge-tts/blob/master/src/edge_tts/communicate.py （查證日期 2026-07-11）
- **Azure Speech TTS SDK**：官方支援 word boundary 事件（`SynthesisWordBoundaryEventAsync`）。來源：https://github.com/Azure-Samples/Cognitive-Speech-TTS/wiki/How-to-get-word-time-stamp-events-using-Azure-TTS （查證日期 2026-07-11）
- **ElevenLabs**：`/v1/text-to-speech/{voice_id}/with-timestamps` 回傳**字元級**時間戳（非字詞級），需自行分組。來源：https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps （查證日期 2026-07-11）

### 方案 B：本機 ASR（適用於外部既有語音/影片素材）
- **openai/whisper**：最新 release v20250625（2025-06-26），MIT 授權（含權重），本機免費；支援中文（訓練涵蓋近 99 種語言含 Mandarin）；原生支援 word-level timestamp（CLI `--word_timestamps True`，PR #869 已合併），但官方註記精度有限（inference-time trick，停頓處易不準）。未見官方凍結標記；`turbo`（large-v3-turbo）是同 repo 內的加速模型，非繼任專案。來源：https://github.com/openai/whisper/releases 、https://github.com/openai/whisper/pull/869 （查證日期 2026-07-11）
- 更快的替代：**faster-whisper**（SYSTRAN，v1.2.1，2025-10-31，快至多 4 倍、省記憶體，https://github.com/SYSTRAN/faster-whisper/releases ）；**whisper.cpp**（v1.9.1，2026-06-19，活躍維護，https://github.com/ggml-org/whisper.cpp/releases ）；需要 sub-100ms 級對齊可疊加 **WhisperX**。（查證日期 2026-07-11）

### 路線 4 建議
管線若自己跑 TTS → 用 TTS word boundary 直接產字幕（$0、零誤差）；只有處理外部語音時才跑 ASR，本機優先 faster-whisper。成本 $0，全自動。

---

## 路線 5：程式化影片組裝框架

**ffmpeg（command line）**
- 字幕燒錄：`subtitles=`（SRT/VTT）或 `ass=`（完整 ASS，支援動畫/卡拉OK/複雜定位），搭配 `force_style`；轉場疊圖用 `-filter_complex`。
- 適合：效能敏感、伺服器端批次渲染、零額外框架成本；`filter_complex` 學習曲線陡。
- 來源：https://en.wikibooks.org/wiki/FFMPEG_An_Intermediate_Guide/subtitle_options （查證日期 2026-07-11）

**moviepy（Python）**
- 最新版 2.2.1，發布於 **2025-05-21**（PyPI JSON API 與 GitHub Releases API 兩者一致）——距查證日已超過一年無新版。README 曾寫 "maintainers wanted"，2.2.1 是被動修 Pillow 相容性，非主動開發。**仍在維護但步調緩慢**。
- 適合：Python 生態內快速原型/中小規模拼接；不建議作為生產管線長期核心依賴，需有 ffmpeg 直呼備援。
- 來源：https://pypi.org/pypi/moviepy/json 、https://api.github.com/repos/Zulko/moviepy/releases/latest （查證日期 2026-07-11）

**Remotion（Node.js/React）**
- **授權不是標準開源**（自訂 Remotion License）：個人、非營利、員工數 ≤3 人的營利組織免費；**4 人以上公司需購買 Company License**。
- 付費方案：Remotion for Creators $25/seat/月；**Remotion for Automators（程式化自動渲染）$0.01/render，最低消費 $100/月**；Enterprise 低消 $500/月。
- 來源：https://www.remotion.dev/docs/license 、https://www.remotion.dev/docs/license/faq 、https://github.com/remotion-dev/remotion/blob/main/LICENSE.md （查證日期 2026-07-11；官方 /docs/pricing 頁為前端渲染 WebFetch 抓不到，數字以 license/FAQ 頁＋搜尋交叉確認）
- 適合：需要複雜 UI 排版/動畫/資料視覺化的影片（React 元件寫版面）；個人專案免費，但商業化自動批次渲染會觸發授權費。

### 路線 5 建議
個人自動化管線：**ffmpeg 為核心**（本機已裝、零成本、全自動）；快速原型可用 moviepy 但留 ffmpeg 備援；需要精緻動態字卡/排版才考慮 Remotion（個人使用免費）。

---

## 路線 6：熱門影片風格分析（yt-dlp ＋ LLM）

- **yt-dlp 維護狀態**：最新 release 2026.07.04（2026-07-04），前版 2026.06.09，發布頻率約每月一次，**2026 年仍積極維護**（2026.07.04 含 CVE-2026-55404 安全修補；最低建議 Python 升至 3.11）。來源：https://github.com/yt-dlp/yt-dlp/releases （查證日期 2026-07-11）
- **功能確認**（官方 README，查證日期 2026-07-11）：
  - `--write-auto-subs`：抓 YouTube 自動字幕，參數有效。
  - `--skip-download`：不下載影片本體但寫出相關檔案（字幕、metadata、縮圖），可行。
  - `--write-info-json` 可取得：id、title、description、upload_date、view_count、like_count、comment_count（需 `--write-comments`）、channel、duration、tags 等——涵蓋風格分析所需全部欄位。
  - 常見組合：`yt-dlp --write-sub --write-auto-sub --sub-langs zh-TW --skip-download "URL"`。
  - 來源：https://raw.githubusercontent.com/yt-dlp/yt-dlp/master/README.md
- **技術可行性判斷**：「抓字幕/metadata → LLM 分析腳本結構（開場鉤子、節奏、結尾 CTA）」**技術上可行**。字幕是帶時間軸的逐字稿（LLM 結構分析的天然輸入），metadata 是結構化 JSON（可當互動數據特徵），串接 LLM API 無工程阻礙。
- **ToS 注意事項**：YouTube 服務條款「使用本服務」章節明文禁止未經授權的自動化工具存取（例外：遵循 robots.txt 的公開搜尋引擎、取得書面許可、法律允許）。yt-dlp 這類工具在個人/研究用途被廣泛使用，屬「條文禁止、實務普遍」的落差狀態；未查到 YouTube 官方對 yt-dlp 的個案聲明。使用者需自行評估合規風險（本報告非法律建議）。來源：https://www.youtube.com/static?template=terms （查證日期 2026-07-11）
- **自動化可行度**：全自動可行（批次抓取＋LLM 分析皆可腳本化），建議保留輕量人工抽查（字幕品質、偶發的機器人驗證/地區限制失敗）。

---

## 推薦排序（權重：零/低成本起步、可全自動、繁中支援）

### 第 1 名：路線 2「AI 圖生影片型」＋ 路線 4「TTS 時間戳字幕」＋ 路線 5「ffmpeg 組裝」
- 理由：三項權重全數滿足——(a) 成本可壓到近零（本機 SD）或每支 $0.2-0.4（API 生圖，中品質）；(b) 唯一真正端到端全自動、無人工匹配環節的路線（AI 生圖依腳本客製，不會有「畫面對不上旁白」問題）；(c) 繁中支援靠 edge-tts 的 3 個 zh-TW 語音（免費）＋ TTS WordBoundary 直接出繁中字幕。
- 建議具體組合：LLM 寫腳本 → edge-tts（zh-TW 語音＋WordBoundary 時間戳）→ gemini-2.5-flash-image（$0.039/張）或本機 SDXL → ffmpeg zoompan（Ken Burns）＋ ass 字幕燒錄 → 1080x1920 輸出。全 API 情境每支約 $0.3；本機生圖情境 $0。
- 注意：不要選 Imagen 4（2026-08-17 停用）；edge-tts 需準備 fallback（OpenAI tts-1，每支約 $0.005）。

### 第 2 名：路線 1「素材拼接型」
- 理由：成本同樣近零、繁中支援相同（同一套 TTS），但輸給第 1 名的原因是自動化品質瓶頸——免費圖庫關鍵字檢索與旁白的語意匹配需人工複核，否則容易出現不相關畫面。適合當第 1 名的補充素材來源（真實影像混搭 AI 圖），而非獨立主線。
- 另注意 Pexels 免費額度（20,000 req/月）對個人量產綽綽有餘。

### 第 3 名：路線 3「AI 文生影片型」
- 理由：品質上限最高，但每支 $1.2-45（主流高品質 $12-21）的邊際成本與「多段拼接一致性」的品質風險，不符合「零/低成本起步」權重。建議定位為升級選項：等第 1 名管線跑順、頻道有收益後，把高表現主題升級用 Veo 3.1 Fast（$0.10/秒，30 秒 $3）重製。首選 Veo（官方 API 穩定、Gemini 生態與生圖共用帳號）；Sora 有未證實的 sunset 傳聞需先確認；Runway/Kling 存取門檻未定案。

### 基礎設施（不參與排序，直接採用）
- **字幕**：TTS WordBoundary 直接產生（$0、零誤差）；處理外部語音才用 faster-whisper 本機跑。
- **組裝**：ffmpeg 為核心（本機已裝、$0、全自動）；moviepy 僅限原型（維護緩慢）；Remotion 個人免費但 4 人以上公司或商業自動渲染要付費（$0.01/render、低消 $100/月），此專案暫不需要。
- **風格分析**：yt-dlp（`--skip-download --write-auto-subs --write-info-json`）＋ LLM 分析技術上完全可行、近零成本，可作為選題與腳本結構的上游模組；留意 YouTube ToS 對自動化存取的限制屬使用者自行承擔的合規風險。

---

## 開源工具維護狀態總表（驗收條件之一）

| 工具 | 最新版本 | 發布日期 | 2026 仍維護？ | 來源 |
|------|---------|----------|---------------|------|
| edge-tts | 7.2.8 | 2026-03-22 | 是 | https://pypi.org/project/edge-tts/ |
| openai/whisper | v20250625 | 2025-06-26 | 是（活躍度中等，無凍結標記） | https://github.com/openai/whisper/releases |
| faster-whisper | v1.2.1 | 2025-10-31 | 是 | https://github.com/SYSTRAN/faster-whisper/releases |
| whisper.cpp | v1.9.1 | 2026-06-19 | 是（活躍） | https://github.com/ggml-org/whisper.cpp/releases |
| moviepy | 2.2.1 | 2025-05-21 | 弱維護（>1 年無新版） | https://pypi.org/pypi/moviepy/json |
| yt-dlp | 2026.07.04 | 2026-07-04 | 是（每月更新） | https://github.com/yt-dlp/yt-dlp/releases |

（所有查證日期均為 2026-07-11。）

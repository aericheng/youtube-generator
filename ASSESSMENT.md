# 自動化 YouTube Shorts 頻道：完整評估與工作流

> 撰寫日期：2026-07-11。所有事實均經三份查證報告佐證（`research/` 目錄，內含官方來源 URL 與查證日期）。
> 目標：自動發現熱門短影音 → 學習其風格 → 原創產出影片 → 上傳到自己的 YouTube 頻道。

---

## 結論（先讀這段）

**能做到，但不是「100% 無人化」，而是「90% 自動化＋你當主編」。** 三個原因：

1. **技術上**：選題分析、腳本、配音、生圖、合成、字幕、上傳，每個環節都有成熟工具，本機已具備大半（ffmpeg 7.1、yt-dlp 2026.03、Python 3.11、Node 24）。單支 30 秒影片成本可壓到 **$0～US$0.4**。
2. **制度上**：用官方 API 自動上傳「公開」影片，必須先通過 YouTube 的 **compliance audit**（API 合規審核，人工審核、數週起跳）；未過審的專案上傳一律被**鎖成私人（private）且不可申訴**（來源：developers.google.com/youtube/v3/docs/videos/insert；support.google.com/youtube/answer/7300965）。所以工作流必須分兩階段：過審前半自動（系統產片、你按上傳），過審後全自動。
3. **政策上**：「全自動模板化量產」是 YouTube 明文點名的違規模式——2026 年 1 月才有 16 個 AI 頻道（合計 47 億觀看）被終止（官方 CEO 信件佐證方向：blog.youtube/inside-youtube/the-future-of-youtube-2026/）。**「模仿風格、原創內容」不只是道德建議，是頻道存活的必要設計**，因此人工品質把關不能完全省掉。

---

## 一、逐環節可行性

| 環節 | 可行性 | 做法 | 限制 |
|------|--------|------|------|
| 發現熱門 Shorts | ⚠️ 可近似 | YouTube Data API `search.list`（videoDuration=short＋order=viewCount＋publishedAfter） | API 無官方 `isShort` 欄位，「短於 4 分鐘」只能近似；舊 Trending 網頁已於 2025-07 下架（research-api.md Q1） |
| 學習風格 | ✅ 可行 | API 抓公開 metadata（標題/觀看數/標籤，1 unit/次）＋ yt-dlp 抓自動字幕（`--skip-download --write-auto-subs`）→ LLM 分析鉤子、節奏、結構 | 官方 API **抓不到別人影片的字幕**；yt-dlp 屬 ToS 灰色地帶（內部分析、不散布，風險較低但非零，見 research-policy.md 問題 3C） |
| 產出影片 | ✅ 可行 | 推薦「AI 圖生影片型」：LLM 腳本 → edge-tts（免費、有 3 個 zh-TW 語音）→ AI 生圖（gemini-2.5-flash-image $0.039/張）→ ffmpeg zoompan（Ken Burns 動態：靜態圖緩慢縮放平移模擬運鏡）＋ ASS 字幕燒錄 | 全 API 每支約 $0.3；本機有 GPU（≥8GB VRAM）跑 Stable Diffusion 則 $0（research-production.md 路線 2） |
| 字幕 | ✅ 可行 | edge-tts 的 WordBoundary 事件直接產時間戳（$0、零誤差） | — |
| 自動上傳 | ⚠️ 有門檻 | API `videos.insert`，預設每日 100 支上限（2026-06 起獨立配額桶） | **未過 audit 一律鎖 private、不可申訴**；瀏覽器自動化上傳（非 API）明文違反 ToS，不採用 |
| 成效迭代 | ✅ 可行 | API 讀自己影片的 statistics，回饋選題 | — |

## 二、三大風險與內建對策

依 `research/research-policy.md` 的風險分級表（10 項做法、逐項附官方條文）：

| 風險 | 等級 | 工作流內建對策 |
|------|------|----------------|
| 模板化量產 AI 內容 → 頻道終止（inauthentic content「不真實內容」：官方指模板化、可規模複製且無原創觀點的內容；spam 政策則逐字點名「同背景音樂＋重複 AI 影像＋AI 口白」模式） | 高 | 每支影片必須有差異化腳本與原創觀點；禁止固定模板複製；每日量控制在少量（1-3 支）；人工抽查 |
| 寫實 AI 內容未揭露 → 下架／暫停營利（2026-05 起 YouTube 有自動偵測） | 中 | 上傳時一律設定 AI 揭露欄位（API `status` 或 Studio 勾選）；內容偏向知識型/動畫風格（非寫實則免揭露，但一律標示最保險） |
| 直接重用他人片段（即使剪輯過）→ 取消營利＋著作權風險 | 高 | **只分析、不下載重用**：學風格（結構/節奏/選題），素材 100% 自產（AI 圖）或授權圖庫（Pexels，商用免掛名） |

明確**不做**的事：瀏覽器自動化上傳（ToS 明文禁止 automated means，未豁免自有帳號）、下載他人影片再剪輯上傳、超量灌片。

## 三、推薦技術架構

```
[選題層]  YouTube Data API (search.list + videos.list)     ← API Key，免費
              ↓ 候選熱門短片清單 (JSON)
[分析層]  yt-dlp 抓自動字幕 + info.json → Claude 分析       ← 本機，$0
              ↓ 風格報告：鉤子類型/節奏/結構/選題角度
[腳本層]  Claude 生成原創腳本（套用風格洞察，非抄內容）      ← Claude Code 訂閱內
              ↓ script.json（分鏡：旁白句 × 畫面描述）
[製作層]  edge-tts (zh-TW + WordBoundary 時間戳)            ← $0
          gemini-2.5-flash-image 生圖 6-10 張               ← ~$0.3/支（或本機 SD $0）
          ffmpeg zoompan + concat + ASS 字幕 + 1080x1920    ← $0
              ↓ final.mp4 + metadata.json（標題/描述/標籤）
[品管層]  verifier：時長/解析度/字幕渲染/音畫同步檢查        ← $0
              ↓ 人工審核（Phase 1 全審 → Phase 2 抽查）
[發佈層]  Phase 1：YouTube Studio 手動上傳（1-2 分鐘/支）
          Phase 2：API videos.insert（過審後，每日上限 100 支）
              ↓
[迭代層]  API 讀自己頻道 statistics → 回饋選題層
```

選型依據（詳見 `research/research-production.md` 推薦排序）：
- **不用** moviepy 當核心（弱維護，>1 年無新版）、**不用** Imagen 4（2026-08-17 停用）、**不用** Remotion（本案不需要，且商用自動渲染要付費）。
- 文生影片（Veo 3.1 Fast，30 秒約 $3）留作升級選項：頻道有成效後，把高表現主題重製。
- edge-tts 是逆向工程專案、有斷供風險，備援為 OpenAI tts-1（每支約 $0.005）。

## 四、工作流（三階段）

### Phase 0：一次性前置（需要你參與，約 1-2 小時＋等待審核）

1. 確定頻道利基（niche）與語言——**這是你要做的第一個決策**（見第六節）。
2. Google Cloud 建專案 → 啟用 YouTube Data API v3 → 建 API Key（讀取用）＋ OAuth 2.0 用戶端（上傳用）。API 本身免費。
3. 送出「YouTube API Services – Audit and Quota Extension Form」申請合規審核（公開上傳的硬前提；官方未承諾時長，社群回報數週～數月）。**送審與 Phase 1 平行進行，不互相卡**。
4. 建 pipeline 程式骨架（Python：`google-api-python-client`、`edge-tts`；此步我可以直接做）。

### Phase 1：半自動 MVP（送審等待期間，1-2 週）

每日流程（單支影片端到端約 5-10 分鐘機器時間）：
1. **掃描**：API 拉近 7 天熱門短片（目標 niche 的關鍵字＋videoDuration=short＋order=viewCount），存 `data/trends/`。
2. **分析**：對前 10-20 支抓字幕與 metadata，Claude 產出風格報告（鉤子/節奏/CTA 模式），存 `data/insights/`。
3. **產製**：Claude 依風格洞察寫**原創**腳本 → TTS → 生圖 → ffmpeg 合成 → 品管檢查。
4. **人工審核＋手動上傳**：你看片（30 秒），OK 就從 YouTube Studio 上傳（順手勾 AI 揭露）。
5. **先樣本後批次**：第一批先做 2-3 支風格差異明顯的樣本讓你定調，確認後才進入每日產製。

### Phase 2：全自動排程（audit 通過後）

- Windows 工作排程器（或 Claude Code scheduled agents）每日觸發 pipeline：掃描 → 產製 → 品管 → `videos.insert` 上傳（帶 AI 揭露標記；可先傳為排程發佈狀態供你抽查）。
- 每週自動報表：各影片觀看/完播數據 → 調整選題權重。
- **保留人工抽查**（例如每 5 支看 1 支）——這是政策風險的最後防線，不建議移除。

## 五、成本估算

| 項目 | 金額 | 來源 |
|------|------|------|
| YouTube Data API | $0（預設配額：上傳 100 支/天＋讀取 10,000 units/天） | research-api.md Q2/Q5 |
| TTS（edge-tts zh-TW） | $0 | research-production.md 路線 1 |
| AI 生圖（gemini-2.5-flash-image，8 張/支） | 約 $0.31/支；本機 SD 則 $0 | 同上路線 2 |
| 合成/字幕（ffmpeg，本機已裝） | $0 | 同上路線 4/5 |
| 腳本與分析（Claude Code） | 訂閱內 | — |
| **每月合計（每日 1 支）** | **約 $0～10/月** | — |
| 升級選項：Veo 3.1 Fast 文生影片 | 約 $3/支（30 秒） | 同上路線 3 |

## 六、需要你決定的事項

1. **頻道利基與語言**：做什麼主題（知識型？冷知識？理財？故事？）、繁中市場還是英文市場？這決定選題關鍵字、TTS 語音與競爭強度。
2. **生圖走本機還是 API**：你的機器有無 ≥8GB VRAM 的 GPU？有 → 本機 Stable Diffusion（$0）；沒有 → Gemini API（需要 API key，約 $0.3/支）。
3. **是否送 YouTube API audit**：不送就永遠停在半自動（手動上傳其實每支只要 1-2 分鐘，也是可接受的長期型態）。
4. **每日產量與審核深度**：建議從每日 1 支＋全數人工過目開始，穩定後再談加量。

## 七、定調更新（2026-07-11，使用者決策後）

**使用者已決定**：
1. **主題**：紓壓短影片／身歷其境場景，**無對話**——TTS 與字幕兩層整個移除，管線簡化。
2. **本機 GPU**：RTX 5070 Ti、16GB VRAM（nvidia-smi 實測 16303 MiB，驅動 591.86）→ 生成走本機優先，成本壓向 $0。
3. Audit 疑問已釐清：**通過 audit 後 API 上傳即可 public**；審核中/未過審的 API 上傳一律鎖 private 且事後不能改 public；手動 Studio 上傳不受影響、隨時可 public（來源：research-api.md Q3）。

**管線修訂**（取代第三節的腳本/製作層）：
```
[腳本層] → 改為「場景概念＋分鏡設計」：場景主題、鏡頭描述、氛圍、音景搭配
[製作層] → 畫面：本機生成（影片生成模型 或 生圖＋zoompan，擇一，待查證）
           音軌：環境音（雨聲/海浪/篝火等），來源與授權待查證
[品管層] → 檢查項改為：時長/解析度 1080x1920/循環順暢度/音量正規化/音畫氛圍匹配
```

**本主題的特有風險註記**：無旁白環境類內容天生接近「模板化」樣態，spam 政策點名的「同背景音樂＋重複 AI 影像」模式要刻意迴避——對策：每支影片不同場景與音景、音源庫要大且多樣、系列間有可辨識的策劃主題（原創觀點的載體）。寫實風格的 AI 場景一律勾 AI 揭露（最保險）。

**製作層選型定案（2026-07-11，依 research/research-localgen.md）**：

| 元件 | 選擇 | 理由 |
|------|------|------|
| 畫面（主力，2026-07-11 使用者定調後改版） | 本機 **Wan 2.2 TI2V-5B** 文生影片（704×1280 直式）＋ 自身 crossfade 無縫循環延長 ＋ lanczos 放大 1080×1920 | 使用者明確否決「定格照＋zoompan」（太廉價）、要求真動態＋單一場景全程沉浸；Wan 2.2 授權最乾淨（Apache 2.0）、原生直式；「單一場景循環」正好避開影片模型最弱的跨段一致性問題 |
| 畫面（備援） | LTX-Video 系列（更快但授權「other」未查清＋RTX 50 有損毀 issue）；雲端 Veo 3.1 Lite $0.05/秒（品質升級選項） | Wan 在 5070 Ti 實測不可用或太慢時切換 |
| ~~畫面（已淘汰）~~ | ~~SDXL 生圖＋zoompan~~ | 技術驗證通過（6.8 秒/張）但使用者品味否決；腳本保留於 pipeline/ 作為 fallback |

**Wan 2.2 TI2V-5B 在 5070 Ti 的一手實測（2026-07-11，樣本輪）**：
- 5 秒 704×1280 clip、35 步、CPU offload：**每支 17-20 分鐘**，VRAM 無 OOM、無 Blackwell 相容性問題（torch 2.11.0+cu128）。單支成品（28 秒）總 GPU 時間約 20 分鐘、成本 $0。
- 已知失敗模式：**夜間＋高頻暗紋理場景（星空、飄散餘燼）會崩壞成馬賽克雜訊**——第一版篝火全片崩壞，簡化背景（移除星空/餘燼、改淺景深模糊）＋換 seed 後一次通過。教訓：prompt 避免大面積暗部細碎紋理；QC 只驗格式驗不出崩壞，**逐格實看的 verifier 不可省**。
- 循環結構：5 秒 clip 經自身 crossfade 取 4 秒無縫單元 × 7 = 28.3 秒，接縫 SSIM 0.87-0.97。
| 音軌（定案 2026-07-12） | 本機 **Stable Audio Open 1.0**（`make_ambient_ai.py`），30 秒音軌實測 **9 秒**生成 | $0、全自動、每支獨特（化解「同背景音」spam 訊號）；Community License 年營收 <$1M 可商用，影片描述欄需標「Powered by Stability AI」；權重 HF gated（token 已設定）。verifier 以頻譜/波形實證：篝火有瞬態劈啪尖峰、海浪有慢週期湧退包絡 |
| ~~音軌（淘汰）~~ | ~~ffmpeg 程序化合成~~（腳本保留為 fallback）；ElevenLabs $6/月 為雲端備援 | 合成噪音質感不足；Freesound API 商用需另行協商，不採用 |
| 部署鐵律 | 先裝 PyTorch ≥2.9（cu128+ wheel）並鎖定版本 | RTX 5070 Ti＝Blackwell sm_120，舊 torch 不支援；各模型 requirements.txt 會偷偷降版 torch，是已查證的共通故障模式 |

已知查證缺口與後續補上的實測（2026-07-11 樣本製作時）：
- ~~無 5070 Ti 一手速度實測~~ → **已實測：平均 6.8 秒/張**（SDXL fp16、768×1344、30 步、torch 2.11.0+cu128），一支 25 秒樣本（6 張圖）生圖僅 41 秒，全管線端到端約 1.5 分鐘。
- ~~SDXL 權重授權未逐字查證~~ → **已確認：CreativeML Open RAIL++-M**，LICENSE.md 明文「Licensor claims no rights in the Output You generate」，產出圖片可商用。
- ElevenLabs「嵌入影片發布」的商用合規仍為合理推論，規模化前建議書面確認（未變）。
- 實務教訓（樣本輪驗收發現）：ffmpeg xfade 串接 PNG 會默默升成 yuv444p（YouTube 相容性差），輸出必須顯式 `-pix_fmt yuv420p`；loudnorm 會把取樣率拉到 96kHz，輸出要顯式 `-ar 48000`。兩者已修進 pipeline 腳本。

## 附錄：查證報告

- `research/research-api.md` — YouTube Data API 能力、配額、audit 門檻（官方文件逐條引用）
- `research/research-policy.md` — AI 揭露、inauthentic content、ToS、風險分級表（10 項）
- `research/research-production.md` — 六條製作路線的價格與可用性（官方 pricing 頁，2026-07-11 查證）
- `research/research-localgen.md` — 16GB VRAM 本機影片生成模型對照、Blackwell 相容性、環境音源授權比較（2026-07-11 查證）

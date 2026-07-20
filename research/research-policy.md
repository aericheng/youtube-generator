# 全自動 AI YouTube Shorts 頻道：2026 平台政策與法律風險研究

查證日期：2026-07-11。查證順序：官方文件（support.google.com、blog.youtube、developers.google.com）優先，媒體報導標註為二手來源。

---

## 問題 1：AI 生成內容揭露要求

**官方來源**：
- https://support.google.com/youtube/answer/14328491 （官方政策說明頁，"About altered or synthetic content"）
- https://blog.youtube/news-and-events/disclosing-ai-generated-content/ （官方公告，發布日 2024-03-18）
- https://blog.youtube/news-and-events/improving-ai-labels-viewers-creators/ （官方公告，自動偵測功能更新，2026 年）

**何時必須揭露**：僅限「寫實內容」（viewer 可能誤認為真實人物/地點/場景/事件的內容），且是透過生成式 AI 或其他方式「改造或合成」而成。官方三個例子：
1. 讓真實人物看起來說了/做了他們沒說過/沒做過的事（換臉、聲音複製）
2. 竄改真實事件或地點的畫面（例：讓真實建築看起來著火）
3. 生成寫實場景描繪未曾發生的虛構重大事件（例：龍捲風逼近真實城市但實際沒發生）

**免除揭露**：明顯不寫實（動畫、奇幻場景）、生產輔助用途（腳本生成、自動字幕、縮圖）、無關緊要的美化（濾鏡、色彩調整、自己聲音的複製）、影片升級/修復。標示方式為上傳時在 YouTube Studio 勾選「AI 使用」設定。

**不揭露的罰則**（引自官方頁面 14328491）：「Creators who consistently choose not to disclose this information may be subject to manual application of a label, or penalties from YouTube, including removal of content or suspension from the YouTube Partner Program.」（持續不揭露者可能被 YouTube 手動加註標籤，或受罰——包括內容下架或暫停 YPP 資格）。2024-03-18 原始公告也指出：即使創作者未揭露，YouTube 也可能主動加註標籤，尤其在內容有混淆/誤導疑慮時。

**2026 年更新（自動偵測）**：據 blog.youtube 官方公告，YouTube 自 2026 年 5 月起導入技術，可在創作者未申報的情況下自動偵測寫實 AI 內容並加註標籤；標籤位置也更顯眼（長影片顯示在影片播放器正下方、描述欄上方；Shorts 則以疊加方式顯示於畫面上）。公告明確聲明：「a disclosure label alone does not change how a video is recommended or whether it's eligible to earn money」——單純的揭露標籤本身不影響推薦或營利資格，但**不揭露**仍可能觸發上述罰則。

---

## 問題 2：YPP「inauthentic content」政策與 2025 年 7 月更新

**官方來源**：https://support.google.com/youtube/answer/1311392 （YouTube channel monetization policies，官方頁面，已更新至含 2025-07-15 版本）

**2025 年 7 月 15 日實際改了什麼**：官方頁面將原本的「repetitious content（重複性內容）」政策**更名**為「inauthentic content（不真實內容）」，並**釐清定義**涵蓋「repetitive or mass-produced」（重複或量產）的內容。YouTube 官方明確聲明這**不是新政策**，只是語言澄清；且「There is no change to our reused content policy」（重用內容政策沒有變動）。

**「mass-produced / repetitious」定義**（引自官方頁面）：
- 「content that appears to be produced using a template and can be repeated at scale」（看起來用模板製作、可大量複製的內容）
- 具體禁止範例：低教育價值/低評論價值/低敘事價值且影片間差異極小的重複內容；使用相似或無原創性模板大量產製的內容；缺乏敘事的圖片幻燈片；**「AI-generated content made with generic templates giving the impression of mass production without adding the creator's original, authentic insights or perspective」**——用通用模板產出、沒有加入創作者原創真實觀點與洞見的 AI 生成內容。

**全 AI 生成頻道還能營利嗎**：官方政策**沒有全面禁止 AI 內容**，禁的是「通用模板量產、無原創觀點」的 AI 內容。也就是說純技術上仍可能營利，但門檻是必須有可辨識的「creator's original, authentic insights or perspective」——這是模糊地帶，實務執法很大程度上仰賴 YouTube 內部審查與演算法判斷（見問題 5 的案例）。

**二手佐證**（標註二手）：Social Media Today、Search Engine Journal、iMusician 等媒體報導與官方頁面內容一致，均引用「2025-07-15 更名、無新規則」的官方說法。

---

## 問題 3：ToS 對自動化上傳與下載的規定

**A. 官方 API 上傳是否允許**
來源：https://developers.google.com/youtube/terms/api-services-terms-of-service

允許透過 API 上傳，但受配額（quota）限制與內容規範限制：條款規定「YouTube may set a quota on usage of any YouTube API Services at any time」，且「You and your API Client(s) will not, and will not attempt to, exceed or circumvent use or quota restrictions」。上傳時仍須遵守社群規範、垃圾內容政策等一般規則；API 本身不豁免內容政策。違反條款時，YouTube 保留「suspend or terminate access to the YouTube API Services at any time」的權利（條款第 24.2 節，因違約或可能造成責任的不當行為）。**結論：用官方 API 上傳自己的內容是被允許的技術路徑，但不豁免內容/垃圾內容政策的實質審查。**

**B. 瀏覽器自動化（非 API）操作自己帳號**
來源：https://www.youtube.com/static?template=terms （YouTube 一般服務條款）

一般 ToS 明確禁止：「access the Service by any automated means (such as bots, botnets, or web crawlers)」，除非遵守 robots.txt（供搜尋引擎）或取得 YouTube 事先書面許可。條款文字**未區分「操作自己帳號」與「操作他人帳號」**，也未針對「沒有 API 時可用其他自動化手段」給予豁免。**結論：用瀏覽器自動化（非官方 API）上傳，即使是自己的帳號，字面上仍落在被禁止的「automated means」範疇內，屬於明確的 ToS 違規風險（非官方 API 是安全路徑，瀏覽器自動化不是）。**

**C. yt-dlp 下載他人影片做「風格分析」**
來源：一般 ToS（同上）+ 二手法律分析（AudioUtils、Hacker News 討論，標註二手）

- ToS 層面：一般條款禁止「access, reproduce, download, publish...any part of the Service or any Content」未經授權；官方僅認可透過「video playback pages、embeddable player，或 YouTube 明確指定的其他授權方式」存取內容。yt-dlp 下載屬於 ToS 違規（違約），但**違約本身不是刑事案件**，救濟手段是帳號停權/終止或 Google 提起民事違約訴訟。
- 著作權層面：ToS 違規與著作權侵權是兩件獨立的事。下載本身若只是取得副本用於內部分析（不重新散布、不公開展示），著作權侵權風險較低（可能落入合理使用討論範圍，惟美國以外法域規則不同，且訓練記憶未涵蓋確定判例，此處**官方文件未記載明確結論，屬二手法律評論觀點**）；但若把下載片段剪輯後重新上傳散布，則同時觸發 ToS 違規與著作權侵權雙重風險。

---

## 問題 4：「模仿風格」vs「抄襲內容」界線

**官方來源**：https://support.google.com/youtube/answer/1311392 （同問題 2 頁面，Reused content 段落）

**官方定義「reused content（重用內容）」**：「content that is not clearly your own original creation and may already be on YouTube or another online source without added significant original commentary, substantive modifications, or educational or entertainment value」——不明顯是你原創、且沒有加入顯著原創評論/實質修改/教育娛樂價值的內容。官方明確：**此政策與著作權執法無關**，即使取得原作者授權，仍可能被判定為不符合營利資格；判定標準是「viewers can tell that there's a meaningful difference between the original video and your video」。

- **只分析熱門影片標題/結構/節奏後原創產出**：這屬於「風格/格式模仿」，不落入官方「reused content」定義（因為沒有重用原始素材本身），**政策風險低**；官方文件對「分析他人爆款模式後原創產出」沒有額外限制條文，此為政策空白地帶，但方向上是安全的。
- **直接重用他人片段（即使剪輯過）**：即使加了剪輯，只要缺乏「顯著原創評論／實質修改／教育娛樂價值」，官方明確列為不合格範例：「compilations or clips edited together with little or no narrative, short videos compiled from other social media」。這是**明確的營利資格風險**（可導致整個頻道被取消營利資格），且若片段本身受著作權保護，另外疊加著作權侵權風險。

---

## 問題 5：Spam/deceptive practices 政策與已知案例

**官方來源**：https://support.google.com/youtube/answer/2801973 （Spam, deceptive practices, and scams policies）

**觸發處罰的行為**（引自官方頁面）：
- 「Using automated tools or AI to churn out high volumes of similar content with minimal changes」（用自動化工具或 AI 大量產出差異極小的相似內容）
- 「coordinated mass-production and technical manipulation to bypass filters or trick viewers」（協調性量產＋技術操弄以規避過濾機制或欺騙觀眾）
- 誤導性 metadata：「maliciously misleading titles, thumbnails, descriptions, or imagery to trick users into clicking」
- 官方**明確點名 AI 頻道範例**：「Channels that use the exact same background music and repetitive AI generated imagery across many videos, with each video reading out an AI-generated script」——violate 本政策。

**罰則**：內容下架＋警告或 Strike；90 天內累積 3 次 strike＝頻道終止；可選政策教育課程讓警告 90 天後失效；也可能導致營利暫停或頻道終止。

**已知案例（2024-2026，二手媒體報導，非官方公告逐案確認，但主要事實有官方 CEO 公開發言佐證）**：
- **2026 年 1 月**：YouTube 一波執法行動終止 16 個 AI 頻道（含知名頻道 CuentosFacianantes，595 萬訂閱），合計約 47 億次觀看、3,500 萬訂閱、估計每年 1,000 萬美元營收被撤銷。YouTube 發言人表示這是依既有「spam and deceptive practices」政策執行，**非新的反 AI 專項規則**。來源：XDA Developers (https://www.xda-developers.com/youtube-just-deleted-over-4-7-billion-views-worth-ofai-slop-videos/)、Android Police、IBTimes UK（均為二手媒體報導）。
- **官方佐證**：YouTube CEO Neal Mohan 於 2026-01-21 官方部落格年度信中證實方向：「To reduce the spread of low-quality AI content, we're actively building on our established systems that have been very successful in combating spam and clickbait, and reducing the spread of low quality, repetitive content.」來源（官方）：https://blog.youtube/inside-youtube/the-future-of-youtube-2026/

**觸發門檻總結**：官方文件未給出量化門檻（例如「每天上傳幾支」會觸發），執法依據是模式辨識（同背景音樂＋重複 AI 影像＋AI 口白腳本＋模板化差異極小）而非單純數量。**短時間大量上傳本身不違規，但「大量上傳＋模板化雷同＋自動生成描述標籤」組合會被系統標記為垃圾/不真實內容。**

---

## 風險分級表

| 做法 | 分級 | 依據 |
|------|------|------|
| 用 YouTube Data API 上傳自己製作的原創影片 | **明確允許** | API ToS 允許上傳，受配額限制（developers.google.com/youtube/terms/api-services-terms-of-service） |
| 上傳含 AI 生成/合成寫實內容時，於 YouTube Studio 誠實勾選「AI 使用」揭露 | **明確允許（且為義務）** | support.google.com/youtube/answer/14328491 |
| AI 生成內容但**不揭露**，且內容屬「寫實可能誤導」類 | **明確違規** | 同上，罰則為下架/暫停 YPP；2026 年起亦可能被自動偵測加註標籤 |
| 分析熱門影片的標題/結構/節奏等「風格」後原創產出新內容 | **灰色偏允許** | 不落入官方「reused content」定義；官方文件無額外限制條文，但也無明文「安全港」保證 |
| AI 生成內容有原創觀點/評論/實質內容價值，非套模板 | **灰色偏允許** | support.google.com/youtube/answer/1311392 明確排除「有原創真實觀點的 AI 內容」於禁止範圍外，但「原創程度」的判定權在 YouTube |
| 全自動化：AI 腳本＋AI 口白＋固定背景音樂＋模板化差異極小＋跨大量影片重複 | **明確違規（高風險）** | support.google.com/youtube/answer/2801973 逐字點名此模式；2026-01 已有 16 頻道／35M 訂閱／47 億觀看被此模式終止的實例 |
| 直接重用他人影片片段（即使剪輯），缺乏顯著原創評論/實質修改 | **明確違規** | support.google.com/youtube/answer/1311392「reused content」段落，明確列為不合格範例，且與著作權無關（即使取得授權仍可能違規） |
| 用瀏覽器自動化（非官方 API）操作自己帳號上傳 | **明確違規（ToS 字面禁止）** | www.youtube.com/static?template=terms 禁止「any automated means (such as bots...)」，未豁免自有帳號 |
| 用 yt-dlp 下載他人影片供內部「風格分析」（不重新散布） | **灰色地帶（ToS 違規／著作權風險較低但非零）** | 一般 ToS 禁止未授權下載（違約，非刑事）；著作權侵權風險視是否重新散布而定，官方文件未記載明確結論，此為二手法律分析觀點 |
| 短時間內大量上傳，但每支皆為獨立原創、非模板化 | **灰色偏允許** | 官方未給量化上傳頻率門檻；執法依據是內容雷同模式而非純數量 |
| 短時間大量上傳＋自動生成描述/標籤＋內容高度雷同 | **明確違規** | support.google.com/youtube/answer/2801973 |

---

## 驗收條件逐項核對

1. AI 揭露要求（何時／罰則）——已回答，附官方 URL 與引用原文，含 2026 年自動偵測更新。
2. YPP inauthentic content 政策與 2025-07-15 更新——已回答，附官方 URL 與定義原文，明確回答「全 AI 頻道能否營利」（能，但需原創觀點，執法有模糊空間）。
3. ToS 對自動化（API / 瀏覽器自動化 / yt-dlp）——已回答，三個子問題分別附官方 ToS 條文與二手法律分析標註。
4. 模仿風格 vs 抄襲內容界線——已回答，附官方「reused content」定義原文，分別評估兩種情境。
5. Spam/deceptive practices 政策與案例——已回答，附官方政策原文（含官方點名 AI 頻道範例）與 2026-01 執法案例（二手媒體＋官方 CEO 公開發言佐證）。

**未能查到官方一手資料、僅能用二手來源佐證的部分**（已在文中標註）：
- 2026 年 1 月 16 頻道終止事件的逐案細節（頻道名稱、確切數字）——官方僅有 CEO 部落格的方向性證實，具體數字來自二手媒體（XDA Developers 等），YouTube 官方**未發布**逐案終止公告或新聞稿列出這 16 個頻道名單。
- yt-dlp 下載他人內容用於「風格分析」是否構成著作權侵權——官方文件未記載，僅有二手法律評論觀點，且涉及合理使用等法域差異問題，非本查證範圍能給出確定結論。

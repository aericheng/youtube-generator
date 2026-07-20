# YouTube Data API v3 ── 自動發現熱門 Shorts + 自動上傳：2026 年可行性研究

查證日期：2026-07-11。查證順序：官方文件（developers.google.com / support.google.com）優先，官方查不到的部分以 WebSearch 補充並明確標註來源等級。

---

## 結論總覽（先讀這段）

1. **熱門影片發現**：`videos.list?chart=mostPopular` 官方文件仍記載為有效端點，但**沒有**任何 duration/aspect-ratio 篩選參數，無法直接篩出 Shorts。`search.list` 有 `videoDuration=short`（<4 分鐘）可近似篩選，但不精確（Shorts 官方定義是「≤3 分鐘」且必須直式，API 不提供官方 `isShort` 欄位、也不回傳長寬比）。YouTube 網頁版 Trending 頁面已於 2025-07-21 下架，但這是**網頁 UI 的改版**，與 API 的 `chart=mostPopular` 端點是否受影響，官方文件未記載，需自行實測驗證。
2. **上傳配額**：2026-07 現況：`videos.insert` 有**自己獨立的配額桶**，預設每日 **100 次呼叫**；`search.list` 也是獨立桶，預設每日 **100 次呼叫**；其餘所有端點共用預設 **10,000 units/天**。這是 2025-12-04（單價從 1600 units 降到約 100 units）與 2026-06-01（改成獨立配額桶，以呼叫次數計而非 units 計）兩次官方異動後的結果。**換算：預設專案每天最多上傳 100 支影片**，且不會排擠讀取類配額。
3. **OAuth 審核門檻（這是最大的架構風險點）**：`videos.insert` 文件明載——**2020-07-28 之後建立、且未通過 YouTube API 審核（audit）的 API 專案，透過該端點上傳的所有影片一律被鎖為 private**，不論你在 request body 裡把 `privacyStatus` 設成什麼。這個限制**無法申訴**（support.google.com/youtube/answer/7300965）。要解鎖必須送出「YouTube API Services – Audit and Quota Extension Form」並通過審核；官方文件未記載審核時長，多份非官方（開發者社群）回報審核耗時從數週到數月不等，且核准範圍會被限定在申請時聲明的用途。
4. **Metadata 讀取**：`videos.list`（snippet/statistics/contentDetails）可拿到標題、描述、標籤、觀看數、時長、頻道 ID；`channels.list` 可拿頻道資訊；`commentThreads.list` 可拿留言（皆 1 unit/call）。**字幕/transcript 讀不到別人的**——`captions.download` 官方文件明載「requires the user to have permission to edit the video」，只能下載自己（或獲授權管理）頻道的字幕，無法用官方 API 抓熱門影片作者的字幕。
5. **申請流程與費用**：Google Cloud 專案 → 啟用 YouTube Data API v3 → 建立憑證（公開讀取用 API Key；寫入操作/上傳一律要 OAuth 2.0 用戶端）→ 設定 OAuth consent screen。**API 本身免費**，預設配額如上，量大需求要送審核（同第 3 點的 audit）才能加量。

---

## Q1：熱門影片發現

### `videos.list?chart=mostPopular`
- 官方文件：https://developers.google.com/youtube/v3/docs/videos/list
- 內容：`chart` 參數支援 `mostPopular`（"Return the most popular videos for the specified content region and video category"），需搭配 `regionCode`、可選 `videoCategoryId`。
- **沒有**任何篩選 duration、aspect ratio 或「是否為 Shorts」的參數。`maxResults` 與 `id` 參數合併使用時不支援（無關本題但值得留意的限制）。
- **未查證的風險點**：YouTube 官方網頁 Trending 頁面已在 2025-07 下架（見下方），改用 YouTube Charts 分類榜單。`chart=mostPopular` API 端點的官方文件目前仍照舊描述，但其底層資料源是否因網頁改版而變化（例如是否仍反映即時熱門，或榜單更新頻率改變），**官方文件未記載**，需要實測（拉幾天資料比對）才能確認,不可只憑文件宣稱可行。

### YouTube Trending 網頁版下架（2025-07）
- 這是**網頁 UI**（youtube.com/feed/trending）的異動，非 API 異動。
- 來源（WebSearch，非官方一手但多家媒體一致報導；官方 support/blog 頁面未能直接 WebFetch 到公告原文，故標記為二手來源）：
  - https://techcrunch.com/2025/07/10/youtube-is-getting-rid-of-its-trending-page-and-trending-now-list/
  - https://ppc.land/youtube-closes-trending-page-after-a-decade-of-operation/
  - 內容：YouTube 於 2025-07-11 宣布移除 Trending 頁與 Trending Now 清單，2025-07-21 正式下架，改以分類制的 YouTube Charts（Trending Music Videos、Weekly Top Podcast Shows、Trending Movie Trailers 等）取代單一總榜。
- **結論**：`chart=mostPopular` API 呼叫本身沒有被官方文件標示為廢止，但它從來就不是「網頁 Trending 頁」的資料源同義詞——兩者關係官方未明確說明，不要假設 API 回傳的清單等同於過去網頁那份 Trending 榜單。

### `search.list` 找「近期爆紅短影音」
- 官方文件：https://developers.google.com/youtube/v3/docs/search/list
- 可用組合：
  - `videoDuration=short`：官方定義為「**少於 4 分鐘**」（不是 60 秒，也不是 Shorts 官方的「≤3 分鐘」定義——三者互不相等，用這個參數篩出來的清單會混入非 Shorts 的短片）。
  - `order=viewCount` / `order=rating` / `order=date`：可排序找熱門或近期。
  - `publishedAfter` / `publishedBefore`：RFC 3339 時間戳，可框「近期」窗口。
  - `type=video`、`q`（可用布林運算子）、`regionCode`。
- **API 沒有官方 `isShort` 或 `isShortsEligible` 欄位**。這點有 Google 官方 Issue Tracker 條目在討論（https://issuetracker.google.com/issues/232112727），但該頁需登入才能看到官方工程團隊回覆內容，WebFetch 被登入牆擋下，**無法直接引用官方回覆原文**；根據 WebSearch 到的社群整理（非官方一手），普遍做法是用 `contentDetails.duration ≤ 60s`（或 ≤3 分鐘後改的新定義）加上人工經驗法則，仍會有「59 秒橫式影片」這類誤判案例，官方文件對此未提供解法。
- Shorts 官方時長定義來源：https://support.google.com/youtube/answer/10059070 ——「up to 3 minutes long」（已從舊制 60 秒放寬）。

**Q1 結論**：能用 API 找「近期熱門短片」的近似清單（`search.list` + `videoDuration=short` + `order=viewCount`/`date`），但**無法用官方 API 精確且可靠地篩出「YouTube Shorts」這個確切分類**——這是產品設計上的硬限制，不是查證不足。

---

## Q2：上傳 quota

### 配額成本演變（官方 revision history）
來源：https://developers.google.com/youtube/v3/revision_history

- **2025-12-04**：`videos.insert` 單次呼叫成本從約 1600 units 降到約 100 units（官方文件原文："a change in the quota cost of a video upload from approximately 1600 units to approximately 100 units"）。
- **2026-06-01**：`videos.insert` 與 `search.list` 改為各自獨立的配額桶，不再與其他端點共用同一個每日 units 池（官方文件原文："API calls to the `videos.insert` and `search.list` methods will be charged to their own respective quota buckets"）。

### 2026-07 現況（即本次查證當下）
來源：
- https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits
- https://developers.google.com/youtube/v3/getting-started

兩份文件一致陳述：新專案預設配額 = **`search.list`：100 次呼叫/天（獨立桶）＋ `videos.insert`：100 次呼叫/天（獨立桶）＋ 其餘所有端點共用 10,000 units/天**。

### 換算「每天最多上傳幾支」
- **預設專案：每天最多 100 支影片**（受限於獨立桶的呼叫次數上限，不再是被 units 吃掉的問題）。
- 若要更多，須通過「YouTube API Services – Audit and Quota Extension Form」（見 Q3）。

其餘方法成本（來源：https://developers.google.com/youtube/v3/determine_quota_cost）：
| 方法 | Units/call |
|---|---|
| `videos.list` | 1 |
| `search.list` | 1（另受每日 100 次呼叫桶限制） |
| `captions.list` | 50 |
| `captions.insert` | 400 |
| `captions.update` | 450 |
| `captions.delete` | 50 |
| `commentThreads.list` | 1 |
| `channels.list` | 1 |
| `playlistItems.list` | 1 |
| `videos.update`/`rate`/`reportAbuse`/`delete` | 50 |

（`captions.download` 未出現在該頁的表格中，官方文件未記載其獨立 units 數字——只在 captions.download 方法頁本身查到「200 units」的敘述，但兩份文件對不上，此數字建議上線前用實際呼叫回應中的配額消耗自行核實，不要僅憑本報告的單一來源數字寫死邏輯。）

**Q2 結論**：2026-07 現況下，預設未加量的專案，`videos.insert` 上限是**每日 100 支**，且已與其他讀取操作解耦，不會互相排擠。

---

## Q3：OAuth 驗證門檻（未審核專案的影片會被鎖 private）

### 官方政策原文與出處
- **videos.insert 文件**（https://developers.google.com/youtube/v3/docs/videos/insert）：
  「All videos uploaded via the `videos.insert` endpoint from unverified API projects created after 28 July 2020 will be restricted to private viewing mode. To lift this restriction, the API project must undergo an audit ... to verify compliance with the Terms of Service.」
  → 即使 request body 把 `status.privacyStatus` 設為 `public`，未過審的專案上傳一律被鎖 private，這是伺服器端強制行為，不是用戶端可覆寫的參數問題。
- **support.google.com/youtube/answer/7300965**（Unverified API Service Restrictions）：
  「For videos that have been locked as private due to upload via an unverified API service, you will not be able to appeal.」
  補救方式只有兩條路：(a) 改用已通過審核的服務或 YouTube 官方 App/網站重新上傳，(b) 讓你自己的服務去申請 API 審核。

### 解鎖流程
- 官方頁面：https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits
  - 需求：填寫「YouTube API Services – Audit and Quota Extension Form」，說明具體用例（use case）；YouTube API Services 團隊審核後會主動聯繫；若沒過可用 Appeals Form 申訴。
  - 核准範圍**限定在申請時聲明的用途**，若之後用途改變需要重新送審。
  - **官方文件未記載具體審核時長**。
- 時長的二手資訊（WebSearch，非官方，僅供風險評估參考，不可當作官方保證）：
  - 開發者社群回報從數週到數月不等，甚至有 5 個月的案例；核准配額也可能低於申請額度或直接被拒。
  - 來源列表：https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits（官方流程頁）、其餘為 Blotato/OutlierKit/SocialCrawl 等第三方部落格整理，屬二手來源，僅作參考。

### 另一層獨立門檻：Google Cloud OAuth consent screen 驗證
這與上面的「YouTube API 專屬審核」是**兩條不同的審核軌道**，容易被混淆：
- 來源：https://support.google.com/cloud/answer/13464321 、https://developers.google.com/identity/protocols/oauth2/production-readiness/brand-verification
- `youtube.upload` / `youtube.force-ssl` 屬於敏感（sensitive）/受限（restricted）範圍的 OAuth scope。App 若處於「Testing」發布狀態（未經 Google 驗證），會有：
  - Tester 警告畫面（unverified app warning）。
  - 使用者人數上限（testing 狀態下的帳號授權人數上限，官方頁面提及但本次 WebFetch 未取得精確數字，需另查 https://support.google.com/cloud/answer/13463817 核實）。
  - **refresh token 生命週期受限**（官方頁面確認「the refresh token lifetime is limited」，但未在本次擷取內容中給出精確天數；坊間常引用「7 天」，此數字**本次查證未在官方頁面直接核實到**，標記為未確認，正式架構設計前建議直接測試或另尋官方原文佐證）。
  - 品牌驗證（domain ownership、隱私權政策等）官方頁面稱「typically takes 2-3 business days」。

**Q3 結論**：要讓自動上傳的影片維持公開狀態，**必須**完成 YouTube API 專屬的 compliance audit（否則一律鎖 private 且不可申訴）；若走生產環境且面向外部使用者，還需另外完成 Google Cloud OAuth 驗證（否則有 warning 畫面與 token 壽命限制）。兩者都是人工審核流程，官方都未承諾時限。

---

## Q4：Metadata 讀取（熱門影片資訊、留言、字幕）

| 資料 | 端點 | Units/call | 限制 |
|---|---|---|---|
| 標題/描述/標籤/時長/分類 | `videos.list`（part=snippet,contentDetails） | 1 | 公開資料，API Key 即可讀 |
| 觀看數/按讚數/留言數 | `videos.list`（part=statistics） | 1 | 同上 |
| 頻道資訊 | `channels.list` | 1 | 同上 |
| 留言 | `commentThreads.list` | 1 | 公開留言可讀；需注意留言相關的自動化行為受 Developer Policies 限制（見下） |
| 字幕/transcript | `captions.download` | 官方文件未給出與其他端點一致的 units 數字（見 Q2 表格附註） | **僅限自己有編輯權限的影片**——官方文件明載「requires the user to have permission to edit the video」，無法用官方 API 下載其他創作者影片的字幕/transcript |

來源：
- https://developers.google.com/youtube/v3/docs/videos/list
- https://developers.google.com/youtube/v3/docs/captions/download

**Q4 結論**：熱門影片的公開 metadata（標題、描述、標籤、觀看數、頻道資訊、留言）都能透過官方 API 合法讀取。但**字幕/transcript 讀取被鎖在「擁有編輯權限」的範圍內**，若架構設計中有「抓熱門 Shorts 的字幕來做二次創作腳本」這類需求，官方 API 做不到，只能：(a) 只處理自己頻道的影片，或 (b) 走非官方管道——但後者會直接牴觸 Developer Policies 的反爬蟲條款（見下方前置條件清單第 6 點），有帳號/專案被停權風險。

---

## Q5：API 金鑰申請流程與費用

來源：https://developers.google.com/youtube/v3/getting-started

流程：
1. Google 帳號 → Google Cloud Console 建立專案。
2. 在「Enabled APIs」頁面啟用 YouTube Data API v3。
3. 建立憑證：
   - **API Key**：僅供公開唯讀資料（如 `videos.list`、`search.list` 讀取公開資料）。
   - **OAuth 2.0 用戶端**：任何牽涉使用者授權的操作（含 `videos.insert` 上傳）都必須用這個，還要另外設定 OAuth consent screen。
4. 費用：**API 本身免費**，文件原文「All requests incur at least a one-point quota cost」，預設配額如 Q2 所述（100 + 100 + 10,000/天），無官方文件提及訂閱制或分級付費。加量需通過 audit（免費，但要通過審核）。

**Q5 結論**：申請流程與其他 Google API 一致，免費且無強制付費升級層級；唯一的「成本」是審核流程的時間與不確定性（Q3）。

---

## 「自動上傳到公開狀態」完整前置條件清單

1. Google Cloud 專案已建立，YouTube Data API v3 已啟用。（https://developers.google.com/youtube/v3/getting-started）
2. 已建立 **OAuth 2.0 用戶端**憑證（API Key 不能用於 `videos.insert`），scope 至少含 `youtube.upload`（需要編輯/字幕/回覆留言等額外操作時另需 `youtube.force-ssl` 或 `youtube`）。（https://developers.google.com/youtube/v3/docs/videos/insert）
3. **YouTube API 專屬 compliance audit 已通過**——這是公開上傳的硬性前提。2020-07-28 後建立、未過審的專案，不論 API 呼叫怎麼設定，影片一律被鎖 private 且不可申訴。（https://developers.google.com/youtube/v3/docs/videos/insert；https://support.google.com/youtube/answer/7300965）
4. 若面向多使用者/正式營運環境：Google Cloud **OAuth 應用程式驗證**也需完成，否則有 unverified-app 警告畫面與 refresh token 壽命限制，長期背景自動化（例如排程每日上傳）會因 token 過期而中斷。（https://support.google.com/cloud/answer/13464321）
5. 配額規劃：預設每日上限 100 支上傳（獨立配額桶），超過需另外送 Audit and Quota Extension Form 加量，官方未承諾審核時效。（https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits）
6. **內容政策合規**（獨立於 API 機制之外，但直接決定帳號存續）：
   - Developer Policies 明文禁止「未經使用者明確同意的自動化上傳/按讚/留言等動作」（Section III.I.2）、「爬取 YouTube 資料」（Section III.E.6）、「未經書面同意下載/備份 YouTube 影音內容」（Section III.E.1）、「建立可替代 YouTube 核心體驗的服務」（Section III.I.1）。（https://developers.google.com/youtube/terms/developer-policies）
   - 若「自動發現熱門 Shorts」的實作方式是**用官方 API 取公開 metadata 做選題參考**，屬合規；若是**直接下載他人影片檔案或字幕再重新上傳**，牴觸上述禁令。
   - 即使上傳機制合規，**產出內容本身**若落入 YouTube 的 Reused/Repetitious Content（垃圾內容）政策——例如「用自動化工具/AI 大量產出雷同內容、稍作修改」「原封不動重傳他人熱門影片、沒有加入原創轉化」——會導致該影片被取消營利資格、下架、警告，累積 3 次 90 天內警告會被終止頻道。這與 API 端的技術限制無關，是內容政策層級的風險。（https://support.google.com/youtube/answer/2801973）

---

## 驗收條件自評

- [x] Q1-Q5 每題先結論後論據，附官方來源 URL。
- [x] 明確列出「自動上傳到公開狀態」的完整前置條件清單（6 大項，含子項）。
- [ ] 部分數字（`captions.download` 精確 units 成本、testing OAuth app 的 refresh token 精確天數、testing 使用者人數上限）**官方文件本次查證未能取得精確原文**，已在報告中明確標註為「未確認/需另查」，未用臆測數字填補。

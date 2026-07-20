# 研究報告：RTX 5070 Ti 本機影片生成 vs 生圖+zoompan，以及紓壓 Shorts 環境音源

查證日期：2026-07-11。方法：官方 GitHub/HuggingFace/授權頁優先（WebFetch 實際開頁），社群實測次之（標註「⚠️社群二手」與可信度），查無則標「未查證」。本報告由 3 個平行 subagent 分頭查證（模型授權/相容性、16GB效能/workflow、環境音源）後彙整，並由主 agent 額外核實 PyTorch/Blackwell 支援時間線。

---

## 結論摘要（先講答案）

**(A) 本機影片生成 vs 生圖+zoompan**：
- **建議：以「生圖(FLUX.1/SDXL)＋ffmpeg zoompan」為全自動管線的主力**，理由是速度快 5-50 倍、失敗模式可預測（不會 OOM 卡在第 40 分鐘才發現失敗）、16GB 顯卡上穩定性最高。
- **本機影片生成模型「不成熟但可用」，非全面不可行**：若要加真動態，**CogVideoX-5B/1.5-5B**（16GB 餘裕最大、官方授權最寬鬆、直式 I2V 原生支援）與 **LTX-Video / LTX-2.3**（16GB 最省資源、速度最快，LTX-2.3 官方原生支援 9:16 直式）是兩個平衡點最好的候選，可作為「精選片段用真動態、其餘用 zoompan 湊量」的混合方案。
- **Wan 2.2 TI2V-5B** 是第三選擇（官方原生 9:16、Apache 2.0 授權最乾淨），但官方建議 24GB，16GB 需要量化才能跑，且與 HunyuanVideo 一樣在 Blackwell 上有零星 issue 回報。
- **不建議**：Mochi 1（專案疑似停滯 18+ 個月、16GB 是壓線邊緣、無直式/循環支援證據）、Step-Video-T2V／Open-Sora（VRAM 需求遠超 16GB）。
- **無縫循環影片**：查證不到任何模型有「一鍵做到首尾無縫」的官方功能，都是靠 VACE/latent-shift 等社群或學術技巧拼接，工程量不小；若管線需要循環播放的背景，**生圖+zoompan 搭配交叉溶接（crossfade）反而更容易做到無縫**。

**(B) 環境音源排序**（權重：合法商用 > 量大多樣 > 可程式化取得）：
1. **YouTube Audio Library**（第一層，先用免費且零風險的部分）——僅能手動下載，需人工/半自動預先建立素材庫，之後程式化調用本地檔案。
2. **Freesound.org API**（CC0/CC-BY 音效，程式化搜尋下載）——但**商業用途需與 UPF 另外協商**，這是四個來源中唯一有此限制的，需人工確認或改用其 CC0 子集並自行斟酌風險。
3. **ElevenLabs Sound Effects API**（付費方案）——生成式、無限多樣、可程式化批次，是解決「YouTube 反覆使用同一背景音」風險最直接的方法，但按量計費、且條款禁止把生成音效當 standalone 音效庫販售。
4. **Stable Audio API（platform.stability.ai）**——同樣生成式可程式化，Community License 年營收 <$100萬可商用，但條款細節較複雜（consumer 訂閱 vs API 授權不完全一致），建議與 ElevenLabs 並列為 AI 生成備援。
5. **Pixabay**——內容量大、授權寬鬆免掛名，但**完全沒有音效 API**，只能手動下載，不適合全自動規模化，建議僅作為人工預建素材庫的來源之一。

---

# (A) 本機開源影片生成模型

## A.1 對照表

| 模型 | 授權（商用結論） | 16GB VRAM 可行性 | 5秒 720p 生成時間量級 | 直式(9:16) | Blackwell(RTX 50) 相容性 |
|---|---|---|---|---|---|
| **Wan 2.1 / 2.2**（14B 或 TI2V-5B） | Apache 2.0，**完全自由商用** | 14B 需 GGUF 量化(Q4-Q6)+T5 offload；5B TI2V 官方建議24GB，16GB需量化 | 官方5B：<9分鐘(24GB卡)；社群14B/16GB：約5-15分鐘(⚠️來源矛盾，量級推估) | **官方原生支援**(720×1280等) | **有已知問題**：sm_120 錯誤、NVFP4量化載入失敗（官方/社群issue皆有），需cu128+ torch |
| **HunyuanVideo**（原版13B／1.5版8.3B） | Tencent Hunyuan Community License，**可商用但排除EU/UK/南韓＋MAU>1億需另洽** | 原版官方45-60GB不可行；1.5版官方無明確16GB數字，社群估算約10-13.6GB可行 | 官方原版(高階GPU)：~31.7分鐘；社群1.5版4090：~5分鐘(但同硬體另一使用者花1小時，變異極大) | **官方原生支援**(544×960/720×1280) | 未查證官方issue；社群部落格列為「Blackwell上smooth」 |
| **LTX-Video（原版）／LTX-2.3** | 原版權重授權未完全查證(HF標「other」)；**LTX-2.3為「年營收<$10M免費商用」授權(非OSI標準)** | **容易**：FP8/distilled版16-24GB可跑，官方稱2026年最省資源選項 | 社群數字差異大：數十秒(改裝48GB 4090)~數分鐘，另有45分-1小時的低信度數字；缺16GB卡一手數據 | **LTX-2.3官方原生支援**(最高1080×1920)；原版未查證 | **有已知問題**：官方repo有RTX 5090影像損毀/OOM issue |
| **CogVideoX**（2B / 5B / 1.5-5B） | 2B：Apache 2.0全自由；5B/1.5-5B：自訂授權，**需至bigmodel.cn註冊+月訪客量上限100萬次** | **容易**：官方BF16僅需5-10GB，16GB餘裕大 | 無16GB一手數字；A100/H100官方數字外推16GB卡約5-10分鐘(推論) | **I2V模式官方原生支援**彈性長寬比含直式；T2V僅固定橫式 | 未查證(查無任何相關GitHub issue或社群討論) |
| **Mochi 1**（Genmo） | Apache 2.0，可商用，但**專案疑似停滯18+個月**(最後重大更新2024-11) | **困難**：16GB為壓線邊緣值，官方原生要60GB/H100 | 無16GB一手數字；社群24GB卡(4090)：8-12分鐘(⚠️低信度) | 官方僅展示480p橫式，**未查證支援直式** | 未查證 |
| SkyReels-V2/V3 | 自訂Skywork License，條款未逐字查證 | 1.3B版540p約14.7GB(勉強可行)；14B版51GB(不可行) | 未查證 | 未查證 | 未查證 |
| Open-Sora 2.0 | 摘要為Apache 2.0(未逐字確認) | 官方建議≥24GB，超出16GB | 未查證 | 未查證 | 未查證 |
| Step-Video-T2V | 摘要為MIT(未逐字確認) | 官方需77-80GB，**直接排除** | 不適用 | 未查證 | 未查證 |
| EasyAnimate | 摘要為Apache 2.0(未逐字確認) | 官方最低16GB但複雜workflow建議24GB，餘裕極小；**已知issue：批次生成2-3支後VRAM未釋放OOM** | 未查證 | 未查證 | 未查證 |
| Kandinsky 5.0 Lite(2B) | 摘要為Apache 2.0(未逐字確認) | 12GB可跑(offload)，適合16GB卡 | 未查證 | 未查證 | 社群部落格列為「Blackwell上very smooth」 |

**表格使用提醒**：標「摘要為XX(未逐字確認)」的授權，在正式商用前務必自行打開該模型的官方 LICENSE 檔案逐字確認，本報告未對其做 WebFetch 逐字查證。

## A.2 各模型細節與來源

### Wan 2.1 / 2.2（阿里巴巴通義萬相）
- GitHub 組織：https://github.com/Wan-Video （官方，僅 Wan2.1/Wan2.2/Wan-skills/diffusers fork，**查無 Wan2.5/2.6/2.7 官方 repo**——網路上多篇宣稱「Wan 2.7 已開源」的文章互相矛盾且找不到官方佐證，判定為不可靠行銷內容，不採信）
- 授權：Apache 2.0，https://github.com/Wan-Video/Wan2.2/blob/main/LICENSE.txt （官方）
- 官方 VRAM：14B系列「至少80GB」；**TI2V-5B「至少24GB(如RTX 4090)」**，官方省顯存flag（`--offload_model True`、`--convert_model_dtype`、`--t5_cpu`）可在單卡9分鐘內出5秒720P影片。https://github.com/Wan-Video/Wan2.2 （官方README）
- 16GB量化路徑：city96 ComfyUI-GGUF（https://github.com/city96/ComfyUI-GGUF）、kijai ComfyUI-WanVideoWrapper 的 block swap（社群回報仍有OOM issue，如 #1267/#1644/#1769，https://github.com/kijai/ComfyUI-WanVideoWrapper）、QuantStack GGUF量化權重（https://huggingface.co/QuantStack/Wan2.2-TI2V-5B-GGUF，⚠️社群）
- ComfyUI官方教學：https://docs.comfy.org/tutorials/video/wan/wan2_2 （官方，稱5B版「應可在8GB VRAM用原生offload跑」）
- 直式：官方HF README列出720×1280、480×832、544×704等直式解析度。https://huggingface.co/Wan-AI/Wan2.1-I2V-14B-720P/blob/main/README.md
- 無縫循環：社群 VACE 拼接 workflow（ComfyUI官方workflow平台 https://comfy.org/workflows/template_sirolim_seamless_loop-31ea7d2d9224/ ；社群方案 https://openart.ai/workflows/nomadoor/loop-anything-with-wan21-vace/qz02Zb3yrF11GKYi6vdu ）——做得到但需額外拼接步驟，非官方一鍵功能。
- Blackwell問題：NVIDIA開發者論壇回報sm120錯誤（https://forums.developer.nvidia.com/t/newbie-wan-2-1-error-unsupported-cuda-architecture-sm120/325878）；ComfyUI官方repo issue回報NVFP4量化在RTX 5090載入失敗（https://github.com/Comfy-Org/ComfyUI/issues/11864）。

### HunyuanVideo（騰訊混元，原版13B + HunyuanVideo-1.5 8.3B）
- 原版：https://github.com/Tencent-Hunyuan/HunyuanVideo （官方，2024-12釋出，仍維護）；1.5版：https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5 （官方，2025-11-21釋出，主推輕量版）
- 授權：Tencent Hunyuan Community License（自訂，非Apache），LICENSE原文已逐字確認：https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5/blob/main/LICENSE 。**明文排除歐盟/英國/南韓使用**；被授權方MAU超過1億需另洽授權。個人小型YouTube頻道不受影響。
- 官方VRAM：原版720×1280×129幀峰值60GB，544×960×129幀峰值45GB（https://github.com/Tencent-Hunyuan/HunyuanVideo README，官方）——**遠超16GB**。1.5版官方README無明確VRAM數字表，社群估算約10-13.6GB(BF16/FP8+offload)，來源為內容農場網站，信度中低。
- 16GB量化：city96 HunyuanVideo-gguf（https://huggingface.co/city96/HunyuanVideo-gguf/discussions/4，模型作者本人回應，準官方）
- 速度：官方基準（單GPU，1280×720，129幀，50步）1904秒(~31.7分鐘)，8卡平行337.6秒（官方README）；1.5版社群HF discussion具名回報：RTX 4090約297秒/5秒影片，但同硬體另一使用者50步花了約3600秒——變異極大（https://huggingface.co/tencent/HunyuanVideo-1.5/discussions/3）
- 直式：官方README列544×960、720×1280等9:16選項（官方，https://github.com/Tencent-Hunyuan/HunyuanVideo）
- 無縫循環：kijai wrapper系列 `HyVideoLoopArgs` 節點（https://www.runcomfy.com/comfyui-nodes/ComfyUI-HunyuanVideoWrapper/hy-video-loop-args，⚠️社群）——非官方一鍵功能。
- Blackwell：官方文件未提及；社群部落格（https://lilting.ch/en/articles/comfyui-blackwell-gpu-compatibility）列HunyuanVideo-1.5 I2V為「Blackwell上smooth」的正面案例之一。

### LTX-Video（Lightricks）／LTX-2／LTX-2.3
- 原版：https://github.com/Lightricks/LTX-Video （2025-07最後版本v0.9.8，2025-10-23公告轉為LTX-2主線）；LTX-2：https://github.com/Lightricks/LTX-2 （2026-01-06發布，原生4K+同步音訊）；LTX-2.3：2026-03推出，https://ltx.io/model/ltx-2-3 （官方）
- 授權：原版repo程式碼LICENSE為Apache 2.0，但HF模型權重卡標示「other」授權（獨立PDF），**確切條款未查證成功**（WebFetch該PDF失敗）。**LTX-2為「LTX-2 Community License Agreement」**：年營收<$10M可免費商用，≥$10M需付費商業授權，違約有雙倍授權費罰則，且禁止用於與Lightricks商業產品直接競爭的產品。（https://github.com/Lightricks/LTX-2/blob/main/LICENSE，官方；說明：https://ltx.io/blog/ltx-licensing-explained）
- 16GB可行性：HF官方討論串確認6GB VRAM+16GB系統RAM可跑量化版（https://huggingface.co/Lightricks/LTX-Video/discussions/6，官方repo下團隊會回應的討論）；LTX-2.3官方FP8量化/distilled版可在16-24GB跑，ComfyUI v0.16.1+已有day-0官方支援（https://blog.comfy.org/p/ltx-23-day-0-supporte-in-comfyui，官方）
- 速度：官方repo issue具名回報13B模型在改裝48GB顯存4090上1216×704/88幀約2分8秒（https://github.com/Lightricks/LTX-Video/issues/166）；HF討論公版24GB 4090在512×512/121幀僅需11秒，H100僅需4秒（https://huggingface.co/Lightricks/LTX-Video/discussions/18）——**均缺乏16GB卡（如4070TiSuper/5070Ti）的一手實測**，另有信度低的說法稱一般本機需45分鐘-1小時，與上述數字矛盾，判斷為不可靠來源。
- 直式：**LTX-2.3官方原生支援最高1080×1920**（https://ltx.io/model/model-blog/ltx-2-3-portrait-video，官方）；原版未查證支援。
- 無縫循環：官方`LTXVLoopingSampler`節點（https://github.com/Lightricks/ComfyUI-LTXVideo/blob/master/looping_sampler.md，官方文件）**用途是長片分段生成，非首尾銜接無縫循環**——查證後**誠實結論：LTX未查證到真正的無縫循環方案**。
- Blackwell：官方LTX-2 repo有issue回報RTX 5090嚴重影像損毀（綠色偽影/近全灰輸出），懷疑是decode/color space在新架構的問題（https://github.com/Lightricks/LTX-2/issues/37，官方repo）；原版repo也有RTX 5090持續OOM的issue（https://github.com/Lightricks/LTX-Video/issues/171）。

### CogVideoX（智譜/Z.ai，原THUDM）
- GitHub已遷移至 https://github.com/zai-org/CogVideo （官方）
- 授權：CogVideoX-2B為Apache 2.0（HF model card逐字確認：https://huggingface.co/THUDM/CogVideoX-2b，官方）；5B/1.5-5B為自訂「CogVideoX LICENSE」，商用需至https://open.bigmodel.cn/mla/form 註冊，商業服務**月訪問量上限100萬次**，禁止軍事用途（https://github.com/zai-org/CogVideo/blob/main/MODEL_LICENSE，官方）
- 官方VRAM（GitHub README表格，官方，最詳細一手數據）：2B diffusers FP16最低4GB；5B BF16最低5GB；1.5-5B BF16最低10GB。**16GB卡餘裕大，甚至部分設定不需量化**。
- 速度（官方README表格，50步，5秒影片）：2B單A100約90秒/單H100約45秒；5B單A100約180秒/單H100約90秒；1.5-5B單A100約1000秒/單H100約550秒。無16GB消費卡一手數字，以算力比例外推16GB卡約5-10分鐘（推論非查證）。
- 直式：I2V模式官方支援彈性長寬比（min(W,H)=768，寬可到1360，接近9:16），1.5版I2V進一步支援任意長寬比含直式；T2V固定1360×768橫式（https://github.com/zai-org/CogVideo README，官方；補充：https://huggingface.co/docs/diffusers/en/api/pipelines/cogvideox 官方）
- 無縫循環：學術方法Mobius（"Text to Seamless Looping Video Generation via Latent Shift"）可套用於CogVideoX，透過latent shift策略達成真正首尾無縫，但**非現成ComfyUI節點，需自行整合程式碼**（論文：https://arxiv.org/html/2502.20307v1；作者實作：https://github.com/YisuiTT/Mobius）——是本次查證中**唯一有明確技術路徑可做到真無縫循環**的模型，但工程成本較高。
- Blackwell：查無任何相關GitHub issue或社群討論，**未查證**（非負面，是真的查無資料）。

### Mochi 1（Genmo）
- https://github.com/genmoai/mochi （官方，3.7k star，最後重大更新2024-11-26，截至2026-07已停滯超過1年8個月，官方部落格查無2025-2026後續更新消息，疑似事實上停止維護）
- 授權：Apache 2.0（GitHub+HF交叉確認：https://github.com/genmoai/mochi 、https://huggingface.co/genmo/mochi-1-preview）
- 官方VRAM：「單GPU約需60GB，建議至少1張H100」；ComfyUI優化可壓到20GB以下（官方部落格 https://blog.comfy.org/p/mochi-1 確認社群端有此優化，但16GB仍是壓線邊緣，非舒適值）。
- 直式：官方僅展示`height=480, width=848`橫式範例，**未查證到直式支援聲明**。
- 無縫循環：**未查證到任何專屬方案**。
- 結論：本次五個主要候選中資訊最不完整、專案活躍度最低的一個，不建議作為主力選擇。

### 其他2025-2026新模型（查證深度較淺，僅供延伸參考）
- **SkyReels-V2/V3**（Skywork AI）：https://github.com/SkyworkAI/SkyReels-V2 、https://github.com/SkyworkAI/SkyReels-V3 ，1.3B版540p約14.7GB峰值VRAM，勉強可塞16GB；授權條款未逐字查證。
- **Open-Sora 2.0**（hpcaitech）：https://github.com/hpcaitech/Open-Sora ，官方建議≥24GB（RTX 3090等級），超出16GB。
- **Step-Video-T2V**（StepFun）：https://github.com/stepfun-ai/Step-Video-T2V ，30B參數需77-80GB，直接排除。
- **EasyAnimate**（阿里PAI）：https://github.com/aigc-apps/EasyAnimate ，v5.1最低16GB但複雜workflow建議24GB；**已知issue：批次生成2-3支影片後VRAM未釋放導致OOM**（https://github.com/aigc-apps/EasyAnimate/issues/157，官方repo issue）——這對「全自動批次管線」是實質風險，需特別注意。
- **Kandinsky 5.0**（ai-forever）：https://github.com/kandinskylab/kandinsky-5 ，Lite(2B)版12GB可跑(offload)，社群部落格列為「Blackwell上very smooth」（https://lilting.ch/en/articles/comfyui-blackwell-gpu-compatibility）。

## A.3 Blackwell / RTX 5070 Ti 共通背景

- RTX 5070 Ti為Blackwell架構，compute capability **sm_120**（NVIDIA官方CUDA GPU清單：https://developer.nvidia.com/cuda-gpus）。
- **PyTorch對sm_120的官方stable支援時間線**（已由主agent二次核實，解決子agent回報的版本衝突）：PyTorch **2.9.0於2025-10-15發布**，首次在stable版納入Blackwell/sm_120支援，提供cu128與新增的cu130 wheel（來源：PyTorch官方dev-discuss發布公告 https://dev-discuss.pytorch.org/t/pytorch-2-9-0-general-availability/3251 ；PyTorch官方部落格 https://pytorch.org/blog/pytorch-2-9/ ；PyTorch官方GitHub issue討論 https://github.com/pytorch/pytorch/issues/164342 ）。**PyTorch 2.10排定2026-01-21發布**（https://dev-discuss.pytorch.org/t/pytorch-release-2-10-key-dates-updated/3259 ，官方）。在2025-10之前僅nightly build能偵測Blackwell GPU。
  - 註：本次查證過程中WebFetch直接抓取pytorch.org/get-started/locally頁面時一度回傳「stable為2.7.0」，與上述官方發布紀錄矛盾，判定為WebFetch摘要層的過期快取，**已用WebSearch交叉確認官方2.9.0(2025-10-15)/2.10(2026-01-21)的發布紀錄為準**。實際部署前建議直接在瀏覽器開啟pytorch.org確認當下最新stable版本號，但無論版本號為何，**只要選擇cu128以上的wheel即可涵蓋Blackwell支援**，這個結論已交叉確認、可信。
- 共通故障模式：多個模型repo的`requirements.txt`會鎖定較舊的torch版本（Wan要求≥2.4.0、HunyuanVideo建議2.6.0、LTX-Video要求≥2.1.2），naive `pip install`容易把Blackwell相容的torch悄悄降版覆蓋掉，導致「Unsupported CUDA architecture: sm_120」或「no kernel image」錯誤（社群整理：https://lilting.ch/en/articles/comfyui-blackwell-gpu-compatibility ，https://github.com/Comfy-Org/ComfyUI/discussions/6643 ）。**部署任何模型前，務必手動安裝cu128+版本的torch並鎖定，不要讓模型的requirements.txt反覆覆蓋。**

## A.4 對比基準：生圖(SDXL/FLUX)+ffmpeg zoompan vs 影片生成模型

**一手實測**（Mac Studio M1 Max，方法論可移植，⚠️社群二手但具名部落格+含實測數據）：
- 來源：Joche Ojeda，"Local AI Studio Part 5"，https://jocheojeda.com/2026/06/02/local-ai-studio-part-5-a-15-second-reel-when-not-to-use-a-video-model/
- SDXL生圖+ffmpeg zoompan：15秒成品總計約429秒（7分9秒，含生圖423秒+動態組裝+轉場）
- 影片生成模型（Wan2.1/LTX-Video）估計約90分鐘（估算，未實跑，需拼接多個4-5秒片段）
- **生圖+zoompan方案快約12.6倍**
- 該作者核心論點：影片模型用寫實影像訓練，若目標畫風非寫實（如扁平/剪紙風格），影片模型會把畫面「融化成寫實糊狀」，破壞原始畫風；生圖+ffmpeg對風格化內容的控制力更好。

**本報告數字重新量化（16GB卡情境，15秒短片估算）**：

| 方案 | 15秒短片估算總時間 |
|---|---|
| FLUX.1 dev FP8(RTX 4080 Super 16GB，⚠️社群Civitai實測，~24秒/張) + zoompan | 約2-3分鐘 |
| SDXL(⚠️社群，~11-12秒/張標準；Lightning 4步更快) + zoompan | 約1-2分鐘 |
| LTX-Video/2.3（16GB卡估，外推自4090/H100數字） | 約1.5-6分鐘（需3段拼接，信度中低） |
| Wan 2.2 14B GGUF/16GB卡 | 約15-45分鐘（來源數字矛盾，量級推估） |
| HunyuanVideo 1.5(4090) | 約15分鐘～3小時（變異極大） |

**結論**：生圖+zoompan在16GB卡上做15秒短片是**幾分鐘以內、最快且最可預測**的路徑；除LTX系列外，主流影片生成模型量級是「15分鐘到數小時」，慢5-50倍以上。品質上影片模型有真實運鏡/物理動態優勢，適合寫實紓壓場景，但生圖+zoompan速度、穩定性、風格可控性明顯更適合「全自動大量生產」的管線定位。**尚未查到針對「紓壓向YouTube Shorts」的專門評測**，此段結論的情境適配是推論延伸，非直接查證結果。

---

# (B) 環境音軌合法來源

## B.1 對照表

| 來源 | 授權可商用 | 環境音數量/多樣性 | 可程式化取得 | 備註 |
|---|---|---|---|---|
| **YouTube Audio Library** | 是（YPP營利明確允許；Standard授權免掛名，CC授權需掛名） | 未查證具體類別清單（僅知有Category篩選，官方未列Ambient/Nature等確切標籤） | **否**，僅YouTube Studio網頁手動下載；YouTube Data API v3無此端點 | 授權侷限於「用於YouTube上傳影片」，跨平台可攜性未經官方明文保證 |
| **Pixabay** | 是，免掛名歸屬 | 12萬+音效，可搜尋rain/ocean/forest等關鍵字 | **否**，官方API僅支援圖片與影片，**無音樂/音效端點** | 禁止「standalone」原封不動轉售音效；規模化只能網頁下載或自行承擔爬蟲違反ToS風險 |
| **Freesound.org** | 視個別音效授權（CC0/CC-BY可商用，CC-BY-NC不可商用） | 依關鍵字量大，含content-based搜尋 | 有官方API，但**條款明文「API僅限非商業用途免費」，商用需與UPF逐案協商** | 四者中唯一有「API商用需另外協商」的明確限制；CC-BY需掛名 |
| **ElevenLabs Sound Effects** | 付費方案(Starter以上)可商用；Free方案不可商用 | 生成式，理論上無限多樣 | 有官方API，付費即可程式化批次生成 | 禁止把生成音效當「standalone音效庫」轉售；嵌入影片發布的合規性為合理推論 |
| **Stable Audio(Stability AI)** | API/開源權重Community License年營收<$100萬可商用；stableaudio.com消費端Creator License明文排除Film/TV/advertisement與>10萬MAU商業產品 | 生成式，文字提示生成 | 有官方API(platform.stability.ai)，$0.20-0.26/次 | 兩套授權(consumer訂閱 vs API/開源)條款不完全一致，規模化前建議書面確認 |

## B.2 各來源細節與來源URL

### YouTube Audio Library
- 官方授權說明：https://support.google.com/youtube/answer/3376882?hl=en （官方，已WebFetch確認）——YPP營利影片可用；Standard授權免掛名，CC授權需在說明欄掛名創作者；下載內容不會被Content ID認領。
- 環境音類別清單：官方文件未列出精確類別標籤，**未查證**具體有無「Ambient/Nature」分類，需實際登入YouTube Studio查看。
- 程式化取得：YouTube Data API v3官方文件（https://developers.google.com/youtube/v3/docs）列出的所有資源類型中**沒有Audio Library端點**，僅有非官方第三方爬蟲專案（未經Google背書，不建議正式依賴）。

### Pixabay
- 官方授權條款：https://pixabay.com/service/terms/ （官方，已透過代理確認原文）——「irrevocable, worldwide, perpetual...royalty-free right...for commercial or non-commercial purposes」，免掛名。摘要頁：https://pixabay.com/service/license-summary/
- 限制：禁止「standalone」原封不動轉售音效內容，混入完整影片剪輯應屬允許範圍但條款未給YouTube Shorts的明確例外聲明。
- API：官方文件https://pixabay.com/api/docs/（已確認）**只有圖片與影片兩個端點，完全沒有音效/音樂API**，音效庫（https://pixabay.com/sound-effects/，12萬+筆）僅能網頁手動下載。

### Freesound.org
- 授權種類（官方FAQ已WebFetch確認：https://freesound.org/help/faq/）：CC0全自由商用；CC-BY需掛名（標題+創作者帳號+頁面連結+授權類型）；CC-BY-NC**不可商用**；Sampling+已停用。
- **關鍵風險**：官方API條款（https://freesound.org/help/tos_api/ 、https://freesound.org/docs/api/terms_of_use.html，皆已WebFetch確認）明文「You can use the Freesound API for free only for non-commercial purposes」，商用需與UPF（Universitat Pompeu Fabra）逐案協商——這代表用API規模化批次抓取素材供營利Shorts使用，字面上需要先協商，不能直接套用免費額度。
- API技術細節（https://freesound.org/docs/api/overview.html）：需API key，搜尋/預覽60次/分鐘、2000次/天；下載原始檔需OAuth2。

### ElevenLabs Sound Effects
- 定價：https://elevenlabs.io/pricing （官方，已確認）——Free $0(1萬credits，不可商用)、Starter $6/月起(3萬credits)。付費方案含Commercial License，已生成內容即使日後取消訂閱仍可繼續商用。
- Prohibited Use Policy：https://elevenlabs.io/use-policy （官方，已逐字確認）——禁止把Sound Effects輸出當「standalone」販售/建立音效庫/取樣庫；未明文禁止嵌入影片作品發布營利，但條款措辭聚焦在「銷售音效本身」，建議規模化前與客服書面確認一次。

### Stable Audio（Stability AI）
- 消費端 stableaudio.com 定價：https://stableaudio.com/pricing （官方，已確認）——Free不可商用；Pro $11.99/月起含Creator License，**明文排除「Film, TV, advertisement」與MAU>10萬的商業產品**，對規模化YouTube營利用途構成灰色地帶風險。
- 開發者API/開源權重：https://platform.stability.ai/pricing （官方，計費$0.20-0.26/次）；開源權重Stable Audio Open 1.0使用Stability AI Community License（https://huggingface.co/stabilityai/stable-audio-open-1.0/blob/main/LICENSE.md，官方逐字確認）——年營收<$100萬可免費商用，需標示「Powered by Stability AI」；總覽頁https://stability.ai/license 確認同一套邏輯適用於API。
- 兩套授權（consumer訂閱 vs API/開源）條款不完全一致，官方未有一頁交叉對照，**建議正式採用API路徑前以官方客服書面確認**。

## B.3 「量大多樣」風險評估（對應YouTube spam政策「跨大量影片用同一背景音樂」）

- **YouTube Audio Library**：音效庫規模未知確切數量，且僅能手動下載——若管線要生產大量影片，需人工預先建一批（例如50-100個環境音檔案）存本地素材庫輪替使用，程式化只能做「從本地素材庫隨機挑選」而非「即時向來源取得新素材」。
- **Freesound**：關鍵字搜尋可觸及的CC0/CC-BY音效數量龐大，多樣性最好，但API商用協商義務是主要障礙，建議優先篩選CC0授權子集降低法律風險，仍建議先發信協商。
- **ElevenLabs / Stable Audio**：**生成式方案是唯一能做到「真正無限多樣、每支影片可生成獨特音軌」的來源**，直接解決「同背景音跨大量影片」的演算法風險，是規模化管線在合規與多樣性之間的最佳解，代價是按次計費成本與需另外確認「嵌入影片發布」的合規細節。
- **Pixabay**：多樣性夠但無API，量產瓶頸在人工下載環節，適合作為補充素材庫而非主要規模化來源。

---

## 查證缺口與可信度總結

**未能完全查證項目**：
- LTX-Video原版權重的確切授權條款（HF標「other」，PDF無法讀取）。
- SkyReels/Open-Sora/Step-Video/EasyAnimate/Kandinsky 5.0的LICENSE原文逐字確認（僅有WebSearch摘要）。
- CogVideoX、SkyReels等模型在RTX 50系列上的相容性（查無任何討論，非負面結論，是真的查無資料）。
- YouTube Audio Library環境音類別的官方精確清單。
- ElevenLabs/Stable Audio「嵌入影片發布」是否完全排除於商用限制之外（條款文字聚焦standalone銷售，未見逐字例外聲明，屬合理推論）。

**資料可信度分層**：
- 高信度（官方一手，已WebFetch確認）：各模型官方GitHub README/LICENSE、HuggingFace官方model card、docs.comfy.org、blog.comfy.org、ltx.io官方部落格、PyTorch官方dev-discuss/blog、YouTube官方support頁、Pixabay/Freesound/ElevenLabs/Stability AI官方條款頁。
- 中信度（社群二手但具名可追溯）：HuggingFace discussions具名使用者、GitHub issues具名回報、Civitai具名文章、具名部落格(Joche Ojeda)、學術論文(Mobius)。
- 低信度（⚠️疑似AI內容農場，數字互相矛盾，僅供量級參考）：willitrunai.com、localaimaster.com、runaihome.com、apatero.com、compute-market.com、cogvideo.net——本報告中引用這些來源的具體數字均已標註警示符號，不建議下游直接引用其精確數字做決策依據。
- 最大資料缺口：**查無任何RTX 5070 Ti或近似的RTX 4070 Ti Super的一手實測數據**，所有速度數字都是從RTX 4080/4090/5090或A100/H100外推，這是本報告最大的限制，建議使用者在正式選定方案前，自行用實際硬體跑一次5秒測試影片驗證量級。

---

## 驗收條件逐條檢查

- (A) 對照表（模型×16GB可行性×5秒片速度×商用授權×直式支援）：**通過**，見A.1。
- (A) 明確推薦：**通過**，見結論摘要——推薦「生圖+zoompan為主力」，「CogVideoX/LTX-2.3為影片生成的兩個平衡點」。
- (B) 環境音來源推薦排序：**通過**，見結論摘要與B.3（YouTube Audio Library > Freesound > ElevenLabs > Stable Audio > Pixabay，依合法商用/量大多樣/可程式化三權重綜合排序）。
- 每個結論附官方來源：**大致通過**，多數結論附官方URL；少數項目（如部分2025-2026新模型的授權條款、部分速度數字）因查證深度限制只達WebSearch摘要或社群二手層級，均已明確標註信度與查證缺口，未查到的誠實標「未查證」而非編造。

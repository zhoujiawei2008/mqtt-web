# mqtt-py — 透過 MQTT 控制 Tasmota 智能插座

**兩個單檔 Python 工具，直接透過 MQTT Broker 驅動 Tasmota 智能插座：一個可腳本化的命令列，一個管理整排插座的瀏覽器面板。**

不需要 Home Assistant、不需要 Tasmota 內建網頁、不需要任何雲端帳號，也沒有安裝步驟——一個 `.py` 檔、一個相依套件、一個 Broker 就夠了。

```
python mqtt-cli.py on --device 6FCE2C
python mqtt-cli.py pulse --seconds 30
python mqtt-cli.py timer 3 --time 08:00 --days weekdays --action on --enable
python mqtt-web.py            # 然後開啟 http://127.0.0.1:8765/
```

---

## 什麼是 MQTT？

MQTT（Message Queuing Telemetry Transport）是一種輕量的**發布／訂閱（publish / subscribe）**訊息傳輸協定。它於 1999 年由 Andy Stanford-Clark 與 Arlen Nipper 設計，原本是為了讓衛星鏈路與油田感測器在**頻寬極小、連線極不穩定**的環境下也能把資料傳回去。如今它已是物聯網（IoT）領域最普遍的通訊協定之一，並成為 OASIS 的開放標準。

它和傳統「用戶端直接呼叫伺服器」的模式很不一樣，核心只有三個概念：

| 概念 | 說明 |
|---|---|
| **Broker（訊息中介）** | 一台中央伺服器，負責接收所有訊息並轉發給訂閱者。用戶端彼此**從不直接連線**，永遠只跟 Broker 對話 |
| **Topic（主題）** | 訊息的分類標籤，以 `/` 分層，例如 `tasmota_6FCE2C/stat/POWER`。發布者把訊息丟到某個主題，訂閱者可用萬用字元（`+` 代表單層、`#` 代表多層）一次訂閱一整批主題 |
| **Publish / Subscribe** | 發布者不知道誰在聽，訂閱者也不知道誰在講。這種**解耦**讓設備可以各自上下線，整個系統不會因此瓦解 |

為什麼智慧家居特別愛用 MQTT：

- **極省資源** — 封包標頭最小只要 2 個位元組，ESP8266 / ESP32 這類小晶片也跑得動
- **長連線加推播** — 裝置與 Broker 之間維持一條 TCP 連線，狀態一有變化就主動推播，不必反覆輪詢
- **服務品質等級（QoS）** — 可選 0（最多一次）、1（至少一次）、2（恰好一次），依可靠性需求取捨
- **Last Will（遺囑訊息）** — 裝置可預先註冊「如果我斷線了，請代我發出這則訊息」，用來判斷設備是否離線
- **Retained（保留訊息）** — Broker 會記住某個主題的最後一則訊息，新訂閱者一連上就立刻拿到當前狀態

**這兩個工具扮演的角色，就是 MQTT 的用戶端。** Tasmota 韌體本身也內建了 MQTT 用戶端，兩邊都連到同一台 Broker（例如 Mosquitto），靠主題名稱互相對話。這就是為什麼完全不需要向任何雲端服務註冊帳號——你的插座和你的電腦只要連得到同一台 Broker 就能通訊。工具送出指令時是往 `cmnd/tasmota_<ID>/POWER` 發布 `ON` / `OFF`，讀取狀態則是接收 `stat/tasmota_<ID>/...` 的回報。

---

## 為什麼寫成這樣

兩個工具都是**各自獨立的完整檔案**。每個檔案不從本專案匯入任何東西，所以你可以把 `mqtt-cli.py` 複製到另一台機器、改個名字、塞進批次檔，行為完全一樣。整個設計目標就是「沒有東西需要部署」：只要 Python 和 `paho-mqtt` 在，它就能跑。

這個限制也解釋了為什麼程式碼刻意寫得緊湊、註解卻很密——推理過程就放在它解釋的那段程式碼旁邊，因為沒有第二個檔案可以放它。

---

## 環境需求

| | |
|---|---|
| Python | 3.9 或更新版本 |
| 相依套件 | [`paho-mqtt`](https://pypi.org/project/paho-mqtt/) —— 1.x 與 2.x 皆支援 |
| Broker | 任何 MQTT Broker（Mosquitto、EMQX⋯⋯），實測以 Mosquitto 為主 |
| 裝置 | 已啟用 MQTT 的 Tasmota 韌體 |

```bash
pip install paho-mqtt
# 或
uv add paho-mqtt
```

若缺少 `paho-mqtt`，工具會明確告知並以代碼 `3` 結束，不會丟出一串難以理解的 traceback。

---

## 快速開始

### 1. 讓裝置連上你的 Broker

在 Tasmota 主控台設定 Broker，並保留預設的主題命名：

```
MqttHost    your.broker.example
MqttPort    1883
MqttUser    mqtt
MqttPassword ********
FullTopic   %prefix%/%topic%/
Topic       tasmota_%06X
```

`%06X` 是 Tasmota 開機時印出的晶片編號（`DVES_6FCE2C` → `6FCE2C`）。本專案所有工具都接受這個編號的各種寫法：

| 你輸入 | 實際使用的主題 |
|---|---|
| `6FCE2C` | `tasmota_6FCE2C` |
| `DVES_6FCE2C` | `tasmota_6FCE2C` |
| `0x6FCE2C` | `tasmota_6FCE2C` |
| `tasmota_6FCE2C` | `tasmota_6FCE2C` |
| `kitchen_plug` | `kitchen_plug`（原樣使用） |

### 2. 告訴工具 Broker 位在哪裡

可以下參數、可以設環境變數，也可以讓網頁面板自己寫一份設定檔：

```bash
export MQTT_HOST=your.broker.example
export MQTT_PORT=1883
export MQTT_USER=mqtt
export MQTT_PASS=your-password
export MQTT_DEVICE=6FCE2C
```

### 3. 執行

```bash
python mqtt-cli.py status --json      # 讀取繼電器狀態
python mqtt-cli.py on                 # 開啟
```

---

## 命令列工具 —— `cli/mqtt-cli.py`

單一檔案，所有設定都是參數。動作是**第一個位置參數**，且為必填。

```bash
python mqtt-cli.py <action> [index] [options]
```

### 動作一覽

| 動作 | 作用 |
|---|---|
| `on` | 開啟繼電器 |
| `off` | 關閉繼電器 |
| `toggle` | 翻轉繼電器 |
| `status` | 讀取目前狀態 |
| `pulse` | 開啟 `--seconds` 秒後自動關閉 |
| `pulseoff` | 關閉 `--seconds` 秒後自動開啟 |
| `timer` | 讀寫**單一**定時槽（1–16） |
| `timers` | 列出全部 16 個槽，或一次全部啟用／停用 |
| `time` | 檢視裝置時鐘與時區 |
| `diag` | 回報裝置硬體資訊 |

### 範例

```bash
# 繼電器
python mqtt-cli.py on  --device A1B2C3
python mqtt-cli.py off --device A1B2C3
python mqtt-cli.py status --json

# 讓它維持某個狀態一段時間，之後自動切回
python mqtt-cli.py pulse    --seconds 30        # 開 30 秒，然後關
python mqtt-cli.py pulseoff --seconds 120       # 關 2 分鐘，然後開

# 定時 —— 動作後面那個參數就是槽位 1..16
python mqtt-cli.py timer 3 --time 08:00 --days weekdays --action on --enable
python mqtt-cli.py timer 3 --time 18:30 --days Mon,Wed,Fri --action off --enable
python mqtt-cli.py timer 3 --mode sunset --time -0:30 --action on --enable
python mqtt-cli.py timer 3 --clear              # 清空該槽
python mqtt-cli.py timers                       # 列出全部 16 個槽
python mqtt-cli.py timers --enable-all          # 啟用所有槽
python mqtt-cli.py time --set-tz +8:00          # 定時用的是裝置本地時間
```

> **定時要真正觸發，全域 `Timers` 開關與該槽自己的 Enable 必須同時開啟。** 只寫入槽位是不夠的——記得執行 `python mqtt-cli.py timers --enable-all`。

### 參數

| 參數 | 意義 |
|---|---|
| `--device`、`-d`、`--chip-id`、`--topic` | 指定插座，可用上表任何一種寫法 |
| `--relay N` | 繼電器索引：`0` 代表全部（`POWER0`），`1` 代表 `POWER`，`n` 代表 `POWERn` |
| `--seconds N` | `pulse` / `pulseoff` 停留在另一狀態的秒數 |
| `--timer-index`、`--slot N` | 定時槽位，1–16 |
| `--time HH:MM` | 時鐘模式的時間，或日出／日落模式的 `+/-H:MM` 偏移量 |
| `--days ...` | `SMTWTFS` 遮罩、`Mon,Wed,Fri`、區間，或 `weekdays` / `weekend` / `all` |
| `--mode {clock,sunrise,sunset}` | 定時的基準時間 |
| `--action`、`--trigger {on,off,toggle,rule}` | 定時觸發時要執行什麼 |
| `--output N` | 要驅動的輸出口，1–16 |
| `--window N` | 隨機延遲分鐘數，0–15 |
| `--repeat` / `--once` | 每個符合的日子都觸發 / 只觸發一次後停用 |
| `--enable` / `--disable` / `--clear` | 啟用 / 停用 / 清空此槽 |
| `--enable-all` / `--disable-all` / `--toggle-all` | 全域 `Timers` 開關 |
| `--set-tz +8:00` | 設定裝置時區 |
| `--host`、`--port`、`--user`、`--password`、`--tls`、`--ca` | Broker 連線設定 |
| `--client-id`、`--retain`、`--timeout`、`--grace` | 底層 MQTT 微調 |
| `--json` | 輸出一行機器可讀的結果 |
| `-v`、`--verbose` | 將每一則 MQTT 訊息印到 stderr |

**結束代碼：** `0` 成功 · `1` 錯誤 · `2` 逾時 · `3` 缺少相依套件。

### 快捷腳本 —— 動作寫在檔名裡

`cli/` 內另有一組可以直接在檔案總管雙擊執行的腳本：

```
mqtt-6FCE2C-on.py            mqtt-6FCE2C-off.py
mqtt-6FCE2C-toggle.py        mqtt-6FCE2C-status.py
mqtt-6FCE2C-timer.py         mqtt-6FCE2C-timers.py
mqtt-6FCE2C-time.py          mqtt-6FCE2C-diag.py
mqtt-6FCE2C-pulse.py         mqtt-6FCE2C-pulseoff.py
mqtt-6FCE2C-pulseoff-120.py
```

**這些檔案裡沒有任何硬編碼——裝置與動作都是從檔名讀出來的。** 十一個檔案內容完全相同，改個名字就變成另一道指令：

```
mqtt-A1B2C3-off.py            ->  裝置 A1B2C3、動作 off
mqtt-kitchen_plug-on.py       ->  裝置 kitchen_plug、動作 on
mqtt-6FCE2C-pulseoff-120.py   ->  pulseoff 持續 120 秒（秒數寫在檔名裡）
6FCE2C_toggle.py              ->  開頭的 "mqtt-" 可以省略
```

檔名以**最後一個** `-` 或 `_` 切分，所以裝置名稱本身可以包含分隔符號。結尾的數字會被解讀為 `--seconds`，但只有在前一段是 `pulse` 或 `pulseoff` 時才成立——這正是讓名為 `plug2` 的裝置不會被誤讀成秒數的原因。

### `--json`

`--json` 讓工具變得可腳本化：每次執行輸出一行物件。

```json
{"device": "6FCE2C", "topic": "tasmota_6FCE2C", "action": "status", "state": "ON", "online": true, "source": "stat/tasmota_6FCE2C/STATUS", "ok": true, "note": null}
```

---

## 網頁面板 —— `web/mqtt-web.py`

一次管理**多個**插座。不同於命令列工具，它不從檔名取裝置，而是管理一份你在頁面上編輯的清單。

```bash
python mqtt-web.py
```

```
mqtt-py web panel -- managing 3 devices
list    : mqtt-web-devices.json
listen  : 0.0.0.0:8765
local   : http://127.0.0.1:8765/
network : http://192.168.1.23:8765/
Ctrl-C to stop.
```

### 頁面功能

| 分頁 | 內容 |
|---|---|
| **devices** | 左欄列出每一個序號及其備註，並顯示即時的 ONLINE / OFFLINE 與繼電器狀態。點一列即可控制該插座；編輯鈕可改序號或備註，不動其他設定 |
| **relay** | ON / OFF / TOGGLE，狀態直接從裝置讀回 |
| **energy** | 裝置自身的電錶：瓦數、電壓、電流、功率因數、視在／無效功率、今日與累計 kWh |
| **pulse** | 「維持某狀態 N 秒後切到另一狀態」。頁面不會等倒數結束——立刻返回並顯示截止時間 |
| **cycle** | 「開 N 秒、關 M 秒，無限循環」——適合魚缸燈或打氣機。定時槽一天只觸發一次、無法交替，所以這裡是用兩條互相重新武裝的 Tasmota RULE 實作；迴圈跑在**插座內部**，因此關掉瀏覽器或關機都不會停 |
| **timers** | 列出並編輯全部 16 個槽，外加一個掌管所有槽的全域 `Timers` 開關 |
| **clock** | 裝置的 UTC／本地時間與時區偏移，附一鍵 `+08:00` 修正 |
| **settings** | Broker 的主機、連接埠、TLS、帳號、密碼與逾時——儲存後立即生效，不需重啟 |
| **account** | 變更自己的密碼或電子郵件、登出 |

### 帳號機制

每個人進站都會先看到登入頁，而登入之後的**任何內容**都不會在沒有工作階段的情況下送到瀏覽器——包括序號，甚至連通往這些序號的按鈕的 HTML 都不會。

- 註冊需要名稱、電子郵件與密碼（至少 8 個字元）。
- 空白面板中的第一個帳號會接收舊的 `mqtt-web-devices.json`（改名為 `.adopted`，不是刪除），所以升級不會遺失任何東西。
- 每個帳號擁有**自己的**裝置清單檔案 `mqtt-web-users/<name>.json`。兩個人可以從同一個面板管理不同的插座，彼此看不到對方的序號。
- 密碼以 **PBKDF2-HMAC-SHA256** 加每個帳號獨立的隨機鹽儲存，絕不存明文，也絕不回傳到瀏覽器。
- 工作階段權杖只存在**記憶體**中，閒置 12 小時後過期——重啟面板即讓所有人登出。
- 同一個名稱連續輸入 8 次錯誤密碼，該名稱將被冷卻 5 分鐘；無論名稱是否存在，登入的回應都完全一致。
- `--no-register` 可在家人帳號都建好之後關上大門。
- `--no-auth` 則完全移除鎖，回到舊的單一共用清單——只適合放在沒有其他人能碰到的機器上。

### 它多常跟插座講話

有三件事會按時去碰裝置，各有自己的參數：

| 節拍 | 參數 | 預設 | 涵蓋範圍 |
|---|---|---|---|
| 聚焦 | `--refresh` | 8 秒 | 你正在看的裝置 |
| 電錶 | `--energy` | 5 秒 | 該裝置的功率、電壓、電流、kWh |
| 掃描 | `--sweep` | 45 秒 | 整份清單，一次一個裝置 |

同一個插座的每次讀取都走**同一條佇列**，所以這三個節拍並非各自獨立：把 `--energy` 調得比 `--refresh` 更小，並不會讓電錶更新，只會讓繼電器狀態讀得更慢。每個節拍都會等到自己的回覆才再問下一次——過去一則緩慢的回覆會讓下一個請求疊在未回覆的請求上，而那條不斷長大的佇列其實是面板自己造成的，結果就是一台健康的插座在慢速 Broker 上被誤判為故障。按下按鈕時，繼電器節拍會降到 1 秒並維持數秒。如果 Broker 距離較遠，或有多個瀏覽器分頁盯著同一個裝置，請調高 `--refresh` 與 `--energy`。

### 面板參數

```
--port 8080          改用其他連接埠
--localhost          只監聽本機（127.0.0.1）
--listen 0.0.0.0     可供區域網路存取（預設）
--list FILE          使用其他裝置清單檔案
--settings FILE      把 Broker 設定放在別處
--users FILE         把帳號資料放在別處
--open               自動開啟瀏覽器
--token SECRET       要求網址帶上 ?token=SECRET
--read-only          頁面以唯讀模式開啟
--no-auth            不登入：所有人共用一份清單
--no-register        不允許再建立帳號
--max-devices 32     超過此數量就拒絕管理
--refresh 8          兩次讀取「開啟中」裝置之間的秒數
--sweep 45           兩趟掃描整份清單之間的秒數
--energy 5           兩次讀取「開啟中」電錶之間的秒數
--help               完整清單，含所有 MQTT 參數
```

之所以有 `--max-devices`，是因為**每一個受管理的裝置都佔一條自己的 MQTT 連線**，數量同時也是執行緒數量。這個上限可以避免一次打錯的匯入嘗試開啟數千個 socket。

---

## 安全性須知 —— 請務必閱讀

**這是區域網路工具，請以區域網路工具的方式對待它。**

- 面板預設綁定 **`0.0.0.0`**。區域網路上任何東西都連得到；若路由器把連接埠轉發出去，甚至可能來自網際網路。連到的雖然只是*登入頁*，但若不需要區域網路存取，請改用 `--localhost`。
- **沒有 TLS**。密碼與工作階段權杖都是明文傳輸。在可信任的區域網路內沒問題，放到網際網路上則不行。若面板必須從外部連線，請置於反向代理加 HTTPS 之後，而不是直接暴露這個連接埠。
- Broker 設定檔中的 **MQTT 密碼以明文儲存**——請像對待密碼一樣對待 `mqtt-web-settings.json`。它永遠不會被交回瀏覽器：欄位一開啟就是空的，留空即保留已儲存的那一組。
- `--no-auth` 會讓任何能連到面板的人切換**任何**繼電器。
- 在 Windows 上，首次的連入連線可能還需要為該連接埠加一條防火牆規則。

本儲存庫**不含任何憑證**。Broker 主機、其位址與密碼在發布前都已替換為佔位符——詳見 `tools/export.sh`，它會在執行時從私有的工作副本中讀出這些值，只要有任何一項殘留就拒絕產出。

---

## 常見問題排除

**繼電器沒有回應。** 在某些韌體上，relay 1 未註冊時 `POWER` 不會有任何回覆。工具會退回使用 `POWER0`，然後改為輪詢 `Status 0`，而不是空等回應——所以靜默的指令仍會得到答案，只是晚一秒。

**`StatusSNS` 回傳 "Unknown"。** `StatusSNS` 是回覆中的*欄位名稱*，不是指令。發布它會讓裝置回答 `Unknown`。讀取電量請用 `Status 8`，面板也是這樣做的。

**08:00 的定時在北京時間 15:00 觸發。** 定時用的是**裝置本地時間**。請到 clock 分頁套用 `+08:00` 修正，或執行：
`python mqtt-cli.py time --set-tz +8:00`。

**定時設好了卻從不觸發。** 全域 `Timers` 開關與該槽的 Enable 必須**兩者都開**。執行 `python mqtt-cli.py timers --enable-all`。

**插座顯示 OFFLINE 但實際上可以控制。** 請調高 `--refresh` / `--energy`，或關掉盯著同一裝置的多餘瀏覽器分頁——每個裝置只有一條佇列，而每個分頁都會往裡面加讀取。

---

## 專案結構

```
.
├── cli/
│   ├── mqtt-cli.py                 # 參數驅動的命令列工具（單檔、完整）
│   ├── mqtt-6FCE2C-*.py            # 11 個快捷腳本，動作寫在檔名裡
│   └── mqtt-CLI-使用说明.pdf        # 命令列中文手冊
├── web/
│   ├── mqtt-web.py                 # 瀏覽器面板（單檔、完整）
│   ├── mqtt-web-使用说明.pdf        # 面板中文手冊
│   └── examples/
│       ├── mqtt-web-settings.example.json
│       └── mqtt-web-devices.example.json
├── tools/
│   └── export.sh                   # 從私有工作副本建出這棵樹
└── README.md
```

`cli/` 與 `web/` 下的兩份 PDF 是原始的圖文手冊（簡體中文），內容與本文件一致，適合拿給不寫程式的人看。本 README 是行為的正式參考。

---

## 授權條款

MIT —— 詳見 [LICENSE](LICENSE)。

Tasmota 是 Theo Arends 與其貢獻者所開發的獨立專案，以 GPL-3.0 授權。本儲存庫只使用它的 MQTT 協定，不含任何 Tasmota 程式碼。

---

## 署名

**HK OCEAN TECHNOLOGY DEVELOPMENT CO., LTD** 是一家充滿活力的初創科技企業，總部位於亞洲國際金融中心——中國香港。我們致力於為全球客戶提供創新、可靠的綜合性技術解決方案，成為您值得信賴的科技合作夥伴。

作為一家新興的科技公司，我們集結了一批充滿熱情且經驗豐富的技術專家，專注於軟體開發、積體電路設計、網絡維護、網頁設計以及電子產品銷售等多元化業務領域。我們以客戶需求為核心，結合前沿技術與創新思維，為企業量身打造最適合的數位化轉型方案。

### 核心業務

**軟體開發** — 我們提供從企業級應用程式到行動 App 的全方位軟體開發服務，涵蓋系統架構設計、資料庫開發、雲端部署及資訊安全等領域。

**積體電路設計** — 專業的 IC 設計團隊為您提供從概念構思到量產的完整積體電路解決方案，運用先進的半導體技術確保產品效能與品質。

**網絡維護** — 可靠的網絡基礎設施支援與維護服務，包括網絡安全監控、系統效能優化及全天候技術支援，確保您的業務穩定運行。

**網頁設計** — 現代化、響應式的網頁設計服務，從 UI/UX 設計到全端開發，為您打造具吸引力且使用者友好的數位體驗。

**電子產品銷售** — 優質電子元件與產品的採購服務，連接全球可信賴的製造商與供應商，滿足您多樣化的採購需求。

### 發展理念

我們秉承「技術連接未來」的發展理念，深信科技創新是推動商業進步的關鍵動力。作為初創企業，我們具備高度的靈活性與快速的響應能力，能夠迅速適應市場變化並提供更具成本效益的解決方案。

未來，公司將繼續深耕技術領域，不斷拓展業務範圍，致力於成為全球客戶首選的綜合科技解決方案提供商。我們期待與您攜手合作，共創雙贏的美好未來。

### 聯繫方式

HK Ocean Technology Development Co., Limited

- **中文地址：** 香港九龍新蒲崗彩虹道 206-208 號盛景工業大廈 1 樓 B19 室
- **英文地址：** Room B19 1/F, Shing King Ind. Bldg., 206-208 Choi Hung Road, San Po Kong, Kowloon, Hong Kong

# mqtt-py — Tasmota Plug Control over MQTT

**Two single-file Python tools that drive Tasmota smart plugs through an MQTT
broker: a scriptable command line, and a browser panel for a whole shelf of them.**

No Home Assistant. No Tasmota web server. No cloud account. No install step — one
`.py` file, one dependency, and a broker.

```
python mqtt-cli.py on --device 6FCE2C
python mqtt-cli.py pulse --seconds 30
python mqtt-cli.py timer 3 --time 08:00 --days weekdays --action on --enable
python mqtt-web.py            # then open http://127.0.0.1:8765/
```

---

## Why it looks like this

Both tools are **complete on their own**. Each file imports nothing from this
repository, so you can copy `mqtt-cli.py` to another machine, rename it, drop it
in a batch file, and it still behaves exactly the same. The whole point is that
there is nothing to deploy: if Python and `paho-mqtt` are there, it runs.

That constraint is also why the code is deliberately dense and heavily
commented — the reasoning lives next to the code it explains, because there is no
second file to put it in.

---

## Requirements

| | |
|---|---|
| Python | 3.9 or newer (f-strings, `from __future__ import annotations`) |
| Dependency | [`paho-mqtt`](https://pypi.org/project/paho-mqtt/) — 1.x and 2.x both supported |
| Broker | Any MQTT broker (Mosquitto, EMQX, ...). Tested against Mosquitto |
| Device | Tasmota firmware with MQTT enabled |

```bash
pip install paho-mqtt
# or
uv add paho-mqtt
```

If `paho-mqtt` is missing the tools say so and exit with code `3` — they never
fail with a bare traceback.

---

## Quick start

### 1. Point the device at your broker

In the Tasmota console, set the broker and keep the topic scheme the default:

```
MqttHost    your.broker.example
MqttPort    1883
MqttUser    mqtt
MqttPassword ********
FullTopic   %prefix%/%topic%/
Topic       tasmota_%06X
```

`%06X` is the chip id Tasmota prints on boot (`DVES_6FCE2C` → `6FCE2C`). Every
tool here accepts that id in any spelling:

| You type | Topic used |
|---|---|
| `6FCE2C` | `tasmota_6FCE2C` |
| `DVES_6FCE2C` | `tasmota_6FCE2C` |
| `0x6FCE2C` | `tasmota_6FCE2C` |
| `tasmota_6FCE2C` | `tasmota_6FCE2C` |
| `kitchen_plug` | `kitchen_plug` (verbatim) |

### 2. Give the tools the broker endpoint

Either pass flags, or export environment variables, or (for the web panel) let it
write a settings file:

```bash
export MQTT_HOST=your.broker.example
export MQTT_PORT=1883
export MQTT_USER=mqtt
export MQTT_PASS=your-password
export MQTT_DEVICE=6FCE2C
```

### 3. Run

```bash
python mqtt-cli.py status --json      # read the relay
python mqtt-cli.py on                 # switch it
```

---

## The command line — `cli/mqtt-cli.py`

One file, everything is an argument. The action is the **first positional
argument** and is required.

```bash
python mqtt-cli.py <action> [index] [options]
```

### Actions

| Action | What it does |
|---|---|
| `on` | Turn the relay on |
| `off` | Turn the relay off |
| `toggle` | Flip the relay |
| `status` | Read the current state |
| `pulse` | On for `--seconds`, then off again |
| `pulseoff` | Off for `--seconds`, then on again |
| `timer` | Read or write **one** timer slot (1–16) |
| `timers` | List all 16 slots, or arm/disarm every slot at once |
| `time` | Inspect the device clock and time zone |
| `diag` | Report the device hardware |

### Examples

```bash
# Relay
python mqtt-cli.py on  --device A1B2C3
python mqtt-cli.py off --device A1B2C3
python mqtt-cli.py status --json

# Park it in one state for a while, then move it back
python mqtt-cli.py pulse    --seconds 30        # on 30 s, then off
python mqtt-cli.py pulseoff --seconds 120       # off 2 min, then on

# Timers -- slot 1..16 is the argument after the action
python mqtt-cli.py timer 3 --time 08:00 --days weekdays --action on --enable
python mqtt-cli.py timer 3 --time 18:30 --days Mon,Wed,Fri --action off --enable
python mqtt-cli.py timer 3 --mode sunset --time -0:30 --action on --enable
python mqtt-cli.py timer 3 --clear              # empty the slot again
python mqtt-cli.py timers                       # list all 16 slots
python mqtt-cli.py timers --enable-all          # arm every slot
python mqtt-cli.py time --set-tz +8:00          # timer times are DEVICE local
```

> **A timer only fires when the global `Timers` switch *and* the slot's own
> Enable are both on.** Writing a slot is not enough — remember
> `python mqtt-cli.py timers --enable-all`.

### Flags

| Flag | Meaning |
|---|---|
| `--device`, `-d`, `--chip-id`, `--topic` | Which plug. Any spelling from the table above |
| `--relay N` | Relay index: `0` = all (`POWER0`), `1` = `POWER`, `n` = `POWERn` |
| `--seconds N` | How long `pulse` / `pulseoff` stay in the other state |
| `--timer-index`, `--slot N` | Timer slot, 1–16 |
| `--time HH:MM` | Clock mode, or `+/-H:MM` offset for sunrise/sunset |
| `--days ...` | `SMTWTFS` mask, `Mon,Wed,Fri`, a range, or `weekdays` / `weekend` / `all` |
| `--mode {clock,sunrise,sunset}` | The timer's time base |
| `--action`, `--trigger {on,off,toggle,rule}` | What the timer fires |
| `--output N` | Output to drive, 1–16 |
| `--window N` | Random jitter in minutes, 0–15 |
| `--repeat` / `--once` | Keep firing every matching day / fire once and disarm |
| `--enable` / `--disable` / `--clear` | Arm / disarm / wipe this slot |
| `--enable-all` / `--disable-all` / `--toggle-all` | The global `Timers` switch |
| `--set-tz +8:00` | Set the device time zone |
| `--host`, `--port`, `--user`, `--password`, `--tls`, `--ca` | Broker endpoint |
| `--client-id`, `--retain`, `--timeout`, `--grace` | Low-level MQTT knobs |
| `--json` | One line of machine-readable output |
| `-v`, `--verbose` | Print every MQTT message on stderr |

**Exit codes:** `0` ok · `1` error · `2` timeout · `3` missing dependency.

### The shortcut scripts — action baked into the file name

`cli/` also contains per-device scripts you can double-click in Explorer:

```
mqtt-6FCE2C-on.py            mqtt-6FCE2C-off.py
mqtt-6FCE2C-toggle.py        mqtt-6FCE2C-status.py
mqtt-6FCE2C-timer.py         mqtt-6FCE2C-timers.py
mqtt-6FCE2C-time.py          mqtt-6FCE2C-diag.py
mqtt-6FCE2C-pulse.py         mqtt-6FCE2C-pulseoff.py
mqtt-6FCE2C-pulseoff-120.py
```

**Nothing is hard-coded in them — the device and the action come from the file
name.** All eleven files are byte-identical. Rename one and it becomes a
different command:

```
mqtt-A1B2C3-off.py            ->  device A1B2C3, action off
mqtt-kitchen_plug-on.py       ->  device kitchen_plug, action on
mqtt-6FCE2C-pulseoff-120.py   ->  pulseoff for 120 s (a duration in the name)
6FCE2C_toggle.py              ->  the leading "mqtt-" is optional
```

The name is split at the **last** `-` or `_`, so a device name may itself contain
separators. A trailing number is read as `--seconds`, but only when the segment
before it is `pulse` or `pulseoff` — which is what keeps a device called `plug2`
from being misread as a duration.

### `--json`

`--json` makes the tool scriptable: one object per run, on one line.

```json
{"device": "6FCE2C", "topic": "tasmota_6FCE2C", "action": "status", "state": "ON", "online": true, "source": "stat/tasmota_6FCE2C/STATUS", "ok": true, "note": null}
```

---

## The web panel — `web/mqtt-web.py`

A browser control panel for **many** plugs at once. Unlike the CLI, this one does
not take its device from its file name — it manages a list you edit in the page.

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

### What the page does

| Tab | Contents |
|---|---|
| **devices** | Left column lists every serial with its note and live ONLINE/OFFLINE + relay state. Click a row to control it; the edit button renames it or changes the serial |
| **relay** | ON / OFF / TOGGLE, state read straight back off the device |
| **energy** | The device's own meter: watts, voltage, current, power factor, apparent/reactive power, today's and total kWh |
| **pulse** | "Hold one state for N seconds, then the other." Returns immediately and shows the deadline |
| **cycle** | "On for N seconds, off for M, forever" — a fish tank light or air pump, written as two Tasmota RULES that re-arm each other, so the loop lives **inside the plug** and survives closing the browser |
| **timers** | All 16 slots listed and editable, plus the one global `Timers` switch that gates them all |
| **clock** | Device UTC / local time / timezone, with the one-click `+08:00` fix |
| **settings** | Broker host, port, TLS, user, password, timeout — applied immediately, no restart |
| **account** | Change your password or email, sign out |

### Accounts

Everybody meets a login page first, and **nothing** behind it is served without a
session — not the serials, not even the markup of the buttons that reach them.

- Registration asks for a name, an email and a password (8 characters minimum).
- The first account in an empty panel adopts the old `mqtt-web-devices.json`
  (renamed to `.adopted`, not deleted), so upgrading loses nothing.
- Each account owns its **own** device list file, `mqtt-web-users/<name>.json`.
  Two people manage different plugs from one panel and neither sees the other's.
- Passwords are **PBKDF2-HMAC-SHA256** with a per-account random salt, never
  stored in plain text and never sent back to a browser.
- Sessions are random tokens held **in memory**, expiring after 12 hours of quiet
  — restarting the panel signs everybody out.
- Eight wrong passwords for one name buys that name a five-minute cool-down, and
  login answers identically whether the name exists or not.
- `--no-register` closes the door once your household is set up.
- `--no-auth` removes the lock entirely and restores the old single shared list —
  only sensible on a machine nobody else can reach.

### How often it talks to the plugs

Three things touch a device on a timer, each with its own flag:

| Beat | Flag | Default | Covers |
|---|---|---|---|
| Focus | `--refresh` | 8 s | the device you are looking at |
| Meter | `--energy` | 5 s | power, voltage, current, kWh of that device |
| Sweep | `--sweep` | 45 s | the whole list, one device at a time |

Every read of one plug goes through **one queue**, so these beats are not
independent: making `--energy` smaller than `--refresh` does not make the meter
fresher, it only makes the relay state read slower. Each beat waits for its own
answer before asking again — a slow reply used to let requests stack up, and the
queue that grew was the panel's own doing, so a healthy plug on a slow broker
looked like a broken one. A button press drops the relay beat to 1 s for a few
seconds. Raise `--refresh` and `--energy` if the broker is far away or several
tabs watch the same device.

### Panel flags

```
--port 8080          listen somewhere else
--localhost          this machine only (127.0.0.1)
--listen 0.0.0.0     reachable from the LAN (the default)
--list FILE          a different device list file
--settings FILE      keep the broker settings somewhere else
--users FILE         keep the accounts somewhere else
--open               launch the browser for you
--token SECRET       require ?token=SECRET
--read-only          the page comes up in view-only mode
--no-auth            no login: one shared list for everybody
--no-register        nobody can create another account
--max-devices 32     refuse to manage more than this many
--refresh 8          seconds between two reads of the OPEN device
--sweep 45           seconds between two passes over the whole list
--energy 5           seconds between two reads of the OPEN meter
--help               the full list, including every MQTT flag
```

`--max-devices` exists because **every managed device holds its own MQTT
connection**, so the count is also a thread count. The cap keeps a mistyped
import from trying to open thousands of sockets.

---

## Security — please read

**This is a LAN tool. Treat it that way.**

- The panel binds to **`0.0.0.0` by default**. Anything on your LAN can reach it,
  and on a router that forwards the port, potentially the Internet. What it
  reaches is the *login page* — but use `--localhost` if you do not need LAN
  access.
- There is **no TLS**. Passwords and session tokens travel in clear text. Fine on
  a trusted LAN, not fine over the Internet. If the panel must be reachable from
  outside, put it behind a reverse proxy with HTTPS instead of exposing this port.
- The **broker settings file stores the MQTT password in plain text** — treat
  `mqtt-web-settings.json` the way you would treat a password. It is never handed
  back to the browser: the field comes up empty, and leaving it empty keeps the
  saved one.
- `--no-auth` lets anyone who can reach the panel switch **any** relay.
- On Windows the first inbound connection may also need a firewall rule for the
  port.

This repository contains **no credentials**. The broker host, its address and the
password were replaced by placeholders before publication — see
`tools/export.sh`, which reads the values out of the private working copy at run
time and refuses to emit a tree if anything survives.

---

## Troubleshooting

**The relay does not answer.** Firmwares where relay 1 is not registered reply to
`POWER` with nothing. The tools fall back to `POWER0` and then poll `Status 0`
instead of waiting for an echo — so a silent command still produces an answer,
just a second later.

**`StatusSNS` returns "Unknown".** `StatusSNS` is the *key inside* a reply, not a
command. Publishing it makes the device answer `Unknown`. Use `Status 8` for the
energy report, which is what the panel does.

**A 08:00 timer fires at 15:00 Beijing time.** Timer times are **device local
time**. Check the clock tab and apply the `+08:00` fix:
`python mqtt-cli.py time --set-tz +8:00`.

**A timer is set but never fires.** The global `Timers` switch and the slot's own
Enable must **both** be on. Run `python mqtt-cli.py timers --enable-all`.

**A plug shows as OFFLINE but the app works.** Raise `--refresh` / `--energy`, or
close extra browser tabs watching the same device — every device has one queue,
and every tab adds reads to it.

---

## Repository layout

```
.
├── cli/
│   ├── mqtt-cli.py                 # the argument-driven CLI (one file, complete)
│   ├── mqtt-6FCE2C-*.py            # 11 shortcut scripts, action in the file name
│   └── mqtt-CLI-使用说明.pdf        # Chinese manual for the CLI
├── web/
│   ├── mqtt-web.py                 # the browser panel (one file, complete)
│   ├── mqtt-web-使用说明.pdf        # Chinese manual for the panel
│   └── examples/
│       ├── mqtt-web-settings.example.json
│       └── mqtt-web-devices.example.json
├── tools/
│   └── export.sh                   # build this tree from a private working copy
└── README.md
```

The Chinese PDFs are the original illustrated manuals. The English README is the
canonical reference for behaviour; the PDFs are the friendliest way to get a
non-programmer started.

---

## 中文说明

**两个单文件 Python 工具，通过 MQTT 控制 Tasmota 智能插座：一个可脚本化的
命令行，一个管理多插座的浏览器面板。**

不需要 Home Assistant、不需要 Tasmota 自带网页、不需要任何云账号，也没有安装
步骤 —— 一个 `.py` 文件、一个依赖库、一个 MQTT broker 就够了。

### 环境要求

Python 3.9+ 与 `paho-mqtt`（1.x / 2.x 均可），以及一个 Tasmota 已接入 MQTT 的
插座。

```bash
pip install paho-mqtt
```

### 命令行用法

动作是**第一个位置参数**，必填：

```bash
python mqtt-cli.py on                     # 开
python mqtt-cli.py off --device A1B2C3    # 关
python mqtt-cli.py status --json          # 读状态（JSON 单行输出）
python mqtt-cli.py pulse --seconds 30     # 开 30 秒后自动关
python mqtt-cli.py toggle                 # 翻转
python mqtt-cli.py timer 3 --time 08:00 --days weekdays --action on --enable
python mqtt-cli.py timers                 # 列出全部 16 个定时槽
python mqtt-cli.py time --set-tz +8:00    # 定时用的是设备本地时间
python mqtt-cli.py diag                   # 硬件信息
```

十个动作：`on` / `off` / `toggle` / `status` / `pulse` / `pulseoff` / `timer` /
`timers` / `time` / `diag`。退出码：`0` 成功 · `1` 出错 · `2` 超时 · `3` 缺依赖。

### 快捷脚本：把动作写进文件名

`cli/` 里的 11 个 `mqtt-6FCE2C-*.py` **内容完全相同** —— 设备和动作是从
**文件名**读出来的，在资源管理器里直接双击就能用。改名即成新命令：

| 文件名 | 效果 |
|---|---|
| `mqtt-6FCE2C-on.py` | 设备 6FCE2C，开 |
| `mqtt-A1B2C3-off.py` | 设备 A1B2C3，关 |
| `mqtt-6FCE2C-pulseoff-120.py` | 关 120 秒后自动开（时长写在名字里） |
| `6FCE2C_toggle.py` | 前缀 `mqtt-` 可以省略 |

名字按**最后一个** `-` 或 `_` 切分，所以设备名里可以带分隔符。结尾的数字只有在
前一段是 `pulse` / `pulseoff` 时才当作秒数，因此叫 `plug2` 的设备不会被误读。

### 浏览器面板用法

```bash
python mqtt-web.py            # 然后打开 http://127.0.0.1:8765/
```

面板包含设备列表、开关、电量计（功率 / 电压 / 电流 / 功率因数 / kWh）、
Pulse、Cycle（在插座内部循环，关掉浏览器也继续跑）、16 个定时槽、设备时钟和
broker 设置。**每个账号有自己独立的设备清单**，互相看不到对方的序列号；密码用
PBKDF2-HMAC-SHA256 + 随机盐存储，只存哈希；会话存在内存里，重启即全部登出。

### 安全须知（重要）

- 面板默认监听 `0.0.0.0`，局域网内谁都够得着。只想本机用请加 `--localhost`。
- **没有 TLS**，密码和会话都是明文传输。只在可信内网使用；要暴露到公网请套
  反向代理 + HTTPS。
- broker 设置文件里的 MQTT 密码是**明文**，请像对待密码一样对待
  `mqtt-web-settings.json`。
- 不要把本仓库里的占位符直接当生产配置用。

### 常见问题

- **定时设了不触发**：全局 `Timers` 开关和该槽位的 Enable **必须同时打开**。
- **`StatusSNS` 回 Unknown**：`StatusSNS` 是应答里的**字段名**，不是命令；读电量
  用 `Status 8`。
- **08:00 的定时在北京时间 15:00 触发**：定时用的是**设备本地时间**，先执行
  `python mqtt-cli.py time --set-tz +8:00`。
- **某个插座显示离线但实际可控**：调大 `--refresh` / `--energy`，或关掉多余的
  浏览器标签页。

---

## License

MIT — see [LICENSE](LICENSE).

Tasmota is a separate project by Theo Arends and contributors, licensed under
GPL-3.0. This repository only speaks its MQTT protocol; it contains no Tasmota
code.

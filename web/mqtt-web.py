#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""A browser control panel for MANY Tasmota plugs at once -- one file, no install.

THIS FILE IS COMPLETE ON ITS OWN: it imports nothing from this project, so it can
be copied to another folder or another machine and still run. It talks to the
BROKER directly and needs no Tasmota web server, no cloud and no Internet account.

    D:\aiwork\mqtt-py>mqtt-web.py
    mqtt-py web panel -- managing 3 devices
    list    : mqtt-web-devices.json
    listen  : 0.0.0.0:8765
    local   : http://127.0.0.1:8765/
    network : http://192.168.1.23:8765/
    Ctrl-C to stop.

UNLIKE the per-device panel (mqtt-6FCE2C-web.py) this one does NOT take its device
from its own file name -- it manages a LIST. The list lives in a small JSON file
next to this script and the page edits it: add a serial, delete one, rename one,
change a note.

    mqtt-web-devices.json
    {
      "version": 1,
      "devices": [
        {"id": "6FCE2C", "note": "living room AC", "added": "2026-09-26T18:30:00"},
        {"id": "A1B2C3", "note": "bedroom humidifier"}
      ]
    }

The file stays human-readable on purpose: back it up, copy it to another machine,
or edit it in a text editor while the panel is stopped. A corrupt file is never
overwritten -- the page says so and leaves your bytes alone.

The broker endpoint lives in its own file beside it, mqtt-web-settings.json,
written by the page's settings dialog. Delete that file and the panel falls back to
its flags and environment on the next start.

ACCOUNTS (new)
Everybody meets a LOGIN page first, and nothing behind it is served to a browser
without a session: not the serials, not even the markup of the buttons that reach
them. Registration asks for a name, an email and a password (8 characters minimum);
the first account in an empty panel is the one that matters, so the card opens on
the registration side until somebody exists. Use --no-register to close the door
once your household is set up, and --no-auth to go back to one shared list with no
login at all -- which is only sensible on a machine nobody else can reach.

Each account owns its OWN device list file, mqtt-web-users/<name>.json, so two
people manage different plugs from one panel and neither sees the other's serials.
Upgrading from an older panel is handled: the first new account adopts the old
mqtt-web-devices.json (which is then renamed to ...json.adopted, not deleted).
The ACCOUNT button changes a password (it asks for the old one first, and signs
out every other window using that account) or corrects the email address.

Passwords are stored as PBKDF2-HMAC-SHA256 with a per-account random salt -- never
in plain text, and never sent back to a browser. Sessions are random tokens held in
MEMORY, so restarting the panel signs everybody out, and they expire after 12 hours
of quiet. Eight wrong passwords for one name buys that name a five minute cool-down,
and login always answers the same way whether the name exists or not.

WHAT THE PAGE DOES
    devices     the left column lists every serial with its note and its live
                ONLINE/OFFLINE + relay state, refreshed on a timer. Click a row to
                control that plug; the edit button changes the serial or the note
                without touching anything else
    relay       ON / OFF / TOGGLE, with the state read straight back off the
                device and a live ONLINE/OFFLINE indicator
    energy      the device's own meter: live power in watts, voltage, current,
                power factor, apparent/reactive power, today's and the total
                kWh -- read with `Status 8` on its own, slower beat. (`StatusSNS`
                is the KEY inside that reply, not a command; publishing it makes
                the device answer "Unknown".) A plug with no energy chip says so
                in words instead of drawing 0 W, and a plug that stops answering
                keeps the last reading with its age beside it
    pulse       "put it in one state for N seconds, then the other": on for 30 s
                then off, or the mirror image. The page does not wait for the
                countdown -- it returns at once and shows the deadline
    cycle       "on for N seconds, off for M seconds, forever" -- a fish tank
                light or an air pump. A timer slot fires once a day and cannot
                alternate, so this is written as two Tasmota RULES that re-arm
                each other; the loop runs INSIDE the plug, so closing the
                browser or shutting this computer down does not stop it. The
                countdown shown is the device's own RuleTimer, read back.
                Stopping disarms the loop and leaves the relay where it is
    timers      all 16 slots listed, any slot set from a form (time, weekdays,
                on/off, arm), one button for the global Timers switch that gates
                every slot
    clock       the device's UTC / local time / timezone offset, and the one-click
                +08:00 fix -- timer times are DEVICE local time, so a 08:00 timer
                fires at 15:00 Beijing until this is applied
    settings    the broker endpoint: host, port, TLS, username, password and the
                per-request timeout. Saving applies them at once, so switching
                brokers needs no restart
    account     who you are: change your password or your email, and sign out

SETTINGS PAGE
The SETTINGS button at the foot of the left column opens the broker settings. Saving
writes them to mqtt-web-settings.json (beside the device list), applies them
immediately and drops every open MQTT link -- the next read dials the new broker.
"TEST CONNECTION" opens one throwaway connection and reports whether the broker
accepts those credentials, which is the only way to tell a wrong password from a
wrong port. "RESTORE STARTUP VALUES" deletes the file and goes back to what this
panel was started with (flags, then environment, then the built-in defaults).

The password is never handed back to the page: the field comes up empty and
leaving it empty KEEPS the saved one; ticking the "clear the saved password"
box is what drops it. What is written to disk is plain text, so treat the
settings file the way you would treat a password.

The panel's OWN address and port are deliberately not in there -- they belong to
the listening socket, which cannot be moved while it is serving. Use --listen /
--port and restart; the dialog says so under the form.

FLAGS
    mqtt-web.py --port 8080        listen somewhere else
    mqtt-web.py --localhost        this machine only (127.0.0.1)
    mqtt-web.py --listen 0.0.0.0   explicit: reachable from the LAN (the default)
    mqtt-web.py --list other.json  use a different device list file
    mqtt-web.py --settings f.json  keep the broker settings somewhere else
    mqtt-web.py --open             launch the browser for you
    mqtt-web.py --token SECRET     require ?token=SECRET (see below)
    mqtt-web.py --read-only        the page comes up in view-only mode
    mqtt-web.py --no-auth         no login: one shared list for everybody
    mqtt-web.py --no-register     nobody can create another account
    mqtt-web.py --users other.json    keep the accounts somewhere else
    mqtt-web.py --max-devices 32  refuse to manage more than this many
    mqtt-web.py --refresh 8       seconds between two reads of the OPEN device
    mqtt-web.py --sweep 45        seconds between two passes over the whole list
    mqtt-web.py --energy 5        seconds between two reads of the OPEN meter
    mqtt-web.py --help            the full list, including every MQTT flag

HOW OFTEN IT TALKS TO THE PLUGS
Three things touch a device on a timer, and each has its own flag. The device
you are looking at is re-read every --refresh seconds (default 8); its METER
(power, voltage, current, kWh) is re-read every --energy seconds (default 5);
and the whole list is re-read every --sweep seconds (default 45), one device at
a time, so the badges on the left stay honest. Everything else happens when you
press something.

Every read of one plug goes through ONE queue, so these three rates are not
independent: making --energy smaller than --refresh does not make the meter
fresher, it only makes the relay state read slower. A plug with no energy chip
is asked once and then left alone until you open it again.

All three beats wait for their own answer before asking again, which is the
point: a slow reply used to let the next request stack on top of an unanswered
one, and the queue that grew was the panel's own doing -- a healthy plug on a
slow broker then looked like a broken one. A button press drops the relay beat
to 1 second for a few seconds (the only moment anybody can see the difference),
and a read that fails backs off instead of hammering. Raise --refresh and
--energy if the broker is far away, or if several browser tabs watch the same
device.

WHY THERE IS A DEVICE LIMIT
Every managed device holds its own MQTT connection, so the count is also a thread
count. --max-devices (default 32) keeps a mistyped import from trying to open
thousands of sockets. Raise it if you really have that many plugs; the cost is
one connection per device.

SECURITY -- PLEASE READ
This binds to every network interface by default (0.0.0.0), so anything on your
LAN -- and, on a router that forwards the port, potentially the Internet -- can
reach the panel. What it reaches is the LOGIN page: devices are behind an account,
and every list API refuses a request without one. Keep it that way -- --no-auth
removes the lock to get the old single-list behaviour, and then anyone who gets
there can switch ANY relay. Registration is open by default as well, so put it
behind --no-register once the people who need accounts have them.

There is no TLS here, so passwords and sessions travel in clear text -- fine on a
trusted LAN, not fine over the Internet. If the panel must be reachable from
outside your network, put it behind a reverse proxy with HTTPS rather than
exposing this port directly. On Windows, the first inbound connection may also
need a firewall rule for this port; see --help notes at startup.

Exit codes: 0 ok / 1 error / 2 timed out / 3 missing dependency.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import ssl
import string
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

try:
    import paho.mqtt.client as mqtt
except ModuleNotFoundError:
    sys.stderr.write(
        "ERROR: paho-mqtt is not installed.\n"
        "  uv add paho-mqtt\n"
        "  # or: python -m pip install paho-mqtt\n"
    )
    raise SystemExit(3)


# --------------------------------------------------------------------------- #
# Defaults -- every value can be overridden by env var or CLI flag.
# --------------------------------------------------------------------------- #
DEF_HOST = os.getenv("MQTT_HOST", "broker.example.com")
DEF_PORT = int(os.getenv("MQTT_PORT", "1883"))
DEF_TLS = os.getenv("MQTT_TLS", "0").strip().lower() in ("1", "true", "yes", "on")
DEF_CA = os.getenv("MQTT_CA", os.path.join("broker-ca", "certs", "ca.crt"))
DEF_USER = os.getenv("MQTT_USER", "")
DEF_PASS = os.getenv("MQTT_PASS", "")

# --------------------------------------------------------------------------- #
# >>> THE DEVICE NAME -- this is the one value to edit for a different plug. <<<
#
# Tasmota builds its topics from FullTopic = "%prefix%/%topic%/" and uses
# "tasmota_%06X" as the default %topic%, where %06X is the chip id Tasmota
# reports on boot (DVES_6FCE2C -> 6FCE2C). All of these spellings are accepted:
#
#     "6FCE2C"           chip id          -> topic "tasmota_6FCE2C"
#     "DVES_6FCE2C"      boot banner      -> topic "tasmota_6FCE2C"
#     "0x6FCE2C"         C literal        -> topic "tasmota_6FCE2C"
#     "tasmota_6FCE2C"   full topic       -> used verbatim
#     "kitchen_plug"     custom %topic%   -> used verbatim
#
# Overridden by the MQTT_DEVICE env var, then by --device / --topic.
# --------------------------------------------------------------------------- #
DEVICE_NAME = os.getenv("MQTT_DEVICE") or os.getenv("MQTT_CHIP_ID") or "6FCE2C"

# Every action this tool understands. build_parser() and the shortcut file-name
# reader (device_action_from_filename) both take their list from here, so the two
# can never drift apart.
ACTIONS = ("on", "off", "toggle", "status", "pulse", "pulseoff", "diag",
           "timers", "timer", "time")

# The two actions that park the relay in one state for --seconds and then move it
# to the other one. Only these may also carry their duration in the FILE NAME,
# one segment after the action:
#     mqtt-6FCE2C-pulseoff-120.py  ==  -pulseoff.py --seconds 120
# Restricting it to them is what keeps a device name ending in digits (say
# "plug2") from being read as a duration.
DURATION_ACTIONS = ("pulse", "pulseoff")

SWITCH_PAYLOADS = {"on": "ON", "off": "OFF", "toggle": "TOGGLE"}
# Fallback for firmwares whose relay 1 is not registered (see notes 1 and 5).
ALL_RELAYS_CMD = "POWER0"
# How long to wait for a command echo before polling `Status 0` instead. The
# reply normally lands in milliseconds; POWER0 is silent by design.
ECHO_WINDOW = 1.5

# How long each kind of command waits for the device, in seconds.
#
# The single --timeout of 6 s is right for a one-shot CLI run, where a slow reply
# costs nothing but patience. A web panel is different: every click BLOCKS until
# the action returns, so 6 s of silence reads as "the page is broken". Measured
# on this unit the round trip is well under a second and the only slow case is
# the deliberate poll after a silent POWER0 command, so these are deliberately
# shorter than --timeout and --timeout still raises the ceiling for every one of
# them. Looked up by name, not by action, so `pulse` and `pulseoff` share the
# same budget and a never-seen action falls back to --timeout.
TIMEOUTS = {
    "status": 2.5,      # one `Status 0` round trip
    "switch": 3.5,      # POWER (+ echo window) or POWER0 (+ one poll)
    "read": 4.0,        # timer / clock read back, which walks more of the device
}


def action_timeout(action: str) -> float:
    """Which TIMEOUTS entry an action uses."""
    if action == "status":
        return TIMEOUTS["status"]
    if action in ("timers", "timer", "time", "diag"):
        return TIMEOUTS["read"]
    return TIMEOUTS["switch"]

# ---------------------------------------------------------------- timer tables
TIMER_COUNT = 16
# Tasmota renders the weekday mask Sunday-first. Writing "1111100" for Mon-Fri
# is the single most common mistake when setting timers by hand.
DAYS_ORDER = ("sun", "mon", "tue", "wed", "thu", "fri", "sat")
DAY_ALIASES = {
    "sun": 0, "su": 0, "sunday": 0,
    "mon": 1, "mo": 1, "monday": 1,
    "tue": 2, "tues": 2, "tu": 2, "tuesday": 2,
    "wed": 3, "we": 3, "wednesday": 3,
    "thu": 4, "thur": 4, "thurs": 4, "th": 4, "thursday": 4,
    "fri": 5, "fr": 5, "friday": 5,
    "sat": 6, "sa": 6, "saturday": 6,
}
DAY_GROUPS = {
    "all": "1111111",
    "everyday": "1111111",
    "daily": "1111111",
    "weekday": "0111110",
    "weekdays": "0111110",
    "weekend": "1000001",
    "weekends": "1000001",
    "none": "0000000",
}
TIMER_MODES = {"clock": 0, "sunrise": 1, "sunset": 2}
TIMER_ACTIONS = {"off": 0, "on": 1, "toggle": 2, "rule": 3, "blink": 3}
TIMER_TEMPLATE = {"Enable": 0, "Mode": 0, "Time": "00:00", "Window": 0,
                  "Days": "0000000", "Repeat": 0, "Output": 1, "Action": 0}

CLOCK_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
OFFSET_RE = re.compile(r"^([+-])(\d{1,2}):([0-5]\d)$")
# The same thing as users actually type it: +8, +8:00, +08:30. The firmware
# rejects a zero-padded hour on this device, so accepting only the padded form
# would hand every user a spelling that cannot work. timezone_spellings() turns
# whatever arrives here into the form the device takes.
OFFSET_ANY_RE = re.compile(r"^([+-])(\d{1,2})(?::([0-5]\d))?$")


def expand_days(spec: str) -> str:
    """Turn a day spec into Tasmota's 7 char SMTWTFS mask.

    Accepts a ready made mask ("MTWTF--", "1111100", "0000000"), a list of day
    names ("Mon,Wed,Fri"), a range ("Mon-Fri") or a keyword ("weekdays").
    """
    text = spec.strip().lower()
    if not text:
        raise ValueError("empty --days")

    if text in DAY_GROUPS:
        return DAY_GROUPS[text]

    # A raw mask: '0' and '-' mean OFF, any other character means ON, so both
    # "0111110" and "SMTWT--" work exactly as the docs describe. The check is
    # deliberately strict so that "mon-fri" is NOT mistaken for a 7 char mask.
    if len(text) == 7 and all(c in "01-+x" or c.upper() in "SMTWF" for c in text):
        return "".join("0" if c in "0-" else "1" for c in text)

    marks = [False] * 7
    for token in re.split(r"[,\s]+", text):
        if not token:
            continue
        if "-" in token:
            head, tail = token.split("-", 1)
            first, last = _day_index(head), _day_index(tail)
            index = first
            while True:
                marks[index] = True
                if index == last:
                    break
                index = (index + 1) % 7
        else:
            marks[_day_index(token)] = True
    return "".join("1" if m else "0" for m in marks)


def _day_index(name: str) -> int:
    key = name.strip().lower()
    if key not in DAY_ALIASES:
        raise ValueError("unknown day %r (use sun/mon/tue/wed/thu/fri/sat)" % name)
    return DAY_ALIASES[key]


def describe_days(mask: str) -> str:
    days = [DAYS_ORDER[i] for i, c in enumerate(mask[:7]) if c not in "0-"]
    if len(days) == 7:
        return "every day"
    if not days:
        return "no day"
    return "/".join(d.capitalize() for d in days)


def canonical_timer_value(key: str, value):
    """Normalise a Timer field so a read back can be compared with what we sent.

    The device zero pads offsets ("-0:30" comes back as "-00:30") and may return
    numbers where we sent strings, so a raw == comparison produces false alarms.
    """
    if key in ("Enable", "Mode", "Window", "Repeat", "Output", "Action"):
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    text = str(value).strip().upper()
    if key == "Time":
        match = re.match(r"^([+-]?)(\d{1,2}):(\d{2})$", text)
        if match:
            return "%s%02d:%02d" % (match.group(1), int(match.group(2)), int(match.group(3)))
    return text


def timer_in_use(cfg: dict) -> bool:
    """True when a slot holds anything other than the empty defaults."""
    if int(cfg.get("Enable") or 0):
        return True
    if str(cfg.get("Days", "")) not in ("", "0000000"):
        return True
    return str(cfg.get("Time", "00:00")) not in ("", "00:00")


def _utc_offset_hours(utc: str, local: str) -> float | None:
    """Derive the offset a device actually applies (DST included) from Status 7."""
    try:
        u = datetime.strptime(utc.rstrip("Z"), "%Y-%m-%dT%H:%M:%S")
        l = datetime.strptime(local, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None
    return (l - u).total_seconds() / 3600.0


# What `Status 7` calls the zone: "UTC+08:00" -> the "+08:00" the Timezone
# command is supposed to take. Anything unexpected is left as the user wrote it.
TZ_APPLIED_RE = re.compile(r"^UTC\s*([+-]\d{1,2}(?::\d{2})?)$")

# One spelling of an offset, reduced to (sign, hour, minute) so that "+8:00",
# "+08:00" and "UTC+08:00" all compare equal no matter who wrote them.
TZ_PARTS_RE = re.compile(r"^\s*(?:UTC\s*)?([+-])0*(\d{1,2})(?::(\d{2}))?\s*$")


def _tz_parts(text: str) -> tuple[str, str, str] | None:
    """("+", "8", "00") for any of +8 / +8:00 / +08:00 / UTC+08:00, else None."""
    match = TZ_PARTS_RE.match(text or "")
    if not match:
        return None
    return (match.group(1), match.group(2), match.group(3) or "00")


def timezone_spellings(offset: str) -> list[str]:
    """Candidate arguments for `Timezone`, best first.

    Measured on Tasmota 15.5.0 (ESP32-C2, device 6FCE2C), a zero-padded hour is
    silently REJECTED and the zone resets to UTC+00:00 -- no error, exit code 0:

        Timezone +8      -> {"Timezone":"+08:00"}   accepted
        Timezone +8:00   -> {"Timezone":"+08:00"}   accepted
        Timezone 8       -> {"Timezone":"+08:00"}   accepted
        Timezone +08:00  -> {"Timezone":"+00:00"}   REJECTED
        Timezone +08     -> {"Timezone":"+00:00"}   REJECTED

    So "+08:00" -- the obvious way to write it, and the firmware's own preferred
    output format -- must not be sent as-is. Only the leading zero is dropped, so
    "+8:00" keeps its ":00" (which the device does accept) and "08:00" becomes
    "8:00"; a bare "+08" becomes "+8". The original is kept as a fallback for
    firmware that wants the padded form.
    """
    text = (offset or "").strip()
    parts = _tz_parts(text)
    if not parts:
        return [text] if text else []
    sign, hours, minutes = parts
    # "+8:00" is accepted while bare "+8" may not be, so a written-out ":00" is
    # kept rather than trimmed -- only the leading zero goes.
    short = "%s%s:%s" % (sign, hours, minutes) if ":" in text else "%s%s" % (sign, hours)
    return [short] if short == text else [short, text]


# A bare Tasmota chip id: the 6 hex digits Tasmota prints as DVES_6FCE2C.
HEX_CHIP_RE = re.compile(r"^[0-9A-Fa-f]{1,6}$")


def resolve_device(spec: str) -> tuple[str, str]:
    """Turn any way of naming a device into (chip_id, topic).

    Tasmota's default %topic% is "tasmota_%06X", built from the chip id, so both
    spellings are common and both are accepted here:

        "6FCE2C"         -> ("6FCE2C", "tasmota_6FCE2C")
        "DVES_6FCE2C"    -> ("6FCE2C", "tasmota_6FCE2C")
        "0x6FCE2C"       -> ("6FCE2C", "tasmota_6FCE2C")
        "tasmota_6FCE2C" -> ("6FCE2C", "tasmota_6FCE2C")
        "kitchen_plug"   -> ("",       "kitchen_plug")     # custom Topic setting
    """
    text = (spec or "").strip()
    if not text:
        raise ValueError("no device name given (set DEVICE_NAME or --device)")

    # Strip the familiar prefixes, but only trust the result if it really is a
    # bare chip id: "DVES_6FCE2C_fb" is a topic name and must stay untouched.
    stripped = text
    for prefix in ("DVES_", "dves_", "0x", "0X"):
        if stripped.startswith(prefix):
            stripped = stripped[len(prefix):]
            break
    if HEX_CHIP_RE.match(stripped):
        chip = stripped.upper()
        return chip, "tasmota_%06X" % int(chip, 16)

    if text.lower().startswith("tasmota_"):
        tail = text[len("tasmota_"):]
        return (tail.upper() if HEX_CHIP_RE.match(tail) else ""), text

    # Some other custom %topic%: use it verbatim, there is no chip id to report.
    return "", text


# --------------------------------------------------------------------------- #
# Shortcut file names -- "mqtt-6FCE2C-on.py" drives tasmota_6FCE2C and turns it
# on. The shortcut scripts read their own name, so switching plugs is a rename
# and nothing else. See make_shortcuts.py for the generator.
# --------------------------------------------------------------------------- #
# Every action is reachable from a file name, so one shortcut can drive the relay,
# the timers and the clock alike -- e.g. "mqtt-6FCE2C-timer.py 3 --time 08:00
# --days weekdays --action on --enable". Kept in sync with the parser via ACTIONS.
SHORTCUT_ACTIONS = ACTIONS
# Both separators are accepted, so the older "6FCE2C_on.py" style keeps working.
SHORTCUT_SEPARATORS = "_-"
# Cosmetic head of the file name: "mqtt-6FCE2C-on.py" and "6FCE2C-on.py" name
# exactly the same thing, so the head can be dropped or kept at will.
SHORTCUT_PREFIX = "mqtt"


def device_action_from_filename(path: str) -> tuple[str, str, int | None]:
    """Read the device, the action and the seconds out of a shortcut's file name.

        "mqtt-6FCE2C-on.py"           -> ("6FCE2C", "on", None)
        "mqtt-A1B2C3-off.py"          -> ("A1B2C3", "off", None)
        "mqtt-kitchen_plug-on.py"     -> ("kitchen_plug", "on", None)
        "mqtt-6FCE2C-timer.py"        -> ("6FCE2C", "timer", None)
        "6FCE2C_toggle.py"            -> ("6FCE2C", "toggle", None)  # head optional
        "tasmota_A1B2C3-status.py"    -> ("tasmota_A1B2C3", "status", None)
        "mqtt-6FCE2C-pulseoff-120.py" -> ("6FCE2C", "pulseoff", 120)

    The name is split at the LAST '_' or '-', so a device name may contain
    separators of its own. A leading "mqtt-"/"mqtt_" is then dropped, which is
    what makes the "mqtt-<device>-<action>.py" convention work. The action is
    matched case-insensitively.

    A trailing NUMBER is read as --seconds, but only when the segment before it is
    one of DURATION_ACTIONS. That is how a single file can mean "off for two
    minutes, then back on" with no argument at all; a device name of its own may
    still end in digits.
    """
    name = os.path.basename(path)
    stem = os.path.splitext(name)[0]
    cut = max(stem.rfind(sep) for sep in SHORTCUT_SEPARATORS)
    seconds = None
    if cut > 0 and stem[cut + 1:].isdigit():
        # "mqtt-6FCE2C-pulseoff-120.py": that last segment is a duration, not the
        # action, so step back one separator -- but only if what sits between them
        # is an action that takes a duration.
        back = max(stem.rfind(sep, 0, cut) for sep in SHORTCUT_SEPARATORS)
        if back > 0 and stem[back + 1:cut].lower() in DURATION_ACTIONS:
            seconds = int(stem[cut + 1:])
            stem = stem[:cut]           # the number is NOT part of the action
            cut = back

    if cut <= 0:                        # no separator at all, or only a leading one
        device, action = "", ""
    else:
        device, action = stem[:cut], stem[cut + 1:].lower()

    for head in (SHORTCUT_PREFIX + "-", SHORTCUT_PREFIX + "_"):
        if device.lower().startswith(head):
            device = device[len(head):]
            break

    if not device or action not in SHORTCUT_ACTIONS:
        raise ValueError(
            "cannot tell the device and the action from %r\n"
            "       expected mqtt-<device>-<action>.py, e.g. mqtt-6FCE2C-on.py\n"
            "       or, to bake in a duration, mqtt-6FCE2C-pulseoff-120.py\n"
            "       <action> must be one of: %s"
            % (name, ", ".join(SHORTCUT_ACTIONS)))
    return device, action, seconds


def shortcut_name(device: str, action: str) -> str:
    """The file name a shortcut script would have for this device and action.

    Only used to make hints point at a runnable file rather than at a bare
    action: "run mqtt-6FCE2C-timers.py --enable-all" tells the user what to type.
    """
    try:
        chip, topic = resolve_device(device)
    except ValueError:
        return "mqtt-<device>-%s.py" % action
    stem = chip or topic
    for bad in '\\/:*?"<>| ':
        stem = stem.replace(bad, "_")
    return "mqtt-%s-%s.py" % (stem or "device", action)


def make_client_id() -> str:
    """Return a fresh, unique MQTT client id.

    Never reuse "DVES_<chip id>" here: that is the plug's OWN client id, and a
    second session claiming it would kick the device off the broker.
    """
    suffix = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(6))
    return "wb-mqtt-py-" + suffix


class TasmotaPlug:
    """One-device Tasmota MQTT client: on / off / toggle / status / pulse / pulseoff."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.topic = args.topic
        self.cmnd = "cmnd/" + self.topic
        self.stat = "stat/" + self.topic
        self.tele = "tele/" + self.topic

        self.state: str | None = None       # "ON" / "OFF"
        self.online: bool | None = None     # from tele/.../LWT
        self.state_src: str | None = None   # topic that delivered the last state
        self.errors: list[str] = []         # {"Command":"Error"} payloads seen
        self.replies: list[tuple[str, str]] = []    # everything, for `diag`
        self.state_ts = 0.0
        # Per-call wait budget, normally the action's own TIMEOUTS entry. A host
        # that embeds this engine (the web panel) raises or lowers it per request;
        # a shortcut leaves it at the action default, so its behaviour is a
        # function of `action` alone.
        self.timeout = getattr(args, "timeout", 6.0)
        self.retries = 0                    # attempts per command, 1 unless asked
        self.retry_delay = 0.8

        self._cv = threading.Condition()
        self._connected = threading.Event()
        self._connect_rc: int | None = None

        self.client = self._build_client()

    # ------------------------------------------------------------------ MQTT
    def _build_client(self) -> "mqtt.Client":
        client_id = self.args.client_id or make_client_id()
        if hasattr(mqtt, "CallbackAPIVersion"):        # paho-mqtt >= 2.0
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        else:                                          # paho-mqtt 1.x
            client = mqtt.Client(client_id=client_id)

        client.username_pw_set(self.args.user, self.args.password)

        if self.args.tls:
            ctx = ssl.create_default_context(cafile=self.args.ca)
            ctx.check_hostname = False      # server cert is IP-based (203.0.113.10)
            ctx.verify_mode = ssl.CERT_REQUIRED
            client.tls_set_context(ctx)

        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.on_disconnect = self._on_disconnect
        return client

    def _on_connect(self, client, userdata, flags, rc, properties=None) -> None:
        code = getattr(rc, "value", rc)     # ReasonCode on paho 2.x, int on 1.x
        self._connect_rc = code
        if code == 0:
            client.subscribe([(self.stat + "/#", 0), (self.tele + "/#", 0)])
        self._connected.set()

    def _on_disconnect(self, client, userdata, *rest) -> None:
        if self.args.verbose:
            codes = [getattr(item, "value", item) for item in rest]
            sys.stderr.write("[mqtt] disconnected (%s)\n" % ", ".join(str(c) for c in codes))

    def _on_message(self, client, userdata, msg) -> None:
        payload = msg.payload.decode("utf-8", "replace").strip()
        topic = msg.topic
        if self.args.verbose:
            sys.stderr.write("[mqtt] %s -> %s\n" % (topic, payload))

        with self._cv:
            self.replies.append((topic, payload))
            if topic.endswith("/LWT"):
                self.online = payload.lower() == "online"
            else:
                if '"Command":"Error"' in payload.replace(" ", ""):
                    self.errors.append(payload)
                state = self._extract_state(payload, self.args.relay)
                if state:
                    self.state = state
                    self.state_src = topic
                    self.state_ts = time.time()
            self._cv.notify_all()

    # ------------------------------------------------------- state extraction
    @classmethod
    def _extract_state(cls, payload: str, relay: int) -> str | None:
        """Pull a relay state out of any Tasmota payload shape we may receive."""
        if payload in ("ON", "OFF"):
            return payload
        if not payload.startswith("{"):
            return None
        try:
            data = json.loads(payload)
        except ValueError:
            return None
        # Explicit POWER keys win over the relay bitmask: StatusSNS carries an
        # `ENERGY.Power` in WATTS that would otherwise be read as a relay state.
        for use_mask in (False, True):
            found = cls._walk(data, relay, use_mask)
            if found:
                return found
        return None

    @classmethod
    def _walk(cls, node, relay: int, use_mask: bool) -> str | None:
        """Depth-first search for a relay state.

        Handles {"POWER":"ON"}, nested {"StatusSTS":{"POWER":"ON"}} and the
        relay bitmask {"Status":{...,"Power":"0",...}}.
        """
        if not isinstance(node, dict):
            return None

        if use_mask:
            # `Power` is the all-relay bitmask; `Power<n>` appears in STATE
            # payloads. Either one can answer for a specific relay index.
            keys = ["Power"] if relay <= 1 else ["Power", "Power%d" % relay]
        elif relay == 1:
            keys = ["POWER", "POWER1"]
        else:
            keys = ["POWER"] if relay == 0 else ["POWER%d" % relay]

        for key in keys:
            if key in node:
                value = cls._coerce(node[key], relay)
                if value:
                    return value

        for key, value in node.items():
            if isinstance(value, dict) and key.upper() != "ENERGY":
                found = cls._walk(value, relay, use_mask)
                if found:
                    return found
        return None

    @staticmethod
    def _coerce(value, relay: int) -> str | None:
        if isinstance(value, str) and value.strip().upper() in ("ON", "OFF"):
            return value.strip().upper()
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            return None

        text = str(value).strip()
        try:
            if text and all(c in "01" for c in text):   # digits, one per relay
                if relay == 0:
                    return "ON" if "1" in text else "OFF"
                return "ON" if len(text) >= relay and text[-relay] == "1" else "OFF"
            mask = int(text, 16)                        # older firmware: hex bitmask
        except ValueError:
            return None
        if relay == 0:
            return "ON" if mask else "OFF"
        return "ON" if (mask >> (relay - 1)) & 1 else "OFF"

    # --------------------------------------------------------------- helpers
    def connect(self) -> None:
        try:
            rc = self.client.connect(self.args.host, self.args.port, keepalive=30)
        except OSError as exc:
            raise RuntimeError("cannot reach %s:%d -> %s" % (self.args.host, self.args.port, exc))
        if rc != 0:
            raise RuntimeError("connect() returned rc=%s" % rc)

        self.client.loop_start()
        if not self._connected.wait(self.args.timeout):
            raise RuntimeError("no CONNACK within %.1fs" % self.args.timeout)
        if self._connect_rc != 0:
            raise RuntimeError(
                "broker refused the connection (rc=%s). Check username/password."
                % self._connect_rc
            )

    def close(self) -> None:
        try:
            self.client.disconnect()
            self.client.loop_stop()
        except Exception:
            pass

    def reset_state(self) -> None:
        """Forget cached replies so the next update is unambiguously fresh."""
        with self._cv:
            self.state = None
            self.state_ts = 0.0
            self.state_src = None
            self.errors = []
            self.replies = []

    def wait_for_update(self, timeout: float, since: float) -> str | None:
        deadline = time.time() + timeout
        with self._cv:
            while True:
                if self.state is not None and self.state_ts >= since:
                    return self.state
                remaining = deadline - time.time()
                if remaining <= 0:
                    return None
                self._cv.wait(remaining)

    def run_with_retries(self, fn, attempts: int | None = None):
        """Call fn() and retry while it keeps answering "no".

        Only for a host that must not leave the user staring at a dead page: the
        MQTT link to this broker occasionally drops a QoS 0 packet, and one lost
        `Status 0` is the difference between a working panel and a red banner.
        A returned exit code of 0 is success; anything else is retried, because
        both 2 (timeout) and 1 (rejected / wrong state) have been seen to be
        transient. The last result is returned unchanged, so a genuine failure
        still surfaces. A shortcut calls this once, with attempts=1.
        """
        last = None
        for attempt in range(max(1, attempts or 1)):
            if attempt:
                time.sleep(self.retry_delay)
            last = fn()
            if last == 0:
                return last
        return last

    def _timeout_for(self, action: str) -> float:
        """The action's own budget, never more than the host allowed.

        A shortcut leaves self.timeout at the parser default, so this is the
        engine's TIMEOUTS table. A web request lowers self.timeout per call, so a
        slow device cannot hold a page for the full CLI timeout.
        """
        return min(action_timeout(action), self.timeout)

    def settle(self, grace: float) -> None:
        """Give the broker a moment to deliver retained stat/tele messages."""
        deadline = time.time() + grace
        with self._cv:
            while self.state is None and time.time() < deadline:
                self._cv.wait(deadline - time.time())

    def publish(self, command: str, payload: str = "") -> str:
        full = "%s/%s" % (self.cmnd, command)
        if self.args.verbose:
            sys.stderr.write("[mqtt] PUB %s -> %s\n" % (full, payload))
        info = self.client.publish(full, payload, qos=0, retain=self.args.retain)
        if info.rc != 0:
            raise RuntimeError("publish to %s failed rc=%s" % (full, info.rc))
        return full

    def query_state(self, timeout: float) -> str | None:
        """Ask the device for its relay bitmask via `Status 0`.

        (An empty POWER payload is rejected by this firmware, so this is the
        only reliable way to read the current state.)
        """
        with self._cv:
            self.state = None
            self.state_ts = 0.0
        t0 = time.time()
        self.publish("Status", "0")
        return self.wait_for_update(timeout, t0)

    def ask(self, command: str, payload: str = "",
            timeout: float | None = None, quiet: float = 0.7) -> list[tuple[str, str]]:
        """Publish a command and return every reply IT produces.

        Stops early once the device has gone quiet for `quiet` seconds, so a
        single-response command does not cost a full `--timeout` wait.

        It deliberately does NOT clear shared state first. Doing that wiped
        `self.state` -- the very field query_state() waits on -- so a cycle
        poll landing between a `Status 0` and its answer swallowed the answer
        and the read timed out for no visible reason. Taking a mark instead
        keeps "what did MY command say" correct without touching anyone else's
        in-flight reply.
        """
        with self._cv:
            mark = len(self.replies)
        self.publish(command, payload)
        deadline = time.time() + (timeout or self.timeout)
        last_seen = time.time()
        count = 0
        with self._cv:
            while time.time() < deadline:
                seen = len(self.replies) - mark
                if seen > count:
                    count = seen
                    last_seen = time.time()
                elif count and time.time() - last_seen >= quiet:
                    break
                self._cv.wait(0.15)
        with self._cv:
            return list(self.replies[mark:])

    # ------------------------------------------------------------------ timers
    def _fetch_timers(self, timeout: float | None = None) -> tuple[str | None, dict]:
        """Return (global_switch, {slot: cfg}) from the `Timers` command."""
        for _topic, payload in self.ask("Timers", "", timeout or self._timeout_for("timers")):
            if not payload.startswith("{"):
                continue
            try:
                data = json.loads(payload)
            except ValueError:
                continue
            slots = {int(k[5:]): v for k, v in data.items()
                     if k.startswith("Timer") and k[5:].isdigit() and isinstance(v, dict)}
            if slots:
                return data.get("Timers"), slots
        return None, {}

    @staticmethod
    def _format_slot(index: int, cfg: dict) -> str:
        mode = {0: "clock", 1: "sunrise", 2: "sunset"}.get(int(cfg.get("Mode") or 0), "?")
        action = {0: "off", 1: "on", 2: "toggle", 3: "rule"}.get(int(cfg.get("Action") or 0), "?")
        days = str(cfg.get("Days", ""))
        return "%-4d %-4s %-8s %-8s %-4s %-13s %-4s %-4s %-7s (%s)" % (
            index, cfg.get("Enable", 0), mode, cfg.get("Time", ""), cfg.get("Window", 0),
            days, cfg.get("Repeat", 0), cfg.get("Output", 1), action, describe_days(days))

    @staticmethod
    def _describe_slot(cfg: dict) -> str:
        mode = int(cfg.get("Mode") or 0)
        action = int(cfg.get("Action") or 0)
        parts = ["at %s" % cfg.get("Time") if mode == 0
                 else "%s from %s" % (cfg.get("Time"), "sunrise" if mode == 1 else "sunset")]
        if int(cfg.get("Window") or 0):
            parts.append("+/-%d min random" % int(cfg["Window"]))
        parts.append("on %s" % describe_days(str(cfg.get("Days", ""))))
        parts.append("-> output %s %s" % (cfg.get("Output", 1), ["OFF", "ON", "TOGGLE", "RULE"][action]))
        parts.append("repeat" if int(cfg.get("Repeat") or 0) else "once, then disarms")
        if not int(cfg.get("Enable") or 0):
            parts.append("NOT armed yet (add --enable)")
        return ", ".join(parts)

    def cmd_timers(self) -> int:
        args = self.args
        if args.arm == "on":
            self.ask("Timers", "1")
        elif args.arm == "off":
            self.ask("Timers", "0")
        elif args.arm == "toggle":
            self.ask("Timers", "2")

        global_state, slots = self._fetch_timers()
        if not slots:
            return self._fail("timers", "no reply to `Timers`")
        used = sorted(i for i, cfg in slots.items() if timer_in_use(cfg))

        lines = ["global : %s%s" % (global_state or "?",
                                    "" if str(global_state).upper() == "ON"
                                    else "   <- no timer fires until you run: %s --enable-all"
                                         % shortcut_name(self.topic, "timers")),
                 "slots  : %d of %d configured" % (len(used), len(slots))]
        if used:
            lines.append("idx  arm  mode     time     win  days(SMTWTFS) rep  out  action  (days)")
            lines += ["  " + self._format_slot(i, slots[i]) for i in used]
        else:
            lines.append("(every slot is empty: Enable=0, Time=00:00, Days=0000000)")
        self._emit({"action": "timers", "ok": True, "global": global_state,
                    "configured": used, "timers": slots}, lines)
        return 0

    def cmd_timer(self) -> int:
        args = self.args
        index = args.timer_index
        if not 1 <= index <= TIMER_COUNT:
            return self._fail("timer", "--timer-index must be 1..%d" % TIMER_COUNT)

        if args.clear:
            self.ask("Timer%d" % index, "0")
            _global, slots = self._fetch_timers()
            cfg = slots.get(index, dict(TIMER_TEMPLATE))
            self._emit({"action": "timer", "ok": True, "index": index, "cleared": True,
                        "timer": cfg},
                       ["action: timer      cleared slot %d" % index,
                        "timer%-2d: %s" % (index, json.dumps(cfg, ensure_ascii=False, sort_keys=True))])
            return 0

        _global, slots = self._fetch_timers()
        cfg = dict(TIMER_TEMPLATE)
        cfg.update(slots.get(index) or {})

        try:
            changes = self._timer_overrides(args, cfg)
        except ValueError as exc:
            return self._fail("timer", str(exc))
        if not changes:
            return self._fail("timer",
                              "nothing to change -- pass --time/--days/--action/--output/... "
                              "or use --clear to wipe the slot")
        cfg.update(changes)

        self.ask("Timer%d" % index, json.dumps(cfg, separators=(",", ":")))
        if self.errors:
            return self._fail("timer", "rejected by the device: %s" % self.errors[-1])

        global_state, slots = self._fetch_timers()
        stored = slots.get(index)
        if stored is None:
            return self._fail("timer", "no read back for slot %d" % index)

        drift = {k: (v, stored.get(k)) for k, v in cfg.items()
                 if canonical_timer_value(k, stored.get(k)) != canonical_timer_value(k, v)}
        notes = []
        if drift:
            notes.append("device stored different values: %s"
                         % ", ".join("%s wanted %s got %s" % (k, a, b) for k, (a, b) in drift.items()))
        elif str(global_state).upper() != "ON":
            notes.append("slot written, but the global `Timers` switch is %s -- run: %s"
                         % (global_state,
                            shortcut_name(self.topic, "timers") + " --enable-all"))

        lines = ["action: timer      slot %d   %s" % (index, "ok" if not drift else "MISMATCH"),
                 "timer%-2d: %s" % (index, json.dumps(stored, ensure_ascii=False, sort_keys=True)),
                 "sets   : %s" % self._describe_slot(stored)]
        lines += ["note:   %s" % n for n in notes]
        self._emit({"action": "timer", "ok": not drift, "index": index, "global": global_state,
                    "timer": stored, "requested": cfg, "note": "; ".join(notes) or None}, lines)
        return 0 if not drift else 1

    @staticmethod
    def _timer_overrides(args, cfg: dict) -> dict:
        """Build the Timer JSON fields the user actually asked to change."""
        changes: dict = {}
        mode = TIMER_MODES[args.mode] if args.mode else int(cfg.get("Mode") or 0)
        if args.mode:
            changes["Mode"] = mode

        if args.time:
            text = args.time.strip()
            if mode == 0:
                match = CLOCK_RE.match(text)
                if not match:
                    raise ValueError("--time must be HH:MM (00:00-23:59) for clock mode, got %r" % text)
                changes["Time"] = "%02d:%02d" % (int(match.group(1)), int(match.group(2)))
            else:
                match = OFFSET_RE.match(text)
                if not match:
                    raise ValueError("--mode %s needs --time as an offset (+/-H:MM, e.g. -0:30), got %r"
                                     % (args.mode, text))
                hours = int(match.group(2))
                if hours > 11:
                    raise ValueError("sunrise/sunset offsets are limited to 0..11 hours, got %d" % hours)
                # Zero pad: the device normalises to "-00:30" anyway, and sending
                # the padded form keeps the read back comparison clean.
                changes["Time"] = "%s%02d:%02d" % (match.group(1), hours, int(match.group(3)))

        if args.days:
            changes["Days"] = expand_days(args.days)
        if args.timer_action:
            changes["Action"] = TIMER_ACTIONS[args.timer_action]
        if args.output is not None:
            if not 1 <= args.output <= 16:
                raise ValueError("--output must be 1..16, got %d" % args.output)
            changes["Output"] = args.output
        if args.window is not None:
            if not 0 <= args.window <= 15:
                raise ValueError("--window must be 0..15 minutes of random jitter, got %d" % args.window)
            changes["Window"] = args.window
        if args.repeat is not None:
            changes["Repeat"] = 1 if args.repeat else 0
        if args.enable:
            changes["Enable"] = 1
        elif args.disable:
            changes["Enable"] = 0
        return changes

    # ------------------------------------------------------------------- clock
    def cmd_time(self) -> int:
        args = self.args
        written = None
        if args.set_tz:
            written = self.set_timezone(args.set_tz)

        payload = None
        for _topic, body in self.ask("Status", "7", self._timeout_for("timers")):
            if '"StatusTIM"' in body:
                payload = body
        if payload is None:
            return self._fail("time", "no reply to `Status 7`")
        info = self._json_field(payload, "StatusTIM") or {}

        utc = str(info.get("UTC", "?"))
        local = str(info.get("Local", "?"))
        offset = _utc_offset_hours(utc, local)
        # Show the device's own UTC converted to Beijing, so the offset maths is
        # verifiable instead of being mixed up with the host clock.
        try:
            beijing = datetime.strptime(utc.rstrip("Z"), "%Y-%m-%dT%H:%M:%S") + timedelta(hours=8)
        except ValueError:
            beijing = datetime.now(timezone.utc) + timedelta(hours=8)

        lines = ["action: time       device clock (from `Status 7`)",
                 "utc        : %s" % utc,
                 "device loc : %s" % local,
                 "timezone   : %s%s" % (info.get("Timezone", "?"),
                                        "" if offset is None else "   (applied offset UTC%+g)" % offset),
                 "beijing    : %s" % beijing.strftime("%Y-%m-%dT%H:%M:%S"),
                 "sunrise    : %s   sunset: %s" % (info.get("Sunrise", "?"), info.get("Sunset", "?"))]
        notes = []
        if written is not None:
            if written.get("ok"):
                lines.insert(1, "wrote      : Timezone %s -> device reports %s"
                             % (written.get("sent"), written.get("device")))
            else:
                lines.insert(1, "wrote      : FAILED -- %s" % written.get("error"))
                notes.append(str(written.get("error")))
        if offset is None:
            notes.append("could not derive the applied UTC offset -- is the clock NTP synced?")
        elif abs(offset - 8.0) > 0.01:
            shift = 8.0 - offset
            fired = (datetime(2000, 1, 1, 8, 0) + timedelta(hours=shift)).strftime("%H:%M")
            notes.append("device local time is UTC%+g, i.e. %.1f h behind Beijing. `Timer` times are "
                         "DEVICE local time, so a 08:00 timer would fire at %s Beijing."
                         % (offset, shift, fired))
            # China has no DST, so a fixed offset is fine -- but the accepted
            # spelling is the zero-stripped one, which is easy to get wrong.
            notes.append("fix it (China has no DST, so a fixed offset is fine): %s"
                         % (shortcut_name(self.topic, "time") + " --set-tz +8:00"))
        lines += ["note:   %s" % n for n in notes]
        ok = written is None or bool(written.get("ok"))
        self._emit({"action": "time", "ok": ok, "utc": utc, "local": local,
                    "timezone": info.get("Timezone"), "offset_hours": offset,
                    "sunrise": info.get("Sunrise"), "sunset": info.get("Sunset"),
                    "wrote": written, "note": " ".join(notes) or None}, lines)
        return 0 if ok else 1

    # ---------------------------------------------------------------- actions
    def run(self, action: str) -> int:
        args = self.args
        self.settle(args.grace)             # catch retained LWT / stat/POWER

        if action == "diag":
            return self.diagnose()

        if action == "timers":
            return self.cmd_timers()

        if action == "timer":
            return self.cmd_timer()

        if action == "time":
            return self.cmd_time()

        if action == "status":
            state = self.query_state(self._timeout_for(action))
            if state is None:
                note = self._error_note() or "timeout: no reply to `Status 0`"
                self._report("status", None, note, ok=False)
                return 2
            self._report("status", state)
            return 0

        if action in DURATION_ACTIONS:
            # pulse    : on for --seconds, then back off
            # pulseoff : off for --seconds, then back on -- the mirror image, handy
            #            for "power-cycle the router after five seconds".
            first, second = (("ON", "OFF") if action == "pulse"
                             else ("OFF", "ON"))
            code = self.switch(first, "%s(%s)" % (action, first.lower()))
            if code != 0:
                return code
            time.sleep(args.seconds)
            return self.switch(second, "%s(%s)" % (action, second.lower()))

        return self.switch(SWITCH_PAYLOADS[action], action)

    def switch(self, payload: str, label: str) -> int:
        """Send a POWER command, then read the relay state back."""
        command, note = self._relay_command()
        code, state, rejection = self._attempt(command, payload)
        if code is not None:
            return code

        if rejection is not None and command != ALL_RELAYS_CMD:
            # The device rejected the command outright. On this firmware relay 1
            # is not registered, so retry through POWER0 ("all relays").
            sys.stderr.write(
                "[fallback] `%s` rejected by the device (%s); retrying with `%s`\n"
                % (command, rejection, ALL_RELAYS_CMD)
            )
            rejected = command
            command = ALL_RELAYS_CMD
            note = "sent `%s` because the device rejects `%s`" % (ALL_RELAYS_CMD, rejected)
            code, state, rejection = self._attempt(command, payload)
            if code is not None:
                return code

        if rejection is not None:
            self._report(label, None, "rejected by the device: %s" % rejection, ok=False)
            return 1

        if state is None:
            note = self._error_note() or "timeout: no reply from the device"
            self._report(label, None, note, ok=False)
            return 2

        if payload in ("ON", "OFF") and state != payload:
            # The device pushes unsolicited STATUS11/STATE messages (TelePeriod is
            # 300 s), and one of them can land between our publish and the echo
            # carrying a pre-command value. Re-read explicitly before crying wolf.
            fresh = self.query_state(max(2.0, self.timeout / 2))
            if fresh == payload:
                self._report(label, fresh, "confirmed by re-reading `Status 0`")
                return 0
            if fresh is not None:
                state = fresh

        if payload in ("ON", "OFF") and state != payload:
            self._report(label, state,
                         "device reports %s after asking for %s%s"
                         % (state, payload, " (%s)" % note if note else ""), ok=False)
            return 1

        self._report(label, state, note)
        return 0

    def _attempt(self, command: str, payload: str):
        """Publish once and read back. Returns (exit_code|None, state, rejection)."""
        self.reset_state()
        t0 = time.time()
        self.publish(command, payload)
        # POWER0 never echoes, so waiting the full --timeout here just makes the
        # command look like it hung. Poll `Status 0` instead once the echo window
        # has passed -- the poll result is authoritative either way.
        state = self.wait_for_update(min(ECHO_WINDOW, self.timeout), t0)

        rejection = self._error_note()
        if state is not None or rejection is not None:
            return None, state, rejection

        # No echo and no complaint: this firmware is quiet, so ask explicitly.
        if self.args.verbose:
            sys.stderr.write("[verify] no echo for `%s %s`, polling `Status 0`\n"
                             % (command, payload))
        state = self.query_state(max(1.0, self.timeout / 2))
        return None, state, self._error_note()

    def _relay_command(self) -> tuple[str, str | None]:
        relay = self.args.relay
        if relay == 0:
            return ALL_RELAYS_CMD, "targeting all relays"
        if relay == 1:
            return "POWER", None
        return "POWER%d" % relay, None

    def _error_note(self) -> str | None:
        return self.errors[-1] if self.errors else None

    # ------------------------------------------------------------ diagnostics
    def diagnose(self) -> int:
        """Report what relay hardware this Tasmota build actually exposes."""
        print("device     : %s  ->  topic %s" % (self.args.device, self.topic))
        print("online     : %s" % self._online_text())

        self.reset_state()
        for command, payload in (("Module", ""), ("Template", ""),
                                 ("Gpio", ""), ("Status", "0")):
            self.publish(command, payload)
            time.sleep(0.7)

        firmware = module = template = gpio = None
        for _topic, payload in list(self.replies):
            if '"StatusFWR"' in payload:
                firmware = (self._json_field(payload, "StatusFWR") or {}).get("Version")
            elif '"NAME"' in payload and '"GPIO"' in payload:
                template = payload
            elif '"GPIO0"' in payload:
                gpio = payload
            elif payload.startswith('{"Module"'):
                module = self._json_field(payload, "Module")

        print("firmware   : %s" % (firmware or "?"))
        print("module     : %s" % (json.dumps(module, ensure_ascii=False) if module else "?"))
        if template:
            print("template   : %s" % template)
            print("             a mapped relay would appear here as 21/22/23/24/25")
        if gpio:
            pins = gpio.count('"GPIO')
            free = gpio.count('":0')
            verdict = ("NO relay is configured" if free == pins
                       else "some pins are assigned, see the map below")
            print("gpio map   : %d/%d pins unassigned -> %s" % (free, pins, verdict))
            print("             %s" % gpio)

        state = self.query_state(self._timeout_for("status"))
        print("relay state: %s%s" % (state or "?", "   (read via `Status 0`)" if state else ""))
        return 0

    @staticmethod
    def _json_field(payload: str, key: str):
        try:
            return json.loads(payload).get(key)
        except ValueError:
            return None

    def _clock_info(self) -> dict:
        """The StatusTIM object, or {} when the device did not answer."""
        payload = None
        for _topic, body in self.ask("Status", "7", self._timeout_for("timers")):
            if '"StatusTIM"' in body:
                payload = body
        if payload is None:
            return {}
        return self._json_field(payload, "StatusTIM") or {}

    def set_timezone(self, offset: str) -> dict:
        """Write the device timezone and CONFIRM it took.

        `Timezone` answers in a /RESULT, but a rejected value still echoes a
        well-formed reply -- it just echoes the old zone -- so the only honest
        check is to read `Status 7` back and compare. Measured on 15.5.0, a
        zero-padded hour is rejected outright, which is exactly the spelling
        everyone reaches for, so trying each candidate matters.
        """
        wanted = _tz_parts(offset)
        if not wanted:
            return {"ok": False, "error": "no offset given"}
        tried = []
        last = ""
        for candidate in timezone_spellings(offset):
            self.ask("Timezone", candidate, self._timeout_for("switch"))
            info = self._clock_info()
            shown = str(info.get("Timezone", ""))
            applied = _tz_parts(shown)
            tried.append({"sent": candidate, "device": shown})
            last = applied or shown
            if applied == wanted:
                return {"ok": True, "offset": last, "device": shown,
                        "sent": candidate, "tried": tried,
                        "utc": info.get("UTC"), "local": info.get("Local")}
        return {"ok": False, "offset": last, "tried": tried,
                "error": "the device did not accept %s (device reports %s)"
                % (offset.strip(), last or "nothing")}

    # -------------------------------------------------------------- reporting
    def _emit(self, data: dict, lines: list[str]) -> None:
        """Print either the JSON object or the human readable lines."""
        if self.args.json:
            print(json.dumps(data, ensure_ascii=False, sort_keys=True))
            return
        for line in lines:
            print(line)

    def _fail(self, action: str, note: str) -> int:
        self._emit({"action": action, "ok": False, "note": note},
                   ["action: %-10s failed" % action, "note:   %s" % note])
        return 1

    def _report(self, action: str, state: str | None, note: str | None = None,
                ok: bool | None = None) -> None:
        if ok is None:
            ok = state is not None
        if self.args.json:
            print(json.dumps({
                "device": self.args.device,
                "topic": self.topic,
                "action": action,
                "state": state,
                "online": self.online,
                "source": self.state_src,
                "ok": ok,
                "note": note,
            }, ensure_ascii=False))
            return

        if state is not None:
            print("action: %-10s state: %-3s  online: %s" % (action, state, self._online_text()))
        else:
            print("action: %-10s failed          online: %s" % (action, self._online_text()))
        if note:
            print("note:   %s" % note)

    def _online_text(self) -> str:
        if self.online is None:
            return "unknown"
        return "yes" if self.online else "no"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Switch a Tasmota plug on/off over MQTT.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("action", choices=list(ACTIONS),
                   help="what to do with the relay (or the device clock/timers)")
    p.add_argument("index", nargs="?", type=int, default=None,
                   help="timer: the slot to touch, 1..16 (same as --timer-index)")
    p.add_argument("--relay", type=int, default=1,
                   help="relay index; 0 = all relays (POWER0), 1 = POWER, n = POWERn")
    p.add_argument("--seconds", type=float, default=5.0,
                   help="pulse: how long to stay ON / pulseoff: how long to stay OFF"
                        " (a file name like -pulseoff-120.py sets this too)")

    # --- timer / time options -------------------------------------------------
    p.add_argument("--timer-index", "--slot", type=int, default=1, dest="timer_index",
                   help="timer: which slot to touch, 1..16")
    p.add_argument("--time", default=None,
                   help="timer: HH:MM for clock mode, +/-H:MM offset for sunrise/sunset")
    p.add_argument("--days", default=None,
                   help="timer: SMTWTFS mask, day list (Mon,Wed,Fri), range or weekdays/weekend/all")
    p.add_argument("--mode", choices=["clock", "sunrise", "sunset"], default=None,
                   help="timer: time base (clock = fixed local time)")
    p.add_argument("--action", "--trigger", dest="timer_action",
                   choices=["on", "off", "toggle", "rule"], default=None,
                   help="timer: what fires; `rule` triggers Clock#Timer=<n> in Rules")
    p.add_argument("--output", type=int, default=None,
                   help="timer: output/relay number to drive, 1..16")
    p.add_argument("--window", type=int, default=None,
                   help="timer: random jitter in minutes, 0..15")
    p.add_argument("--repeat", dest="repeat", action="store_true", default=None,
                   help="timer: keep firing every matching day")
    p.add_argument("--once", dest="repeat", action="store_false",
                   # default=None (not store_false's implicit True) so that omitting
                   # BOTH flags leaves the slot's Repeat field untouched.
                   default=None,
                   help="timer: fire once, then disarm the slot")
    p.add_argument("--enable", action="store_true", help="timer: arm this slot")
    p.add_argument("--disable", action="store_true", help="timer: disarm this slot")
    p.add_argument("--clear", action="store_true", help="timer: wipe the slot back to empty")
    p.add_argument("--enable-all", dest="arm", action="store_const", const="on",
                   help="timers: switch the global `Timers` flag ON")
    p.add_argument("--disable-all", dest="arm", action="store_const", const="off",
                   help="timers: switch the global `Timers` flag OFF")
    p.add_argument("--toggle-all", dest="arm", action="store_const", const="toggle",
                   help="timers: flip the global `Timers` flag")
    p.add_argument("--set-tz", default=None, metavar="OFFSET",
                   help="time: write the device timezone, e.g. +8:00 for China "
                        "(the firmware rejects a zero-padded hour like +08:00, "
                        "so both spellings are accepted and converted)")

    p.add_argument("--mqtt-host", default=DEF_HOST)
    p.add_argument("--mqtt-port", type=int, default=DEF_PORT)
    p.add_argument("--user", default=DEF_USER)
    p.add_argument("--password", default=DEF_PASS)
    p.add_argument("--tls", action="store_true", default=DEF_TLS, help="use TLS (port 8883)")
    p.add_argument("--ca", default=DEF_CA, help="CA certificate used for TLS")
    p.add_argument("--device", "-d", default=DEVICE_NAME, metavar="NAME",
                   help="device to control: chip id (6FCE2C), DVES_6FCE2C, or a "
                        "full topic (tasmota_6FCE2C / kitchen_plug)")
    p.add_argument("--chip-id", default=None, metavar="ID",
                   help="legacy alias of --device (env: MQTT_DEVICE / MQTT_CHIP_ID)")
    p.add_argument("--topic", default=None, metavar="TOPIC",
                   help="override the full Tasmota topic, taken verbatim")
    p.add_argument("--client-id", default=None,
                   help="MQTT client id (default: random; never reuse the device id)")
    p.add_argument("--retain", action="store_true",
                   help="publish the command with the retain flag")
    p.add_argument("--timeout", type=float, default=6.0, help="seconds to wait for a reply")
    p.add_argument("--grace", type=float, default=0.6,
                   help="seconds to collect retained state after subscribing")
    p.add_argument("--json", action="store_true", help="machine readable output")
    p.add_argument("-v", "--verbose", action="store_true", help="log every MQTT message")

    if DEF_TLS and DEF_PORT == 1883:
        p.set_defaults(mqtt_port=8883)           # keep the port in sync with --tls
    return p


def preprocess_argv(argv: list[str]) -> list[str]:
    """Make values that begin with '-' survive argparse.

    argparse treats a bare "-0:30" as the start of an option and then complains
    that --time has no argument. Joining the pair as "--time=-0:30" fixes it.
    """
    patched: list[str] = []
    index = 0
    while index < len(argv):
        item = argv[index]
        if (item in ("--time", "--set-tz") and index + 1 < len(argv)
                and argv[index + 1][:1] in ("-", "+") and not argv[index + 1].startswith("--")):
            patched.append("%s=%s" % (item, argv[index + 1]))
            index += 2
            continue
        patched.append(item)
        index += 1
    return patched


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(preprocess_argv(sys.argv[1:] if argv is None else argv))
    if args.index is not None:
        if args.action not in ("timer", "timers"):
            sys.stderr.write("ERROR: the positional number only applies to `timer`/`timers`\n")
            return 1
        args.timer_index = args.index

    # Priority: --topic (verbatim) > --chip-id (legacy) > --device/default, where
    # the default was already overridden by MQTT_DEVICE / MQTT_CHIP_ID.
    try:
        args.chip_id, args.topic = resolve_device(args.topic or args.chip_id or args.device)
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    if args.verbose:
        sys.stderr.write("[device] %s -> topic %s\n" % (args.device, args.topic))

    if args.tls and not os.path.isfile(args.ca):
        sys.stderr.write("WARNING: CA file not found: %s\n" % args.ca)

    plug = TasmotaPlug(args)
    try:
        plug.connect()
    except Exception as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1

    try:
        return plug.run(args.action)
    except KeyboardInterrupt:
        return 1
    except Exception as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    finally:
        plug.close()

# --------------------------------------------------------------------------- #
# The multi-device panel. Appended to a copy of the engine, the same way the
# single-device panel is, so it can use TasmotaPlug, build_parser() and the rest
# of the engine directly. Only the standard library is imported: the generated
# file must run with nothing but paho-mqtt installed.
# --------------------------------------------------------------------------- #
import copy as _copy
import hashlib as _hashlib
import hmac as _hmac
import html as _html
import http.cookies
import http.server
import json as _json
import os as _os
import re as _re
import secrets as _secrets
import socket as _socket
import threading as _threading
import time as _time
import urllib.parse
import webbrowser

HUB_VERSION = "1.1"
HUB_PORT = 8765                       # the default listen port
HUB_REQUEST_TIMEOUT = 12.0            # hard ceiling for one user action, seconds
HUB_READ_TIMEOUT = 4.0                # ... and for a plain state read, seconds
# 4 s, not 2.5 s: this talks to a plug through a broker on the public internet,
# where a healthy `Status 0` comes back in 0.2 s but a busy one can take a
# second -- and a too-tight budget turns that into "no reply to `Status 0`",
# which looks exactly like the device being offline when it is not.
#
# A read also gets more than one go now (HUB_READ_ATTEMPTS). A QoS 0 publish can
# be dropped by the broker or the Wi-Fi hop, and this is the path the page hits
# every few seconds -- so one lost packet used to surface as "no reply to
# `Status 0`" for a whole refresh. Two attempts of 2.2 s cost the device ~0.3 s
# in the normal case (it answers in 0.15 s) and still give up in under 5 s.
HUB_READ_ATTEMPTS = 2                 # goes at one state read before giving up
HUB_READ_ATTEMPT_SECONDS = 2.2        # per attempt; 2 x this stays near 4 s
HUB_READ_RETRY_DELAY = 0.35           # pause between attempts, seconds
# The page's own cadence. 8 s, not 4 s: a relay state is not a sparkline, and at
# 4 s the interval exactly equalled the read budget -- so the tick after a slow
# one always stacked another request on top of an unanswered one. A press on any
# button drops the beat to HUB_REFRESH_BURST_MS for a few seconds, which is where
# the responsiveness actually matters, and a failed read backs off instead of
# hammering a plug that is having a bad minute.
HUB_REFRESH_MS = 8000                 # how often the page re-reads the open device
HUB_REFRESH_MIN_MS = 1000             # --refresh floor: nobody gets to hammer a plug
HUB_REFRESH_MAX_MS = 120000           # ... and ceiling: 2 minutes is still "live"
HUB_REFRESH_BURST_MS = 1000           # after you press a button, re-read this fast
HUB_REFRESH_BURST_SECONDS = 6         # ... for this long, then back to the beat
HUB_REFRESH_FAIL_MS = 15000           # first back-off after a failed read
HUB_REFRESH_FAIL_MAX_MS = 60000       # ... doubling up to here, reset on success
HUB_SWEEP_SECONDS = 45                # how often the LIST refreshes every device
HUB_SWEEP_MIN_SECONDS = 5             # --sweep floor: each tick costs one round
HUB_SWEEP_MAX_SECONDS = 3600          # ... and ceiling, for a fleet of sleeping plugs
# The energy card gets its own beat, and it is NOT the relay beat. A relay state
# changes when somebody presses something; power is a number that moves on its
# own, so it is worth looking at more often -- but HALF as often as the state
# read, not twice, because every read of one plug shares ONE queue (see
# Fleet._lock_for) and a faster energy beat would only make the relay read
# slower. Its own floor and ceiling keep --energy from being turned into a
# poll loop, and the card backs off on its own when a plug has no sensor.
HUB_ENERGY_MS = 5000                  # how often the page re-reads power/voltage
HUB_ENERGY_MIN_MS = 1000              # --energy floor
HUB_ENERGY_MAX_MS = 300000            # --energy ceiling: 5 minutes is still "live"
HUB_ENERGY_FAIL_MS = 20000            # first back-off when a plug does not answer
HUB_ENERGY_FAIL_MAX_MS = 120000       # ... doubling up to here, reset on success
HUB_ENERGY_MAX_AGE = 2.4              # seconds a stored reading is still "live"
HUB_ENERGY_NOTE_MAX = 160             # longest sensor note the page will render
HUB_MAX_DEVICES = 32                  # refuse to open more MQTT links than this
HUB_LIST_NAME = "mqtt-web-devices.json"
HUB_SETTINGS_NAME = "mqtt-web-settings.json"
HUB_CYCLE_NAME = "mqtt-web-cycle.json"   # remembered cycle CONFIG, never progress
# The administrator's book of ORIGINAL device passwords. Its own file, NOT
# beside anybody's list: it is a property of the hardware, not of a login.
HUB_VAULT_NAME = "mqtt-web-vault.json"
# Who may open it. The first account ever created is the administrator (see
# UserStore.create), and UserStore._ensure_admin() hands the role to the oldest
# account when a file predates the idea of roles entirely.
HUB_ROLE_ADMIN = "admin"
HUB_ROLE_USER = "user"
HUB_DEVICE_PASSWORD_MAX = 128
HUB_PROBE_ID = "_hub_probe_"          # throwaway id for the connection test
DEVICE_ID_RE = _re.compile(r"^[A-Za-z0-9_-]{1,32}$")
# A broker host is a name, an IPv4 or an IPv6 literal -- never anything that
# could smuggle a topic, a path or a shell character into the connect() call.
BROKER_HOST_RE = _re.compile(r"^[A-Za-z0-9._:-]{1,255}$")
BROKER_TIMEOUT_MIN = 1.0
BROKER_TIMEOUT_MAX = 60.0
HUB_USERS_NAME = "mqtt-web-users.json"   # accounts: name, email, salt + hash
HUB_USERS_DIR = "mqtt-web-users"         # one device list per account, in here
HUB_SESSION_HOURS = 12                   # a session survives this many hours of idle
HUB_IDLE_MINUTES = 20                    # ...then the account's MQTT links are parked
HUB_PASSWORD_MIN = 8
HUB_PASSWORD_MAX = 128
HUB_MAX_USERS = 50
HUB_LOGIN_LIMIT = 8                      # wrong passwords before a cool-down
HUB_LOGIN_COOLDOWN = 300.0
HUB_HASH_ROUNDS = 200000
HUB_SESSION_COOKIE = "mqttpy_session"
# A name that also becomes a FILENAME, so it stays inside [A-Za-z0-9._-] and
# starts with a letter: no leading dots, no separators, nothing that escapes.
USERNAME_RE = _re.compile(r"^[A-Za-z][A-Za-z0-9._-]{2,31}$")
EMAIL_RE = _re.compile(r"^[^@\s]{1,64}@[^@\s.]+(?:\.[^@\s.]+)+$")
AUTH_ROUTES = ("/api/auth/me", "/api/auth/login", "/api/auth/register",
               "/api/auth/logout", "/api/auth/account", "/api/auth/role")


# --------------------------------------------------------------- the listen socket
# On Windows, SO_REUSEADDR -- which http.server sets for you -- does NOT merely
# allow rebinding a port in TIME_WAIT: it lets a second socket bind AND listen on
# an address another process is already serving.  The second copy then shows up in
# netstat as LISTENING and the kernel silently picks one of them per connection, so
# two panels appear to work while each keeps its own MQTT sessions and caches.  That
# is the worst kind of failure: no error, wrong answers.
#
# SO_EXCLUSIVEADDRUSE is the Windows-only opposite: bind fails outright if anyone
# already owns the address.  It is not defined on Linux (there SO_REUSEADDR already
# behaves exclusively for live listeners), so the guard below is a no-op elsewhere.
class ExclusiveThreadingHTTPServer(http.server.ThreadingHTTPServer):
    """ThreadingHTTPServer that refuses to share its port with another process."""

    daemon_threads = True

    def server_bind(self):
        exclusive = getattr(_socket, "SO_EXCLUSIVEADDRUSE", None)
        if exclusive is not None:
            # Must be set BEFORE bind().  A plain setsockopt here would raise
            # WinError 10022 because the option only applies pre-bind.
            self.socket.setsockopt(_socket.SOL_SOCKET, exclusive, 1)
        # Keep this at 0 when the exclusive option did apply: the two are mutually
        # exclusive on Windows and setting both fails the bind with 10022.
        self.allow_reuse_address = exclusive is None
        http.server.ThreadingHTTPServer.server_bind(self)


# ------------------------------------------------------- addresses worth printing
def _reachable_hosts() -> tuple:
    """Every IPv4 address somebody could type to reach this panel: loopback, then LAN.

    Nothing is sent anywhere. The 8.8.8.8 trick only asks the routing table which
    local address it would pick for the outside world -- no packet leaves the box --
    and every step is guarded, because a laptop with Wi-Fi off must still be able
    to print a banner and serve localhost. Link-local 169.254.* is dropped: it
    means "no DHCP server answered" and nobody can route to it on purpose.
    """
    hosts = ["127.0.0.1"]
    try:
        for info in _socket.getaddrinfo(_socket.gethostname(), None, _socket.AF_INET):
            host = info[4][0]
            if host not in hosts and not host.startswith("169.254."):
                hosts.append(host)
    except _socket.error:
        pass
    try:
        probe = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        try:
            probe.connect(("8.8.8.8", 80))       # routing table only, no traffic
            host = probe.getsockname()[0]
            if host not in hosts and not host.startswith("169.254."):
                hosts.append(host)
        finally:
            probe.close()
    except _socket.error:
        pass
    return tuple(hosts)


def _listen_urls(host: str, port: int, token: str | None = None) -> tuple:
    """URLs for the startup banner: (this machine's, everybody else's).

    A wildcard bind -- the default, which is what makes the panel reachable from a
    phone -- has no single address of its own, so every real address is listed.
    An explicit bind answers with exactly that one.
    """
    suffix = ("?token=" + urllib.parse.quote(token)) if token else ""

    def url(name: str) -> str:
        return "http://%s:%d/%s" % (name, port, suffix)

    if host not in ("0.0.0.0", "::", ""):
        return (url(host), ())
    found = _reachable_hosts()
    return (url(found[0]), tuple(url(name) for name in found[1:]))


# ---------------------------------------------------------------- time keeping
def _fmt_offset(hours: float | None) -> str:
    """Render a UTC offset the way a human writes it: +08:00, -03:30, ?"""
    if hours is None:
        return "?"
    sign = "+" if hours >= 0 else "-"
    total = int(round(abs(hours) * 60))
    return "%s%02d:%02d" % (sign, total // 60, total % 60)


def _utc_stamp() -> str:
    """Now, as 2026-09-26T18:30:00 -- a note's birthday, in UTC, for the JSON."""
    return _time.strftime("%Y-%m-%dT%H:%M:%S", _time.gmtime())


def _device_offset(utc: str, local: str) -> float | None:
    """The offset the DEVICE is applying, derived from its own UTC/Local pair.

    Both stamps are wall-clock text with no zone marker, so subtracting them is
    the only way to learn the offset. `Local` carries no trailing Z. This is what
    catches the firmware's default +01:00, which silently makes an 08:00 timer
    fire at 15:00 Beijing time.
    """
    try:
        import datetime as _dt
        u = _dt.datetime.strptime(utc.rstrip("Z"), "%Y-%m-%dT%H:%M:%S")
        l = _dt.datetime.strptime(local.rstrip("Z"), "%Y-%m-%dT%H:%M:%S")
    except Exception:                                # noqa: BLE001
        return None
    return (l - u).total_seconds() / 3600.0


def _as_utc(stamp: str) -> str:
    """A bare wall-clock stamp -> the same instant spelled with a trailing Z.

    The page compares these strings, so an unmarked stamp and a Z-marked one that
    name the same instant must not look different.
    """
    text = stamp.strip()
    if not text or text == "?":
        return "?"
    return text if text.endswith("Z") else text + "Z"


# ------------------------------------------------------------- the device book
class DeviceBook:
    """The device list on disk: a tiny human-editable JSON document.

    Deliberately boring. The file is the user's data, so every write is atomic
    (temp file + os.replace) and a file we cannot parse is NEVER overwritten --
    the panel reports it and leaves the bytes alone. Losing a hand-curated list to
    a half-finished save would be unforgivable; refusing to start is merely
    annoying, and the error text says exactly what to fix.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = _threading.Lock()
        self.devices: list[dict] = []
        self.error: str | None = None
        self.load()

    # ------------------------------------------------------------------ disk
    def load(self) -> None:
        """Read the list. A missing file is normal; an unreadable one is not."""
        with self._lock:
            self.error = None
            if not _os.path.exists(self.path):
                self.devices = []
                return
            try:
                with open(self.path, encoding="utf-8") as handle:
                    raw = _json.load(handle)
            except (OSError, ValueError) as exc:
                self.devices = []
                self.error = ("cannot read %s (%s). Fix or move the file, then "
                              "reload -- nothing has been overwritten."
                              % (_os.path.basename(self.path), exc))
                return
            devices = raw.get("devices") if isinstance(raw, dict) else None
            if not isinstance(devices, list):
                self.devices = []
                self.error = ("%s has no \"devices\" list. Fix the file, then "
                              "reload -- nothing has been overwritten."
                              % _os.path.basename(self.path))
                return
            clean: list[dict] = []
            seen: set[str] = set()
            for item in devices:
                if not isinstance(item, dict):
                    continue
                ident = normalize_device_id(str(item.get("id", "")))
                if not ident or ident in seen:
                    continue            # skip junk and duplicates, keep the rest
                seen.add(ident)
                entry = {"id": ident, "note": str(item.get("note", "") or "")}
                added = item.get("added")
                if isinstance(added, str) and added:
                    entry["added"] = added
                clean.append(entry)
            self.devices = clean

    def save(self) -> None:
        """Write the list atomically, with a .bak of the previous version.

        Temp file + os.replace means a crash mid-write leaves the old file intact
        rather than a truncated one. The .bak is plain insurance against a bad
        edit that the user only notices later.
        """
        with self._lock:
            directory = _os.path.dirname(_os.path.abspath(self.path)) or "."
            # A per-account list lives in a subfolder the panel may not have made
            # yet, and nothing else is in a position to know that.
            try:
                _os.makedirs(directory, exist_ok=True)
            except OSError:
                pass            # a read-only folder fails again below, said plainly
            temp = _os.path.join(directory, ".%s.tmp" % _os.path.basename(self.path))
            payload = {"version": 1, "devices": self.devices}
            with open(temp, "w", encoding="utf-8", newline="\n") as handle:
                _json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            if _os.path.exists(self.path):
                backup = self.path + ".bak"
                try:
                    if _os.path.exists(backup):
                        _os.remove(backup)
                    _os.replace(self.path, backup)
                except OSError:
                    pass                    # a missing backup must not block the save
            _os.replace(temp, self.path)

    # ------------------------------------------------------------------- read
    def find(self, ident: str) -> dict | None:
        with self._lock:
            for entry in self.devices:
                if entry["id"] == ident:
                    return dict(entry)
        return None

    def ids(self) -> list[str]:
        with self._lock:
            return [entry["id"] for entry in self.devices]

    def snapshot(self) -> list[dict]:
        with self._lock:
            return [dict(entry) for entry in self.devices]

    # ------------------------------------------------------------------ write
    # ------------------------------------------------------- id resolution
    def resolve(self, ident: str) -> str:
        """The spelling the LIST already stores for `ident`, or "" if unknown.

        Matching is case-insensitive, and the stored spelling is what comes back.
        MQTT topics are case-sensitive, so the panel must never invent a
        spelling: a user who types `6fce2c` means the `6FCE2C` that is already
        there, and answering with `tasmota_6fce2c` would open a second, silently
        dead topic for the same physical plug. An exact hit wins over a
        case-folded one, so two ids differing only in case keep their own
        spelling as long as they are both stored.
        """
        if not ident:
            return ""
        for entry in self.devices:
            if entry["id"] == ident:
                return entry["id"]
        lowered = ident.lower()
        for entry in self.devices:
            if entry["id"].lower() == lowered:
                return entry["id"]
        return ""

    def add(self, ident: str, note: str, limit: int | None = None) -> tuple[bool, str]:
        ident = normalize_device_id(ident)
        if not ident:
            return False, "a serial must be 1-32 characters of A-Z, a-z, 0-9, _ or -"
        # The cap is the RUNTIME one when the caller passes it: --max-devices is
        # what the page shows as the ceiling, so enforcing the module default here
        # let a panel started with --max-devices 1 accept 32 serials and then
        # display "2 / 1".
        cap = HUB_MAX_DEVICES if limit is None else max(1, int(limit))
        with self._lock:
            twin = self.resolve(ident)
            if twin:
                return False, "%s is already in the list" % twin
            if len(self.devices) >= cap:
                return False, ("the list is full (%d devices); raise --max-devices"
                               % cap)
            self.devices.append({"id": ident, "note": note or "", "added": _utc_stamp()})
        self.save()
        return True, ident

    def set_note(self, ident: str, note: str) -> tuple[bool, str]:
        with self._lock:
            stored = self.resolve(ident)
            if not stored:
                return False, "%s is not in the list" % ident
            for entry in self.devices:
                if entry["id"] == stored:
                    entry["note"] = note or ""
                    break
        self.save()
        return True, stored

    def rename(self, old: str, new: str) -> tuple[bool, str]:
        """Change the serial in place, keeping its note and position."""
        new = normalize_device_id(new)
        if not new:
            return False, "a serial must be 1-32 characters of A-Z, a-z, 0-9, _ or -"
        with self._lock:
            stored = self.resolve(old)
            if not stored:
                return False, "%s is not in the list" % old
            twin = self.resolve(new)
            if twin and twin != stored:
                return False, "%s is already in the list" % twin
            for entry in self.devices:
                if entry["id"] == stored:
                    entry["id"] = new
                    break
        self.save()
        return True, new

    def remove(self, ident: str) -> tuple[bool, str]:
        with self._lock:
            stored = self.resolve(ident)
            if not stored:
                return False, "%s is not in the list" % ident
            self.devices = [entry for entry in self.devices if entry["id"] != stored]
        self.save()
        return True, stored


def normalize_device_id(text: str) -> str:
    """A user-typed serial -> the bare chip id we store, or empty if it is junk.

    Accepts what people actually paste -- 6FCE2C, DVES_6FCE2C, tasmota_6FCE2C
    -- and reduces all three to 6FCE2C, because the topic is
    always derived as tasmota_<id>. Storing the full topic would mean two ways to
    say the same thing and a list that quietly holds both.

    Case is kept exactly as typed on purpose: MQTT topics are case-sensitive and
    a plug may legitimately be named in lower case (`kitchen-plug`), so the panel
    must not fold it. DeviceBook.resolve() is what lets a typed `6fce2c` find the
    `6FCE2C` already in the list -- by returning the stored spelling, never by
    inventing a new one.
    """
    text = (text or "").strip()
    for prefix in ("tasmota_", "cmnd/tasmota_", "stat/tasmota_", "tele/tasmota_"):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    if text.upper().startswith("DVES_"):
        text = text[5:]
    return text if DEVICE_ID_RE.match(text) else ""


class DeviceVault:
    """The administrator's book of ORIGINAL device passwords, kept on disk.

    Adding a serial is the only act that lets somebody point this panel at
    hardware they were never given, so it is the only act that needs a second
    opinion. When this book has ANY entries in it, /api/devices/add accepts a
    serial only if the password typed with it matches what the administrator
    wrote down here. An empty book means the feature is not in use and nothing
    is checked -- otherwise the very first device could never be added.

    The passwords are stored AS TYPED, because being able to read one back is
    the entire point of a password book. That makes this file exactly as
    sensitive as the plugs themselves: it is never handed to a non-administrator
    and the page shows it masked until somebody asks to see it.

    Same discipline as every other file here: atomic write, a .bak, and a file
    that cannot be parsed is REPORTED and left alone. Overwriting a garbled book
    would destroy the only copy of hardware passwords that exist nowhere else.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = _threading.Lock()
        self.entries: list[dict] = []
        self.error: str | None = None
        self.load()

    # ------------------------------------------------------------------ disk
    def load(self) -> None:
        with self._lock:
            self.error = None
            if not _os.path.exists(self.path):
                self.entries = []
                return
            try:
                with open(self.path, encoding="utf-8") as handle:
                    raw = _json.load(handle)
            except (OSError, ValueError) as exc:
                self.entries = []
                self.error = ("cannot read %s (%s). Fix or move the file, then "
                              "reload -- nothing has been overwritten."
                              % (_os.path.basename(self.path), exc))
                return
            rows = raw.get("devices") if isinstance(raw, dict) else None
            if not isinstance(rows, list):
                self.entries = []
                self.error = ("%s has no \"devices\" list. Fix the file, then "
                              "reload -- nothing has been overwritten."
                              % _os.path.basename(self.path))
                return
            clean: list[dict] = []
            seen: set[str] = set()
            for item in rows:
                if not isinstance(item, dict):
                    continue
                ident = normalize_device_id(str(item.get("id", "")))
                # Case-insensitive here, unlike the device list: a serial in this
                # book is a lookup key, and `6fce2c` typed by a user has to find
                # the administrator's `6FCE2C` rather than report "not in the book".
                if not ident or ident.lower() in seen:
                    continue
                seen.add(ident.lower())
                clean.append({"id": ident,
                              "password": str(item.get("password", "") or ""),
                              "note": str(item.get("note", "") or ""),
                              "added": str(item.get("added", "") or "")})
            self.entries = clean

    def save(self) -> None:
        with self._lock:
            directory = _os.path.dirname(_os.path.abspath(self.path)) or "."
            try:
                _os.makedirs(directory, exist_ok=True)
            except OSError:
                pass            # a read-only folder fails again below, said plainly
            temp = _os.path.join(directory, ".%s.tmp" % _os.path.basename(self.path))
            payload = {"version": 1, "devices": self.entries}
            with open(temp, "w", encoding="utf-8", newline="\n") as handle:
                _json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            if _os.path.exists(self.path):
                backup = self.path + ".bak"
                try:
                    if _os.path.exists(backup):
                        _os.remove(backup)
                    _os.replace(self.path, backup)
                except OSError:
                    pass                    # a missing backup must not block the save
            _os.replace(temp, self.path)

    # ------------------------------------------------------------------- read
    def find(self, ident: str) -> dict | None:
        wanted = normalize_device_id(ident).lower()
        if not wanted:
            return None
        with self._lock:
            for entry in self.entries:
                if entry["id"].lower() == wanted:
                    return dict(entry)
        return None

    def count(self) -> int:
        with self._lock:
            return len(self.entries)

    def enforcing(self) -> bool:
        """True once the administrator has put something in the book.

        An empty book checks nothing ON PURPOSE: the panel must stay usable
        before the first entry exists, and "empty means off" is a rule nobody
        has to be told twice.
        """
        return self.count() > 0

    def snapshot(self) -> list[dict]:
        with self._lock:
            return [dict(entry) for entry in self.entries]

    def check(self, ident: str, password) -> tuple[bool, str]:
        """May this serial be added? (True, "") or (False, why it may not).

        Messages are for the person adding the device, who is not the
        administrator, so they say what to do about it rather than which field
        failed: the book is not a secret, its contents are.
        """
        if not self.enforcing():
            return True, ""
        stored = self.find(ident)
        if stored is None:
            return False, ("%s 不在管理员维护的设备密码本里 —— 请先联系管理员把它"
                           "建档，再来添加。" % (normalize_device_id(ident) or "这个序列号"))
        typed = password if isinstance(password, str) else ""
        if not _hmac.compare_digest(stored["password"], typed):
            return False, ("%s 的原始密码不对：密码本里有这台设备，但填的密码和它"
                           "对不上。" % stored["id"])
        return True, ""

    # ------------------------------------------------------------------ write
    def add(self, ident: str, password, note="") -> tuple[bool, str]:
        ident = normalize_device_id(ident)
        if not ident:
            return False, "序列号要是 1-32 位字母 / 数字 / _ / -"
        if not isinstance(password, str) or not password.strip():
            return False, "要填这台设备的原始密码"
        if len(password) > HUB_DEVICE_PASSWORD_MAX:
            return False, "密码最多 %d 位" % HUB_DEVICE_PASSWORD_MAX
        with self._lock:
            for entry in self.entries:
                if entry["id"].lower() == ident.lower():
                    return False, "%s 已经在密码本里了" % entry["id"]
            self.entries.append({"id": ident, "password": password,
                                 "note": str(note or ""), "added": _utc_stamp()})
        self.save()
        return True, ident

    def set(self, ident: str, password, note=None) -> tuple[bool, str]:
        """Change the password and/or the note of an entry that is already here.

        `password` empty means "leave the password alone" -- a text field the
        browser autofilled with nothing must never be able to blank a hardware
        password by accident. `note` is only written when it is not None, so
        clearing a note stays possible without also clearing the password.
        """
        stored = self.find(ident)
        if stored is None:
            return False, "%s 不在密码本里" % (normalize_device_id(ident) or ident)
        if password not in (None, ""):
            if not isinstance(password, str):
                return False, "密码要是一段文本"
            if len(password) > HUB_DEVICE_PASSWORD_MAX:
                return False, "密码最多 %d 位" % HUB_DEVICE_PASSWORD_MAX
        with self._lock:
            for entry in self.entries:
                if entry["id"] == stored["id"]:
                    if password not in (None, ""):
                        entry["password"] = password
                    if note is not None:
                        entry["note"] = str(note)
                    break
        self.save()
        return True, stored["id"]

    def remove(self, ident: str) -> tuple[bool, str]:
        stored = self.find(ident)
        if stored is None:
            return False, "%s 不在密码本里" % (normalize_device_id(ident) or ident)
        with self._lock:
            self.entries = [e for e in self.entries if e["id"] != stored["id"]]
        self.save()
        return True, stored["id"]


class BrokerSettings:
    """The broker endpoint the panel dials: editable from the page, kept on disk.

    Split out of the command line on purpose. The endpoint is the one thing a
    user has to change when a broker moves, and making them find the shortcut,
    edit a flag and restart the panel is how a working setup gets abandoned
    instead of re-pointed. So the page owns a second, smaller file beside the
    device list -- same shape, same atomic write, same rule about a file we
    cannot parse: report it, never overwrite it.

    Two rules keep this from being a foot-gun:

    * the password is WRITE-ONLY. It is never sent to the page, and an empty
      field on save means "leave it alone", not "set it to empty" -- clearing is
      a separate, explicit tick. Otherwise a dialog that came up blank would
      silently wipe the credential on the first save;
    * validation happens before anything is applied. A host that is not a host
      is rejected rather than passed to connect(), which is where a bad value
      would turn into a 12-second hang per device.
    """

    FIELDS = ("host", "port", "tls", "user", "password", "timeout")

    def __init__(self, path: str, args=None) -> None:
        self.path = path
        self._lock = _threading.Lock()
        self.error: str | None = None
        self.saved = False
        # What flags/env/defaults gave us: the answer to "go back".
        self.startup = self.from_args(args)
        self.values = dict(self.startup)
        self.load()

    # ------------------------------------------------------------------ disk
    @staticmethod
    def from_args(args) -> dict:
        """The endpoint a Namespace already carries, in settings-file spelling."""
        if args is None:
            return {"host": "", "port": 1883, "tls": False, "user": "",
                    "password": "", "timeout": 6.0}
        return {"host": str(getattr(args, "mqtt_host", "") or ""),
                "port": int(getattr(args, "mqtt_port", 1883) or 1883),
                "tls": bool(getattr(args, "tls", False)),
                "user": str(getattr(args, "user", "") or ""),
                "password": str(getattr(args, "password", "") or ""),
                "timeout": float(getattr(args, "timeout", 6.0) or 6.0)}

    def load(self) -> None:
        """Read the file if there is one. Missing is normal; unreadable is not."""
        with self._lock:
            self.error = None
            self.saved = False
            if not _os.path.exists(self.path):
                return
            try:
                with open(self.path, encoding="utf-8") as handle:
                    raw = _json.load(handle)
            except (OSError, ValueError) as exc:
                self.error = ("cannot read %s (%s). The panel kept the settings it "
                              "started with -- nothing has been overwritten."
                              % (_os.path.basename(self.path), exc))
                return
            if not isinstance(raw, dict):
                self.error = ("%s is not a settings object. The panel kept the "
                              "settings it started with -- nothing has been "
                              "overwritten." % _os.path.basename(self.path))
                return
            clean, problem = self.validate(self._merged(raw))
            if problem:
                self.error = ("%s holds an unusable value (%s). The panel kept the "
                              "settings it started with -- nothing has been "
                              "overwritten." % (_os.path.basename(self.path), problem))
                return
            self.values = clean
            self.saved = True

    def _merged(self, raw: dict) -> dict:
        """File contents over the startup values, so a partial file still works."""
        merged = dict(self.startup)
        for key in self.FIELDS:
            if key in raw:
                merged[key] = raw[key]
        return merged

    def save(self) -> None:
        """Write the endpoint atomically, with a .bak of the previous version."""
        with self._lock:
            directory = _os.path.dirname(_os.path.abspath(self.path)) or "."
            temp = _os.path.join(directory, ".%s.tmp" % _os.path.basename(self.path))
            payload = {"version": 1}
            payload.update({key: self.values[key] for key in self.FIELDS})
            with open(temp, "w", encoding="utf-8", newline="\n") as handle:
                _json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            if _os.path.exists(self.path):
                backup = self.path + ".bak"
                try:
                    if _os.path.exists(backup):
                        _os.remove(backup)
                    _os.replace(self.path, backup)
                except OSError:
                    pass
            _os.replace(temp, self.path)

    def forget(self) -> bool:
        """Delete the file and go back to the startup values."""
        with self._lock:
            self.values = dict(self.startup)
            self.saved = False
            self.error = None
        try:
            if _os.path.exists(self.path):
                _os.remove(self.path)
            return True
        except OSError:
            return False

    # ------------------------------------------------------------ validation
    @classmethod
    def validate(cls, values: dict) -> tuple[dict, str]:
        """A candidate endpoint -> (clean, ""), or (partial, why not).

        Every field is checked before any of it is applied, so a typo cannot
        leave the panel half-pointed at a new broker.
        """
        host = str(values.get("host", "")).strip()
        if not host:
            return {}, "the host is empty"
        if not BROKER_HOST_RE.match(host):
            return {}, ("the host may only contain letters, digits, dot, "
                        "dash, underscore and colon")
        try:
            port = int(values.get("port", 0))
        except (TypeError, ValueError):
            return {}, "the port must be a number"
        if not 1 <= port <= 65535:
            return {}, "the port must be 1..65535"
        try:
            timeout = float(values.get("timeout", 0))
        except (TypeError, ValueError):
            return {}, "the timeout must be a number"
        if not BROKER_TIMEOUT_MIN <= timeout <= BROKER_TIMEOUT_MAX:
            return {}, ("the timeout must be %.0f..%.0f seconds"
                        % (BROKER_TIMEOUT_MIN, BROKER_TIMEOUT_MAX))
        user = str(values.get("user", "") or "")
        if len(user) > 128:
            return {}, "the username is longer than 128 characters"
        password = values.get("password", None)
        if password is None:
            password = ""
        password = str(password)
        if len(password) > 256:
            return {}, "the password is longer than 256 characters"
        return {"host": host, "port": port, "tls": bool(values.get("tls", False)),
                "user": user, "password": password, "timeout": timeout}, ""

    def update(self, changes: dict) -> tuple[bool, str]:
        """Apply a partial change set: unknown keys are ignored, not stored."""
        candidate = dict(self.values)
        for key in self.FIELDS:
            if key in changes:
                candidate[key] = changes[key]
        clean, problem = self.validate(candidate)
        if problem:
            return False, problem
        with self._lock:
            self.values = clean
            self.error = None
        self.save()
        self.saved = True
        return True, ""

    def candidate(self, changes: dict) -> tuple[dict, str]:
        """What the endpoint WOULD be -- for the connection test, nothing saved."""
        merged = dict(self.values)
        for key in self.FIELDS:
            if key in changes:
                merged[key] = changes[key]
        return self.validate(merged)

    # ------------------------------------------------------------------ read
    def as_page(self) -> dict:
        """The endpoint as the page draws it. The password is not in here.

        Deliberately: this dict crosses an HTTP connection that may be on a LAN
        (--listen 0.0.0.0), so answering with the broker's password would hand
        it to anyone who can reach the port. `password_set` is enough for the
        form to say "已保存，留空则不改".
        """
        with self._lock:
            values = dict(self.values)
            saved, error = self.saved, self.error
        return {"host": values["host"], "port": values["port"],
                "tls": values["tls"], "user": values["user"],
                "password_set": bool(values["password"]),
                "timeout": values["timeout"],
                "saved": saved, "error": error,
                "file": _os.path.basename(self.path),
                "startup": {key: self.startup[key]
                            for key in ("host", "port", "tls", "user", "timeout")}}

    def apply_to(self, args) -> None:
        """Push the endpoint onto a Namespace the way the engine reads it.

        The builder renames the engine's --host/--port to --mqtt-host/--mqtt-port,
        so the broker lives in mqtt_host/mqtt_port; Fleet._args_for() copies them
        onto host/port for TasmotaPlug. Writing both spellings here would be
        harmless today but would hide which one is real -- so only the renamed
        pair is set, and the bridge stays the one place that translates.
        """
        with self._lock:
            values = dict(self.values)
        args.mqtt_host = values["host"]
        args.mqtt_port = values["port"]
        args.tls = values["tls"]
        args.user = values["user"]
        args.password = values["password"]
        args.timeout = values["timeout"]


class CycleMemory:
    """The REMEMBERED cycle configuration: last on/off lengths, one file on disk.

    This is the CONFIGURATION memory and it is deliberately NOT a progress
    memory. What gets written is the shape of the loop the user asked for -- how
    long it stays on, how long it stays off, which phase starts, and whether the
    panel may restart it on its own. Where the loop had GOT to is never stored:
    a plug that loses mains comes back with `Rule1` intact but its RuleTimer at
    zero, so a remembered countdown would be a number the device does not agree
    with, and the page says "规则还在，但没在跑" instead of inventing one.

    Same house rules as DeviceBook: atomic write, a .bak, and a file that cannot
    be parsed is reported rather than overwritten -- this one is small, but a
    panel that silently blanked it would leave nothing to restore from.
    """

    FIELDS = ("on", "off", "first")

    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = _threading.Lock()
        self.cycles: dict[str, dict] = {}
        self.error: str | None = None
        self.load()

    # ------------------------------------------------------------------ disk
    def load(self) -> None:
        """Read the remembered settings. A missing file is the normal case."""
        with self._lock:
            self.error = None
            self.cycles = {}
            if not _os.path.exists(self.path):
                return
            try:
                with open(self.path, encoding="utf-8") as handle:
                    raw = _json.load(handle)
            except (OSError, ValueError) as exc:
                self.error = ("cannot read %s (%s). Fix or move the file -- "
                              "nothing has been overwritten."
                              % (_os.path.basename(self.path), exc))
                return
            rows = raw.get("cycles") if isinstance(raw, dict) else None
            if rows is None:
                rows = raw if isinstance(raw, list) else None
            if not isinstance(rows, list):
                self.error = ("%s has no \"cycles\" list. Fix the file, then "
                              "reload -- nothing has been overwritten."
                              % _os.path.basename(self.path))
                return
            for item in rows:
                if not isinstance(item, dict):
                    continue
                entry = self._clean(item)
                if entry:
                    self.cycles[entry["id"]] = entry

    def save(self) -> None:
        """Write atomically, keeping a .bak of the previous version."""
        with self._lock:
            directory = _os.path.dirname(_os.path.abspath(self.path)) or "."
            try:
                _os.makedirs(directory, exist_ok=True)
            except OSError:
                pass
            temp = _os.path.join(directory, ".%s.tmp" % _os.path.basename(self.path))
            payload = {"version": 1,
                       "cycles": [self.cycles[key] for key in sorted(self.cycles)]}
            with open(temp, "w", encoding="utf-8", newline="\n") as handle:
                _json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            if _os.path.exists(self.path):
                backup = self.path + ".bak"
                try:
                    if _os.path.exists(backup):
                        _os.remove(backup)
                    _os.replace(self.path, backup)
                except OSError:
                    pass
            _os.replace(temp, self.path)

    @classmethod
    def _clean(cls, item: dict) -> dict | None:
        """One stored row -> a sane entry, or None if it is unusable.

        A hand-edited file is expected, so every field is checked rather than
        trusted: a remembered "off" of 0 would otherwise be sent straight to the
        plug as a duration, and `first` must be one of the two values the rule
        text knows how to write.
        """
        ident = normalize_device_id(str(item.get("id", "")))
        if not ident:
            return None
        try:
            on = int(item.get("on", 0))
            off = int(item.get("off", 0))
        except (TypeError, ValueError):
            return None
        if not (CYCLE_MIN_SECONDS <= on <= CYCLE_MAX_SECONDS):
            return None
        if not (CYCLE_MIN_SECONDS <= off <= CYCLE_MAX_SECONDS):
            return None
        first = str(item.get("first", "ON")).upper()
        if first not in ("ON", "OFF"):
            first = "ON"
        return {"id": ident, "on": on, "off": off, "first": first,
                "auto": bool(item.get("auto", False)),
                "running": bool(item.get("running", False)),
                "saved": str(item.get("saved") or "")}

    # ------------------------------------------------------------------- read
    def get(self, ident: str) -> dict | None:
        with self._lock:
            found = self.cycles.get(ident)
            return dict(found) if found else None

    def for_page(self, ident: str) -> dict | None:
        """What the page needs, including how long ago it was written."""
        entry = self.get(ident)
        if entry is None:
            return None
        entry["saved_text"] = _stamp_text(entry.get("saved"))
        return entry

    # ------------------------------------------------------------------ write
    def remember(self, ident: str, on_seconds: int, off_seconds: int,
                 first: str, running: bool, auto: bool | None = None) -> dict:
        """Store the configuration. `auto=None` keeps the switch as it was.

        A stop does NOT clear the numbers -- that is the whole point: the last
        configuration stays available to restart, and only `running` changes, so
        "自动接着跑" does not fire on a loop the user stopped on purpose.
        """
        with self._lock:
            old = self.cycles.get(ident) or {}
            entry = {"id": ident, "on": int(on_seconds), "off": int(off_seconds),
                     "first": first, "auto": bool(old.get("auto", False))
                     if auto is None else bool(auto),
                     "running": bool(running), "saved": _local_stamp()}
            self.cycles[ident] = entry
        self.save()
        return dict(entry)

    def mark_stopped(self, ident: str) -> dict | None:
        """The loop was stopped: keep the numbers, forget that it was running."""
        with self._lock:
            entry = self.cycles.get(ident)
            if entry is None:
                return None
            entry = dict(entry)
            entry["running"] = False
            self.cycles[ident] = entry
        self.save()
        return dict(entry)

    def set_auto(self, ident: str, auto: bool) -> dict | None:
        with self._lock:
            entry = self.cycles.get(ident)
            if entry is None:
                return None
            entry = dict(entry)
            entry["auto"] = bool(auto)
            self.cycles[ident] = entry
        self.save()
        return dict(entry)

    def forget(self, ident: str) -> bool:
        with self._lock:
            existed = ident in self.cycles
            self.cycles.pop(ident, None)
        if existed:
            self.save()
        return existed


def _local_stamp() -> str:
    """Now, as 'YYYY-MM-DDTHH:MM:SS', on THIS machine's wall clock.

    The device list stores UTC (`_utc_stamp`) because a plug's own clock is
    UTC-based and the two are compared. A remembered cycle is different: it is
    only ever read by one person sitting at this PC, so "saved at 07:12" in
    UTC would look like the wrong half of the day.
    """
    return _time.strftime("%Y-%m-%dT%H:%M:%S", _time.localtime())


def _stamp_text(stamp: str) -> str:
    """'2026-09-27T15:20:11' -> '09-27 15:20': enough to tell today from
    yesterday, not enough to look like a precise log."""
    text = (stamp or "").strip()
    if not text or "T" not in text:
        return ""
    date_part, _, time_part = text.partition("T")
    bits = date_part.split("-")
    if len(bits) != 3:
        return ""
    return "%s-%s %s" % (bits[1], bits[2], time_part[:5])


class _BadRequest(Exception):
    """The request itself is wrong -- the route answers 400 with this message.

    A named exception rather than a sentinel, because the alternative -- quietly
    acting on some other device -- is the kind of bug nobody notices until the
    wrong outlet switches.
    """


# POST paths that act on one device. Listed once so _dispatch can answer 404 for
# an unknown path BEFORE it resolves a device: otherwise a mistyped URL came back
# as "the device list is empty", which sends the reader off to fix the wrong thing.
DEVICE_POST_ROUTES = ("/api/reload", "/api/switch", "/api/pulse", "/api/timer",
                      "/api/timers", "/api/timezone", "/api/cycle")


# ---- the aquarium cycle ---------------------------------------------------
# A Tasmota timer slot fires once a day and cannot alternate; what CAN loop is
# a pair of rules feeding each other. Timer 1 switches the relay ON and arms
# timer 2 for how long it stays ON; timer 2 switches it OFF and arms timer 1
# for how long it stays OFF. That is the whole trick -- and it runs inside the
# plug, so closing the browser does not stop it.
#
# Rule1 is one bank of the device's rule memory and a device may already have
# something in it, so it is read back before being overwritten and a foreign
# rule is only replaced on a confirmed second click.
CYCLE_RULE = "Rule1"
CYCLE_TIMER_ON = 2          # RuleTimer2 counts down while the relay is ON
CYCLE_TIMER_OFF = 1         # RuleTimer1 counts down while the relay is OFF
CYCLE_MIN_SECONDS = 1
CYCLE_MAX_SECONDS = 86400   # 24 h; the firmware's own ceiling for a RuleTimer
CYCLE_MARKER = "Rules#Timer="
# ...and the two durations, read back out of whatever Rule1 currently holds.
# Timer 2's value is the ON length, timer 1's is the OFF length: swapping them
# is the one mistake that leaves a cycle running with inverted durations.
CYCLE_RULE_RE = _re.compile(r"RuleTimer2\s+(\d+).*?RuleTimer1\s+(\d+)", _re.S)
CYCLE_QUIET_SECONDS = 0.4   # how long the device must be silent before we call
                            # a cycle read complete; default ask() waits 0.7 s
                            # per command, and two of those were most of the
                            # 1.8 s every cycle poll used to cost


# ------------------------------------------------------- engine plumbing
# These read one plug and return plain dicts. They are module functions rather
# than methods so the single-device panel and this one can share the same shape
# of answer without either owning the other's class.
def _timers_of(plug) -> dict:
    """All 16 slots, flattened for the page. Reads `Timers` once."""
    global_state, slots = plug._fetch_timers()
    rows = []
    for index in sorted(slots):
        cfg = slots[index]
        rows.append({"index": index, "used": timer_in_use(cfg),
                     "enable": int(cfg.get("Enable") or 0),
                     "mode": ["clock", "sunrise", "sunset"][int(cfg.get("Mode") or 0) % 3],
                     "time": str(cfg.get("Time", "")), "window": int(cfg.get("Window") or 0),
                     "days": str(cfg.get("Days", "")),
                     "days_text": describe_days(str(cfg.get("Days", ""))),
                     "repeat": int(cfg.get("Repeat") or 0),
                     "output": int(cfg.get("Output") or 1),
                     "action": int(cfg.get("Action") or 0),
                     "action_text": ["off", "on", "toggle", "rule"][int(cfg.get("Action") or 0) % 4]})
    return {"ok": bool(slots) or global_state is not None, "global": global_state,
            "slots": rows, "used": [r["index"] for r in rows if r["used"]],
            "error": None if slots else "no reply to `Timers`"}


def _clock_of(plug) -> dict:
    """`Status 7`: the device's UTC, its local time, and the offset between them."""
    payload = None
    for _topic, body in plug.ask("Status", "7"):
        if '"StatusTIM"' in body:
            payload = body
    if payload is None:
        return {"ok": False, "error": "no reply to `Status 7`"}
    info = json.loads(payload).get("StatusTIM") or {}
    utc = str(info.get("UTC", "")) or "?"
    local = str(info.get("Local", "")) or "?"
    offset = _device_offset(utc, local)
    # The device reports UTC and Local, and Sunrise/Sunset belong to Local.
    # Normalising both to UTC keeps a client in any timezone from reading the
    # device's raw local text as if it were its own wall clock.
    return {"ok": True, "utc": _as_utc(utc), "local": local,
            "local_utc": _as_utc(local),
            "offset_hours": offset, "offset_text": _fmt_offset(offset),
            "sunrise": info.get("Sunrise", "?"), "sunset": info.get("Sunset", "?"),
            "needs_fix": offset is None or abs(offset - 8.0) > 0.01,
            "error": None if offset is not None else
                     "the device clock is not NTP synced, so the offset is unknown"}


# ------------------------------------------------------------- the sensors
# Power, voltage, current and the two counters live in the device's SENSOR
# block, which is `StatusSNS` / `Status 8` -- not in `Status 0`, whose `Power`
# is the relay bitmask (1 for on, 0 for off). Those two meanings of "Power"
# share a name and nothing else, so this reads the sensor block on its own and
# never walks into it from the relay side.
#
# A plug with no energy chip answers `{"StatusSNS":{}}` (or `{}`), which is not
# an error and not a zero: it is "this device has no meter". The page says so
# in words instead of drawing 0 W, because a meterless plug and a plug whose
# load is genuinely idle would otherwise look identical.
ENERGY_FIELDS = ("Total", "Yesterday", "Today", "Period",
                 "Power", "ApparentPower", "ReactivePower", "Factor",
                 "Voltage", "Current")
# Every spelling Tasmota and its forks have used for the same two ideas. The
# normalised names the page reads are `today` and `yesterday`; the rest of the
# set is passed through as the device sent it.
ENERGY_TODAY_KEYS = ("Today", "EnergyToday", "TodayEnergy")
ENERGY_YESTERDAY_KEYS = ("Yesterday", "EnergyYesterday", "YesterdayEnergy")


def _energy_number(block: dict, names) -> float | None:
    """The first of `names` that the device actually sent, as a number.

    A missing key (`null`, `""`, `"---"`) is not a zero -- X10 and PZEM builds
    disagree about which counters they carry, and reporting an absent one as
    0.000 kWh would be a number the device never said.
    """
    for name in names:
        if name not in block:
            continue
        value = block.get(name)
        if value is None:
            continue
        if isinstance(value, bool):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _energy_parse(data) -> dict:
    """Pull the meter out of a decoded `StatusSNS` reply, or say there is none.

    Kept separate from the read so the parsing can be exercised without a
    broker, and so every "this device has no meter" answer comes out of ONE
    place -- the page has three ways to show it and none of them should be
    guessing what the device meant.
    """
    sns = data.get("StatusSNS") if isinstance(data, dict) else None
    if not isinstance(sns, dict):
        return {"ok": False, "no_sensor": True, "sensor": None,
                "values": {}, "error": None}
    # The block is keyed by the sensor's own name -- ENERGY, ENERGY1, BL0942,
    # HWSB, CSE7766, PZEM0XX ... -- and `Time` is a sibling string, not a
    # sensor. Taking the FIRST entry that holds a dictionary is what makes this
    # work across the whole family instead of only on the one chip the author
    # happens to own; a build that reports no chip at all answers with an empty
    # block, which is caught by `body is None` below.
    sensor = None
    body = None
    for key, value in sns.items():
        if key == "Time" or not isinstance(value, dict):
            continue
        sensor, body = key, value
        break
    if body is None:
        return {"ok": False, "no_sensor": True, "sensor": None,
                "values": {}, "error": None}
    values = {}
    for name in ENERGY_FIELDS:
        number = _energy_number(body, (name,))
        if number is not None:
            values[name] = number
    today = _energy_number(body, ENERGY_TODAY_KEYS)
    yesterday = _energy_number(body, ENERGY_YESTERDAY_KEYS)
    if today is not None:
        values["today"] = today
    if yesterday is not None:
        values["yesterday"] = yesterday
    if not values:
        return {"ok": False, "no_sensor": True, "sensor": sensor,
                "values": {}, "error": None}
    return {"ok": True, "no_sensor": False, "sensor": sensor,
            "values": values, "error": None,
            "time": str(sns.get("Time") or "") or None}


def _energy_of(plug) -> dict:
    """`Status 8`: the meter's instantaneous numbers and its two counters.

    `StatusSNS` is NOT a command. It is the KEY inside the payload, and the
    device answers `{"Command":"Unknown","Input":"STATUSSNS"}` if you publish
    it -- so send `Status 8`, which is the documented index for that block and
    replies on `stat/<topic>/STATUS8` with `{"StatusSNS":{...}}`.

    This matters more than it looks. The old spelling appeared to work at first
    because `Status 0` (the relay beat) makes the device publish the WHOLE
    StatusX batch, and STATUS10 carries a `{"StatusSNS":...}` payload that this
    reader accepted no matter which topic it arrived on. So the first read of a
    session was real data scavenged from an unrelated reply, and every read
    after it failed. Parsing has nothing to do with the topic on purpose -- the
    payload is self-describing -- but the COMMAND has to exist.
    """
    payload = None
    for _topic, body in plug.ask("Status", "8", quiet=0.4):
        if not body.startswith("{"):
            continue
        try:
            data = json.loads(body)
        except ValueError:
            continue
        if isinstance(data, dict) and "StatusSNS" in data:
            payload = data
    if payload is None:
        return {"ok": False, "no_sensor": False, "sensor": None, "values": {},
                "error": "no reply to `Status 8`"}
    out = _energy_parse(payload)
    out["age"] = 0.0
    return out


def _write_timer(plug, index: int, changes: dict) -> tuple[bool, str]:
    """Merge a few Timer fields into one slot and write the whole object back.

    Same policy as `-timer.py`: the page sends only what the user touched, the
    slot is read first, and the full JSON goes back -- which also works on
    firmwares that insist on every field being present.
    """
    _global, slots = plug._fetch_timers()
    cfg = dict(TIMER_TEMPLATE)
    cfg.update(slots.get(index) or {})
    cfg.update(changes)
    plug.ask("Timer%d" % index, _json.dumps(cfg, separators=(",", ":")))
    error = plug._error_note()
    if error:
        return False, error
    _global, slots = plug._fetch_timers()
    stored = slots.get(index)
    if stored is None:
        return False, "no read back for slot %d" % index
    return True, "slot %d -> %s" % (index, TasmotaPlug._describe_slot(stored))


def _set_all_timers(plug, on: bool) -> tuple[bool, str]:
    """The global `Timers` switch that gates every slot."""
    plug.ask("Timers", "1" if on else "0")
    global_state, _slots = plug._fetch_timers()
    error = plug._error_note()
    if error:
        return False, error
    return True, "global Timers = %s" % global_state


# ------------------------------------------------------------ the cycle
# Everything below talks to one plug and returns plain data, like the helpers
# above. None of it keeps state of its own: the loop lives in the DEVICE, so
# the panel can be closed, restarted, or opened from another machine and still
# show the truth -- it only ever reads.
def _cycle_rule_text(on_seconds: int, off_seconds: int) -> str:
    """The two-rule loop that alternates the relay forever.

    Read it as: "when timer 1 expires, switch ON and give the ON phase
    `on_seconds` to run; when timer 2 expires, switch OFF and give the OFF
    phase `off_seconds`". Each rule arms the OTHER one's timer, which is what
    makes it a cycle rather than a one-shot.
    """
    return ("ON Rules#Timer=1 DO Backlog Power1 ON; RuleTimer%d %d ENDON "
            "ON Rules#Timer=2 DO Backlog Power1 OFF; RuleTimer%d %d ENDON"
            % (CYCLE_TIMER_ON, on_seconds, CYCLE_TIMER_OFF, off_seconds))


def _cycle_seconds(rules: str) -> tuple[int, int] | None:
    """(on, off) out of a rule text, or None if Rule1 holds something else.

    A device can have any rule in bank 1 -- an automation somebody wrote in the
    console, or a rule from another tool. Only a text carrying BOTH
    `Rules#Timer=1` and `Rules#Timer=2` is a cycle this panel recognises, and
    anything else must not be silently replaced.
    """
    if not rules or CYCLE_MARKER not in rules:
        return None
    match = CYCLE_RULE_RE.search(rules)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _rule_of(plug) -> dict:
    """`Rule1`: is it armed, and what is written in it?"""
    for _topic, body in plug.ask(CYCLE_RULE, ""):
        if not body.startswith("{"):
            continue
        try:
            data = json.loads(body)
        except ValueError:
            continue
        info = data.get(CYCLE_RULE)
        if isinstance(info, dict):
            # The state arrives as the device's own wording -- this build says
            # "ON"/"OFF" where others say 1/0 -- so it is normalised here and
            # never compared raw. See globalOn() for the same trap on Timers.
            return {"state": str(info.get("State", "")).strip().upper() == "ON",
                    "state_text": str(info.get("State", "?")),
                    "rules": str(info.get("Rules", "") or ""),
                    "free": info.get("Free")}
    return {"state": None, "state_text": "?", "rules": "", "free": None}


def _rule_timers_of(plug) -> dict:
    """Every RuleTimer's REMAINING seconds, straight off the device.

    `RuleTimer1` with no value is a query, and this firmware answers with all
    eight (T1..T8), which is why the countdown on the page is the device's own
    number and not a guess from the moment the button was pressed -- a guess
    that silently drifts the moment the plug reboots.
    """
    for _topic, body in plug.ask("RuleTimer%d" % CYCLE_TIMER_OFF, ""):
        if not body.startswith("{"):
            continue
        try:
            data = json.loads(body)
        except ValueError:
            continue
        found = {}
        for key, value in data.items():
            if len(key) == 2 and key[0] == "T" and key[1:].isdigit():
                try:
                    found[key] = max(0, int(value))
                except (TypeError, ValueError):
                    continue
        if found:
            return found
    return {}


def _duration_text(seconds: int) -> str:
    """'1800' -> '30 分钟'. Used in messages, where seconds read as noise."""
    value = int(seconds)
    if value % 3600 == 0:
        return "%d 小时" % (value // 3600)
    if value >= 3600:
        return "%d 小时 %d 分" % (value // 3600, (value % 3600) // 60)
    if value >= 60:
        return "%d 分 %d 秒" % (value // 60, value % 60) if value % 60 \
               else "%d 分钟" % (value // 60)
    return "%d 秒" % value


def _cycle_snapshot(plug) -> tuple[dict, dict]:
    """`Rule1` and every RuleTimer, in ONE exchange.

    Read separately they cost two round trips, and each ask() waits for the
    device to fall quiet before returning -- nearly two seconds during which
    every other read on this plug queues behind the same per-device lock,
    which is what made the relay state itself feel slow. `Backlog Rule1;
    RuleTimer1` makes the device answer both back to back (~0.3 s apart), so
    one quiet window serves both.
    """
    rule = {"state": None, "state_text": "?", "rules": "", "free": None}
    timers: dict = {}
    for _topic, body in plug.ask("Backlog",
                                 "%s; RuleTimer%d" % (CYCLE_RULE, CYCLE_TIMER_OFF),
                                 quiet=CYCLE_QUIET_SECONDS):
        if not body.startswith("{"):
            continue
        try:
            data = json.loads(body)
        except ValueError:
            continue
        info = data.get(CYCLE_RULE)
        if isinstance(info, dict):
            # The state arrives as the device's own wording -- this build says
            # "ON"/"OFF" where others say 1/0 -- so it is normalised here and
            # never compared raw. See globalOn() for the same trap on Timers.
            rule = {"state": str(info.get("State", "")).strip().upper() == "ON",
                    "state_text": str(info.get("State", "?")),
                    "rules": str(info.get("Rules", "") or ""),
                    "free": info.get("Free")}
        found = {}
        for key, value in data.items():
            if len(key) == 2 and key[0] == "T" and key[1:].isdigit():
                try:
                    found[key] = max(0, int(value))
                except (TypeError, ValueError):
                    continue
        if found:
            timers = found
    return rule, timers


def _cycle_read(plug) -> dict:
    """Everything the page shows about the cycle, read from the device."""
    rule, timers = _cycle_snapshot(plug)
    wanted = _cycle_seconds(rule["rules"])
    on_secs, off_secs = wanted if wanted else (None, None)
    # Timer 2 pending means the relay is ON and counting down to OFF; timer 1
    # pending means the opposite. Neither pending means the loop is armed but
    # idle -- which is exactly the state a plug reboot leaves behind.
    left_on = timers.get("T%d" % CYCLE_TIMER_ON, 0)
    left_off = timers.get("T%d" % CYCLE_TIMER_OFF, 0)
    if left_on > 0:
        phase, left = "on", left_on
    elif left_off > 0:
        phase, left = "off", left_off
    else:
        phase, left = None, 0
    return {"ok": rule["state"] is not None, "id": None,
            "armed": bool(rule["state"]),
            "running": bool(rule["state"]) and phase is not None,
            "phase": phase, "left": left,
            "on": on_secs, "off": off_secs,
            "ours": wanted is not None,
            "rules": rule["rules"], "state_text": rule["state_text"],
            "free": rule["free"],
            "error": None if rule["state"] is not None else "no reply to `Rule1`"}


def _cycle_start(plug, first: str, on_seconds: int, off_seconds: int,
                 force: bool = False) -> tuple[bool, str, bool]:
    """Write the loop, arm it, and start the phase the user asked for.

    Returns (ok, message, taken). `taken` means Rule1 already held a rule this
    panel did not write: nothing was touched, and the caller may ask the user
    before overwriting. Writing over a stranger's rule without asking is how an
    automation somebody set up in the console disappears.
    """
    rule = _rule_of(plug)
    if rule["rules"] and _cycle_seconds(rule["rules"]) is None and not force:
        shown = rule["rules"]
        if len(shown) > 70:
            shown = shown[:70] + "..."
        return False, ("插座的 Rule1 里已经有别的规则：" + shown +
                       "\n覆盖会把它丢掉。确定要继续吗？"), True

    wanted = _cycle_rule_text(on_seconds, off_seconds)
    if rule["rules"] != wanted:
        plug.ask(CYCLE_RULE, wanted)
        stored = _rule_of(plug)
        if stored["rules"] != wanted:
            return False, ("规则没写进去（设备回读的是 %r）。可能是长度不够："
                           "Rule1 还剩 %s 字节。" % (stored["rules"], stored["free"])), False
    plug.ask(CYCLE_RULE, "1")
    if not _rule_of(plug)["state"]:
        return False, "规则写进去了，但启用 Rule1 之后设备仍显示关闭", False

    # Start the phase the user picked, then arm the timer that ENDS it:
    # starting ON arms RuleTimer2 (the one that switches it off), and starting
    # OFF arms RuleTimer1. Arming the wrong one turns the first phase into the
    # wrong length and the loop never settles into the rhythm asked for.
    if first == "ON":
        plug.ask("Backlog", "Power1 ON; RuleTimer%d %d"
                 % (CYCLE_TIMER_ON, on_seconds))
    else:
        plug.ask("Backlog", "Power1 OFF; RuleTimer%d %d"
                 % (CYCLE_TIMER_OFF, off_seconds))
    error = plug._error_note()
    if error:
        return False, error, False
    read = _cycle_read(plug)
    if not read["running"]:
        return False, ("命令发出去了，但设备现在没有在跑循环 —— "
                       "点一下刷新看看"), False
    return True, ("循环中：开 %s / 关 %s，当前是「%s」，%d 秒后切换"
                  % (_duration_text(on_seconds), _duration_text(off_seconds),
                     "开" if read["phase"] == "on" else "关", read["left"])), False


def _cycle_stop(plug) -> tuple[bool, str]:
    """Stop the loop and leave the relay exactly where it is.

    The rule text stays on the device, only disarmed -- re-arming later is one
    command, and deleting it would be one fewer thing to restore. The relay is
    deliberately NOT switched: stopping a fish-tank pump mid-cycle should not
    also decide what state the outlet is left in.
    """
    plug.ask("Backlog", "RuleTimer%d 0; RuleTimer%d 0"
             % (CYCLE_TIMER_OFF, CYCLE_TIMER_ON))
    plug.ask(CYCLE_RULE, "0")
    error = plug._error_note()
    if error:
        return False, error
    read = _cycle_read(plug)
    if read["armed"]:
        return False, "定时器清零了，但 Rule1 还是开着 —— 再点一次停止"
    state = plug.query_state(plug.timeout)
    return True, ("已停止循环（规则留在插座里、已停用）。继电器现在是 %s。"
                  % (state or "未知"))


def _link_up(plug) -> bool:
    """True while this plug still holds a live MQTT session.

    A link is opened once and kept, so nothing else would ever notice it dying:
    after a broker restart or a dropped Wi-Fi association the object stays in
    the table looking perfectly healthy, every read quietly waits out its own
    timeout, and the page says "no reply to Status 0" until somebody restarts
    the panel. Asking paho is cheap; being wrong about this costs the session.
    """
    try:
        client = getattr(plug, "client", None)
        return client is not None and bool(client.is_connected())
    except Exception:                                   # noqa: BLE001
        return False        # a client we cannot ask gets rebuilt, not trusted


# --------------------------------------------------------- the device fleet
class Fleet:
    """One MQTT link per managed device, all sharing the broker settings.

    Each TasmotaPlug subscribes to its OWN stat/tele topics, so instances never
    see each other's traffic -- and each gets a fresh random client id, so none of
    them can accidentally claim a device's own session and kick it offline.

    Links are opened lazily: a device is connected the first time someone reads it
    or sweeps the list, not when the list is loaded. Booting 32 connections before
    the first page load would be rude to the broker and pointless for devices
    nobody looks at. A device that fails to connect is remembered as failed and
    retried on the next sweep, so one dead plug cannot stall the page.
    """

    def __init__(self, args, book: DeviceBook, settings: "BrokerSettings | None" = None,
                 memory: "CycleMemory | None" = None) -> None:
        self.args = args
        self.book = book
        self.settings = settings
        self.memory = memory        # remembered cycle configuration, may be None
        self._lock = _threading.Lock()          # guards the two dicts below
        self._plugs: dict[str, "TasmotaPlug"] = {}
        self._failed: dict[str, str] = {}       # id -> why it could not connect
        self._sweep: dict[str, dict] = {}       # id -> last known summary
        self._stop = _threading.Event()
        self._reader: _threading.Thread | None = None

    # ------------------------------------------------------------------- link
    def _args_for(self, ident: str, override: dict | None = None):
        """A per-device copy of the shared MQTT settings.

        `override` is a partial endpoint in TasmotaPlug's own spelling
        (host/port/tls/user/password/timeout) used only by the connection test:
        it must be able to dial a broker the panel has NOT adopted yet, which is
        the whole point of "测试连接" -- you want to know before you save.

        copy.copy, not the original: TasmotaPlug stores topic/cmnd/stat/tele on
        itself, and mutating one namespace for every device would leave the last
        device's topic on all of them.

        host/port are re-stated from mqtt_host/mqtt_port on purpose. The builder
        renames the engine's --host/--port to --mqtt-host/--mqtt-port, which moves
        the parsed values to args.mqtt_host/args.mqtt_port -- but TasmotaPlug, the
        engine's own class, still dials args.host and args.port. Handing it a
        namespace with both spellings keeps the engine unmodified and the panel's
        flags honest. The panel's listen pair is listen_host/listen_port, so
        nothing here can shadow its own socket.
        """
        local = _copy.copy(self.args)
        local.host = self.args.mqtt_host
        local.port = self.args.mqtt_port
        local.device = ident
        local.topic = "tasmota_" + ident
        local.client_id = None                  # fresh random id per plug
        if override:
            for key, value in override.items():
                setattr(local, key, value)
        return local

    def reconfigure(self) -> int:
        """Drop every open link so the next read dials the CURRENT endpoint.

        Returns how many links were closed. Nothing reconnects here: links are
        opened lazily, so the next status read or sweep picks up the new broker
        on its own. Doing it eagerly would mean N connect() calls inside one
        HTTP request, and every one of them can hang for the timeout.
        """
        with self._lock:
            plugs = list(self._plugs.values())
            self._plugs.clear()
            self._failed.clear()
            self._sweep.clear()
        closed = 0
        for plug in plugs:
            try:
                plug.close()
                closed += 1
            except Exception:                           # noqa: BLE001
                pass
        return closed

    def probe_broker(self, override: dict | None = None) -> dict:
        """One throwaway connection: do these settings actually work?

        Uses a scratch device id so the test cannot collide with a real plug's
        session, and subscribes to a topic nobody publishes -- the answer is
        purely "did the broker accept us", which is what distinguishes a wrong
        password (CONNACK 4/5) from a wrong port (no CONNACK at all).

        The CONNACK code is translated on the way out. The engine says
        "broker refused the connection (rc=135)", which is true and useless:
        135 is paho's code for "not authorised", and the user is left staring
        at a number when the fix is "your password is wrong".
        """
        local = self._args_for(HUB_PROBE_ID, override)
        local.timeout = min(float(local.timeout), HUB_REQUEST_TIMEOUT)
        plug = TasmotaPlug(local)
        label = "%s:%d%s" % (local.host, local.port, " (TLS)" if local.tls else "")
        try:
            plug.timeout = local.timeout
            plug.connect()
            return {"ok": True, "host": local.host, "port": local.port,
                    "tls": bool(local.tls), "user": local.user,
                    "detail": "连上了 %s（用户 %s）" % (label, local.user or "空")}
        except Exception as exc:                        # noqa: BLE001
            return {"ok": False, "host": local.host, "port": local.port,
                    "tls": bool(local.tls), "user": local.user,
                    "error": "%s -> %s" % (label, _connack_text(exc))}
        finally:
            try:
                plug.close()
            except Exception:                           # noqa: BLE001
                pass

    def plug_for(self, ident: str, connect: bool = True) -> "TasmotaPlug | None":
        """The plug for `ident`, connecting on first use. None if it is unusable.

        A cached plug whose socket has died is thrown away and rebuilt rather
        than handed out: an MQTT link once established is kept open, so a
        broker restart or a lost association would otherwise leave every later
        read waiting out its timeout against nothing.
        """
        with self._lock:
            plug = self._plugs.get(ident)
            dead = plug is not None and not _link_up(plug)
            if plug is not None and not dead:
                return plug
            if not connect:
                return plug
            if plug is None and len(self._plugs) >= self.max_devices():
                self._failed[ident] = ("too many devices open (%d); raise "
                                       "--max-devices" % self.max_devices())
                return None
        # Outside the lock: rebuilding means a connect() that can take seconds,
        # and holding the fleet lock across it would stall every other device.
        if dead:
            self.drop(ident)
        return self._open(ident)

    def _open(self, ident: str) -> "TasmotaPlug | None":
        """Build and connect one plug. Never raises: a bad device is data, not an
        exception, because one unreachable plug must not break the whole page."""
        plug = TasmotaPlug(self._args_for(ident))
        try:
            plug.timeout = self.args.timeout
            plug.connect()
            plug.settle(self.args.grace)
        except Exception as exc:                        # noqa: BLE001
            try:
                plug.close()
            except Exception:                           # noqa: BLE001
                pass
            with self._lock:
                self._failed[ident] = str(exc)
            return None
        with self._lock:
            self._plugs[ident] = plug
            self._failed.pop(ident, None)
        return plug

    def drop(self, ident: str) -> None:
        """Forget one device: close its link and its cached summary.

        Used when a serial is renamed or deleted, so a stale connection does not
        linger on the broker under the old name.
        """
        with self._lock:
            plug = self._plugs.pop(ident, None)
            self._failed.pop(ident, None)
            self._sweep.pop(ident, None)
        if plug is not None:
            try:
                plug.close()
            except Exception:                           # noqa: BLE001
                pass

    def close(self) -> None:
        self._stop.set()
        if self._reader is not None:
            self._reader.join(timeout=5.0)
        with self._lock:
            plugs = list(self._plugs.values())
            self._plugs.clear()
        for plug in plugs:
            try:
                plug.close()
            except Exception:                           # noqa: BLE001
                pass

    def failure(self, ident: str) -> str | None:
        with self._lock:
            return self._failed.get(ident)

    def max_devices(self) -> int:
        return max(1, int(getattr(self.args, "max_devices", HUB_MAX_DEVICES)))

    def links(self) -> int:
        """How many MQTT connections are open right now."""
        with self._lock:
            return len(self._plugs)

    def _timeout(self, read_only: bool) -> float:
        allowed = HUB_READ_TIMEOUT if read_only else HUB_REQUEST_TIMEOUT
        return min(self.args.timeout, allowed)

    def _attempt_timeout(self) -> float:
        """Budget for ONE go at a read.

        Smaller than the total on purpose: a read now gets up to
        HUB_READ_ATTEMPTS goes, so two of these plus the pause between them is
        what a genuinely silent plug costs, and it lands near the old ceiling.
        """
        return min(self.args.timeout, HUB_READ_ATTEMPT_SECONDS)

    def _read_once(self, plug, reader):
        """Run one device read under this plug's lock, with the read budget."""
        with self._lock_for(plug):
            plug.timeout = self._attempt_timeout()
            return reader(plug)

    def _read_with_retry(self, ident: str, reader, failed=None):
        """Read one device, giving a lost reply a second chance.

        Returns (value, plug); `plug` is None when there is no usable link at
        all. `reader(plug)` produces the value and `failed(value)` says whether
        it is a miss.

        Why this exists: the publish is QoS 0, so the broker or the Wi-Fi hop is
        allowed to drop it, and one dropped `Status 0` is the difference between
        a live panel and a red "no reply" banner. The action paths have always
        retried for exactly that reason (see engine.run_with_retries); reads did
        not, which is why the state came back fine most of the time and not at
        all the rest of the time. A rebuild is attempted only when paho says the
        session actually died, and a device whose own LWT says it is offline is
        not interrogated twice.
        """
        failed = failed or (lambda value: value is None)
        plug = self.plug_for(ident)
        if plug is None:
            return None, None
        value = self._read_once(plug, reader)
        for _attempt in range(1, HUB_READ_ATTEMPTS):
            if not failed(value):
                break
            _time.sleep(HUB_READ_RETRY_DELAY)
            if not _link_up(plug):
                # The link, not the packet: ask for a fresh one and retry on
                # that. plug_for() rebuilds whenever the socket is dead.
                plug = self.plug_for(ident)
                if plug is None:
                    return value, None
            elif getattr(plug, "online", None) is False:
                # The device published LWT=offline. Another packet will not
                # conjure an answer, so keep the first result and stop.
                break
            value = self._read_once(plug, reader)
        return value, plug

    # --------------------------------------------------------------- read only
    def status(self, ident: str) -> dict:
        """One `Status 0` for one device, plus how the list should draw it."""
        state, plug = self._read_with_retry(
            ident, lambda plug: plug.query_state(plug.timeout))
        if plug is None:
            return {"id": ident, "state": None, "online": False, "online_text": "no",
                    "error": self.failure(ident) or "not connected"}
        online = self._online_of(plug)
        return {"id": ident, "state": state, "online": online,
                "online_text": {True: "yes", False: "no", None: "unknown"}[online],
                "last_seen": plug.state_ts or None,
                "error": None if state else (plug._error_note()
                                             or "no reply to `Status 0`")}

    def clock(self, ident: str) -> dict:
        plug = self.plug_for(ident)
        if plug is None:
            return {"id": ident, "timers": [], "clock": {"ok": False,
                    "error": self.failure(ident) or "not connected"}}
        with self._lock_for(plug):
            plug.timeout = self._timeout(read_only=True)
            timers = _timers_of(plug)
            info = _clock_of(plug)
        return {"id": ident, "timers": timers, "clock": info}

    def energy(self, ident: str) -> dict:
        """Power, voltage, current and the counters for one device.

        Goes through `_read_with_retry` like `status()` rather than taking the
        lock by hand like `clock()`: a meter read is the second-most-frequent
        thing this panel does, it lands on the same per-plug queue as the relay
        read, and one dropped QoS 0 packet should not blank the card. A device
        that answers but has no meter is a SUCCESS, not a failure -- so the
        retry predicate only re-asks when the plug said nothing at all.
        """
        info, plug = self._read_with_retry(
            ident, _energy_of,
            failed=lambda value: not value.get("ok") and not value.get("no_sensor"))
        if not info:
            return {"id": ident, "ok": False, "no_sensor": False, "sensor": None,
                    "values": {}, "age": None,
                    "error": self.failure(ident) or "not connected"}
        info["id"] = ident
        info["age"] = 0.0
        return info

    def switch(self, ident: str, payload: str) -> dict:
        plug = self.plug_for(ident)
        if plug is None:
            return {"ok": False, "state": None, "exit": 1,
                    "error": self.failure(ident) or "not connected"}
        with self._lock_for(plug):
            plug.timeout = self._timeout(read_only=False)
            code = plug.run({"ON": "on", "OFF": "off", "TOGGLE": "toggle"}[payload])
            state = plug.state
        return {"ok": code == 0, "state": state, "exit": code,
                "error": None if code == 0 else (plug._error_note()
                                                 or "the device did not confirm %s" % payload)}

    def pulse(self, ident: str, first: str, seconds: float) -> dict:
        plug = self.plug_for(ident)
        if plug is None:
            return {"ok": False, "error": self.failure(ident) or "not connected"}
        second = "OFF" if first == "ON" else "ON"
        with self._lock_for(plug):
            plug.timeout = self._timeout(read_only=False)
            code = plug.run({"ON": "on", "OFF": "off"}[first])
            if code == 0:
                deadline = _time.time() + max(0.0, seconds)

                def flip() -> None:
                    with self._lock_for(plug):
                        plug.timeout = self._timeout(read_only=False)
                        plug.run({"ON": "on", "OFF": "off"}[second])

                timer = _threading.Timer(max(0.0, seconds), flip)
                timer.daemon = True
                plug._pulse_timer = timer
                timer.start()
                return {"ok": True, "state": first,
                        "until_text": _time.strftime(
                            "%H:%M:%S", _time.localtime(deadline)),
                        "seconds": seconds, "then": second}
        return {"ok": False, "error": plug._error_note()
                or "the device did not accept the first half"}

    def set_timezone(self, ident: str, offset: str) -> dict:
        plug = self.plug_for(ident)
        if plug is None:
            return {"ok": False, "error": self.failure(ident) or "not connected"}
        with self._lock_for(plug):
            plug.timeout = self._timeout(read_only=False)
            ok, detail = plug.set_timezone(offset)
        return {"ok": ok, "detail": detail, "error": None if ok else detail}

    def write_timer(self, ident: str, index: int, changes: dict) -> dict:
        plug = self.plug_for(ident)
        if plug is None:
            return {"ok": False, "error": self.failure(ident) or "not connected"}
        with self._lock_for(plug):
            plug.timeout = self._timeout(read_only=False)
            ok, detail = _write_timer(plug, index, changes)
        return {"ok": ok, "detail": detail, "error": None if ok else detail}

    def set_all_timers(self, ident: str, on: bool) -> dict:
        plug = self.plug_for(ident)
        if plug is None:
            return {"ok": False, "error": self.failure(ident) or "not connected"}
        with self._lock_for(plug):
            plug.timeout = self._timeout(read_only=False)
            ok, detail = _set_all_timers(plug, on)
        return {"ok": ok, "detail": detail, "error": None if ok else detail}

    # ----------------------------------------------------------------- cycle
    def _stored_id(self, ident: str) -> str:
        """The spelling the LIST uses, so a remembered setting is not orphaned.

        A device renamed in the page would otherwise leave its cycle under the
        old id, and the same plug typed as `6fce2c` would look like a different
        device with nothing remembered.
        """
        return self.book.resolve(ident) or ident

    def cycle(self, ident: str) -> dict:
        """The current loop read from the plug, plus what this panel remembers.

        `stale` is the power-cut fingerprint: the rule is ours and still armed,
        but no RuleTimer is running. The device keeps rules across a reboot and
        drops the countdown, so this is the state to offer a restart in -- not a
        state to guess a remaining time for.
        """
        info, plug = self._read_with_retry(
            ident, _cycle_read, failed=lambda value: not value.get("ok"))
        if not info:
            return {"ok": False, "id": ident, "saved": None, "stale": False,
                    "error": self.failure(ident) or "not connected"}
        info["id"] = ident
        info["stale"] = bool(info["armed"] and info["ours"] and not info["running"])
        info["saved"] = self.memory.for_page(self._stored_id(ident)) \
            if self.memory else None
        if self.memory and self.memory.error:
            info["memory_error"] = self.memory.error
        return info

    def cycle_start(self, ident: str, first: str, on_seconds: int,
                    off_seconds: int, force: bool = False,
                    auto: bool | None = None) -> dict:
        """Write, arm and start the loop. `force` overwrites a foreign rule.

        A successful start is what gets remembered -- not the click. A start that
        was refused (a foreign rule, a rule that would not fit) leaves the old
        configuration alone, so the memory always describes a loop that really
        ran on this plug.
        """
        plug = self.plug_for(ident)
        if plug is None:
            return {"ok": False, "error": self.failure(ident) or "not connected"}
        with self._lock_for(plug):
            plug.timeout = self._timeout(read_only=False)
            ok, detail, taken = _cycle_start(plug, first, on_seconds,
                                             off_seconds, force)
            info = _cycle_read(plug) if ok else None
        if ok and self.memory is not None:
            self.memory.remember(self._stored_id(ident), on_seconds, off_seconds,
                                 first, running=True, auto=auto)
        answer = {"ok": ok, "detail": detail, "cycle": info,
                  "error": None if ok else detail}
        if taken:
            answer["taken"] = True
        return answer

    def cycle_stop(self, ident: str) -> dict:
        """Disarm the loop. The relay is left exactly where it is.

        The remembered numbers stay: a stop is not a decision that the
        configuration was wrong, and re-starting is one click. Only `running`
        is cleared, which is what keeps "自动接着跑" from undoing this by hand.
        """
        plug = self.plug_for(ident)
        if plug is None:
            return {"ok": False, "error": self.failure(ident) or "not connected"}
        with self._lock_for(plug):
            plug.timeout = self._timeout(read_only=False)
            ok, detail = _cycle_stop(plug)
            info = _cycle_read(plug) if ok else None
        if ok and self.memory is not None:
            self.memory.mark_stopped(self._stored_id(ident))
        return {"ok": ok, "detail": detail, "cycle": info,
                "error": None if ok else detail}

    def cycle_restore(self, ident: str) -> dict:
        """Start the remembered configuration again -- the power-cut recovery.

        Nothing but the memory is consulted, so the page cannot pass a duration
        here by accident; a device with nothing remembered gets a plain error.
        """
        if self.memory is None:
            return {"ok": False, "error": "this panel keeps no cycle memory"}
        entry = self.memory.get(self._stored_id(ident))
        if entry is None:
            return {"ok": False, "error": "这台插座没有记住的循环设置 —— 先填好 "
                                          "开 / 关秒数点一次「开始循环」"}
        answer = self.cycle_start(ident, entry["first"], entry["on"], entry["off"])
        if answer.get("ok"):
            answer["detail"] = ("按记忆重启：开 %s / 关 %s，先%s"
                                % (_duration_text(entry["on"]),
                                   _duration_text(entry["off"]),
                                   "开" if entry["first"] == "ON" else "关"))
        return answer

    def cycle_remember(self, ident: str, first: str, on_seconds: int,
                       off_seconds: int, auto: bool | None = None) -> dict:
        """Store a configuration WITHOUT touching the plug.

        Filling in the boxes and clicking "记住这组数字" is a different act from
        starting a loop: someone sets a fish tank up at their desk and starts it
        at the tank. `running` stays False so an automatic restart does not fire
        for a configuration that has never actually run.
        """
        if self.memory is None:
            return {"ok": False, "error": "this panel keeps no cycle memory"}
        entry = self.memory.remember(self._stored_id(ident), on_seconds,
                                     off_seconds, first, running=False, auto=auto)
        return {"ok": True, "detail": "已记住：开 %s / 关 %s，先%s（不会自动开始）"
                % (_duration_text(on_seconds), _duration_text(off_seconds),
                   "开" if first == "ON" else "关"),
                "saved": self.memory.for_page(self._stored_id(ident))}

    def cycle_auto(self, ident: str, auto: bool) -> dict:
        """Turn "restart it by itself after a power cut" on or off."""
        if self.memory is None:
            return {"ok": False, "error": "this panel keeps no cycle memory"}
        entry = self.memory.set_auto(self._stored_id(ident), auto)
        if entry is None:
            return {"ok": False, "error": "这台插座没有记住的循环设置"}
        return {"ok": True, "error": None,
                "detail": "断电后自动接着跑：%s" % ("开" if auto else "关"),
                "saved": self.memory.for_page(self._stored_id(ident))}

    def cycle_forget(self, ident: str) -> dict:
        """Drop the remembered configuration for one device."""
        if self.memory is None:
            return {"ok": False, "error": "this panel keeps no cycle memory"}
        gone = self.memory.forget(self._stored_id(ident))
        return {"ok": True, "saved": None,
                "detail": "已清除这台插座的循环记忆" if gone
                          else "这台插座本来就没有记住的设置"}

    # --------------------------------------------------------------- the sweep
    def _online_of(self, plug) -> bool | None:
        lwt = plug.online
        if lwt is None:
            return None
        if not lwt:
            return False
        return (_time.time() - (plug.state_ts or 0.0)) < 120.0

    def _lock_for(self, plug):
        """A per-plug command lock, so two requests cannot interleave on one link."""
        lock = getattr(plug, "_hub_lock", None)
        if lock is None:
            lock = _threading.Lock()
            plug._hub_lock = lock
        return lock

    def sweep_once(self) -> dict[str, dict]:
        """Read every device's relay state, SERIALLY, and cache the result.

        Serial on purpose: N devices polled at once means N simultaneous round
        trips to one broker, which is how you get timeouts that look like offline
        devices. Sequential reads with a short per-device budget keep the whole
        sweep predictable -- and one slow plug only delays itself.
        """
        rows: dict[str, dict] = {}
        for ident in self.book.ids():
            if self._stop.is_set():
                break
            try:
                rows[ident] = self.status(ident)
            except Exception as exc:                    # noqa: BLE001
                rows[ident] = {"id": ident, "state": None, "online": False,
                               "online_text": "no", "error": str(exc)}
        with self._lock:
            self._sweep = rows
        return rows

    def sweep_cached(self) -> dict[str, dict]:
        with self._lock:
            return dict(self._sweep)

    def refresh_ms(self) -> int:
        """How often the page re-reads the device it is showing, milliseconds.

        Lives on the Fleet because that is what the page already has a handle
        on; resolved here rather than at import time so a --refresh typo shows
        up as the default instead of an exception.
        """
        seconds = _clamp(getattr(self.args, "refresh_seconds", None),
                         HUB_REFRESH_MIN_MS / 1000.0, HUB_REFRESH_MAX_MS / 1000.0,
                         HUB_REFRESH_MS / 1000.0)
        return int(round(seconds * 1000.0))

    def sweep_seconds(self) -> float:
        """How long the sweeper waits between passes (--sweep, clamped)."""
        return _clamp(getattr(self.args, "sweep_seconds", None),
                      HUB_SWEEP_MIN_SECONDS, HUB_SWEEP_MAX_SECONDS,
                      float(HUB_SWEEP_SECONDS))

    def energy_ms(self) -> int:
        """How often the page re-reads the meter of the open device (--energy)."""
        seconds = _clamp(getattr(self.args, "energy_seconds", None),
                         HUB_ENERGY_MIN_MS / 1000.0, HUB_ENERGY_MAX_MS / 1000.0,
                         HUB_ENERGY_MS / 1000.0)
        return int(round(seconds * 1000.0))

    def start_sweeper(self) -> None:
        """A background thread that refreshes the list while the panel runs."""
        def loop() -> None:
            while not self._stop.is_set():
                try:
                    self.sweep_once()
                except Exception:                       # noqa: BLE001
                    pass
                self._stop.wait(self.sweep_seconds())

        self._reader = _threading.Thread(target=loop, name="hub-sweep", daemon=True)
        self._reader.start()


# ------------------------------------------------------------------- accounts
# Three small pieces: UserStore keeps the ACCOUNTS on disk, Sessions keeps who is
# signed in right now, and AccountHub joins them to per-account device lists.
#
# Why files and not a database -- this is the same promise the rest of the panel
# makes: one folder, human-readable JSON, `copy the folder` is the backup. A user
# file small enough to read in an editor is also small enough to reason about.
def _hash_password(password: str, salt: bytes, rounds: int = HUB_HASH_ROUNDS) -> str:
    """PBKDF2-HMAC-SHA256, hex encoded. Deliberately boring: hashlib is always
    there, and a password store is the last place to add a dependency. The salt
    is per account and random, so two people who chose the same password do not
    look alike in the file, and one rainbow table cannot be reused across it.
    """
    return _hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt,
                                rounds).hex()


def _login_file_name(name: str) -> str:
    """A safe file stem for a user name.

    USERNAME_RE already keeps names inside [A-Za-z0-9._-], but this is the one
    place a name becomes a PATH, so nothing downstream gets to assume that held.
    Anything unexpected becomes "_" rather than being trusted twice.
    """
    stem = "".join(char if char.isalnum() or char in "._-" else "_"
                   for char in str(name).strip())
    return (stem or "account").lower()


class UserStore:
    """The accounts file: name, email, and a salted hash -- never the password.

    Same discipline as DeviceBook because it is the same kind of file: written
    atomically with a .bak, and a copy we cannot parse is REPORTED, never
    overwritten. Here that matters even more, because clobbering the accounts
    file while it is the only copy of everybody's password hash locks out every
    user at once.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self.error: str | None = None
        self._lock = _threading.Lock()
        self._users: dict[str, dict] = {}       # key: lower-cased name
        self.load()
        self._ensure_admin()

    def _ensure_admin(self) -> None:
        """A panel with no administrator is one only a text editor can fix.

        Accounts written before roles existed have none, and the password book
        is administrator-only -- so the OLDEST account takes the role when this
        file is loaded. "Oldest" is the earliest `created` stamp with file order
        breaking ties, which is the same rule a fresh panel follows: the first
        person to register is the administrator. The file is rewritten only when
        a role actually changed, so a file that is already right is never
        touched by simply starting the panel.
        """
        with self._lock:
            if not self._users:
                return
            if any(row["role"] == HUB_ROLE_ADMIN for row in self._users.values()):
                return
            oldest = sorted(self._users.values(),
                            key=lambda row: (row["created"] or "", row["name"]))[0]
            oldest["role"] = HUB_ROLE_ADMIN
            self._write()

    # ------------------------------------------------------------------ disk
    def load(self) -> None:
        with self._lock:
            self.error = None
            if not _os.path.exists(self.path):
                self._users = {}
                return
            try:
                with open(self.path, encoding="utf-8") as handle:
                    raw = _json.load(handle)
            except (OSError, ValueError) as exc:
                self._users = {}
                self.error = ("cannot read %s (%s). Nothing has been overwritten -- "
                              "fix it or move it aside, then restart the panel."
                              % (_os.path.basename(self.path), exc))
                return
            rows = raw.get("users") if isinstance(raw, dict) else None
            if not isinstance(rows, list):
                self._users = {}
                self.error = ('%s has no "users" list. Nothing has been overwritten.'
                              % _os.path.basename(self.path))
                return
            clean: dict[str, dict] = {}
            for item in rows:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", "")).strip()
                salt = str(item.get("salt", "") or "")
                digest = str(item.get("hash", "") or "")
                # A row with a broken name or hash cannot be used, and keeping it
                # would only hide the reason nobody can log in.
                if not USERNAME_RE.match(name) or not salt or not digest:
                    continue
                try:
                    _hash_password("probe", bytes.fromhex(salt), 1)
                except ValueError:
                    continue
                clean[name.lower()] = {
                    "name": name,
                    "email": str(item.get("email", "") or ""),
                    "salt": salt, "hash": digest,
                    "rounds": int(item.get("rounds") or HUB_HASH_ROUNDS),
                    "created": str(item.get("created", "") or ""),
                    # Anything unrecognised becomes "user": _ensure_admin() then
                    # promotes somebody, so a typo can never hand out the role.
                    "role": (str(item.get("role", "") or "").strip().lower()
                             if str(item.get("role", "") or "").strip().lower()
                             == HUB_ROLE_ADMIN else HUB_ROLE_USER),
                }
            self._users = clean

    def save(self) -> None:
        """Rewrite the file. Callers that already hold the lock use _write()."""
        with self._lock:
            self._write()

    def _write(self) -> None:
        # NOT re-entrant: every caller below holds self._lock already, and this
        # method must stay lock-free, or registration deadlocks on itself.
        directory = _os.path.dirname(_os.path.abspath(self.path)) or "."
        temp = _os.path.join(directory, ".%s.tmp" % _os.path.basename(self.path))
        rows = [self._users[key] for key in sorted(self._users)]
        payload = {"version": 1, "users": rows}
        with open(temp, "w", encoding="utf-8", newline="\n") as handle:
            _json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        if _os.path.exists(self.path):
            backup = self.path + ".bak"
            try:
                if _os.path.exists(backup):
                    _os.remove(backup)
                _os.replace(self.path, backup)
            except OSError:
                pass            # a missing backup must never block the save
        _os.replace(temp, self.path)

    # ------------------------------------------------------------------ read
    def count(self) -> int:
        with self._lock:
            return len(self._users)

    def find(self, name: str) -> dict | None:
        if not name:
            return None
        with self._lock:
            return dict(self._users.get(str(name).lower(), {})) or None

    def find_email(self, email: str) -> dict | None:
        wanted = str(email or "").strip().lower()
        if not wanted:
            return None
        with self._lock:
            for record in self._users.values():
                if record["email"].lower() == wanted:
                    return dict(record)
        return None

    def profile(self, name: str) -> dict:
        record = self.find(name)
        return ({"name": record["name"], "email": record["email"],
                 "role": record["role"]} if record else {})

    # ----------------------------------------------------------------- write
    def create(self, name: str, email: str, password: str) -> None:
        with self._lock:
            salt = _os.urandom(16)
            self._users[name.lower()] = {
                "name": name, "email": email,
                "salt": salt.hex(),
                "hash": _hash_password(password, salt),
                "rounds": HUB_HASH_ROUNDS, "created": _utc_stamp(),
                # The FIRST account is the administrator, which is the promise
                # the login card has always made ("the first visitor to
                # register is this panel's administrator").
                "role": HUB_ROLE_USER if self._users else HUB_ROLE_ADMIN,
            }
            self._write()

    def set_password(self, name: str, password: str) -> None:
        with self._lock:
            record = self._users.get(name.lower())
            if record is None:
                return
            # A NEW salt, not the old one: re-hashing the same password over the
            # same salt would keep any table already built against this file.
            salt = _os.urandom(16)
            record["salt"] = salt.hex()
            record["hash"] = _hash_password(password, salt)
            self._write()

    def set_email(self, name: str, email: str) -> None:
        with self._lock:
            record = self._users.get(name.lower())
            if record is None:
                return
            record["email"] = email
            self._write()

    # --------------------------------------------------------------- checking
    def check(self, name: str, password: str) -> bool:
        """True if this is the right password for this name.

        The hash is always computed, even for a name nobody uses, and always
        compared with compare_digest. Doing less would answer "wrong password"
        faster than "no such user", which is a free way to enumerate accounts.
        """
        record = self.find(name)
        rounds = record["rounds"] if record else HUB_HASH_ROUNDS
        salt = bytes.fromhex(record["salt"]) if record else b"nobody-here-at-all"
        candidate = _hash_password(password, salt, rounds)
        return _hmac.compare_digest(record["hash"] if record else "0" * 64,
                                    candidate)

    # ------------------------------------------------------------------ roles
    def role(self, name: str) -> str:
        record = self.find(name)
        return record["role"] if record else HUB_ROLE_USER

    def is_admin(self, name: str) -> bool:
        return self.role(name) == HUB_ROLE_ADMIN

    def admin_names(self) -> list[str]:
        with self._lock:
            return sorted(row["name"] for row in self._users.values()
                          if row["role"] == HUB_ROLE_ADMIN)

    def set_role(self, name: str, role: str) -> tuple[bool, str]:
        """Hand the administrator role to somebody, or take it back.

        There is no account-management page, so this exists to make exactly one
        thing fixable without a text editor: a panel where the WRONG account
        ended up as administrator (whoever registered first). The last
        administrator cannot be demoted -- a panel with none has no way to open
        the password book, which is the same as losing it.
        """
        role = str(role or "").strip().lower()
        if role not in (HUB_ROLE_ADMIN, HUB_ROLE_USER):
            return False, "role must be %s or %s" % (HUB_ROLE_ADMIN, HUB_ROLE_USER)
        with self._lock:
            record = self._users.get(str(name or "").strip().lower())
            if record is None:
                return False, "no such account"
            if record["role"] == role:
                return True, role
            if role == HUB_ROLE_USER and not any(
                    row["role"] == HUB_ROLE_ADMIN and row is not record
                    for row in self._users.values()):
                return False, ("the last administrator cannot be demoted -- "
                               "promote somebody else first")
            record["role"] = role
            self._write()
        return True, role


class Sessions:
    """Who is signed in: a random token in a cookie, remembered only in memory.

    Not persisted on purpose. Sessions in a file would outlive the process that
    validated them and would need their own secrecy; losing everybody's session
    when the panel restarts costs one login and removes both problems. The
    expiry is rolling -- a session dies after `hours` of quiet, not `hours`
    after login, because the page polls the whole time it is open.
    """

    def __init__(self, hours: float = HUB_SESSION_HOURS) -> None:
        self._seconds = max(60.0, hours * 3600.0)
        self._lock = _threading.Lock()
        self._tokens: dict[str, list] = {}      # token -> [name, expiry]

    def issue(self, name: str) -> str:
        token = _secrets.token_urlsafe(32)
        with self._lock:
            self._tokens[token] = [name, _time.monotonic() + self._seconds]
        return token

    def peek(self, token: str) -> str | None:
        if not token:
            return None
        with self._lock:
            entry = self._tokens.get(token)
            if entry is None:
                return None
            if _time.monotonic() > entry[1]:
                self._tokens.pop(token, None)
                return None
            entry[1] = _time.monotonic() + self._seconds
            return entry[0]

    def drop(self, token: str) -> None:
        with self._lock:
            self._tokens.pop(token, None)

    def revoke(self, name: str, keep: str | None = None) -> int:
        """Every session of one account except `keep` -- used after a password
        change, so an old window elsewhere cannot keep acting as this user."""
        with self._lock:
            doomed = [token for token, entry in self._tokens.items()
                      if entry[0] == name and token != keep]
            for token in doomed:
                self._tokens.pop(token, None)
        return len(doomed)

    def count(self) -> int:
        with self._lock:
            return len(self._tokens)


class AccountHub:
    """Accounts plus everything that hangs off one of them.

    Each account owns its own device list FILE and its own Fleet, so two people
    can manage different plugs from one panel and neither sees the other's
    serials. Fleets are created on first use and parked once an account goes
    quiet (every device holds an MQTT connection, and browser tabs get closed
    without saying goodbye), so connections track who is actually looking.
    """

    def __init__(self, args, settings: "BrokerSettings | None", users_path: str,
                 lists_dir: str, registration: bool = True,
                 legacy_list: str | None = None) -> None:
        self.args = args
        self.settings = settings
        self.store = UserStore(users_path)
        self.sessions = Sessions()
        self.lists_dir = lists_dir
        self.registration = registration
        self.legacy_list = legacy_list      # an older shared list to adopt once
        if lists_dir:
            try:
                _os.makedirs(lists_dir, exist_ok=True)
            except OSError as exc:
                sys.stderr.write("WARNING: cannot create the account folder %s "
                                  "(%s). Nobody will be able to save devices.\n"
                                  % (lists_dir, exc))
        self._books: dict[str, DeviceBook] = {}
        self._fleets: dict[str, Fleet] = {}
        self._memories: dict[str, CycleMemory] = {}
        self._idle: dict[str, float] = {}   # name -> monotonic time of last use
        self._failed: dict[str, list] = {}  # name -> [wrong answers, cooldown end]
        self._lock = _threading.Lock()
        self._stop = _threading.Event()
        self._keeper: _threading.Thread | None = None

    # ---------------------------------------------------------- per-account IO
    def list_path(self, name: str) -> str:
        return _os.path.join(self.lists_dir, "%s.json" % _login_file_name(name))

    def cycle_path(self, name: str) -> str:
        """The remembered cycles live next to this account's device list, so
        nobody's fish tank shows up in somebody else's panel."""
        return _os.path.join(self.lists_dir,
                             "%s-cycle.json" % _login_file_name(name))

    def book(self, name: str) -> DeviceBook:
        """This account's device list. One object per name, so the file on disk
        cannot be read twice into two disagreeing copies."""
        with self._lock:
            book = self._books.get(name)
            if book is None:
                book = DeviceBook(self.list_path(name))
                self._books[name] = book
            return book

    def _memory_unlocked(self, name: str) -> CycleMemory:
        """The lock-free half, for callers that ALREADY hold self._lock.

        AccountHub._lock is a plain Lock, not an RLock: taking it twice from one
        thread stops the panel dead, with no traceback and no log line. Calling
        memory() from inside fleet() did exactly that once, and it looked like
        "the password stopped working" because the login itself answered while
        the page load behind it hung forever.
        """
        memory = self._memories.get(name)
        if memory is None:
            memory = CycleMemory(self.cycle_path(name))
            self._memories[name] = memory
        return memory

    def memory(self, name: str) -> CycleMemory:
        """This account's remembered cycle settings."""
        with self._lock:
            return self._memory_unlocked(name)

    def fleet(self, name: str) -> Fleet:
        """This account's links, opened on first use. Creating it also makes this
        account "recently active", which is what keeps it out of the reaper."""
        with self._lock:
            fleet = self._fleets.get(name)
            if fleet is None:
                book = self._books.get(name)
                if book is None:
                    book = DeviceBook(self.list_path(name))
                    self._books[name] = book
                # _memory_unlocked, not memory(): this block already holds the
                # lock, and a plain Lock taken twice never comes back.
                fleet = Fleet(self.args, book, self.settings,
                              self._memory_unlocked(name))
                fleet.start_sweeper()
                self._fleets[name] = fleet
            self._idle[name] = _time.monotonic()
            return fleet

    def touch(self, name: str) -> None:
        with self._lock:
            self._idle[name] = _time.monotonic()

    # ----------------------------------------------------------------- lookup
    def who(self, token: str) -> str | None:
        return self.sessions.peek(token)

    def intro(self) -> dict:
        """What an anonymous page needs before it can draw the login card."""
        return {"signed_in": False, "accounts": self.store.count(),
                "registration": self.registration, "error": self.store.error}

    def profile(self, name: str) -> dict:
        data = self.store.profile(name)
        data["signed_in"] = True
        data["registration"] = self.registration
        data["file"] = _os.path.basename(self.list_path(name))
        # Normalised here as well as in UserStore: the page decides whether to
        # draw the password book's button from this, and an account that somehow
        # has no role must not read as "maybe an administrator".
        data["role"] = self.store.role(name)
        return data

    def is_admin(self, name: str) -> bool:
        return bool(name) and self.store.is_admin(name)

    def admin_names(self) -> list[str]:
        return self.store.admin_names()

    # -------------------------------------------------------------- passwords
    def _locked(self, name: str) -> float:
        entry = self._failed.get(name)
        if not entry:
            return 0.0
        if _time.monotonic() > entry[1]:
            self._failed.pop(name, None)
            return 0.0
        return max(0.0, entry[1] - _time.monotonic()) if entry[0] >= HUB_LOGIN_LIMIT \
            else 0.0

    def _wrong_password(self, name: str) -> str:
        entry = self._failed.get(name) or [0, 0.0]
        count = entry[0] + 1
        # The lockout window starts at the first miss, not the last, so retrying
        # forever cannot push it out indefinitely.
        until = entry[1] if entry[1] else _time.monotonic() + HUB_LOGIN_COOLDOWN
        self._failed[name] = [count, until]
        if count >= HUB_LOGIN_LIMIT:
            return ("密码连错 %d 次，请 %d 分钟后再试"
                    % (count, max(1, int((until - _time.monotonic()) // 60) + 1)))
        return ("用户名或密码不对（还可试 %d 次）" % max(0, HUB_LOGIN_LIMIT - count))

    def login(self, name: str, password: str) -> tuple:
        """(True, token) or (False, why). Never says which half was wrong."""
        name = str(name or "").strip()
        wait = self._locked(name)
        if wait:
            return False, "密码错太多次，请 %d 分钟后再试" % max(1, int(wait // 60) + 1)
        if not name or not isinstance(password, str):
            return False, "请填用户名和密码"
        if not self.store.check(name, password):
            return False, self._wrong_password(name)
        self._failed.pop(name, None)
        record = self.store.find(name)
        if record is None:
            return False, "用户名或密码不对"
        return True, self.sessions.issue(record["name"])

    def register(self, name: str, email: str, password: str) -> tuple:
        """Create an account and sign it straight in: (True, token) or (False, why)."""
        name = str(name or "").strip()
        email = str(email or "").strip()
        if not self.registration:
            return False, "注册已关闭：让管理员去掉 --no-register 再启动面板"
        if not USERNAME_RE.match(name):
            return False, ("用户名要是字母开头、3-32 位的字母/数字/._-，"
                           "例如 admin 或 plug.admin")
        if not EMAIL_RE.match(email):
            return False, "邮箱地址看起来不对"
        if not isinstance(password, str) or len(password) < HUB_PASSWORD_MIN:
            return False, "密码至少 %d 位" % HUB_PASSWORD_MIN
        if len(password) > HUB_PASSWORD_MAX:
            return False, "密码最多 %d 位" % HUB_PASSWORD_MAX
        with self._lock:
            if self.store.count() >= HUB_MAX_USERS:
                return False, "账户数已达上限 %d" % HUB_MAX_USERS
            if self.store.find(name):
                return False, "这个用户名已经有人用了"
            if self.store.find_email(email):
                return False, "这个邮箱已经注册过了"
            self.store.create(name, email, password)
        adopted = self._adopt_legacy(name)
        token = self.sessions.issue(name)
        if adopted:
            sys.stderr.write("NOTE: %s took over %s (%d serial(s)); the old file "
                             "is kept as %s.\n"
                             % (name, _os.path.basename(self.legacy_list or ""),
                                adopted, _os.path.basename(self.legacy_list or "")
                                + ".adopted"))
        return True, token

    def _adopt_legacy(self, name: str) -> int:
        """Give the OLD shared list to the first new account, exactly once.

        Before accounts existed there was one device list next to the panel, and
        somebody upgrading would otherwise wake up to an empty page with all
        their serials still sitting in that file. So the first account inherits
        it -- and it is RENAMED, not deleted, so nothing is lost even if the
        copy is wrong.
        """
        if not self.legacy_list or not _os.path.exists(self.legacy_list):
            return 0
        old = DeviceBook(self.legacy_list)
        rows = old.snapshot()
        if not rows:
            return 0
        mine = self.book(name)
        existing = set(mine.ids())
        moved = 0
        for row in rows:
            if row["id"] in existing:
                continue
            mine.add(row["id"], row.get("note", ""),
                     limit=max(1, int(getattr(self.args, "max_devices",
                                              HUB_MAX_DEVICES))))
            moved += 1
        try:
            _os.replace(self.legacy_list, self.legacy_list + ".adopted")
        except OSError:
            pass
        return moved

    def change_password(self, name: str, old: str, new: str, keep: str | None = None
                        ) -> tuple:
        if not isinstance(old, str) or not self.store.check(name, old):
            return False, "旧密码不对"
        ok, why = _password_rules(new)
        if not ok:
            return False, why
        self.store.set_password(name, new)
        dropped = self.sessions.revoke(name, keep=keep)
        return True, "密码已修改，另外 %d 处登录已被登出" % dropped

    def change_email(self, name: str, email: str) -> tuple:
        email = str(email or "").strip()
        if not EMAIL_RE.match(email):
            return False, "邮箱地址看起来不对"
        other = self.store.find_email(email)
        if other and other["name"].lower() != name.lower():
            return False, "这个邮箱已经注册过了"
        self.store.set_email(name, email)
        return True, "邮箱已更新"

    # ------------------------------------------------------------- lifecycle
    def start(self) -> None:
        def loop() -> None:
            while not self._stop.wait(60.0):
                self._reap()

        self._keeper = _threading.Thread(target=loop, name="hub-accounts",
                                         daemon=True)
        self._keeper.start()

    def _reap(self) -> int:
        """Park the fleets nobody has looked at recently, releasing their MQTT links."""
        deadline = _time.monotonic() - HUB_IDLE_MINUTES * 60.0
        with self._lock:
            stale = [name for name, seen in self._idle.items() if seen < deadline]
            parked = [self._fleets.pop(name) for name in stale if name in self._fleets]
        for fleet in parked:
            try:
                fleet.close()
            except Exception:                       # noqa: BLE001
                pass
        return len(parked)

    def active(self) -> int:
        with self._lock:
            return len(self._fleets)

    def close(self) -> None:
        self._stop.set()
        with self._lock:
            fleets = list(self._fleets.values())
            self._fleets.clear()
        for fleet in fleets:
            try:
                fleet.close()
            except Exception:                       # noqa: BLE001
                pass


def _password_rules(value) -> tuple:
    if not isinstance(value, str) or len(value) < HUB_PASSWORD_MIN:
        return False, "密码至少 %d 位" % HUB_PASSWORD_MIN
    if len(value) > HUB_PASSWORD_MAX:
        return False, "密码最多 %d 位" % HUB_PASSWORD_MAX
    return True, ""


def _connack_text(exc) -> str:
    """A connect() failure the way a person can act on it.

    paho reports a refused connection as `rc=<code>`; the codes that matter here
    are the ones where the endpoint is right but the credential is not. Anything
    unrecognised falls through unchanged rather than being guessed at.
    """
    text = str(exc)
    match = _re.search(r"rc=(\d+)", text)
    if not match:
        return text
    code = int(match.group(1))
    # 4/5 are MQTT 3.1.1 CONNACK codes; 134/135 are paho's v5 spelling of the
    # same two answers, which is what the client actually hands back.
    why = {1: "协议版本不被接受",
           2: "客户端 ID 被拒绝",
           3: "服务器不可用",
           4: "用户名或密码不对",
           5: "没有授权（用户名或密码不对）",
           134: "用户名或密码不对",
           135: "没有授权（用户名或密码不对）"}.get(code)
    if not why:
        return text
    return "服务器拒绝了连接：%s（rc=%d）" % (why, code)


def _timer_changes(body: dict) -> dict:
    """Turn the page's form into the Timer fields the user actually changed.

    Mirrors TasmotaPlug._timer_overrides() so the panel and `-timer.py` accept and
    reject exactly the same input -- one implementation of the rules, one place to
    fix them. Raises ValueError with a message meant for the page to display.
    """
    changes: dict = {}
    text = str(body.get("time", "")).strip()
    if text:
        match = CLOCK_RE.match(text)
        if not match:
            raise ValueError("time must be HH:MM (00:00-23:59)")
        changes["Time"] = "%02d:%02d" % (int(match.group(1)), int(match.group(2)))
        changes["Mode"] = TIMER_MODES["clock"]      # the page only sets clock times

    days = str(body.get("days", "")).strip()
    if days:
        if len(days) != 7 or any(c not in "01" for c in days):
            raise ValueError("days must be a 7 character 0/1 mask")
        changes["Days"] = days

    for key, table, low, high in (("action", TIMER_ACTIONS, 0, 3),
                                  ("output", None, 1, 16),
                                  ("window", None, 0, 15)):
        if key not in body:
            continue
        try:
            value = int(body[key])
        except (TypeError, ValueError):
            raise ValueError("%s must be an integer" % key)
        if not low <= value <= high:
            raise ValueError("%s must be %d..%d" % (key, low, high))
        if key == "action":
            changes["Action"] = value
        else:
            changes[key.capitalize()] = value

    for key, field in (("enable", "Enable"), ("repeat", "Repeat")):
        if key in body:
            changes[field] = 1 if body[key] else 0
    return changes


# ------------------------------------------------------------- HTTP layer

class HubHandler(http.server.BaseHTTPRequestHandler):
    """Routes the page and its JSON API onto a Fleet plus a DeviceBook.

    Kept deliberately small: parse, dispatch, serialise. Device knowledge lives in
    Fleet, list knowledge in DeviceBook, rendering in page_html(), so a change to
    any one cannot break the others.
    """

    server_version = "mqtt-py-webhub/" + HUB_VERSION
    fleet: "Fleet" = None               # set by serve() when accounts are off,
    book: "DeviceBook" = None           # and per request when they are on
    token: str | None = None            # --token, or None for no check
    accounts: "AccountHub | None" = None # set by serve(); None = one shared list
    vault: "DeviceVault | None" = None  # the administrator's password book
    user: str | None = None             # who this request belongs to

    # --------------------------------------------------------------- plumbing
    def log_message(self, fmt, *args) -> None:
        """Quiet by default: one line per request would drown the start-up text."""
        if getattr(self.server, "verbose", False):
            sys.stderr.write("[web] %s %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, body: bytes, ctype: str,
              cookies: list | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for crumb in cookies or []:
            self.send_header("Set-Cookie", crumb)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError):
            pass                        # the browser navigated away mid-reply

    def _send_html(self, body: bytes, cookies: list | None = None) -> None:
        self._send(200, body, "text/html; charset=utf-8", cookies)

    def _json(self, data: dict, code: int = 200, cookies: list | None = None) -> None:
        body = _json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8", cookies)

    # -------------------------------------------------------------- sessions
    def _crumb(self, key: str) -> str:
        """One cookie's value, or "". Kept manual rather than clever: the session
        cookie is ours alone, and SimpleCookie raises on some garbage headers."""
        raw = self.headers.get("Cookie") or ""
        for part in raw.split(";"):
            name, _, value = part.partition("=")
            if name.strip() == key:
                return value.strip().strip('"')
        return ""

    @staticmethod
    def _cookie_of(key: str, value: str, seconds: float | None = None) -> str:
        crumb = "%s=%s; Path=/; HttpOnly; SameSite=Lax" % (key, value)
        # Max-Age=0 tells the browser to DROP it, which is how logout works.
        return crumb + ("; Max-Age=%d" % int(seconds) if seconds else "; Max-Age=0")

    def _session_name(self) -> str | None:
        """Who this request belongs to, or None. None with self.accounts set means
        "nobody is signed in"; None without it means accounts are switched off."""
        if self.accounts is None:
            return None
        return self.accounts.who(self._crumb(HUB_SESSION_COOKIE))

    def _bind(self, name: str) -> None:
        """Point this request at one account's list and links."""
        self.user = name
        self.book = self.accounts.book(name)
        self.fleet = self.accounts.fleet(name)
        self.accounts.touch(name)

    def _signed_out(self) -> None:
        self._json({"error": "not signed in", "need_login": True}, 401)

    def _is_admin(self) -> bool:
        """Who may open the password book.

        With accounts ON that is an account whose role is admin, and only while
        it is signed in -- and only ONE account ever gets the role from a plain
        registration (the first), so "signed in" is not by itself enough. With
        --no-auth there is no second party at all: whoever can reach this panel
        started it, and there is nobody else the book could be kept from.
        """
        if self.accounts is None:
            return self.vault is not None
        name = self._session_name()
        return bool(name) and self.accounts.is_admin(name)

    def _vault_view(self) -> dict:
        """The book as the administrator's own page draws it -- passwords included.

        Only ever reached through _is_admin(), both on the way in and on the way
        out, because this payload IS the secret.
        """
        vault = self.vault
        if vault is None:
            return {"entries": [], "count": 0, "enforcing": False,
                    "file": "", "load_error": None}
        return {"file": _os.path.basename(vault.path),
                "entries": vault.snapshot(), "count": vault.count(),
                # Whether adds are checked is NOT a secret: it is a rule every
                # user has to follow, and the add dialog has to say so. The
                # count is public for the same reason. The entries are not.
                "enforcing": vault.enforcing(),
                "load_error": vault.error}

    def _vault_route(self, path: str, body: dict) -> None:
        if not self._is_admin():
            self._json({"error": "只有管理员能管理设备序列号密码本",
                        "admin_only": True}, 403)
            return
        vault = self.vault
        if vault is None:
            self._json({"error": "this panel has no password book"}, 500)
            return
        action = str(body.get("action", "")).strip().lower()
        if not action:
            # A plain GET: the whole book, passwords included. The page masks
            # them until somebody asks for one, which is a screen concern -- the
            # session here already proved it is the administrator reading.
            self._json(dict(self._vault_view(), ok=True))
            return
        if action == "add":
            ok, detail = vault.add(body.get("id"), body.get("password"),
                                   body.get("note"))
        elif action == "set":
            ok, detail = vault.set(body.get("id"), body.get("password"),
                                   note=body.get("note"))
        elif action == "remove":
            # Same rule as removing a device: the destructive one asks first.
            if not body.get("confirm"):
                self._json({"error": "refusing to delete without confirm=1"},
                           400)
                return
            ok, detail = vault.remove(body.get("id"))
        elif action == "reload":
            vault.load()
            ok = vault.error is None
            detail = "已重新读取密码本" if ok else vault.error
        else:
            self._json({"error": "action must be add, set, remove or reload"}, 400)
            return
        if not ok:
            self._json({"error": detail}, 400)
            return
        self._json(dict(self._vault_view(), ok=True, detail=detail))

    # ---------------------------------------------------------- auth routes
    def _auth_route(self, path: str, body: dict, name: str | None) -> None:
        accounts = self.accounts
        if accounts is None:
            self._json({"error": "accounts are switched off (--no-auth)"}, 404)
            return

        if path == "/api/auth/me":
            self._json(accounts.profile(name) if name else accounts.intro())
            return

        if path in ("/api/auth/login", "/api/auth/register"):
            if name:
                self._json({"error": "already signed in"}, 400)
                return
            wanted = str(body.get("user") or body.get("name") or "").strip()
            if path.endswith("register"):
                ok, answer = accounts.register(wanted, str(body.get("email", "")).strip(),
                                               body.get("password"))
            else:
                ok, answer = accounts.login(wanted, body.get("password"))
            if not ok:
                self._json({"error": answer}, 401)
                return
            who = accounts.who(answer) or wanted
            self._json({"ok": True, "name": who, "profile": accounts.profile(who)},
                       cookies=[self._cookie_of(HUB_SESSION_COOKIE, answer,
                                                HUB_SESSION_HOURS * 3600.0)])
            return

        if path == "/api/auth/logout":
            accounts.sessions.drop(self._crumb(HUB_SESSION_COOKIE))
            self._json({"ok": True},
                       cookies=[self._cookie_of(HUB_SESSION_COOKIE, "")])
            return

        if path == "/api/auth/account":
            if not name:
                self._signed_out()
                return
            changed = str(body.get("new_password") or "").strip()
            if changed:
                # A password change is the one way to lock this account out of
                # its own data, so it needs the OLD password even though the
                # session already proves who is asking.
                ok, why = accounts.change_password(name, body.get("old_password"),
                                                   changed,
                                                   keep=self._crumb(HUB_SESSION_COOKIE))
                if not ok:
                    self._json({"error": why}, 400)
                    return
            email = str(body.get("email") or "").strip()
            if email and email != accounts.profile(name).get("email", ""):
                ok, why = accounts.change_email(name, email)
                if not ok:
                    self._json({"error": why}, 400)
                    return
            self._json({"ok": True, "profile": accounts.profile(name)})
            return

        if path == "/api/auth/role":
            # Handing over the administrator role. There is no account page, so
            # this is here to make ONE situation fixable: the wrong account
            # registered first and became the administrator of a panel whose
            # password book it cannot open. An administrator does it, nobody
            # else, and the last one cannot demote itself.
            if not name:
                self._signed_out()
                return
            if not accounts.is_admin(name):
                self._json({"error": "只有管理员能改角色", "admin_only": True}, 403)
                return
            target = str(body.get("name") or "").strip()
            ok, detail = accounts.store.set_role(target, body.get("role"))
            self._json({"ok": True, "name": target, "role": detail,
                        "admins": accounts.admin_names()} if ok
                       else {"error": detail}, 200 if ok else 400)
            return

        self._json({"error": "not found: %s" % path}, 404)

    def _authorised(self, query: dict) -> bool:
        """A shared secret, if one was asked for. Compared without short-circuit
        so the answer does not leak the length of the right token."""
        if not self.token:
            return True
        given = (query.get("token") or [""])[0]
        if len(given) != len(self.token):
            return False
        same = 0
        for a, b in zip(given, self.token):
            same |= ord(a) ^ ord(b)
        return same == 0

    def _payload(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return {}
        if length <= 0:
            return {}
        raw = self.rfile.read(min(length, 65536))
        try:
            data = _json.loads(raw.decode("utf-8"))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def _target(self, query: dict, body: dict) -> str:
        """Which device a request is about: ?device=, else the body, else the first.

        Always normalised through normalize_device_id so "DVES_6FCE2C",
        "tasmota_6FCE2C" and "6fce2c" cannot address the same plug three ways --
        and so a path-like string is rejected rather than turned into a topic.

        A device that was ASKED for must resolve, and must be in the list. The
        earlier version fell back to the first device whenever the id failed to
        normalise, which pointed a typo at somebody else's plug: with two outlets
        on the desk, `device: "bad id!"` flipped the wrong one while the page kept
        showing the name you clicked. Asking for nothing still means "the first
        device" -- that is the documented convenience, and it is not a guess.

        The answer is the spelling the list stores, so a typed `6fce2c` reaches
        `6FCE2C` without the panel inventing a second topic for the same chip.
        """
        asked = str((query.get("device") or [None])[0]
                    or body.get("device") or "").strip()
        if asked:
            ident = normalize_device_id(asked)
            if not ident:
                raise _BadRequest("device id %r is not a valid serial" % asked)
            stored = self.book.resolve(ident)
            if not stored:
                raise _BadRequest("device %s is not in the list" % ident)
            return stored
        first = (self.book.ids() or [""])[0]
        if not first:
            raise _BadRequest("the device list is empty -- add a serial first")
        return first

    # -------------------------------------------------------------- settings
    @staticmethod
    def _settings_changes(body: dict) -> dict:
        """The endpoint fields the page actually sent; absent means 'keep mine'.

        The password is the delicate one. It never travels to the page, so the
        form always posts an empty field -- and an empty field must mean "no
        change", not "set it to empty", or simply opening the dialog and saving
        would log every device out of the broker. Clearing is a separate flag
        the page only sends when its checkbox is ticked.
        """
        changes: dict = {}
        for key in ("host", "port", "tls", "user", "timeout"):
            if key in body:
                changes[key] = body[key]
        password = body.get("password")
        if isinstance(password, str) and password:
            changes["password"] = password
        elif body.get("clear_password"):
            changes["password"] = ""
        return changes

    def _settings_route(self, path: str, body: dict) -> None:
        settings = self.fleet.settings
        if settings is None:
            self._json({"error": "this panel has no settings object"}, 500)
            return
        changes = self._settings_changes(body)

        if path == "/api/settings/test":
            # Validate first: a port of 99999 must not become a connect() call
            # that hangs for the timeout and then reports "no CONNACK" as if the
            # broker were down.
            values, problem = settings.candidate(changes)
            if problem:
                self._json({"error": problem}, 400)
                return
            self._json(self.fleet.probe_broker(values))
            return

        if body.get("reset"):
            settings.forget()
            settings.apply_to(self.fleet.args)
            self._json({"ok": True, "reset": True, "closed": self.fleet.reconfigure(),
                        "settings": settings.as_page()})
            return

        ok, problem = settings.update(changes)
        if not ok:
            self._json({"error": problem}, 400)
            return
        settings.apply_to(self.fleet.args)
        self._json({"ok": True, "closed": self.fleet.reconfigure(),
                    "settings": settings.as_page()})

    # ----------------------------------------------------------------- routes
    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        if not self._authorised(query):
            self._json({"error": "token mismatch -- append ?token=... to the URL"}, 403)
            return
        path = parsed.path.rstrip("/") or "/"

        # The front door. With accounts on, an anonymous visitor gets the login
        # card and nothing else -- every other route is answered 401, so there
        # is no way to reach a device list from outside a session.
        if self.accounts is not None:
            # Only "me" answers a GET: register/login need a body, and replying
            # to a stray GET with a validation error reads like a broken form.
            name = self._session_name()
            if path == "/api/auth/me":
                self._auth_route(path, {}, name)
                return
            if name is None:
                if path in ("/", "/index.html"):
                    self._send_html(login_html(self.accounts.registration,
                                               self.accounts.store.count(),
                                               self.accounts.store.error)
                                    .encode("utf-8"))
                    return
                self._signed_out()
                return
            self._bind(name)

        if path in ("/", "/index.html"):
            body = page_html(getattr(self.server, "read_only", False),
                             self.token, self.fleet.max_devices(),
                             accounts=self.accounts is not None,
                             refresh_ms=self.fleet.refresh_ms(),
                             sweep_ms=int(round(self.fleet.sweep_seconds() * 1000)),
                             admin=self._is_admin(),
                             energy_ms=self.fleet.energy_ms()
                             ).encode("utf-8")
            self._send_html(body)
            return
        if path == "/favicon.ico":
            self._send(204, b"", "image/x-icon")
            return
        if path == "/api/devices":
            # The list as the page draws it: each entry plus the last sweep result.
            swept = self.fleet.sweep_cached()
            rows = []
            for entry in self.book.snapshot():
                ident = entry["id"]
                row = dict(entry)
                row.update(swept.get(ident) or {"state": None, "online": None,
                                                "online_text": "unknown"})
                row["error"] = self.fleet.failure(ident)
                rows.append(row)
            self._json({"devices": rows, "file": _os.path.basename(self.book.path),
                        "load_error": self.book.error,
                        "max_devices": self.fleet.max_devices(),
                        "read_only": bool(getattr(self.server, "read_only", False)),
                        # Whether adding a device needs a password from the
                        # administrator's book is a RULE, not a secret -- the add
                        # dialog of every user has to say so. The entries
                        # themselves stay behind /api/vault.
                        "admin": self._is_admin(),
                        "vault_count": self.vault.count() if self.vault else 0,
                        "vault_enforcing": bool(self.vault
                                                and self.vault.enforcing())})
            return
        if path == "/api/info":
            # What the page needs before it can talk to anything. The builder
            # renames the engine's broker flags to --mqtt-host/--mqtt-port, and
            # argparse derives dest from the flag -- so the broker endpoint lives
            # in args.mqtt_host/args.mqtt_port, exactly as it does in webapp.py.
            # The panel's own socket is listen_host/listen_port, never reused.
            self._json({"devices": len(self.book.ids()), "version": HUB_VERSION,
                        "file": _os.path.basename(self.book.path),
                        "host": self.fleet.args.mqtt_host,
                        "port": self.fleet.args.mqtt_port,
                        "tls": bool(self.fleet.args.tls),
                        "max_devices": self.fleet.max_devices()})
            return
        if path == "/api/settings":
            settings = self.fleet.settings
            if settings is None:
                self._json({"error": "this panel has no settings object"}, 500)
                return
            view = settings.as_page()
            # The panel's own socket is here so the dialog can say "restart to
            # change it" instead of leaving the reader to guess. It is never
            # editable: moving a listening socket mid-request is how you lose
            # the browser that was waiting for the answer.
            listen_host = getattr(self.fleet.args, "listen_host", "0.0.0.0")
            listen_port = getattr(self.fleet.args, "listen_port", HUB_PORT)
            view["listen_host"] = listen_host
            view["listen_port"] = listen_port
            # 0.0.0.0 is a wildcard, not something to type into another machine.
            _mine, others = _listen_urls(listen_host, listen_port, self.token)
            view["listen_urls"] = list(others)
            view["links"] = self.fleet.links()
            view["read_only"] = bool(getattr(self.server, "read_only", False))
            self._json(view)
            return

        if path == "/api/vault":
            # Global like /api/settings: the book belongs to the hardware, not
            # to a device in somebody's list. Administrator only, in both
            # directions -- the 403 comes before anything is read.
            self._vault_route(path, {})
            return

        try:
            ident = self._target(query, {})
        except _BadRequest as exc:
            self._json({"error": str(exc)}, 400)
            return
        if path == "/api/status":
            self._json(self.fleet.status(ident))
            return
        if path == "/api/timers":
            data = self.fleet.clock(ident)
            self._json({"device": ident, "timers": data["timers"],
                        "clock": data["clock"]})
            return
        if path == "/api/cycle":
            self._json(self.fleet.cycle(ident))
            return
        if path == "/api/energy":
            # Read-only by nature: the meter is the device's own, and nothing
            # here writes. It therefore answers in --read-only mode too, which
            # is the point -- watching the load is what that mode is for.
            self._json(self.fleet.energy(ident))
            return
        if path == "/api/probe":
            # On-demand reachability, used after adding a serial.
            self._json(self.fleet.status(ident))
            return
        self._json({"error": "not found: %s" % path}, 404)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        if not self._authorised(query):
            self._json({"error": "token mismatch"}, 403)
            return
        path = parsed.path.rstrip("/")

        # Accounts answer their own routes first: a visitor has NO session yet
        # when they post a login, and the read-only gate is a *write* gate -- it
        # would otherwise lock everybody out of signing in. --read-only still
        # refuses ACCOUNT changes, which are the mutations in there.
        if self.accounts is not None:
            name = self._session_name()
            if path in AUTH_ROUTES:
                if path in ("/api/auth/account", "/api/auth/role") \
                        and getattr(self.server, "read_only", False):
                    self._json({"error": "the panel is in --read-only mode"}, 403)
                    return
                try:
                    self._auth_route(path, self._payload(), name)
                except Exception as exc:                    # noqa: BLE001
                    self._json({"error": "%s: %s" % (type(exc).__name__, exc)}, 500)
                return
            if name is None:
                self._signed_out()
                return
            self._bind(name)

        if getattr(self.server, "read_only", False):
            self._json({"error": "the panel is in --read-only mode"}, 403)
            return
        body = self._payload()
        try:
            self._dispatch(path, body)
        except Exception as exc:                    # noqa: BLE001
            self._json({"error": "%s: %s" % (type(exc).__name__, exc)}, 500)

    def _dispatch(self, path: str, body: dict) -> None:
        # ---- the list itself (no device needed) -----------------------------
        # The endpoint is global, not per-device: one broker serves every plug in
        # the list, so changing it is a fleet-wide act and must not go through
        # _target(). It is also a write, which --read-only already refuses above.
        if path in ("/api/settings", "/api/settings/test"):
            self._settings_route(path, body)
            return

        if path == "/api/vault":
            self._vault_route(path, body)
            return

        if path == "/api/devices/add":
            ident = normalize_device_id(str(body.get("id", "")))
            if not ident:
                self._json({"error": "a serial must be 1-32 characters of "
                                     "A-Z, a-z, 0-9, _ or -"}, 400)
                return
            # The administrator's password book, when it has anything in it, is
            # what decides whether a serial may be added at all -- and it is
            # checked BEFORE the list, so a refused add cannot be used to work
            # out which serials are already in somebody's list.
            if self.vault is not None:
                allowed, why = self.vault.check(ident, body.get("password"))
                if not allowed:
                    self._json({"error": why, "vault_refused": True}, 403)
                    return
            ok, detail = self.book.add(ident, str(body.get("note", "")),
                                       limit=self.fleet.max_devices())
            if not ok:
                self._json({"error": detail}, 400)
                return
            # Probe it once so the page can say "found" or "no reply" right away.
            # A device that is merely unplugged still gets saved: refusing would
            # make the list impossible to prepare before the hardware arrives.
            status = self.fleet.status(ident)
            self._json({"ok": True, "id": ident, "found": status.get("state") is not None,
                        "status": status})
            return

        if path == "/api/devices/note":
            ident = normalize_device_id(str(body.get("id", "")))
            if not ident:
                self._json({"error": "missing or malformed id"}, 400)
                return
            ok, detail = self.book.set_note(ident, str(body.get("note", "")))
            self._json({"ok": ok, "id": detail} if ok else {"error": detail},
                       200 if ok else 400)
            return

        if path == "/api/devices/rename":
            old = normalize_device_id(str(body.get("id", "")))
            new = normalize_device_id(str(body.get("new_id", "")))
            if not old or not new:
                self._json({"error": "both the old and the new serial are required, "
                                     "1-32 characters of A-Z, a-z, 0-9, _ or -"}, 400)
                return
            ok, detail = self.book.rename(old, new)
            if not ok:
                self._json({"error": detail}, 400)
                return
            self.fleet.drop(old)        # close the old link before it goes stale
            status = self.fleet.status(new)
            self._json({"ok": True, "id": new, "found": status.get("state") is not None,
                        "status": status})
            return

        if path == "/api/devices/remove":
            ident = normalize_device_id(str(body.get("id", "")))
            if not ident:
                self._json({"error": "missing or malformed id"}, 400)
                return
            # Deleting is the one irreversible act here, so it needs an explicit
            # confirmation from the page rather than a stray click.
            if not body.get("confirm"):
                self._json({"error": "refusing to delete without confirm=1 "
                                     "(this only forgets the serial and its note; "
                                     "it does not touch the device)"}, 400)
                return
            ok, detail = self.book.remove(ident)
            if not ok:
                self._json({"error": detail}, 400)
                return
            self.fleet.drop(ident)
            self._json({"ok": True, "id": detail})
            return

        # ---- everything else acts on one device ------------------------------
        if path not in DEVICE_POST_ROUTES:
            self._json({"error": "not found: %s" % path}, 404)
            return
        try:
            ident = self._target({}, body)
        except _BadRequest as exc:
            self._json({"error": str(exc)}, 400)
            return

        if path == "/api/reload":
            self.book.load()
            self._json({"ok": self.book.error is None, "devices": self.book.ids(),
                        "load_error": self.book.error})
            return

        if path == "/api/switch":
            action = str(body.get("action", "")).upper()
            if action not in ("ON", "OFF", "TOGGLE"):
                self._json({"error": "action must be ON, OFF or TOGGLE"}, 400)
                return
            self._json(self.fleet.switch(ident, action))
            return

        if path == "/api/pulse":
            first = str(body.get("first", "ON")).upper()
            if first not in ("ON", "OFF"):
                self._json({"error": "first must be ON or OFF"}, 400)
                return
            try:
                seconds = float(body.get("seconds", 5))
            except (TypeError, ValueError):
                self._json({"error": "seconds must be a number"}, 400)
                return
            if not 1 <= seconds <= 86400:
                self._json({"error": "seconds must be between 1 and 86400"}, 400)
                return
            self._json(self.fleet.pulse(ident, first, seconds))
            return

        if path == "/api/timer":
            try:
                index = int(body.get("index", 1))
            except (TypeError, ValueError):
                self._json({"error": "index must be an integer"}, 400)
                return
            if not 1 <= index <= TIMER_COUNT:
                self._json({"error": "index must be 1..%d" % TIMER_COUNT}, 400)
                return
            try:
                changes = _timer_changes(body)
            except ValueError as exc:
                self._json({"error": str(exc)}, 400)
                return
            if not changes:
                self._json({"error": "nothing to change"}, 400)
                return
            self._json(self.fleet.write_timer(ident, index, changes))
            return

        if path == "/api/timers":
            action = str(body.get("action", "")).lower()
            if action not in ("on", "off"):
                self._json({"error": "action must be on or off"}, 400)
                return
            self._json(self.fleet.set_all_timers(ident, action == "on"))
            return

        if path == "/api/timezone":
            offset = str(body.get("offset", "")).strip()
            if not OFFSET_ANY_RE.match(offset):
                self._json({"error": "offset must look like +8:00, +08:00 or -5:30"}, 400)
                return
            self._json(self.fleet.set_timezone(ident, offset))
            return

        if path == "/api/cycle":
            self._cycle_route(body, ident)
            return

        self._json({"error": "not found: %s" % path}, 404)

    def _cycle_route(self, body: dict, ident: str) -> None:
        """Start, stop, restore or remember the repeating on/off loop.

        Two numbers arrive in whole seconds -- the page converts minutes for
        the user, and Tasmota's RuleTimer is a second counter, so there is no
        unit to negotiate. The 24 h ceiling is the firmware's own: a longer
        RuleTimer is silently refused on some builds.

        `restore` and `remember` are the configuration memory: the first starts
        whatever was last remembered WITHOUT being handed a duration (so a stale
        page cannot start a loop with numbers the user never saw), the second
        stores numbers without touching the plug at all.
        """
        action = str(body.get("action", "")).lower()
        if action not in ("start", "stop", "restore", "remember", "auto", "forget"):
            self._json({"error": "action must be start, stop, restore, remember, "
                                 "auto or forget"}, 400)
            return
        if action == "stop":
            self._json(self.fleet.cycle_stop(ident))
            return
        # 400 for a refused memory action, not a 200 carrying ok:false -- the
        # page's error branch is what explains "this plug has nothing saved".
        if action == "restore":
            answer = self.fleet.cycle_restore(ident)
            self._json(answer, 200 if answer.get("ok") else 400)
            return
        if action == "forget":
            answer = self.fleet.cycle_forget(ident)
            self._json(answer, 200 if answer.get("ok") else 400)
            return
        if action == "auto":
            # The one switch that changes what the panel does unattended, so it
            # is its own action rather than a field riding along on "start".
            answer = self.fleet.cycle_auto(ident, bool(body.get("auto")))
            self._json(answer, 200 if answer.get("ok") else 400)
            return

        first = str(body.get("first", "ON")).upper()
        if first not in ("ON", "OFF"):
            self._json({"error": "first must be ON or OFF"}, 400)
            return
        try:
            on_seconds = int(body.get("on", 0))
            off_seconds = int(body.get("off", 0))
        except (TypeError, ValueError):
            self._json({"error": "on and off must be whole seconds"}, 400)
            return
        for label, value in (("on", on_seconds), ("off", off_seconds)):
            if not CYCLE_MIN_SECONDS <= value <= CYCLE_MAX_SECONDS:
                self._json({"error": "%s must be %d..%d seconds"
                                     % (label, CYCLE_MIN_SECONDS,
                                        CYCLE_MAX_SECONDS)}, 400)
                return
        if action == "remember":
            auto = body["auto"] if "auto" in body else None
            answer = self.fleet.cycle_remember(ident, first, on_seconds,
                                               off_seconds, auto)
            self._json(answer, 200 if answer.get("ok") else 400)
            return
        answer = self.fleet.cycle_start(ident, first, on_seconds, off_seconds,
                                        bool(body.get("force")),
                                        body["auto"] if "auto" in body else None)
        # 409, not 400: the request was well formed, it is the DEVICE that
        # already has something in Rule1. The page turns this into a confirm.
        self._json(answer, 409 if answer.get("taken") else 200)

# ---------------------------------------------------------------- the page

def page_html(read_only: bool, token: str | None, max_devices: int,
              accounts: bool = True, refresh_ms: int | None = None,
              sweep_ms: int | None = None, admin: bool = False,
              energy_ms: int | None = None) -> str:
    '''The whole UI: one HTML document, no external requests, no build step.

    Everything is inlined on purpose -- no CDN, no fonts, no images -- so the
    panel also works on a machine with no Internet, and there is nothing to
    install. The look follows the rest of the toolchain: dark, quiet, and the
    Chinese convention that ON is red.

    `accounts` hides the two controls that belong to a login. Serving them in
    --no-auth mode would leave buttons whose every answer is a 404.

    `admin` hides the password book's button. Hiding it is comfort, not the
    guard: /api/vault answers 403 to anybody else whatever the page draws.
    '''
    token_line = ("var TOKEN = %s;" % _json.dumps(token)) if token else "var TOKEN = null;"
    # Resolved here rather than in the signature: the build executes this text
    # on its own, with the constants injected afterwards, so a default that
    # mentions one of them is evaluated too early and raises NameError.
    if refresh_ms is None:
        refresh_ms = HUB_REFRESH_MS
    if sweep_ms is None:
        sweep_ms = int(round(HUB_SWEEP_SECONDS * 1000))
    if energy_ms is None:
        energy_ms = HUB_ENERGY_MS
    return _PAGE % {
        "version": HUB_VERSION,
        # The page's own cadence, in milliseconds. Both beats are adaptive at
        # run time; these are the resting values and the bounds they move inside.
        "refresh_ms": refresh_ms, "sweep_ms": sweep_ms,
        "burst_ms": HUB_REFRESH_BURST_MS,
        "burst_seconds": HUB_REFRESH_BURST_SECONDS,
        "fail_ms": HUB_REFRESH_FAIL_MS, "fail_max_ms": HUB_REFRESH_FAIL_MAX_MS,
        # The energy card has its own, slower-doubling beat -- see HUB_ENERGY_MS.
        "energy_ms": energy_ms, "energy_fail_ms": HUB_ENERGY_FAIL_MS,
        "energy_fail_max_ms": HUB_ENERGY_FAIL_MAX_MS,
        "note_max": HUB_ENERGY_NOTE_MAX,
        "readonly": "true" if read_only else "false", "token_line": token_line,
        "maxdevices": max_devices,
        "logged_in": "true" if accounts else "false",
        "account_hide": "" if accounts else " style=\"display:none\"",
        "vault_hide": "" if admin else " style=\"display:none\"",
    }


def login_html(registration: bool, accounts: int, error: str | None = None) -> str:
    '''The door everybody has to walk through first: sign in, or create an account.

    A separate document rather than a dialog inside the app page, because the
    point is that NOTHING from the panel reaches a browser without a session --
    not the device list route, not even the add-serial button's markup. This
    page contains no device logic at all; it can only talk to the two anonymous
    routes, /api/auth/login and /api/auth/register.
    '''
    note = []
    if error:
        note.append("账户文件读不出来：%s" % error)
    elif not accounts:
        note.append("还没有账户 —— 第一位注册的访客就是这台面板的管理员。")
    elif not registration:
        note.append("注册已关闭（--no-register）：只能用已有账户登录。")
    return _LOGIN_PAGE % {
        "version": HUB_VERSION,
        "can_register": "true" if registration else "false",
        "first": "true" if not accounts else "false",
        "note": _html.escape("　".join(note)) if note else "",
    }


_PAGE = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tasmota 多设备控制台</title>
<style>
:root {
  --bg:#14161a; --panel:#1b1e24; --panel2:#22262e; --line:#2e333d;
  --fg:#e8eaed; --dim:#9aa3b0; --faint:#6b7480;
  --on:#e05252; --off:#4a9e6a; --warn:#d8a13a; --err:#d0595c;
  --accent:#5b8dd6;
}
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
  font:14px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif; }
button { font:inherit; cursor:pointer; border-radius:8px; border:1px solid var(--line);
  background:var(--panel2); color:var(--fg); padding:7px 14px; }
button:hover:not(:disabled) { border-color:#3d4450; background:#282d36; }
button:disabled { opacity:.45; cursor:not-allowed; }
button.primary { background:#2b4a78; border-color:#3a5f95; }
button.danger { background:#5a2a2c; border-color:#7a3a3d; }
button.small { padding:4px 9px; font-size:13px; }
input, select { font:inherit; background:#171a20; color:var(--fg);
  border:1px solid var(--line); border-radius:8px; padding:6px 9px; }
input:focus, select:focus { outline:none; border-color:var(--accent); }

.wrap { display:grid; grid-template-columns:290px 1fr; height:100vh; }
.side { background:var(--panel); border-right:1px solid var(--line);
  display:flex; flex-direction:column; min-height:0; }
.side header { padding:16px 16px 12px; border-bottom:1px solid var(--line); }
.side h1 { margin:0 0 2px; font-size:15px; font-weight:500; }
.side .sub { color:var(--faint); font-size:12px; word-break:break-all; }
.side .tools { padding:10px 12px; display:flex; gap:8px; }
.side .tools button { flex:1; }
.list { overflow:auto; flex:1; min-height:0; padding:4px 8px 12px; }
.row { padding:9px 10px; border-radius:9px; cursor:pointer; margin-bottom:3px;
  border:1px solid transparent; }
.row:hover { background:var(--panel2); }
.row.active { background:#252b36; border-color:#384252; }
.row .top { display:flex; align-items:center; gap:7px; }
.row .id { font-family:ui-monospace,Consolas,monospace; font-size:13px; }
.row .note { color:var(--dim); font-size:12px; margin-top:1px;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.dot { width:8px; height:8px; border-radius:50%%; flex:none; background:var(--faint); }
.dot.on { background:var(--on); } .dot.off { background:var(--off); }
.dot.bad { background:var(--err); }
.row .st { margin-left:auto; font-size:12px; color:var(--dim); }

.main { display:flex; flex-direction:column; min-height:0; }
.main header { padding:14px 20px; border-bottom:1px solid var(--line);
  display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
.main h2 { margin:0; font-size:16px; font-weight:500;
  font-family:ui-monospace,Consolas,monospace; }
.main .note { color:var(--dim); font-size:13px; }
.badge { font-size:12px; padding:3px 9px; border-radius:20px;
  border:1px solid var(--line); color:var(--dim); }
.badge.ok { color:#8fd0a5; border-color:#2f5a40; background:#1c2b22; }
.badge.no { color:#eaa4a6; border-color:#5e2f31; background:#2a1c1d; }
.badge.wait { color:#e0c286; border-color:#5a4a28; background:#2a2318; }
/* the ON/OFF buttons mirror the live relay state: current state looks pressed */
button.cur-on  { border-color:#5e2f31; background:#2a1c1d; color:#eaa4a6; }
button.cur-off { border-color:#2f5a40; background:#1c2b22; color:#8fd0a5; }
.body { overflow:auto; padding:16px 20px 40px; flex:1; min-height:0; }
.cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(310px,1fr)); gap:14px; }
.card { background:var(--panel); border:1px solid var(--line);
  border-radius:12px; padding:15px 16px; }
.card h3 { margin:0 0 12px; font-size:14px; font-weight:500; color:var(--dim); }
.rowbtns { display:flex; gap:8px; flex-wrap:wrap; }
.kv { display:grid; grid-template-columns:auto 1fr; gap:5px 14px; margin:0;
  font-size:13px; }
.kv dt { color:var(--dim); } .kv dd { margin:0;
  font-family:ui-monospace,Consolas,monospace; word-break:break-all; }
/* the energy card: a wide instantaneous readout over a grid of small ones.
   The number is the largest thing in the panel on purpose -- it is the only
   figure anybody reads from across the room. */
.en-top { display:flex; align-items:baseline; gap:9px; margin:2px 0 12px; }
.en-power { font-family:ui-monospace,Consolas,monospace; font-size:32px;
  line-height:1.05; font-weight:500; }
.en-unit { color:var(--dim); font-size:14px; }
.en-tag { margin-left:auto; font-size:12px; color:var(--faint); }
.en-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(96px,1fr));
  gap:9px 12px; }
.en-cell { background:var(--panel2); border:1px solid var(--line);
  border-radius:9px; padding:7px 9px; }
.en-cell .k { color:var(--dim); font-size:12px; }
.en-cell .v { font-family:ui-monospace,Consolas,monospace; font-size:15px;
  margin-top:2px; }
.en-cell .v small { color:var(--faint); font-size:11px; font-family:inherit; }
.en-cell.na .v { color:var(--faint); }
.en-bar { height:4px; border-radius:3px; background:var(--line); margin:11px 0 0;
  overflow:hidden; }
.en-bar i { display:block; height:100%%; width:0; background:var(--accent);
  transition:width .35s ease; }
.en-bar i.hot { background:var(--on); }
.msg { margin-top:11px; font-size:13px; min-height:19px; }
.msg.err { color:#eaa4a6; } .msg.ok { color:#8fd0a5; } .msg.warn { color:var(--warn); }
.empty { color:var(--faint); padding:40px 20px; text-align:center; }
table { width:100%%; border-collapse:collapse; font-size:13px; }
th, td { text-align:left; padding:6px 8px; border-bottom:1px solid var(--line); }
th { color:var(--dim); font-weight:400; }
td.mono { font-family:ui-monospace,Consolas,monospace; }
tr.used td { background:#20242c; }

.overlay { position:fixed; inset:0; background:rgba(10,12,15,.72);
  display:none; align-items:center; justify-content:center; padding:20px; z-index:50; }
.overlay.show { display:flex; }
.modal { background:var(--panel); border:1px solid var(--line); border-radius:14px;
  padding:20px; width:100%%; max-width:430px; }
.modal h3 { margin:0 0 14px; font-size:15px; font-weight:500; }
.modal label { display:block; font-size:13px; color:var(--dim); margin:11px 0 5px; }
.modal input { width:100%%; }
.modal input[type="checkbox"] { width:auto; }
.modal .chk { display:flex; align-items:center; gap:8px; margin:11px 0 0;
  font-size:13px; color:var(--fg); }
.modal .btns { display:flex; gap:9px; justify-content:flex-end; margin-top:18px; }
/* settings dialog: two columns of fields, plus a read-only footer */
.set-modal { max-width:470px; max-height:92vh; overflow-y:auto; }
/* the password book: a wide dialog because it holds a 4-column table */
.vault-modal { max-width:600px; max-height:92vh; overflow-y:auto; }
.vault-modal td.acts { white-space:nowrap; }
.vault-modal td.acts button { padding:3px 8px; margin-left:4px; }
.set-grid { display:grid; grid-template-columns:1fr 1fr; gap:0 12px; }
.set-foot { margin-top:16px; padding-top:13px; border-top:1px solid var(--line);
  font-size:12px; color:var(--faint); line-height:1.7; }
.set-foot b { color:var(--dim); font-weight:500; }
/* visual time picker (timer slots) */
.tm-modal { max-width:330px; max-height:92vh; overflow-y:auto; }
.tm-disp { display:flex; align-items:center; justify-content:center; gap:9px;
  margin:10px 0 2px; }
.tm-sel { font-family:ui-monospace,Consolas,monospace; font-size:22px;
  padding:5px 10px; border-radius:10px; }
.tm-colon { font-size:24px; color:var(--dim); }
.tm-quick { display:flex; gap:6px; flex-wrap:wrap; justify-content:center;
  margin-top:10px; }
.tm-quick button { font-size:12px; padding:2px 9px;
  font-family:ui-monospace,Consolas,monospace; }
.tm-sec { color:var(--faint); font-size:12px; margin:12px 0 5px; text-align:center; }
.tm-days { display:flex; gap:6px; justify-content:center; flex-wrap:wrap; }
.tm-days button { min-width:32px; padding:3px 7px; font-size:13px; }
.tm-days button.on { border-color:var(--accent); color:var(--accent); }
.hint { color:var(--faint); font-size:12px; margin-top:5px; }
.sr { position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); }
/* second line inside a card: pulse lives under the relay buttons, same card */
.subline { margin-top:11px; padding-top:11px; border-top:1px solid var(--line); }
.subline .lead { align-self:center; color:var(--dim); font-size:13px; }
.subline .unit { align-self:center; color:var(--dim); font-size:13px; }

/* ---- narrow screens: phones and half-screen windows ---------------- */
@media (max-width:760px) {
  /* the sidebar moves on top and its device list becomes a swipeable strip */
  .wrap { grid-template-columns:1fr; grid-template-rows:auto 1fr;
    height:100vh; height:100dvh; }
  .side { border-right:none; border-bottom:1px solid var(--line); }
  .side header { padding:12px 14px 9px; }
  .side h1 { font-size:14px; }
  .side .sub { display:none; }
  .side .tools { padding:9px 12px 4px; }
  .list { display:flex; gap:7px; overflow-x:auto; overflow-y:hidden; flex:none;
    padding:4px 12px 10px; -webkit-overflow-scrolling:touch; }
  .row { flex:none; min-width:150px; max-width:230px; margin-bottom:0;
    background:var(--panel2); border-color:var(--line); padding:7px 10px; }
  .row .note { display:none; }
  .main header { padding:11px 13px; gap:8px; }
  .main h2 { font-size:15px; }
  .body { padding:12px 12px 34px; }
  .cards { grid-template-columns:1fr; gap:11px; }
  .card { padding:13px 14px; }
  /* thumb-sized controls; 16px also stops iOS from zooming in on focus */
  button { padding:10px 15px; }
  button.small { padding:8px 12px; font-size:13px; }
  input, select { padding:9px 11px; font-size:16px; }
  .rowbtns { gap:7px; }
  .modal { max-width:100%%; padding:16px; }
  .set-modal, .tm-modal, .vault-modal { max-width:none; }
  .set-grid { grid-template-columns:1fr; }
  /* the power figure stays the big number, but a 32px one wraps on a phone */
  .en-power { font-size:26px; }
  .en-grid { grid-template-columns:repeat(auto-fit,minmax(84px,1fr)); gap:7px 9px; }
  .en-cell { padding:6px 8px; }
  th, td { padding:5px 7px; }
}
@media (max-width:420px) {
  .main header { padding:10px 11px; }
  .body { padding:10px 10px 30px; }
  .card { padding:12px 12px; }
  .tm-sel { font-size:19px; }
  .en-power { font-size:23px; }
  .en-grid { grid-template-columns:1fr 1fr; }
}
</style>
</head>
<body>
<h2 class="sr">Tasmota 多设备控制台</h2>
<div class="wrap">
  <aside class="side">
    <header>
      <h1>Tasmota 多设备控制台</h1>
      <div class="sub" id="listFile">设备清单</div>
      <div class="sub" id="whoLine">—</div>
    </header>
    <div class="tools">
      <button id="addBtn" class="primary small">+ 添加序列号</button>
      <button id="reloadBtn" class="small" title="重新从磁盘读取清单">重载</button>
    </div>
    <div class="list" id="list"><div class="empty">读取中…</div></div>
    <div style="padding:9px 14px;border-top:1px solid var(--line);display:flex;align-items:center;gap:6px;flex-wrap:wrap">
      <span class="badge" id="listBadge">读取中…</span>
      <span style="margin-left:auto"></span>
      <button id="accountBtn" class="small" title="当前账户：改密码 / 邮箱"%(account_hide)s>账户</button>
      <button id="vaultBtn" class="small" title="设备序列号原始密码本：加设备时按它验证（只有管理员）"%(vault_hide)s>密码本</button>
      <button id="settingsBtn" class="small" title="MQTT 服务器地址、端口等">设置</button>
      <button id="logoutBtn" class="small" title="退出登录"%(account_hide)s>退出</button>
    </div>
  </aside>

  <main class="main">
    <header>
      <h2 id="devId">—</h2>
      <span class="note" id="devNote"></span>
      <span class="badge" id="linkBadge">读取中…</span>
      <span style="margin-left:auto"></span>
      <button id="editBtn" class="small" disabled>改序列号/备注</button>
      <button id="delBtn" class="danger small" disabled>删除</button>
    </header>
    <div class="body" id="body">
      <div class="empty" id="empty">左侧还没有设备。点「添加序列号」开始。</div>
      <div class="cards" id="cards" style="display:none">
        <div class="card">
          <h3>继电器 / 脉冲</h3>
          <div class="kv" style="margin-bottom:11px">
            <dt>状态</dt><dd id="relayState">—</dd>
          </div>
          <div class="rowbtns">
            <button id="btnOn">开 ON</button>
            <button id="btnOff">关 OFF</button>
            <button id="btnToggle">翻转</button>
            <button id="btnRefresh" class="small">刷新状态</button>
          </div>
          <div class="rowbtns subline">
            <span class="lead">脉冲</span>
            <select id="pulseFirst">
              <option value="ON">先开 ON</option>
              <option value="OFF">先关 OFF</option>
            </select>
            <input id="pulseSecs" type="number" min="1" max="86400" value="30" style="width:80px">
            <span class="unit">秒后切回</span>
            <button id="btnPulse" class="small">开始</button>
          </div>
          <div class="hint">面板每 <b id="beatHint">—</b> 秒自动读一次状态（启动时用 --refresh 可调）；按过按钮后会读得更勤几秒，读不到就退回慢一些再来。</div>
          <div class="msg" id="relayMsg"></div>
        </div>

        <div class="card">
          <h3>实时功率 / 电压</h3>
          <div class="en-top">
            <span class="en-power" id="enPower">—</span>
            <span class="en-unit">W</span>
            <span class="en-tag" id="enTag"></span>
          </div>
          <div class="en-grid">
            <div class="en-cell" id="enCellV"><div class="k">电压</div>
              <div class="v" id="enV">—</div></div>
            <div class="en-cell" id="enCellA"><div class="k">电流</div>
              <div class="v" id="enA">—</div></div>
            <div class="en-cell" id="enCellPF"><div class="k">功率因数</div>
              <div class="v" id="enPF">—</div></div>
            <div class="en-cell" id="enCellS"><div class="k">视在 / 无功</div>
              <div class="v" id="enS" style="font-size:13px">—</div></div>
            <div class="en-cell" id="enCellToday"><div class="k">今日用电</div>
              <div class="v" id="enToday">—</div></div>
            <div class="en-cell" id="enCellTotal"><div class="k">累计用电</div>
              <div class="v" id="enTotal">—</div></div>
          </div>
          <div class="en-bar" id="enBarWrap"><i id="enBar"></i></div>
          <div class="hint" id="enHint">面板每 <b id="enHintSec">—</b> 秒读一次功率（启动时用 --energy 可调）。</div>
          <div class="hint">数字是插座自己的计量芯片报的：没有计量芯片的插座会写「此设备无功率计量」；插座离线时保留上一次的读数，并标出「离线读数」。</div>
          <div class="msg" id="enMsg"></div>
        </div>

        <div class="card">
          <h3>循环（鱼缸模式）</h3>
          <dl class="kv" style="margin-bottom:11px">
            <dt>状态</dt><dd id="cycState">读取中…</dd>
            <dt>切换</dt><dd id="cycLeft">—</dd>
          </dl>
          <div class="rowbtns">
            <select id="cycFirst">
              <option value="ON">先开 ON</option>
              <option value="OFF">先关 OFF</option>
            </select>
            <input id="cycOn" type="number" min="1" max="86400" value="1800" style="width:82px">
            <span style="align-self:center;color:var(--dim);font-size:13px">秒开 /</span>
            <input id="cycOff" type="number" min="1" max="86400" value="1800" style="width:82px">
            <span style="align-self:center;color:var(--dim);font-size:13px">秒关</span>
          </div>
          <div class="rowbtns" style="margin-top:9px">
            <button id="btnCycStart">开始循环</button>
            <button id="btnCycStop" class="danger">停止</button>
            <button id="btnCycRefresh" class="small">刷新</button>
          </div>
          <div class="rowbtns" id="cycQuick" style="margin-top:9px"></div>
          <div class="rowbtns" style="margin-top:11px;border-top:1px solid var(--line);padding-top:11px">
            <button id="btnCycRemember" class="small">记住这组数字</button>
            <button id="btnCycRecall" class="small">用记忆填充</button>
            <button id="btnCycRestore" class="small">按记忆重启</button>
            <button id="btnCycForget" class="small danger">清除记忆</button>
            <label style="align-self:center;display:flex;align-items:center;gap:6px;color:var(--dim);font-size:13px;cursor:pointer">
              <input id="cycAuto" type="checkbox" style="width:auto">断电后自动接着跑
            </label>
          </div>
          <div class="hint" id="cycSaved">记忆：—</div>
          <div class="hint">记住的是「配置」（开多久 / 关多久 / 先开还是先关），不是「进度」：插座断电后规则还在、定时器归零，剩几秒不会记，也不会记错。</div>
          <div class="hint">循环写进插座自己的规则里，关掉浏览器、关掉这台电脑也照跑。</div>
          <div class="msg" id="cycMsg"></div>
        </div>

        <div class="card">
          <h3>设备时钟与时区</h3>
          <dl class="kv" id="clockKv"><dt>—</dt><dd>读取中…</dd></dl>
          <div class="rowbtns" style="margin-top:12px">
            <button id="btnTz" class="small">写入 +8:00</button>
          </div>
          <div class="msg" id="clockMsg"></div>
        </div>

        <div class="card" style="grid-column:1/-1">
          <h3>定时器（16 个槽位）</h3>
          <div class="rowbtns" style="margin-bottom:11px">
            <button id="btnTimersAllOn" class="small">全局开启</button>
            <button id="btnTimersAllOff" class="small">全局关闭</button>
            <button id="btnTimersRefresh" class="small">刷新</button>
            <span style="align-self:center;color:var(--dim);font-size:13px" id="timersGlobal"></span>
          </div>
          <div style="overflow:auto">
            <table>
              <thead><tr><th>#</th><th>时间</th><th>星期</th><th>动作</th>
                <th>启用</th><th></th></tr></thead>
              <tbody id="timersBody"></tbody>
            </table>
          </div>
          <div class="msg" id="timersMsg"></div>
        </div>
      </div>
    </div>
  </main>
</div>

<div class="overlay" id="overlay">
  <div class="modal">
    <h3 id="modalTitle">添加序列号</h3>
    <label for="fId">序列号 / 设备 ID</label>
    <input id="fId" placeholder="例如 6FCE2C" autocomplete="off">
    <div class="hint">1-32 位，仅 A-Z a-z 0-9 _ -。可直接粘 tasmota_6FCE2C 或 DVES_6FCE2C，会自动去掉前缀。</div>
    <label for="fNote">备注</label>
    <input id="fNote" placeholder="例如 客厅空调插座" autocomplete="off">
    <div id="addPassWrap" style="display:none">
      <label for="fPass">原始密码</label>
      <input id="fPass" type="text" placeholder="设备出厂／交付时的原始密码" autocomplete="off" spellcheck="false">
      <div class="hint">管理员已经启用了校验：这台设备的<b>序列号和原始密码</b>要和「密码本」上的一致，才能加进清单。密码忘了就找管理员。</div>
    </div>
    <div class="msg" id="modalMsg"></div>
    <div class="btns">
      <button id="modalCancel">取消</button>
      <button id="modalOk" class="primary">保存</button>
    </div>
  </div>
</div>

<div class="overlay" id="acctOverlay">
  <div class="modal set-modal">
    <h3>账户</h3>
    <label>用户名（不可改）</label>
    <input id="acctName" disabled autocomplete="username">
    <label for="acctEmail">邮箱</label>
    <input id="acctEmail" type="email" autocomplete="email" spellcheck="false">
    <div class="hint">邮箱只是登记信息；留着不动就不改。</div>
    <label for="acctOld">旧密码</label>
    <input id="acctOld" type="password" placeholder="改密码时才需要填" autocomplete="current-password">
    <label for="acctNew">新密码</label>
    <input id="acctNew" type="password" placeholder="至少 8 位，留空则不改" autocomplete="new-password">
    <label for="acctNew2">再输一次新密码</label>
    <input id="acctNew2" type="password" autocomplete="new-password">
    <div class="hint">改完密码，这个账户在别处的登录会被登出。</div>
    <div class="msg" id="acctMsg"></div>
    <div class="btns">
      <button id="acctCancel">取消</button>
      <button id="acctSave" class="primary">保存</button>
    </div>
  </div>
</div>

<div class="overlay" id="setOverlay">
  <div class="modal set-modal">
    <h3>MQTT 服务器设置</h3>
    <div class="set-grid">
      <div>
        <label for="setHost">服务器地址</label>
        <input id="setHost" placeholder="例如 broker.example.com" autocomplete="off" spellcheck="false">
      </div>
      <div>
        <label for="setPort">端口</label>
        <input id="setPort" type="number" min="1" max="65535" autocomplete="off">
      </div>
      <div>
        <label for="setUser">用户名</label>
        <input id="setUser" autocomplete="off" spellcheck="false">
      </div>
      <div>
        <label for="setPass">密码</label>
        <input id="setPass" type="password" placeholder="留空则不改" autocomplete="new-password">
      </div>
      <div>
        <label for="setTmo">超时（秒）</label>
        <input id="setTmo" type="number" min="1" max="60" step="0.5" autocomplete="off">
      </div>
      <div>
        <label>加密</label>
        <div class="chk"><input id="setTls" type="checkbox"><span>启用 TLS</span></div>
      </div>
    </div>
    <div class="chk" style="margin-top:13px">
      <input id="setClearPass" type="checkbox"><span>保存时清除已保存的密码</span>
    </div>
    <div class="hint">密码不会回传到页面，所以这一栏打开时永远是空的：留空 = 不改。只有勾上上面这一项才会真的清掉。</div>
    <div class="msg" id="setMsg"></div>
    <div class="set-foot">
      <div><b>面板监听</b> <span id="setListen">—</span>（只读；要改请带 --listen / --port 重启面板）</div>
      <div><b>手机 / 其他电脑</b> <span id="setUrls">—</span></div>
      <div><b>设置文件</b> <span id="setFile">—</span></div>
      <div><b>启动参数</b> <span id="setStartup">—</span></div>
    </div>
    <div class="btns">
      <button id="setTest">测试连接</button>
      <button id="setReset">恢复启动值</button>
      <button id="setCancel">取消</button>
      <button id="setSave" class="primary">保存并应用</button>
    </div>
  </div>
</div>

<div class="overlay" id="vaultOverlay">
  <div class="modal vault-modal">
    <h3>设备序列号原始密码本</h3>
    <div class="hint">这里维护<b>设备序列号 + 原始密码</b>。只要本子里有哪怕一条，别人在「添加序列号」时就必须填上
      <b>对得上的序列号和原始密码</b>，否则加不进清单；本子是空的时候不校验（这样才有办法加进第一台）。
      只有管理员能打开这个窗口。文件里存的是<b>原始密码本身</b>，所以这个文件要和插座一样当心。</div>
    <div class="rowbtns" style="margin-top:12px">
      <input id="vaultId" placeholder="序列号，如 6FCE2C" style="width:138px" autocomplete="off">
      <input id="vaultPass" type="text" placeholder="原始密码" style="width:148px" autocomplete="off" spellcheck="false">
      <input id="vaultNote" placeholder="备注（可选）" style="flex:1;min-width:104px" autocomplete="off">
      <button id="vaultSave" class="primary small">添加</button>
      <button id="vaultEditCancel" class="small" style="display:none">取消编辑</button>
    </div>
    <div style="overflow:auto;max-height:38vh;margin-top:12px">
      <table>
        <thead><tr><th>序列号</th><th>原始密码</th><th>备注</th><th></th></tr></thead>
        <tbody id="vaultBody"></tbody>
      </table>
    </div>
    <div class="hint" id="vaultFoot">读取中…</div>
    <div class="msg" id="vaultMsg"></div>
    <div class="btns">
      <button id="vaultReload" class="small">重读文件</button>
      <span style="margin-left:auto"></span>
      <button id="vaultClose">关闭</button>
    </div>
  </div>
</div>

<div class="overlay" id="tmOverlay">
  <div class="modal tm-modal">
    <h3 id="tmTitle">编辑定时</h3>
    <div class="tm-disp">
      <select id="tmHour" class="tm-sel" title="小时（可键盘输入数字跳转）"></select>
      <span class="tm-colon">:</span>
      <select id="tmMin" class="tm-sel" title="分钟（可键盘输入数字跳转）"></select>
    </div>
    <div class="tm-quick" id="tmQuick"></div>
    <div class="tm-sec">星期（点选，可多天；日 = 周日）</div>
    <div class="tm-days" id="tmDays">
      <button data-i="0">日</button>
      <button data-i="1">一</button>
      <button data-i="2">二</button>
      <button data-i="3">三</button>
      <button data-i="4">四</button>
      <button data-i="5">五</button>
      <button data-i="6">六</button>
    </div>
    <div class="tm-sec">动作</div>
    <div class="tm-days" id="tmActs">
      <button data-a="0">关</button>
      <button data-a="1">开</button>
      <button data-a="2">翻转</button>
      <button data-a="3">规则</button>
    </div>
    <div class="tm-sec">启用</div>
    <div class="tm-days"><button id="tmEnable">已启用</button></div>
    <div class="btns">
      <button id="tmCancel">取消</button>
      <button id="tmOk" class="primary">保存</button>
    </div>
  </div>
</div>

<script>
var READONLY = %(readonly)s;
var MAXDEV = %(maxdevices)s;
%(token_line)s

var q=function(id){return document.getElementById(id);};
var current=null, devices=[], modalMode="add", timerRows=[];
var clockLast=null, clockAt=0;
// The last meter reading, the moment it arrived, and how far ahead this card
// has backed off. All three are cleared on a device switch: a wattage left
// standing under a new serial is the most convincing wrong number the panel
// could possibly show, because nothing about it looks out of place.
var enLast=null, enAt=0, enWait=0, enPeak=0;
// Whether the administrator's password book is in use. Comes from /api/devices,
// so EVERY user learns the rule ("a password is required") without ever seeing
// the book itself.
var VAULT_ENFORCING=false, VAULT=[], VAULT_EDITING=false;

window.onerror=function(m,src,line){
  var b=q("linkBadge");
  if(b){b.textContent="页面脚本出错";b.className="badge no";}
  var s=q("listBadge");
  if(s){s.textContent=m+" (行 "+line+")";}
  return false;
};

// Built-in escapes, kept OUT of the source text: this whole block is one big
// raw Python literal at module level, so a backslash written here would reach
// the browser doubled. NL is a dialog line break; the warning sign is a code
// point, which also avoids depending on the file's encoding.
var NL=String.fromCharCode(10);
var WARN=String.fromCharCode(9888)+" ";

function gone(){
  // A session can die mid-session: the server restarted, or somebody changed
  // the password elsewhere. Reload rather than showing "400/401" in every card.
  location.href="/";
  return new Promise(function(){});      // never settles: nothing left to render
}
function api(path,opts){
  opts=opts||{};
  // Anything that is not a plain read just changed the plug, so arm the short
  // fast-watch window here, once, instead of at each of the two dozen buttons.
  if((opts.method||"GET")!=="GET"){ armBurst(); }
  var url=path;
  if(TOKEN){ url += (path.indexOf("?")<0?"?":"&")+"token="+encodeURIComponent(TOKEN); }
  var ctl=new AbortController();
  var t=setTimeout(function(){ctl.abort();},20000);
  return fetch(url,{method:opts.method||"GET",headers:{"Content-Type":"application/json"},
    body:opts.body?JSON.stringify(opts.body):undefined,signal:ctl.signal})
    .then(function(r){ return r.json().then(function(j){
      if(r.status===401 || (j && j.need_login)){ gone(); }
      if(!r.ok){ var e=new Error(j.error||("HTTP "+r.status)); e.data=j; throw e; }
      return j; }); })
    .finally(function(){ clearTimeout(t); });
}

function msg(el,kind,text){ el.className="msg"+(kind?" "+kind:""); el.textContent=text||""; }

function esc(s){ return String(s==null?"":s).replace(/[&<>"']/g,function(c){
  return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]; }); }

// ---------------------------------------------------------------- the list
function paintList(data){
  devices=data.devices||[];
  VAULT_ENFORCING=!!data.vault_enforcing;
  var box=q("list");
  q("listFile").textContent="清单："+(data.file||"?")+"　("+devices.length+
    (data.max_devices?" / "+data.max_devices:"")+")";
  if(data.load_error){
    q("listBadge").textContent="清单文件有问题"; q("listBadge").className="badge no";
    box.innerHTML='<div class="empty" style="text-align:left;padding:14px 10px">'+esc(data.load_error)+'</div>';
    return;
  }
  if(!devices.length){
    box.innerHTML='<div class="empty">还没有设备。<br>点上面「+ 添加序列号」。</div>';
    selectDevice(null); return;
  }
  box.innerHTML=devices.map(function(d){
    var cls = d.error ? "bad" : (d.state==="ON" ? "on" : (d.state==="OFF" ? "off" : ""));
    var st  = d.state ? d.state : (d.online===false ? "离线" : "—");
    return '<div class="row'+(d.id===current?" active":"")+'" data-id="'+esc(d.id)+'">'+
      '<div class="top"><span class="dot '+cls+'"></span>'+
      '<span class="id">'+esc(d.id)+'</span>'+
      '<span class="st">'+esc(st)+'</span></div>'+
      (d.note?'<div class="note">'+esc(d.note)+'</div>':'')+
      '</div>';
  }).join("");
  Array.prototype.forEach.call(box.querySelectorAll(".row"),function(el){
    el.onclick=function(){ selectDevice(el.getAttribute("data-id")); };
  });
  q("listBadge").textContent="共 "+devices.length+" 台设备";
  q("listBadge").className="badge ok";
}

function loadDevices(){
  return api("/api/devices").then(function(d){
    paintList(d);
    if(current && !devices.some(function(x){return x.id===current;})){ selectDevice(null); }
    else if(!current && devices.length){ selectDevice(devices[0].id); }
    else if(current){ paintHeader(); }
  }).catch(function(e){
    q("listBadge").textContent="连不上页面服务"; q("listBadge").className="badge no";
    q("list").innerHTML='<div class="empty">'+esc(e.message)+'</div>';
  });
}

function entryOf(id){
  for(var i=0;i<devices.length;i++){ if(devices[i].id===id) return devices[i]; }
  return null;
}

function selectDevice(id){
  current=id;
  Array.prototype.forEach.call(document.querySelectorAll(".row"),function(el){
    el.classList.toggle("active", el.getAttribute("data-id")===id);
  });
  paintHeader();
  if(!id){ q("cards").style.display="none"; q("empty").style.display="block"; return; }
  q("cards").style.display="grid"; q("empty").style.display="none";
  clockLast=null; cycLast=null;
  paintEnergyUnknown();
  // cycAutoTried is deliberately NOT cleared here. "Restart by itself after a
  // power cut" is meant to be tried once per device per page session, and
  // clearing it on every open turned each click through the list into a fresh
  // chance to fire -- so an armed-but-idle rule plus a remembered cycle turned
  // the relay ON again on every switch. From the user's chair that is "the plug
  // switches itself on, and the OFF I sent a moment ago never landed".
  // true = opening a device, so the cycle boxes may be filled from the device
  // or from what this panel remembered. The poll passes false.
  // A newly opened plug gets a FRESH beat: the previous one may have earned a
  // back-off (up to FAIL_MAX_MS wide) that has nothing to do with this plug,
  // and waiting that out is exactly what makes switching feel broken. The card
  // is cleared as well, so no reading is ever left on screen under a new name.
  stateWait=STATE_MS;
  paintStateUnknown();
  pokeState(); loadTimers(); loadCycle(true); pokeEnergy();
}

function paintHeader(){
  var d=entryOf(current);
  q("devId").textContent = current || "—";
  q("devNote").textContent = d && d.note ? d.note : "";
  var can = !!current && !READONLY;
  q("editBtn").disabled=!can; q("delBtn").disabled=!can;
}

// ---------------------------------------------------------------- state read
// The ON/OFF buttons double as a state indicator: whichever state the relay
// is in right now looks pressed. Anything unknown clears both, so a stale
// highlight never claims a state the panel has not just read.
function paintRelayButtons(on){
  q("btnOn").classList.toggle("cur-on", on===true);
  q("btnOff").classList.toggle("cur-off", on===false);
}

function paintState(o){
  var lb=q("linkBadge");
  if(o.link_error){ lb.textContent="连不上页面服务"; lb.className="badge no";
    q("relayState").textContent="—"; paintRelayButtons(null); return; }
  if(o.error || !o.state){
    lb.textContent="未读到状态"; lb.className="badge wait";
    q("relayState").textContent="未知";
    paintRelayButtons(null);
    msg(q("relayMsg"),"err",o.error||"设备没有回读");
    return;
  }
  var on=o.state==="ON";
  lb.textContent=on?"开 ON":"关 OFF"; lb.className="badge "+(on?"no":"ok");
  q("relayState").textContent=o.state+(o.online===false?"（离线读数）":"");
  paintRelayButtons(on);
  msg(q("relayMsg"),"","");
}

// Nothing is known about the plug on screen yet -- which is the truth right
// after switching devices, and a better thing to show than the previous plug's
// reading under a new name.
function paintStateUnknown(){
  var lb=q("linkBadge");
  if(lb){ lb.textContent="读取中…"; lb.className="badge"; }
  q("relayState").textContent="—";
  paintRelayButtons(null);
  msg(q("relayMsg"),"","");
}

function readState(){
  if(!current) return Promise.resolve(null);
  // Tag the request with the plug it is about. Switching device while a read is
  // in the air is the normal case, not the rare one: the beat is 8 s wide and a
  // read against a silent plug takes about that long. The answer that comes
  // back describes the plug the user just left, and painting it is how the
  // panel shows "未读到状态 / no reply to `Status 0`" for a plug that is
  // perfectly healthy -- simply because the one before it was offline.
  var want=current;
  var lb=q("linkBadge");
  if(lb && /读取中|未读到/.test(lb.textContent)){ lb.textContent="读取中…"; lb.className="badge"; }
  var r="/api/status?device="+encodeURIComponent(want);
  // Hands the ANSWER back, not paintState()'s return value (it has none): the
  // poll beat decides whether to back off by looking at what came back.
  return api(r).then(function(d){
    if(want!==current) return {stale:true};      // not this plug any more
    paintState(d); return d;
  }).catch(function(e){
    if(want!==current) return {stale:true};
    paintState({state:null,error:e.message,link_error:true});
    return null;
  });
}

// ---------------------------------------------------------------- energy
// Power, voltage, current and the two counters, straight off the device's
// sensor block. Three states have to LOOK different, because they mean
// different things: a plug with no meter ("此设备无功率计量"), a plug that did
// not answer (an error, with the last reading still shown but marked stale),
// and a real reading. Drawing 0 W for the first two would be a number the
// device never said.
var NOTE_MAX=%(note_max)s;
function fmtNum(v,digits){
  if(v===null||v===undefined||isNaN(v)) return null;
  return Number(v).toFixed(digits);
}
function enCell(id,txt,na){
  var cell=q(id); if(!cell) return;
  cell.classList.toggle("na",!!na);
  var v=cell.querySelector(".v");
  // The unit lives in a <small> so it can be greyed and shrunk, which means the
  // value is markup, not text. textContent would print the tag itself -- the
  // card would read "242.0 <small>V</small>". Units are ours and the number is
  // a rounded float, so there is nothing here a device could inject.
  if(v) v.innerHTML=txt;
}
function paintEnergyUnknown(){
  enLast=null; enAt=0; enPeak=0;
  // Blank the figure AND drop the "no meter" styling. renderEnergy() returns
  // early while there is no answer, so whatever this leaves is what the user
  // sees until the first reply lands -- a leftover "—", or a leftover grey
  // "n/a" inherited from a previous plug, would be the panel stating something
  // about a device it has not asked yet.
  var power=q("enPower");
  if(power){ power.textContent="—"; power.style.color=""; }
  q("enTag").textContent="";
  enCell("enCellV","—"); enCell("enCellA","—"); enCell("enCellPF","—");
  enCell("enCellS","—"); enCell("enCellToday","—"); enCell("enCellTotal","—");
  q("enBar").style.width="0"; q("enBar").className="";
  msg(q("enMsg"),"","");
}
function renderEnergy(){
  var e=enLast;
  if(!e) return;
  var tag=q("enTag"), bar=q("enBar");
  if(e.link_error){ tag.textContent="连不上页面服务"; return; }
  if(e.no_sensor){
    // Not a failure: this plug has no meter. Say so where the number goes,
    // rather than leaving a dash that reads like "the read is still coming".
    q("enPower").textContent="n/a"; q("enPower").style.color="var(--faint)";
    tag.textContent="此设备无功率计量";
    enCell("enCellV","—",true); enCell("enCellA","—",true);
    enCell("enCellPF","—",true); enCell("enCellS","—",true);
    enCell("enCellToday","—",true); enCell("enCellTotal","—",true);
    bar.style.width="0"; bar.className="";
    msg(q("enMsg"),"warn","插座没有回传功率／电压：这台设备（或这版固件）没有功率计量芯片。");
    return;
  }
  if(!e.ok || !e.values){
    // Keep the last reading but say how old it is. Blanking it would lose the
    // one piece of information that survives a blip.
    var aged = enAt ? Math.round((Date.now()-enAt)/1000) : null;
    q("enPower").style.color="";
    tag.textContent = aged===null ? "未读到读数"
      : ("未读到读数（上次 "+aged+" 秒前）");
    msg(q("enMsg"),"err",e.error||"设备没有回读");
    return;
  }
  var v=e.values, stale=(e.online===false);
  var seconds=Math.round((Date.now()-enAt)/1000);
  var age = seconds>=3 ? seconds : 0;
  q("enPower").style.color="";
  var p=fmtNum(v.Power,1);
  q("enPower").textContent = p==null ? "—" : p;
  enCell("enCellV", fmtNum(v.Voltage,1)==null?"—":fmtNum(v.Voltage,1)+" <small>V</small>");
  enCell("enCellA", fmtNum(v.Current,3)==null?"—":fmtNum(v.Current,3)+" <small>A</small>");
  enCell("enCellPF", fmtNum(v.Factor,2));
  var s=fmtNum(v.ApparentPower,1), r=fmtNum(v.ReactivePower,1);
  enCell("enCellS", (s==null&&r==null) ? "—" : ((s==null?"—":s)+(r==null?"":(" / "+r))+" <small>VA</small>"));
  enCell("enCellToday", fmtNum(v.today,3)==null?"—":fmtNum(v.today,3)+" <small>kWh</small>");
  enCell("enCellTotal", fmtNum(v.Total,3)==null?"—":fmtNum(v.Total,3)+" <small>kWh</small>");
  var bits=[];
  if(e.sensor) bits.push(e.sensor);
  if(stale) bits.push("离线读数");
  else if(age>0) bits.push(age+" 秒前");
  tag.textContent=bits.join("　");
  // A quiet bar, not a gauge: it is a share of the highest wattage seen while
  // this device has been open, so it means "busier or quieter than before",
  // which is the question a load meter actually gets asked.
  if(p!=null && !stale){
    var w=parseFloat(p);
    if(w>enPeak) enPeak=w;
    var frac = enPeak>0 ? Math.min(1, w/enPeak) : 0;
    bar.style.width=Math.round(frac*100)+"%%";
    bar.className = frac>0.85 ? "hot" : "";
  } else { bar.style.width="0"; bar.className=""; }
  msg(q("enMsg"),"","");
}

function loadEnergy(){
  if(!current) return Promise.resolve();
  var want=current;
  return api("/api/energy?device="+encodeURIComponent(want))
    .then(function(e){
      if(want!==current) return {stale:true};
      // The answer names the device it describes; /api/status does not, so this
      // card can check the label instead of trusting the order of events.
      if(e.id && e.id!==want) return {stale:true};
      enLast=e; enAt=Date.now();
      renderEnergy();
      return e;
    })
    .catch(function(err){
      if(want!==current) return {stale:true};
      enLast={ok:false,error:err.message,link_error:true}; enAt=Date.now();
      renderEnergy();
      return {ok:false};
    });
}

// ---------------------------------------------------------------- clock
function clockDriftText(deviceUtc){
  if(!deviceUtc) return null;
  var dev=Date.parse(deviceUtc.replace("Z","")+"Z");
  if(isNaN(dev)) return null;
  var secs=Math.round((Date.now()-dev)/1000);
  if(Math.abs(secs)<=2) return "与本机同步";
  return "本机比设备"+(secs>0?"快":"慢")+" "+Math.abs(secs)+" 秒";
}
function addSeconds(stamp,secs){
  var m=/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/.exec(stamp||"");
  if(!m) return stamp;
  var d=new Date(Date.UTC(+m[1],+m[2]-1,+m[3],+m[4],+m[5],+m[6])+secs*1000);
  var p=function(n){return (n<10?"0":"")+n;};
  return d.getUTCFullYear()+"-"+p(d.getUTCMonth()+1)+"-"+p(d.getUTCDate())+"T"+
         p(d.getUTCHours())+":"+p(d.getUTCMinutes())+":"+p(d.getUTCSeconds());
}
function renderClock(){
  var c=clockLast, box=q("clockKv");
  if(!c || !box) return;
  if(!c.ok){ box.innerHTML='<dt>读取失败</dt><dd>'+esc(c.error||"?")+'</dd>'; return; }
  var elapsed=Math.round((Date.now()-clockAt)/1000);
  var utc=addSeconds(c.utc,elapsed), local=addSeconds(c.local,elapsed);
  var rows=[["设备 UTC",utc],["设备本地",local+"   ("+c.offset_text+")"],
            ["日出/日落",c.sunrise+" / "+c.sunset+"  (设备本地)"]];
  var drift=clockDriftText(utc);
  if(drift) rows.push(["与本机时钟",(drift==="与本机同步"?"":WARN)+drift]);
  box.innerHTML=rows.map(function(r){
    var v=esc(r[1]);
    if(r[0]==="与本机时钟" && v.indexOf(WARN)===0){
      v='<span style="color:var(--warn)">'+v+'</span>';
    }
    return "<dt>"+r[0]+"</dt><dd>"+v+"</dd>";
  }).join("");
}

function loadTimers(){
  if(!current) return;
  // Same rule as readState(): the answer is only about the plug that was on
  // screen when the request went out, so drop it if that has changed.
  var want=current;
  var r="/api/timers?device="+encodeURIComponent(want);
  api(r).then(function(d){
    if(want!==current) return;
    var c=d.clock||{};
    clockLast=c; clockAt=Date.now(); renderClock();
    if(c.ok && c.needs_fix){
      msg(q("clockMsg"),"err","设备时区不是 +08:00（当前 "+c.offset_text+
        "），定时器按设备本地时间触发，请写入 +8:00。");
    } else { msg(q("clockMsg"),"",""); }
    paintTimers(d.timers||{});
  }).catch(function(e){
    if(want!==current) return;
    clockLast={ok:false,error:e.message}; renderClock();
    paintTimersGlobalButtons(null);
    msg(q("timersMsg"),"err",e.message);
  });
}

// The global switch arrives as the device's own wording: this firmware reports
// `"Timers": "ON"` in the status payload, other builds report 1/0. Normalize
// once, or every reader has to guess -- the panel used to test `===1` and so
// showed "关" and highlighted 全局关闭 no matter what the device answered,
// which made the buttons look broken even though the command always landed.
function globalOn(g){
  if(g===null || g===undefined || g==="") return null;
  if(g===true || g===false) return g;
  var s=String(g).trim().toUpperCase();
  if(s==="1"||s==="ON"||s==="TRUE"||s==="YES") return true;
  if(s==="0"||s==="OFF"||s==="FALSE"||s==="NO") return false;
  return null;
}

// The global ON/OFF buttons mirror the Timers switch, same rule as the relay
// pair: the current state looks pressed, an unknown state clears both.
function paintTimersGlobalButtons(g){
  q("btnTimersAllOn").classList.toggle("cur-on", g===true);
  q("btnTimersAllOff").classList.toggle("cur-off", g===false);
}

function paintTimers(t){
  var gon = globalOn(t.global);
  q("timersGlobal").textContent = gon==null ? "" :
    ("全局 Timers："+(gon?"开":"关"));
  paintTimersGlobalButtons(gon);
  var rows=t.slots||[]; timerRows=rows;
  if(!rows.length){
    q("timersBody").innerHTML='<tr><td colspan="6">读取失败或设备未响应</td></tr>';
  } else {
    q("timersBody").innerHTML=rows.map(function(s){
      return '<tr class="'+(s.used?"used":"")+'">'+
        '<td class="mono">'+s.index+'</td>'+
        '<td class="mono">'+esc(s.time||"—")+'</td>'+
        '<td>'+esc(s.days_text||s.days||"—")+'</td>'+
        '<td>'+esc(s.action_text)+'</td>'+
        '<td>'+(s.enable?"是":"否")+'</td>'+
        '<td><button class="small" data-slot="'+s.index+'"'+(READONLY?" disabled":"")+
          '>编辑</button></td></tr>';
    }).join("");
    Array.prototype.forEach.call(q("timersBody").querySelectorAll("button[data-slot]"),
      function(b){ b.onclick=function(){ editSlot(parseInt(b.getAttribute("data-slot"),10)); }; });
  }
}

function post(path,body){
  if(READONLY){
    msg(q("relayMsg"),"err","面板处于只读模式");
    return Promise.reject(new Error("面板处于只读模式"));
  }
  return api(path,{method:"POST",body:body||{}});
}

function act(path,body,msgEl){
  msg(msgEl,"","");
  return post(path,body).then(function(r){
    msg(msgEl, r && r.ok===false ? "err" : "ok",
        (r && (r.detail || r.until_text || r.error)) || "完成");
    return r;
  }).catch(function(e){ msg(msgEl,"err",e.message); })
    .then(function(){ pokeState(); });
}

// ---------------------------------------------------------------- wiring
if(READONLY){
  // The memory buttons write too: "记住" and "清除" change what this panel
  // stores, and "自动接着跑" would start a loop unattended.
  ["btnOn","btnOff","btnToggle","btnPulse","btnTz","addBtn","btnTimersAllOn",
   "btnTimersAllOff","btnCycStart","btnCycStop","btnCycRemember","btnCycRecall",
   "btnCycRestore","btnCycForget","cycAuto"].forEach(function(i){
     var el=q(i); if(el) el.disabled=true; });
}

q("btnOn").onclick=function(){ act("/api/switch",{device:current,action:"ON"},q("relayMsg")); };
q("btnOff").onclick=function(){ act("/api/switch",{device:current,action:"OFF"},q("relayMsg")); };
q("btnToggle").onclick=function(){ act("/api/switch",{device:current,action:"TOGGLE"},q("relayMsg")); };
q("btnRefresh").onclick=function(){ pokeState(); loadTimers(); pokeEnergy(); };

q("btnPulse").onclick=function(){
  act("/api/pulse",{device:current,first:q("pulseFirst").value,
                    seconds:parseFloat(q("pulseSecs").value)||30},q("relayMsg"));
};

// -------------------------------------------------------------- cycle (loop)
// This card is a VIEW of something that lives in the plug: both the on/off
// durations and the countdown come from `Rule1` and the RuleTimer the device
// reports. The only local arithmetic is the seconds ticking away between two
// reads, and every read re-anchors it -- so a slow page or a sleepy tab shows
// a stale number for one refresh at most, never a drifting one.
//
// Two different things could be "remembered" here and keeping them apart is the
// whole point. The CONFIGURATION -- how long on, how long off, which phase
// starts -- is ours to store, and the page does: it survives closing the
// browser, restarting the panel and moving to another PC. The PROGRESS -- how
// far into the current phase the plug had got -- is NOT stored anywhere,
// because a plug that loses mains comes back with its rule intact and its
// RuleTimer at zero. A remembered countdown would be a number the device
// disagrees with, so the page answers that case with "规则还在，但没在跑"
// and an offer to start it again.
var cycLast=null, cycAt=0, cycAutoTried={};

function cycText(n){
  n=Math.max(0,Math.round(n));
  var h=Math.floor(n/3600), m=Math.floor((n-h*3600)/60), s=n-h*3600-m*60;
  if(n>=3600) return h+" 小时"+(m?" "+m+" 分":"");
  if(n>=60)   return m+" 分"+(s?" "+s+" 秒":"");
  return n+" 秒";
}
function paintCycle(c){ cycLast=c; cycAt=Date.now(); renderCycle(); renderCycleSaved(); }
function renderCycle(){
  var c=cycLast;
  if(!c){ q("cycState").textContent="—"; q("cycLeft").textContent="—"; return; }
  if(!c.ok){ q("cycState").textContent="读取失败";
             q("cycLeft").textContent=c.error||"?"; return; }
  if(!c.armed){
    q("cycState").textContent = c.ours ? "没在跑（规则还在插座里，已停用）" : "没在跑";
    q("cycLeft").textContent="—"; return;
  }
  // Armed but holding somebody else's rule: say so instead of showing a cycle
  // this panel cannot read durations out of.
  if(!c.ours){ q("cycState").textContent="Rule1 被别的规则占用";
               q("cycLeft").textContent="—"; return; }
  // The power-cut fingerprint: our rule is armed, yet no RuleTimer is counting.
  // Tasmota keeps rules across a reboot and starts the timers at zero, so there
  // is no "remaining" to show -- only the fact that it stopped.
  if(!c.running){
    q("cycState").textContent="没在跑（规则还在插座里 —— 断电后计时不恢复）";
    q("cycLeft").textContent = c.saved ? "点「按记忆重启」接着跑" : "—";
    return;
  }
  var left=Math.max(0, c.left-Math.round((Date.now()-cycAt)/1000));
  q("cycState").textContent="循环中：开 "+cycText(c.on)+" / 关 "+cycText(c.off)+
    "　现在是"+(c.phase==="on"?"开着":"关着");
  q("cycLeft").textContent=left+" 秒后"+(c.phase==="on"?"关":"开");
}
function renderCycleSaved(){
  var c=cycLast, s=(c&&c.saved)||null;
  if(!s){ q("cycSaved").textContent="记忆：还没有 —— 填好数字点「记住这组数字」";
          q("cycAuto").checked=false; return; }
  q("cycSaved").textContent="记忆：开 "+cycText(s.on)+" / 关 "+cycText(s.off)+
    "，先"+(s.first==="ON"?"开":"关")+
    (s.saved_text?"　· 存于 "+s.saved_text:"")+
    (s.running?"　· 上次在跑":"　· 上次是手动停的");
  q("cycAuto").checked=!!s.auto;
}
// Fill the boxes from the DEVICE first -- if a loop is running, those are the
// numbers actually in force -- and only then from what this panel remembered.
// Called on device switch only: a 5-second poll must not overwrite what someone
// is halfway through typing.
function cycFillFrom(c){
  if(!c) return;
  if(c.ours&&c.on&&c.off){ q("cycOn").value=c.on; q("cycOff").value=c.off; return; }
  if(c.saved){ q("cycOn").value=c.saved.on; q("cycOff").value=c.saved.off;
               q("cycFirst").value=c.saved.first; }
}
// "Restart by itself after a power cut": only when it had been running, only
// while the rule is ours and idle, and only ONCE per device -- otherwise a plug
// that refuses would be retried every five seconds forever.
function cycAutoWatch(c){
  if(!current||!c||!c.saved||!c.saved.auto||!c.saved.running) return;
  if(!c.stale){ delete cycAutoTried[current]; return; }
  if(cycAutoTried[current]) return;
  cycAutoTried[current]=1;
  post("/api/cycle",{device:current,action:"restore"}).then(function(r){
    msg(q("cycMsg"),"ok","断电后自动接着跑："+((r&&r.detail)||"已开始"));
    if(r&&r.cycle) paintCycle(r.cycle);
    pokeState();
  }).catch(function(e){ msg(q("cycMsg"),"err","自动重启失败："+e.message); });
}
function loadCycle(fill){
  if(!current) return Promise.resolve();
  // Polled like the state read, so it can land after a switch just as easily --
  // and a loop's durations shown under another plug's name would be worse than
  // an error, because they look plausible.
  var want=current;
  return api("/api/cycle?device="+encodeURIComponent(want))
    .then(function(c){
      if(want!==current) return;
      paintCycle(c); if(fill) cycFillFrom(c); cycAutoWatch(c);
    })
    .catch(function(e){
      if(want!==current) return;
      paintCycle({ok:false,error:e.message});
    });
}
function cycNumbers(){
  var on=parseInt(q("cycOn").value,10), off=parseInt(q("cycOff").value,10);
  if(!(on>=1&&on<=86400)||!(off>=1&&off<=86400)) return null;
  return {on:on, off:off, first:q("cycFirst").value};
}
// One place that decides what the card says, because an answer with ok:false
// and a `detail` is still a FAILURE -- showing "已开始" for it is how a panel
// ends up claiming to have started a loop the plug refused.
function cycMsg(r, fallback){
  if(!r || r.ok===false) msg(q("cycMsg"),"err",(r&&(r.error||r.detail))||"失败");
  else msg(q("cycMsg"),"ok",(r&&r.detail)||fallback);
}
function startCycle(force){
  var n=cycNumbers();
  var b={device:current,action:"start",first:q("cycFirst").value,
         on:n?n.on:0, off:n?n.off:0};
  if(force) b.force=1;
  // Only sent when it is ON: an unticked box means "leave the switch alone",
  // not "turn the switch off" -- otherwise starting a loop would silently
  // cancel the automatic restart set up earlier.
  if(q("cycAuto").checked) b.auto=1;
  return post("/api/cycle",b);
}

q("btnCycStart").onclick=function(){
  msg(q("cycMsg"),"","");
  var on=parseInt(q("cycOn").value,10), off=parseInt(q("cycOff").value,10);
  if(!(on>=1&&on<=86400)||!(off>=1&&off<=86400)){
    msg(q("cycMsg"),"err","开 / 关的秒数要在 1 到 86400（24 小时）之间"); return; }
  startCycle(false).then(function(r){
    cycMsg(r,"已开始");
    if(r&&r.cycle) paintCycle(r.cycle);
  }).catch(function(e){
    var d=e.data||{};
    if(d.taken){
      // Somebody else's rule is in Rule1 and NOTHING has been written yet, so
      // this is the moment to ask. Once it is overwritten there is no undo.
      if(!confirm(d.error)){ msg(q("cycMsg"),"warn","已取消，插座里的规则没动");
                             return null; }
      return startCycle(true).then(function(r){
        cycMsg(r,"已开始");
        if(r&&r.cycle) paintCycle(r.cycle);
      }).catch(function(e2){ msg(q("cycMsg"),"err",e2.message); });
    }
    msg(q("cycMsg"),"err",e.message); return null;
  }).then(function(){ pokeState(); });
};

q("btnCycStop").onclick=function(){
  msg(q("cycMsg"),"","");
  post("/api/cycle",{device:current,action:"stop"}).then(function(r){
    cycMsg(r,"已停止");
    if(r&&r.cycle) paintCycle(r.cycle);
  }).catch(function(e){ msg(q("cycMsg"),"err",e.message); })
    .then(function(){ pokeState(); });
};
q("btnCycRefresh").onclick=function(){ loadCycle(false); };

q("btnCycRemember").onclick=function(){
  msg(q("cycMsg"),"","");
  var n=cycNumbers();
  if(!n){ msg(q("cycMsg"),"err","开 / 关的秒数要在 1 到 86400（24 小时）之间"); return; }
  // Stores the numbers WITHOUT starting anything: setting a tank up at a desk
  // and switching it on at the tank are two different moments.
  post("/api/cycle",{device:current,action:"remember",on:n.on,off:n.off,
                     first:n.first,auto:q("cycAuto").checked?1:0})
    .then(function(r){ cycMsg(r,"已记住"); return loadCycle(false); })
    .catch(function(e){ msg(q("cycMsg"),"err",e.message); });
};
q("btnCycRecall").onclick=function(){
  msg(q("cycMsg"),"","");
  var s=cycLast&&cycLast.saved;
  if(!s){ msg(q("cycMsg"),"warn","这台插座没有记住的设置"); return; }
  q("cycOn").value=s.on; q("cycOff").value=s.off; q("cycFirst").value=s.first;
  msg(q("cycMsg"),"ok","已把记忆填回上面的输入框（还没开始）");
};
q("btnCycRestore").onclick=function(){
  msg(q("cycMsg"),"","");
  // No numbers travel in this request on purpose: the plug gets exactly what
  // was remembered, so a stale page cannot restart a loop with values from
  // somewhere else.
  post("/api/cycle",{device:current,action:"restore"})
    .then(function(r){ cycMsg(r,"已开始");
                       if(r&&r.cycle) paintCycle(r.cycle); })
    .catch(function(e){ msg(q("cycMsg"),"err",e.message); })
    .then(function(){ pokeState(); });
};
q("btnCycForget").onclick=function(){
  msg(q("cycMsg"),"","");
  post("/api/cycle",{device:current,action:"forget"})
    .then(function(r){ cycMsg(r,"已清除"); return loadCycle(false); })
    .catch(function(e){ msg(q("cycMsg"),"err",e.message); });
};
q("cycAuto").onchange=function(){
  msg(q("cycMsg"),"","");
  post("/api/cycle",{device:current,action:"auto",auto:q("cycAuto").checked?1:0})
    .then(function(r){ cycMsg(r,"已保存"); })
    .catch(function(e){ msg(q("cycMsg"),"err",e.message); })
    .then(function(){ return loadCycle(false); });
};

(function(){
  // A fish tank wants minutes, the firmware counts seconds; these fill both
  // boxes in one click so nobody has to multiply by 60.
  var quick=[["30秒 / 30秒",30,30],["5分 / 5分",300,300],["15分 / 15分",900,900],
             ["30分 / 30分",1800,1800],["1时 / 1时",3600,3600],["10分 / 50分",600,3000]];
  q("cycQuick").innerHTML=quick.map(function(t){
    return '<button class="small" data-on="'+t[1]+'" data-off="'+t[2]+'">'+t[0]+'</button>';
  }).join("");
  Array.prototype.forEach.call(q("cycQuick").querySelectorAll("button"),function(b){
    b.onclick=function(){
      q("cycOn").value=b.getAttribute("data-on");
      q("cycOff").value=b.getAttribute("data-off");
    };
  });
})();

q("btnTz").onclick=function(){
  msg(q("clockMsg"),"","");
  post("/api/timezone",{device:current,offset:"+8:00"}).then(function(r){
    msg(q("clockMsg"), r && r.ok ? "ok":"err", (r && (r.detail||r.error)) || "已写入");
  }).catch(function(e){ msg(q("clockMsg"),"err",e.message); })
    .then(loadTimers);
};

q("btnTimersAllOn").onclick=function(){
  act("/api/timers",{device:current,action:"on"},q("timersMsg")).then(loadTimers); };
q("btnTimersAllOff").onclick=function(){
  act("/api/timers",{device:current,action:"off"},q("timersMsg")).then(loadTimers); };
q("btnTimersRefresh").onclick=loadTimers;

// ------------------------------------------------------ timer slot editor
// One modal edits the whole slot: clock time (two dropdowns, hour 00-23 and
// minute 00-59), weekdays (7 toggles in SMTWTFS order), action and enable.
// The overlay opens from editSlot with the slot's current values prefilled,
// and reports back through a callback: true (save everything) or false
// (cancel).
var tm={h:8,m:0,days:"0000000",action:1,enable:1,cb:null};

function editSlot(index){
  if(READONLY) return;
  openTimePicker(index,function(ok){
    if(!ok) return;
    var body={device:current,index:index,
      time:tmPad(tm.h)+":"+tmPad(tm.m),
      days:tm.days, action:tm.action, enable:tm.enable};
    post("/api/timer",body).then(function(r){
      msg(q("timersMsg"), r && r.ok ? "ok":"err", (r && (r.detail||r.error)) || "完成");
    }).catch(function(e){ msg(q("timersMsg"),"err",e.message); }).then(loadTimers);
  });
}

function openTimePicker(index,cb){
  tm.cb=cb;
  var cur=null;
  for(var i=0;i<timerRows.length;i++){
    if(timerRows[i].index===index){ cur=timerRows[i]; break; }
  }
  var mt=cur && cur.time && /^(\d{1,2}):(\d{2})$/.exec(cur.time);
  tm.h=mt?Math.min(23,parseInt(mt[1],10)):8;
  tm.m=mt?Math.min(59,parseInt(mt[2],10)):0;
  tm.days=(cur && /^[01]{7}$/.test(cur.days||"")) ? cur.days : "0000000";
  tm.action=(cur && cur.action!=null) ? ((cur.action%%4)+4)%%4 : 1;
  tm.enable=(cur && cur.enable) ? 1 : 0;
  q("tmTitle").textContent="槽位 "+index+" · 编辑定时";
  paintTm();
  q("tmOverlay").classList.add("show");
}
function closeTm(fin){
  q("tmOverlay").classList.remove("show");
  var cb=tm.cb; tm.cb=null;
  if(cb) cb(fin);
}

function tmPad(n){ return (n<10?"0":"")+n; }
function paintTm(){
  q("tmHour").value=tmPad(tm.h);
  q("tmMin").value=tmPad(tm.m);
  Array.prototype.forEach.call(q("tmDays").querySelectorAll("button"),function(b){
    b.classList.toggle("on",tm.days.charAt(parseInt(b.getAttribute("data-i"),10))==="1");
  });
  Array.prototype.forEach.call(q("tmActs").querySelectorAll("button"),function(b){
    b.classList.toggle("on",parseInt(b.getAttribute("data-a"),10)===tm.action);
  });
  q("tmEnable").classList.toggle("on",tm.enable===1);
  q("tmEnable").textContent=tm.enable?"已启用":"已停用";
}
(function(){
  // Populate the two dropdowns once: 24 hours, 60 minutes. Typing digits while
  // a closed select has focus jumps to the matching option in every browser,
  // which doubles as direct keyboard entry.
  var h=q("tmHour"), m=q("tmMin"), i, o;
  for(i=0;i<24;i++){
    o=document.createElement("option"); o.value=tmPad(i); o.textContent=tmPad(i);
    h.appendChild(o);
  }
  for(i=0;i<60;i++){
    o=document.createElement("option"); o.value=tmPad(i); o.textContent=tmPad(i);
    m.appendChild(o);
  }
  h.onchange=function(){ tm.h=parseInt(h.value,10); paintTm(); };
  m.onchange=function(){ tm.m=parseInt(m.value,10); paintTm(); };
})();
Array.prototype.forEach.call(q("tmDays").querySelectorAll("button"),function(b){
  b.onclick=function(){
    var i=parseInt(b.getAttribute("data-i"),10);
    tm.days=tm.days.substr(0,i)+(tm.days.charAt(i)==="1"?"0":"1")+tm.days.substr(i+1);
    paintTm();
  };
});
Array.prototype.forEach.call(q("tmActs").querySelectorAll("button"),function(b){
  b.onclick=function(){ tm.action=parseInt(b.getAttribute("data-a"),10); paintTm(); };
});
q("tmEnable").onclick=function(){ tm.enable=tm.enable?0:1; paintTm(); };
q("tmOk").onclick=function(){ closeTm(true); };
q("tmCancel").onclick=function(){ closeTm(false); };
q("tmOverlay").onclick=function(e){ if(e.target===q("tmOverlay")) closeTm(false); };
document.addEventListener("keydown",function(e){
  if(e.key==="Escape" && q("tmOverlay").classList.contains("show")) closeTm(false);
});
(function(){
  var quick=[["06:30",6,30],["07:00",7,0],["07:30",7,30],["08:00",8,0],
             ["12:00",12,0],["18:00",18,0],["20:00",20,0],["22:00",22,0],["23:30",23,30]];
  q("tmQuick").innerHTML=quick.map(function(t){
    return '<button data-h="'+t[1]+'" data-m="'+t[2]+'">'+t[0]+'</button>';
  }).join("");
  Array.prototype.forEach.call(q("tmQuick").querySelectorAll("button"),function(b){
    b.onclick=function(){
      tm.h=parseInt(b.getAttribute("data-h"),10);
      tm.m=parseInt(b.getAttribute("data-m"),10);
      paintTm();
    };
  });
})();

// ---------------------------------------------------------------- modal
function openModal(mode){
  if(READONLY) return;
  modalMode=mode;
  var d=entryOf(current);
  q("modalMsg").textContent="";
  if(mode==="add"){
    q("modalTitle").textContent="添加序列号";
    q("fId").value=""; q("fNote").value=""; q("fPass").value="";
  } else {
    q("modalTitle").textContent="修改序列号 / 备注";
    q("fId").value=current||""; q("fNote").value=(d&&d.note)||"";
  }
  var hint=document.querySelector("#overlay .hint");
  // "block", never "": an empty string DELETES the inline value and the element
  // falls back to its class rules, which is how a toggle that looks right ends
  // up revealing nothing at all.
  if(hint){ hint.style.display = mode==="add" ? "block" : "none"; }
  // The password box shows up only when it is actually required, and only when
  // adding: on a panel whose book is still empty the dialog stays two fields.
  q("addPassWrap").style.display =
    (mode==="add" && VAULT_ENFORCING) ? "block" : "none";
  q("overlay").classList.add("show");
  setTimeout(function(){ q("fId").focus(); },30);
}
function closeModal(){ q("overlay").classList.remove("show"); }

q("addBtn").onclick=function(){ openModal("add"); };
q("editBtn").onclick=function(){ if(current) openModal("edit"); };
q("modalCancel").onclick=closeModal;
q("overlay").onclick=function(e){ if(e.target===q("overlay")) closeModal(); };

q("modalOk").onclick=function(){
  var id=q("fId").value.trim(), note=q("fNote").value.trim();
  msg(q("modalMsg"),"","");
  if(modalMode==="add"){
    post("/api/devices/add",{id:id,note:note,password:q("fPass").value}).then(function(r){
      closeModal();
      return loadDevices().then(function(){ selectDevice(r.id); });
    }).catch(function(e){ msg(q("modalMsg"),"err",e.message); });
    return;
  }
  var renamed = (id && id!==current)
    ? post("/api/devices/rename",{id:current,new_id:id})
    : Promise.resolve(null);
  renamed.then(function(r){
    var target = r ? r.id : current;
    return post("/api/devices/note",{id:target,note:note}).then(function(){ return target; });
  }).then(function(target){
    closeModal(); current=null;
    return loadDevices().then(function(){ selectDevice(target); });
  }).catch(function(e){ msg(q("modalMsg"),"err",e.message); });
};

q("delBtn").onclick=function(){
  if(!current) return;
  if(!confirm("从清单里删除 "+current+"？"+NL+NL+"只会忘掉这个序列号和它的备注，不会动设备本身。")) return;
  post("/api/devices/remove",{id:current,confirm:1}).then(function(){
    current=null; return loadDevices();
  }).catch(function(e){ alert("删除失败："+e.message); });
};

q("reloadBtn").onclick=function(){
  post("/api/reload",{}).then(function(){ current=null; return loadDevices(); })
    .catch(function(e){ alert(e.message); });
};

// ------------------------------------------------------- the password book
// Administrator-only. Hiding the button is comfort, not the guard: /api/vault
// answers 403 to everybody else whatever the page draws, and the page is only
// ever told WHETHER adding a device needs a password -- never the entries.
var MASK=String.fromCharCode(8226,8226,8226,8226,8226,8226);
var VAULT_SHOWN={};
function vaultSay(kind,text){ msg(q("vaultMsg"),kind,text); }
function vaultEditStop(){
  VAULT_EDITING=false;
  q("vaultSave").textContent="添加";
  q("vaultEditCancel").style.display="none";
  q("vaultId").value=""; q("vaultPass").value=""; q("vaultNote").value="";
}
function paintVault(d){
  VAULT=(d.entries||[]);
  VAULT_SHOWN={};
  var body=q("vaultBody");
  if(!VAULT.length){
    body.innerHTML='<tr><td colspan="4" style="color:var(--faint)">本子还是空的 —— '+
      '往里加一条之后，所有人添加设备时就必须填对原始密码了。</td></tr>';
  } else {
    // Password cells start masked and are filled in one at a time, on request:
    // the whole point of the book is that somebody can read one back, and no
    // point in putting them all on screen by default.
    body.innerHTML=VAULT.map(function(e,i){
      return '<tr>'+
        '<td class="mono">'+esc(e.id)+'</td>'+
        '<td class="mono" id="vaultPw'+i+'">'+MASK+'</td>'+
        '<td>'+esc(e.note||"")+'</td>'+
        '<td class="acts">'+
          '<button class="small" data-vact="show" data-i="'+i+'">显示</button>'+
          '<button class="small" data-vact="edit" data-i="'+i+'">编辑</button>'+
          '<button class="small danger" data-vact="del" data-i="'+i+'">删除</button>'+
        '</td></tr>';
    }).join("");
  }
  q("vaultFoot").textContent="文件："+(d.file||"?")+"　共 "+VAULT.length+" 条"+
    (VAULT.length ? "　已启用校验：添加设备必须填对序列号和原始密码"
                  : "　本子为空，暂时不校验")+
    (d.load_error ? "　注意："+d.load_error : "");
}
function loadVault(){
  return api("/api/vault").then(paintVault)
    .catch(function(e){ vaultSay("err","读取密码本失败："+e.message); });
}
function openVault(){
  vaultSay("","");
  vaultEditStop();
  q("vaultOverlay").classList.add("show");
  loadVault();
  setTimeout(function(){ q("vaultId").focus(); },30);
}
function closeVault(){
  q("vaultOverlay").classList.remove("show");
  VAULT_SHOWN={};
}
function vaultPost(action,extra){
  var b={action:action};
  for(var k in extra){ if(extra.hasOwnProperty(k)){ b[k]=extra[k]; } }
  return post("/api/vault",b).then(function(r){
    paintVault(r);
    vaultSay("ok",r.detail||"已保存");
    vaultEditStop();
    // An add or a remove can switch the check on or off, and the add-device
    // dialog has to follow at once. Its own failures are none of this dialog's
    // business, so they are left to loadDevices() to report.
    loadDevices();
    return r;
  }).catch(function(e){ vaultSay("err",e.message); });
}

q("vaultBtn").onclick=openVault;
q("vaultClose").onclick=closeVault;
q("vaultOverlay").onclick=function(e){ if(e.target===q("vaultOverlay")) closeVault(); };
document.addEventListener("keydown",function(e){
  if(e.key==="Escape" && q("vaultOverlay").classList.contains("show")) closeVault();
});
q("vaultEditCancel").onclick=function(){ vaultEditStop(); vaultSay("",""); };
q("vaultReload").onclick=function(){ vaultSay("",""); vaultPost("reload",{}); };
q("vaultSave").onclick=function(){
  var id=q("vaultId").value.trim(), pass=q("vaultPass").value;
  var note=q("vaultNote").value.trim();
  vaultSay("","");
  if(!id){ vaultSay("err","请填序列号"); return; }
  if(VAULT_EDITING){
    // Empty password = leave it alone, which is what makes "fix the note" a
    // one-field edit instead of a chance to blank a hardware password.
    vaultPost("set",{id:id,password:pass,note:note});
    return;
  }
  if(!pass){ vaultSay("err","请填这台设备的原始密码"); return; }
  vaultPost("add",{id:id,password:pass,note:note});
};
q("vaultBody").onclick=function(ev){
  var b=(ev.target && ev.target.closest) ? ev.target.closest("button[data-vact]") : null;
  if(!b){ return; }
  var i=parseInt(b.getAttribute("data-i"),10), e=VAULT[i];
  var act=b.getAttribute("data-vact");
  if(!e){ return; }
  if(act==="show"){
    var cell=q("vaultPw"+i);
    if(VAULT_SHOWN[e.id]){
      cell.textContent=MASK; delete VAULT_SHOWN[e.id]; b.textContent="显示";
    } else {
      cell.textContent=e.password||"（空）"; VAULT_SHOWN[e.id]=1; b.textContent="隐藏";
    }
    return;
  }
  if(act==="edit"){
    VAULT_EDITING=true;
    q("vaultId").value=e.id;
    q("vaultPass").value=""; q("vaultNote").value=e.note||"";
    q("vaultSave").textContent="保存修改";
    q("vaultEditCancel").style.display="inline-block";
    vaultSay("warn","正在改 "+e.id+"：密码留空就只改备注。");
    q("vaultPass").focus();
    return;
  }
  if(act==="del"){
    if(!confirm("从密码本里删掉 "+e.id+"？"+NL+NL+"删掉之后普通用户就不能再添加这个序列号了；"+
                "已经加进清单的设备不受影响。")) return;
    vaultPost("remove",{id:e.id,confirm:1});
  }
};

// ---------------------------------------------------------------- account
// Whoever is signed in owns the device list they are looking at, so the only
// things worth editing here are the login itself: the password and the email.
var ME={name:"",email:"",role:""};
function paintWho(){
  var line=q("whoLine");
  if(line) line.textContent=ME.name
    ? ("用户："+ME.name+(ME.role==="admin"?"（管理员）":""))
    : "";
}
function openAccount(){
  msg(q("acctMsg"),"","");
  api("/api/auth/me").then(function(p){
    ME=p;
    q("acctName").value=p.name||""; q("acctEmail").value=p.email||"";
    q("acctOld").value=""; q("acctNew").value=""; q("acctNew2").value="";
    q("acctSave").disabled=!!READONLY;
    if(READONLY) msg(q("acctMsg"),"warn","只读模式下只能查看，不能修改。");
    q("acctOverlay").classList.add("show");
    setTimeout(function(){ q("acctEmail").focus(); },30);
  }).catch(function(e){ alert("读取账户失败："+e.message); });
}
function closeAccount(){ q("acctOverlay").classList.remove("show"); }

q("accountBtn").onclick=openAccount;
q("acctCancel").onclick=closeAccount;
q("acctOverlay").onclick=function(e){ if(e.target===q("acctOverlay")) closeAccount(); };
document.addEventListener("keydown",function(e){
  if(e.key==="Escape" && q("acctOverlay").classList.contains("show")) closeAccount();
});

q("acctSave").onclick=function(){
  msg(q("acctMsg"),"","");
  var nw=q("acctNew").value, old=q("acctOld").value, email=q("acctEmail").value.trim();
  if(nw){
    if(nw!==q("acctNew2").value){ msg(q("acctMsg"),"err","两次输入的新密码不一样"); return; }
    if(!old){ msg(q("acctMsg"),"err","改密码要先填旧密码"); return; }
    if(nw.length<8){ msg(q("acctMsg"),"err","新密码至少 8 位"); return; }
  }
  if(!nw && email===(ME.email||"")){ msg(q("acctMsg"),"warn","没有要改的东西"); return; }
  var b={email:email};
  if(nw){ b.old_password=old; b.new_password=nw; }
  q("acctSave").disabled=true;
  post("/api/auth/account",b).then(function(r){
    ME=(r&&r.profile)||ME;
    paintWho();
    closeAccount();
    alert("已保存。");
  }).catch(function(e){
    msg(q("acctMsg"),"err",e.message);
  }).then(function(){ q("acctSave").disabled=!!READONLY; });
};

q("logoutBtn").onclick=function(){
  post("/api/auth/logout",{}).then(function(){ location.href="/"; })
    .catch(function(){ location.href="/"; });
};

// ---------------------------------------------------------------- settings
// The broker endpoint gets its own dialog because it is GLOBAL: one broker
// serves every plug in the list, so it cannot live inside a per-device card.
// Two things about the password are deliberate and easy to get wrong:
//   * it is never sent back by the server, so the field opens empty;
//   * an empty field therefore means "keep the saved one" -- clearing takes a
//     tick. Otherwise opening the dialog and pressing save would log every
//     device out of the broker.
function openSettings(){
  msg(q("setMsg"),"","");
  api("/api/settings").then(function(s){
    q("setHost").value=s.host||"";
    q("setPort").value=s.port;
    q("setUser").value=s.user||"";
    q("setPass").value="";
    q("setTls").checked=!!s.tls;
    q("setClearPass").checked=false;
    q("setTmo").value=s.timeout;
    q("setListen").textContent=(s.listen_host||"?")+":"+(s.listen_port||"?");
    // Nobody can type "0.0.0.0" into a phone: that is the WILDCARD, meaning "every
    // address this machine has". List the addresses somebody can actually reach.
    var urls=s.listen_urls||[];
    q("setUrls").textContent=urls.length?urls.join("　"):"（没有找到局域网地址）";
    q("setFile").textContent=(s.file||"?")+
      (s.saved?"（已保存，正生效）":"（还没保存，用的是启动参数）");
    var st=s.startup||{};
    q("setStartup").textContent=(st.host||"?")+":"+(st.port||"?")+(st.tls?" TLS":"")+
      "　用户 "+(st.user||"(空)")+"　超时 "+(st.timeout==null?"?":st.timeout)+"s"+
      (s.links!=null?"　已连 "+s.links+" 台":"");
    q("setSave").disabled=!!READONLY;
    q("setTest").disabled=!!READONLY;
    q("setReset").disabled=!!READONLY;
    if(READONLY) msg(q("setMsg"),"warn","只读模式下只能查看，不能修改。");
    else if(s.error) msg(q("setMsg"),"err",s.error);
    q("setOverlay").classList.add("show");
    setTimeout(function(){ q("setHost").focus(); },30);
  }).catch(function(e){ alert("读取设置失败："+e.message); });
}
function closeSettings(){ q("setOverlay").classList.remove("show"); }

function settingsBody(){
  var b={host:q("setHost").value.trim(), port:parseInt(q("setPort").value,10),
         tls:!!q("setTls").checked, user:q("setUser").value.trim(),
         timeout:parseFloat(q("setTmo").value)};
  var pw=q("setPass").value;
  if(pw) b.password=pw;
  if(q("setClearPass").checked) b.clear_password=1;
  return b;
}

q("settingsBtn").onclick=openSettings;
q("setCancel").onclick=closeSettings;
q("setOverlay").onclick=function(e){ if(e.target===q("setOverlay")) closeSettings(); };
document.addEventListener("keydown",function(e){
  if(e.key==="Escape" && q("setOverlay").classList.contains("show")) closeSettings();
});

q("setTest").onclick=function(){
  msg(q("setMsg"),"","");
  q("setTest").disabled=true;
  // Tests what is TYPED, not what is saved: the point is to find out before
  // committing. A wrong port says "no CONNACK"; a wrong password says
  // "broker refused (rc=4/5)" -- different fixes, so the text is kept verbatim.
  api("/api/settings/test",{method:"POST",body:settingsBody()})
    .then(function(r){ msg(q("setMsg"), r.ok?"ok":"err", r.ok?r.detail:r.error); })
    .catch(function(e){ msg(q("setMsg"),"err",e.message); })
    .then(function(){ q("setTest").disabled=!!READONLY; });
};

q("setSave").onclick=function(){
  msg(q("setMsg"),"","");
  q("setSave").disabled=true;
  api("/api/settings",{method:"POST",body:settingsBody()}).then(function(r){
    msg(q("setMsg"),"ok","已保存并生效"+
      (r.closed?("；断开 "+r.closed+" 条旧连接，下次读取用新设置重连"):""));
    q("setFile").textContent=((r.settings&&r.settings.file)||"?")+"（已保存，正生效）";
    q("setPass").value=""; q("setClearPass").checked=false;
    return loadDevices().then(function(){ if(current) pokeState(); });
  }).catch(function(e){ msg(q("setMsg"),"err",e.message); })
    .then(function(){ q("setSave").disabled=!!READONLY; });
};

q("setReset").onclick=function(){
  if(!confirm("恢复成启动时的参数？"+NL+NL+"会删掉设置文件，回到命令行（或默认值）给的那一套。")) return;
  msg(q("setMsg"),"","");
  api("/api/settings",{method:"POST",body:{reset:1}}).then(function(r){
    var s=r.settings||{};
    q("setHost").value=s.host||""; q("setPort").value=s.port;
    q("setUser").value=s.user||""; q("setPass").value="";
    q("setTls").checked=!!s.tls; q("setClearPass").checked=false;
    q("setTmo").value=s.timeout;
    q("setFile").textContent=(s.file||"?")+"（还没保存，用的是启动参数）";
    msg(q("setMsg"),"ok","已恢复启动值"+(r.closed?("，断开 "+r.closed+" 条旧连接"):""));
    return loadDevices().then(function(){ if(current) pokeState(); });
  }).catch(function(e){ msg(q("setMsg"),"err",e.message); });
};

// ---------------------------------------------------------------- boot
var LOGGED_IN=%(logged_in)s;
if(LOGGED_IN) api("/api/auth/me").then(function(p){ ME=p; paintWho(); })
  .catch(function(){ /* the next poll retries; the page stays usable */ });

// ------------------------------------------------------------- the two beats
// Both beats re-schedule THEMSELVES instead of using setInterval, and neither
// asks for another read until the previous one has come back. That is not
// style. setInterval fires whether or not the last request was answered, so at
// a beat equal to the read budget one slow read stacked a second request on an
// unanswered first, then a third -- and the queue that grew was the panel's own
// doing, arriving at the user as "sometimes it reads, sometimes it errors". A
// beat that waits for its own answer cannot build that queue.
var LIST_MS=%(sweep_ms)s, STATE_MS=%(refresh_ms)s;
var BURST_MS=%(burst_ms)s, BURST_FOR=%(burst_seconds)s*1000;
var FAIL_MS=%(fail_ms)s, FAIL_MAX_MS=%(fail_max_ms)s;
// The energy card is a SEPARATE beat with its own back-off, and deliberately a
// slower one than --refresh: a faster beat would not make the number fresher,
// it would only queue more reads behind the relay read on the same plug. The
// card is still live (it is a load meter, not a log), and --energy moves it.
var EN_MS=%(energy_ms)s, EN_FAIL_MS=%(energy_fail_ms)s, EN_FAIL_MAX_MS=%(energy_fail_max_ms)s;
var stateBusy=false, stateWait=STATE_MS, burstUntil=0;
var stateTimer=null, listBusy=false, listTimer=null;
var enBusy=false, enTimer=null;
var beatHint=q("beatHint");
if(beatHint) beatHint.textContent=Math.round(STATE_MS/1000);
var enHintSec=q("enHintSec");
if(enHintSec) enHintSec.textContent=Math.round(EN_MS/1000);

// A write just happened, so the state is about to change: watch closely for a
// few seconds. Armed centrally from api() so no button can forget to do it.
function armBurst(){ burstUntil=Date.now()+BURST_FOR; }

// The ONE way anything else asks for a state read: not "read now" but "read
// next". Every other caller used to call readState() straight, which put a
// second request in the air next to the beat's -- harmless once, but on a slow
// broker it is the same pile-up by another route. Going through the beat means
// a pending read is joined instead of duplicated.
function pokeState(){
  if(stateTimer){ clearTimeout(stateTimer); }
  stateTimer=setTimeout(stateBeat, 60);
}

function stateBeat(){
  if(document.hidden || !current){ stateTimer=setTimeout(stateBeat, 2000); return; }
  if(stateBusy){ stateTimer=setTimeout(stateBeat, 400); return; }  // never stack
  stateBusy=true;
  readState().then(function(r){
    stateBusy=false;
    if(r && r.stale){
      // That answer was about the plug the user just left, so it neither paints
      // nor decides this beat: read the plug on screen now, without delay.
      stateTimer=setTimeout(stateBeat, 60);
      return;
    }
    // A miss backs off rather than being retried harder: a plug having a bad
    // minute should be asked LESS, not more. Any good answer resets the beat.
    stateWait = (r && r.state)
      ? (Date.now()<burstUntil ? BURST_MS : STATE_MS)
      : Math.min(FAIL_MAX_MS, Math.max(FAIL_MS, stateWait*2));
    stateTimer=setTimeout(stateBeat, stateWait);
  });
}

// The third beat, same discipline: it re-arms itself and never asks again
// before its own answer is in. It is NOT poked by the buttons -- pressing ON
// does not change the wattage, the LOAD does -- so it keeps its own rhythm and
// its own back-off. A plug with no meter answers instantly ("no sensor") and
// would otherwise be asked every 5 s forever; instead the NO-SENSOR case is a
// success that parks the beat at the ceiling, so a fleet of meterless plugs
// costs almost nothing. Opening a device resets both, so the card is live
// again the moment it is looked at.
function enNextDelay(r){
  if(!r) return EN_FAIL_MS;
  if(r.stale) return 60;
  if(r.no_sensor) return EN_FAIL_MAX_MS;      // nothing to meter: stop asking
  if(r.ok) return EN_MS;
  return Math.min(EN_FAIL_MAX_MS, Math.max(EN_FAIL_MS, (enWait||EN_FAIL_MS)*2));
}
function enBeat(){
  if(document.hidden || !current){ enTimer=setTimeout(enBeat, 2000); return; }
  if(enBusy){ enTimer=setTimeout(enBeat, 400); return; }
  enBusy=true;
  loadEnergy().then(function(r){
    enBusy=false;
    if(r && r.stale){ enTimer=setTimeout(enBeat, 60); return; }
    enWait=enNextDelay(r);
    enTimer=setTimeout(enBeat, enWait);
  });
}
function pokeEnergy(){
  // Switching device is the one moment this card must be restarted rather
  // than waited out: its back-off may be minutes wide and belongs to the plug
  // the user just left.
  enWait=0;
  if(enTimer){ clearTimeout(enTimer); }
  enTimer=setTimeout(enBeat, 60);
}

// The list route is answered from the panel's sweep cache -- no device I/O --
// so it needs the one-at-a-time guard, not the back-off.
function listBeat(){
  if(document.hidden || listBusy){ listTimer=setTimeout(listBeat, 3000); return; }
  listBusy=true;
  loadDevices().then(function(){},function(){}).then(function(){
    listBusy=false;
    listTimer=setTimeout(listBeat, LIST_MS);
  });
}

loadDevices();
setInterval(function(){ if(!document.hidden) renderClock(); }, 1000);
setInterval(function(){ if(!document.hidden) renderCycle(); }, 1000);
// The energy card keeps its own age line honest without re-asking the plug:
// the timestamp is already on screen, only "how long ago" needs redrawing.
setInterval(function(){ if(!document.hidden) renderEnergy(); }, 1000);
stateTimer=setTimeout(stateBeat, 400);
enTimer=setTimeout(enBeat, 900);
listTimer=setTimeout(listBeat, LIST_MS);
// The countdown ticks locally off the device's own number; polling is what keeps
// it honest when the plug reboots or somebody stops the loop elsewhere. It is
// NOT a fixed 5 s beat any more: every cycle read sits in the same per-device
// queue as the relay state, so this card asks only as often as it needs to --
// often while a loop is actually running, barely at all when nothing uses it.
function cycNextDelay(){
  var c=cycLast;
  if(!c || !c.ok) return 15000;   // nothing known yet, or the last read failed
  if(c.running) return 10000;     // counting down: keep the number honest
  if(c.armed) return 30000;       // a rule is in place but idle
  return 60000;                   // nothing configured on this plug
}
var cycTimer=null, cycBusy=false;
function cycBeat(){
  if(document.hidden || !current || cycBusy){ cycTimer=setTimeout(cycBeat,5000); return; }
  cycBusy=true;
  loadCycle().then(function(){},function(){}).then(function(){
    cycBusy=false;
    cycTimer=setTimeout(cycBeat, cycNextDelay());
  });
}
cycTimer=setTimeout(cycBeat, 3000);
window.addEventListener("focus",function(){ loadDevices(); });
</script>
</body>
</html>
'''

_LOGIN_PAGE = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>登录 · Tasmota 多设备控制台</title>
<style>
:root {
  --bg:#14161a; --panel:#1b1e24; --panel2:#22262e; --line:#2e333d;
  --fg:#e8eaed; --dim:#9aa3b0; --faint:#6b7480;
  --warn:#d8a13a; --err:#d0595c; --accent:#5b8dd6;
}
* { box-sizing:border-box; }
body { margin:0; min-height:100vh; display:flex; align-items:center;
  justify-content:center; padding:24px; background:var(--bg); color:var(--fg);
  font:14px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif; }
.card { width:100%%; max-width:380px; background:var(--panel);
  border:1px solid var(--line); border-radius:14px; padding:24px 24px 20px; }
h1 { margin:0 0 4px; font-size:17px; font-weight:500; }
.sub { color:var(--faint); font-size:12px; margin-bottom:16px; }
label { display:block; font-size:13px; color:var(--dim); margin:12px 0 5px; }
input { width:100%%; font:inherit; background:#171a20; color:var(--fg);
  border:1px solid var(--line); border-radius:8px; padding:8px 10px; }
input:focus { outline:none; border-color:var(--accent); }
button { font:inherit; cursor:pointer; border-radius:8px; border:1px solid var(--line);
  background:var(--panel2); color:var(--fg); padding:9px 14px; }
button:hover:not(:disabled) { border-color:#3d4450; background:#282d36; }
button:disabled { opacity:.45; cursor:not-allowed; }
button.primary { background:#2b4a78; border-color:#3a5f95; }
button.link { background:none; border:none; color:var(--accent); padding:6px 4px; }
.btns { display:flex; gap:9px; align-items:center; margin-top:18px; }
.btns button.primary { flex:1; }
.msg { margin-top:11px; font-size:13px; min-height:19px; }
.msg.err { color:#eaa4a6; } .msg.ok { color:#8fd0a5; } .msg.warn { color:var(--warn); }
.hint { color:var(--faint); font-size:12px; margin-top:7px; }
/* phones: top-align the form instead of centring it in a tall viewport */
@media (max-width:420px) {
  body { padding:14px; align-items:flex-start; padding-top:7vh; }
  .card { padding:20px 18px 17px; }
  input { padding:10px 11px; font-size:16px; }
  button { padding:11px 15px; }
}
</style>
</head>
<body>
<div class="card">
  <h1 id="title">登录</h1>
  <div class="sub">Tasmota 多设备控制台 v%(version)s</div>
  <div class="msg warn" id="note">%(note)s</div>

  <label for="lgUser">用户名</label>
  <input id="lgUser" autocomplete="username" autocapitalize="off" spellcheck="false">
  <div id="extraEmail" style="display:none">
    <label for="lgEmail">邮箱</label>
    <input id="lgEmail" type="email" autocomplete="email" spellcheck="false">
  </div>
  <label for="lgPass">密码</label>
  <input id="lgPass" type="password" autocomplete="current-password">
  <div id="extraPass2" style="display:none">
    <label for="lgPass2">再输一次密码</label>
    <input id="lgPass2" type="password" autocomplete="new-password">
    <div class="hint">密码至少 8 位。用户名限字母开头、3-32 位字母/数字/._-。</div>
  </div>

  <div class="btns">
    <button id="lgGo" class="primary">登录</button>
    <button id="lgSwap" class="link">注册新账户</button>
  </div>
  <div class="msg" id="lgMsg"></div>
</div>
<script>
var REGISTER=%(can_register)s;
var FIRST=%(first)s;
var MODE="login";
function q(id){ return document.getElementById(id); }
function msg(text,kind){ q("lgMsg").className="msg"+(kind?" "+kind:""); q("lgMsg").textContent=text||""; }
function setMode(mode){
  MODE=mode;
  var reg = mode==="register";
  q("title").textContent = reg?"注册新账户":"登录";
  // "block", never "": clearing an inline style hands the element back to the
  // stylesheet, and a stylesheet rule like display:none then wins again. These
  // two start hidden through their own inline style, so that stays the single
  // source of truth -- visible when the dialog is opened by JS, not before.
  q("extraEmail").style.display = reg?"block":"none";
  q("extraPass2").style.display = reg?"block":"none";
  q("lgPass").autocomplete = reg?"new-password":"current-password";
  q("lgGo").textContent = reg?"注册并登录":"登录";
  q("lgSwap").textContent = reg?"已经有账户了，去登录":"注册新账户";
  msg("","");
  q("lgUser").focus();
}
q("lgSwap").onclick=function(){ setMode(MODE==="login"?"register":"login"); };

function send(path,body){
  return fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify(body)})
    .then(function(r){ return r.json().then(function(j){
      if(!r.ok) throw new Error(j.error||("HTTP "+r.status));
      return j; }); });
}
q("lgGo").onclick=function(){
  var user=q("lgUser").value.trim(), pass=q("lgPass").value;
  if(!user){ msg("请填用户名","err"); return; }
  if(!pass){ msg("请填密码","err"); return; }
  msg("正在…","");
  q("lgGo").disabled=true;
  var body={user:user,password:pass}, path="/api/auth/login";
  if(MODE==="register"){
    path="/api/auth/register";
    body.email=q("lgEmail").value.trim();
    // An empty confirmation is not the same mistake as a mismatched one, and
    // "they do not match" reads as nonsense when the confirm box is off screen.
    if(!q("lgPass2").value){
      q("lgGo").disabled=false; msg("请在「再输一次密码」里再填一遍","err"); return;
    }
    if(pass!==q("lgPass2").value){
      q("lgGo").disabled=false; msg("两次输入的密码不一样","err"); return;
    }
  }
  send(path,body).then(function(){
    // The server answers with the session cookie; reloading then serves the
    // panel itself, which refuses to render for anyone without one.
    location.href="/";
  }).catch(function(e){
    q("lgGo").disabled=false;
    msg(e.message,"err");
  });
};
["lgUser","lgPass","lgPass2","lgEmail"].forEach(function(id){
  var el=q(id);
  if(el) el.addEventListener("keydown",function(e){ if(e.key==="Enter") q("lgGo").click(); });
});
// Somebody has to go first: without an account there is nothing to sign in to,
// so the card opens on the registration side.
if(FIRST && REGISTER) setMode("register");
else q("lgUser").focus();
</script>
</body>
</html>
'''

# ------------------------------------------------------------------ bootstrap
def _clamp(value, low: float, high: float, fallback: float) -> float:
    """Keep a user-supplied interval inside sane bounds.

    Clamped, not rejected: `--refresh 0` almost certainly means "as fast as is
    reasonable", and refusing to start over it would be unhelpful. The startup
    banner reports the value actually in force, so the correction is visible.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    if number != number:                            # NaN
        return fallback
    return max(low, min(high, number))


def parse_hub_args(argv: list[str] | None = None):
    """The engine's flags, plus the panel's own -- and the two must not collide.

    build_parser() owns every MQTT flag: mqtt-host, mqtt-port, user, password,
    tls. The generated file renames the engine's host and port flags at build
    time, exactly as the single-device panel does. The panel then adds its own
    listen socket under listen_host/listen_port -- separate dests, so neither set
    can silently overwrite the other.
    """
    parser = build_parser()
    parser.description = ("Serve a browser control panel that manages MANY Tasmota "
                          "plugs, listed in a small JSON file beside this script.")
    # The engine's parser runs ONE action and exits, so its `action` positional is
    # required and its `choices` reject anything else. The panel drives actions
    # over HTTP, so both have to be relaxed -- otherwise every launch dies with
    # "the following arguments are required: action" before the socket opens.
    for arg in parser._actions:                     # noqa: SLF001 - argparse has
        if arg.dest == "action":                    # no public hook for this
            arg.required = False
            arg.nargs = "?"
            arg.default = None
            arg.choices = None
            arg.metavar = "{on,off,toggle,status,pulse,pulseoff,diag,timers,timer,time}"
            arg.help = ("unused here -- the panel drives actions over HTTP; the "
                        "flag exists because the engine's parser supplies it")
            break
    else:
        raise SystemExit("build_parser() no longer has an `action` argument -- the "
                         "hub's parser relaxation needs revisiting")
    parser.add_argument("--port", dest="listen_port", metavar="PORT", type=int,
                        default=HUB_PORT,
                        help="port the panel itself listens on (default %d)" % HUB_PORT)
    parser.add_argument("--listen", dest="listen_host", metavar="ADDR",
                        default="0.0.0.0",
                        help="address to listen on; 0.0.0.0 = every interface, so "
                             "the LAN can reach the panel (the default), "
                             "127.0.0.1 = this machine only")
    parser.add_argument("--localhost", dest="localhost_only", action="store_true",
                        help="shorthand for --listen 127.0.0.1: nobody off this "
                             "machine can reach the panel")
    parser.add_argument("--list", dest="list_path", metavar="FILE", default=None,
                        help="SHARED device list JSON, used only with --no-auth "
                             "(default: %s next to this script)" % HUB_LIST_NAME)
    parser.add_argument("--vault", dest="vault_path", metavar="FILE", default=None,
                        help="the administrator's password book: serial -> the "
                             "device's ORIGINAL password. While it has entries, "
                             "adding a serial requires a matching pair from it "
                             "(default: %s next to this script)" % HUB_VAULT_NAME)
    parser.add_argument("--settings", dest="settings_path", metavar="FILE",
                        default=None,
                        help="broker settings JSON, written by the page's settings dialog "
                             "(default: %s beside the device list)" % HUB_SETTINGS_NAME)
    parser.add_argument("--no-auth", dest="no_auth", action="store_true",
                        help="no login page: ONE shared device list for everybody "
                             "who can reach the panel (what you do not want on a "
                             "shared network)")
    parser.add_argument("--no-register", dest="no_register", action="store_true",
                        help="stop accepting new accounts; existing ones still "
                             "sign in (do this once everybody has one)")
    parser.add_argument("--users", dest="users_path", metavar="FILE", default=None,
                        help="account file with the password hashes (default: %s "
                             "next to this script)" % HUB_USERS_NAME)
    parser.add_argument("--cycle", dest="cycle_path", metavar="FILE", default=None,
                        help="where the remembered cycle SETTINGS are kept, used "
                             "only with --no-auth (default: %s beside the device "
                             "list). Accounts get one each, named <account>-cycle.json"
                             % HUB_CYCLE_NAME)
    parser.add_argument("--lists", dest="lists_dir", metavar="DIR", default=None,
                        help="where each account's device list is kept (default: "
                             "%s\\ next to this script)" % HUB_USERS_DIR)
    parser.add_argument("--max-devices", dest="max_devices", metavar="N", type=int,
                        default=HUB_MAX_DEVICES,
                        help="refuse to manage more than N devices (default %d); each "
                             "one holds an MQTT connection" % HUB_MAX_DEVICES)
    parser.add_argument("--refresh", dest="refresh_seconds", metavar="SECONDS",
                        type=float, default=HUB_REFRESH_MS / 1000.0,
                        help="how often the page re-reads the device you are looking "
                             "at (default %.0f s). This is the only setting that "
                             "touches the plug on a timer, so raise it if the broker "
                             "is slow or several tabs watch the same device. "
                             "%g..%g seconds"
                             % (HUB_REFRESH_MS / 1000.0, HUB_REFRESH_MIN_MS / 1000.0,
                                HUB_REFRESH_MAX_MS / 1000.0))
    parser.add_argument("--sweep", dest="sweep_seconds", metavar="SECONDS",
                        type=float, default=float(HUB_SWEEP_SECONDS),
                        help="how often the background thread re-reads EVERY device "
                             "in the list, to keep the list's badges honest "
                             "(default %d s); the device you are looking at is "
                             "polled by --refresh instead" % HUB_SWEEP_SECONDS)
    parser.add_argument("--energy", dest="energy_seconds", metavar="SECONDS",
                        type=float, default=HUB_ENERGY_MS / 1000.0,
                        help="how often the page re-reads the meter (power, voltage, "
                             "current, kWh) of the device you are looking at "
                             "(default %g s). Its own beat, separate from --refresh, "
                             "because a load reading moves on its own. Every read of "
                             "one plug shares one queue, so setting this below "
                             "--refresh only makes the relay state read slower. "
                             "%g..%g seconds"
                             % (HUB_ENERGY_MS / 1000.0, HUB_ENERGY_MIN_MS / 1000.0,
                                HUB_ENERGY_MAX_MS / 1000.0))
    parser.add_argument("--token", metavar="SECRET", default=None,
                        help="shared secret; the page must then be opened as ?token=...")
    parser.add_argument("--read-only", dest="read_only", action="store_true",
                        help="serve a view-only panel: every control is disabled")
    parser.add_argument("--open", dest="open_browser", action="store_true",
                        help="open the panel in the default browser once it is listening")
    parser.add_argument("--log-requests", dest="verbose2", action="store_true",
                        help="log every HTTP request the panel serves")
    args = parser.parse_args(argv)
    if getattr(args, "localhost_only", False):
        # Kept as a separate dest on purpose: two actions sharing one dest would
        # make the default depend on which was added first.
        args.listen_host = "127.0.0.1"
    # Resolve both poll rates here, once, so nothing downstream has to reinterpret
    # "--refresh 0.5" as milliseconds.
    args.refresh_ms = int(round(_clamp(getattr(args, "refresh_seconds", None),
                                       HUB_REFRESH_MIN_MS / 1000.0,
                                       HUB_REFRESH_MAX_MS / 1000.0,
                                       HUB_REFRESH_MS / 1000.0) * 1000.0))
    args.sweep_seconds = _clamp(getattr(args, "sweep_seconds", None),
                                HUB_SWEEP_MIN_SECONDS, HUB_SWEEP_MAX_SECONDS,
                                float(HUB_SWEEP_SECONDS))
    args.energy_seconds = _clamp(getattr(args, "energy_seconds", None),
                                 HUB_ENERGY_MIN_MS / 1000.0,
                                 HUB_ENERGY_MAX_MS / 1000.0,
                                 HUB_ENERGY_MS / 1000.0)
    return args


def serve(parsed) -> int:
    """Load the device list, open the panel, and serve until Ctrl-C."""
    args = parsed
    args.verbose = bool(getattr(args, "verbose", False) or getattr(args, "verbose2", False))

    here = _os.path.dirname(_os.path.abspath(__file__))
    list_path = args.list_path or _os.path.join(here, HUB_LIST_NAME)
    book = DeviceBook(list_path)
    if book.error:
        sys.stderr.write("WARNING: %s\n" % book.error)

    # The administrator's password book, deliberately NOT beside anybody's device
    # list: it describes the hardware (which serial was issued with which
    # original password), so it is one file for the whole panel.
    vault_path = getattr(args, "vault_path", None) \
        or _os.path.join(here, HUB_VAULT_NAME)
    vault = DeviceVault(vault_path)
    if vault.error:
        sys.stderr.write("WARNING: %s\n" % vault.error)
    HubHandler.vault = vault

    # The saved endpoint WINS over the flags: the file exists because somebody
    # typed it into the page, and a panel that silently ignored it would look
    # like a broken settings dialog. --settings moves the file; --list does not
    # move it, because the two are edited by different hands.
    settings_path = getattr(args, "settings_path", None) \
        or _os.path.join(_os.path.dirname(_os.path.abspath(list_path)) or here,
                         HUB_SETTINGS_NAME)
    settings = BrokerSettings(settings_path, args)
    if settings.error:
        sys.stderr.write("WARNING: %s\n" % settings.error)
    # A saved file outranks the flags, which is the right default for a panel
    # someone edits in the browser -- but it is silent from the outside, so say
    # which values are being overridden. Otherwise "I passed --mqtt-host and it
    # ignored me" looks like a broken flag rather than a saved setting.
    if settings.saved:
        beaten = [key for key in settings.FIELDS
                  if key != "password" and settings.values[key] != settings.startup[key]]
        if beaten:
            sys.stderr.write("NOTE: %s overrides the command line for %s. Use the "
                             "page's settings dialog, or delete the file.\n"
                             % (HUB_SETTINGS_NAME, ", ".join(beaten)))
    settings.apply_to(args)

    # ---- accounts, or one shared list --------------------------------------
    # With accounts ON there is no single list to load here: every account gets
    # its own file, created the moment somebody signs in for the first time.
    # The panel still needs one Fleet for the account-less mode (--no-auth), and
    # for the broker settings object that both modes share.
    HubHandler.token = args.token or None
    accounts = None
    # Where the remembered cycle CONFIGURATION lives: beside the device list in
    # the shared mode (one file, one panel), and per account when accounts are
    # on -- a remembered pump schedule belongs to whoever set it.
    cycle_path = getattr(args, "cycle_path", None) \
        or _os.path.join(_os.path.dirname(_os.path.abspath(list_path)) or here,
                         HUB_CYCLE_NAME)

    if getattr(args, "no_auth", False):
        book = DeviceBook(list_path)
        if book.error:
            sys.stderr.write("WARNING: %s\n" % book.error)
        memory = CycleMemory(cycle_path)
        if memory.error:
            sys.stderr.write("WARNING: %s\n" % memory.error)
        fleet = Fleet(args, book, settings, memory)
        HubHandler.fleet = fleet
        HubHandler.book = book
    else:
        users_path = getattr(args, "users_path", None) \
            or _os.path.join(here, HUB_USERS_NAME)
        lists_dir = getattr(args, "lists_dir", None) \
            or _os.path.join(here, HUB_USERS_DIR)
        try:
            _os.makedirs(lists_dir, exist_ok=True)
        except OSError as exc:
            sys.stderr.write("ERROR: cannot create %s -> %s\n" % (lists_dir, exc))
            return 1
        accounts = AccountHub(args, settings, users_path, lists_dir,
                              registration=not getattr(args, "no_register", False),
                              legacy_list=list_path)
        if accounts.store.error:
            sys.stderr.write("WARNING: %s\n" % accounts.store.error)
        accounts.start()
        HubHandler.accounts = accounts
        # A placeholder so a request that somehow arrives before binding still
        # fails loudly instead of saying "no devices".
        fleet = None

    try:
        httpd = ExclusiveThreadingHTTPServer((args.listen_host, args.listen_port),
                                             HubHandler)
    except OSError as exc:
        sys.stderr.write("ERROR: cannot listen on %s:%d -> %s\n"
                         % (args.listen_host, args.listen_port, exc))
        sys.stderr.write("       another copy of this panel already owns that port; "
                         "open it, or use --port 8766\n")
        sys.stderr.write("       find the owner: "
                         "netstat -ano | findstr :%d\n" % args.listen_port)
        if fleet is not None:
            fleet.close()
        elif accounts is not None:
            accounts.close()
        return 1

    httpd.read_only = getattr(args, "read_only", False)

    opener, network_urls = _listen_urls(args.listen_host, args.listen_port,
                                        getattr(args, "token", None))

    print("mqtt-py web panel%s"
          % ("" if accounts is None else " -- %s signed in out of %d account(s)"
             % (accounts.sessions.count(), accounts.store.count())))
    print("broker  : %s:%d%s" % (args.mqtt_host, args.mqtt_port,
                                 " (TLS)" if args.tls else ""))
    if accounts is None:
        print("list    : %s" % list_path)
        for ident in book.ids():
            print("          %s" % ident)
        print("memory  : %s (%d remembered)" % (cycle_path, len(memory.cycles)))
    else:
        print("accounts: %s (%d)" % (accounts.store.path, accounts.store.count()))
        print("lists   : %s\\<account>.json  (one per user)" % accounts.lists_dir)
        print("memory  : %s\\<account>-cycle.json" % accounts.lists_dir)
        if not accounts.store.count():
            print("          nobody yet -- open the page and register the first "
                  "account")
    print("settings: %s%s" % (settings_path,
                              " (saved, in use)" if settings.saved
                              else " (none yet -- using the flags above)"))
    print("vault   : %s (%d entr%s%s)" % (
        vault_path, vault.count(), "y" if vault.count() == 1 else "ies",
        " -- adding a device needs a matching serial + original password"
        if vault.enforcing() else " -- empty, so adds are NOT checked yet"))
    if accounts is not None:
        admins = accounts.admin_names()
        if not admins:
            print("          no administrator yet -- the first account to register gets it")
        else:
            print("          administrator: %s (only they may manage the book)"
                  % ", ".join(admins))
    if vault.error:
        print("          WARNING: %s" % vault.error)
    print("listen  : %s:%d" % (args.listen_host, args.listen_port))
    print("polling : the device you are watching, every %g s (--refresh); "
          "the whole list,\n          every %g s (--sweep)"
          % (args.refresh_ms / 1000.0,
             _clamp(getattr(args, "sweep_seconds", None), HUB_SWEEP_MIN_SECONDS,
                    HUB_SWEEP_MAX_SECONDS, float(HUB_SWEEP_SECONDS))))
    print("local   : %s" % opener)
    for network_url in network_urls:
        print("network : %s" % network_url)
    if args.read_only:
        print("mode    : READ ONLY -- the page refuses every command")
    if args.token:
        print("token   : required (it travels in clear text; see --help)")
    if network_urls:
        print("NOTE    : open to your whole network, so anyone reaching this port "
              "gets the\n          LOGIN page -- not the devices. Accounts are what "
              "they have to get past.")
    if accounts is not None and not getattr(args, "no_register", False) \
            and accounts.store.count():
        print("NOTE    : registration is OPEN (--no-register closes it). Anyone on "
              "the network\n          can create an account and their own list.")
    if args.open_browser:
        print("open    : %s" % opener)
    print("\nCtrl-C to stop.")

    if fleet is not None:
        fleet.start_sweeper()
    if args.open_browser:
        _threading.Timer(0.4, lambda: webbrowser.open(opener)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("\nstopping\n")
    finally:
        httpd.shutdown()
        if fleet is not None:
            fleet.close()      # close every MQTT link, or the process will not exit
        if accounts is not None:
            accounts.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    return serve(parse_hub_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())

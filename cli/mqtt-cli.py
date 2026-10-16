#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Drive a Tasmota plug over MQTT -- EVERYTHING is a command-line argument.

THIS FILE IS COMPLETE ON ITS OWN: it imports nothing from this project, so it can
be copied to another folder or another machine and still run.

    python mqtt-cli.py on
    python mqtt-cli.py off --device A1B2C3
    python mqtt-cli.py status --json
    python mqtt-cli.py pulse --seconds 30
    python mqtt-cli.py timer 3 --time 08:00 --days weekdays --action on --enable

NOTHING IS READ FROM THIS FILE'S NAME. Unlike the mqtt-<device>-<action>.py
shortcuts, this file never looks at what it is called, so you can rename it,
copy it, or wire it into a batch file and it behaves exactly the same. The device
comes from --device, the action is the first positional argument.

THE ACTION IS REQUIRED and is one of these ten:

    on        turn the relay on
    off       turn the relay off
    toggle    flip the relay
    status    read the current state
    pulse     on for --seconds, then off again       e.g. --seconds 30
    pulseoff  off for --seconds, then on again       e.g. --seconds 120
    timer     read or write ONE timer slot           needs a slot, see below
    timers    list all 16 slots, or arm/disarm them all
    time      inspect the device clock and time zone
    diag      report the device hardware

Run `python mqtt-cli.py --help` for the full list of flags; the common ones are:

    --device NAME      which plug: 6FCE2C, DVES_6FCE2C, tasmota_6FCE2C,
                       or any custom topic (also: -d, --chip-id, --topic)
    --seconds N        how long pulse/pulseoff stay in the other state
    --json             one line of machine-readable output
    -v, --verbose      print every MQTT message on stderr
    --host --port --user --password     connection details
    --timeout N        seconds to wait for the device

TIMERS -- the slot (1..16) is the first argument that follows the action:

    python mqtt-cli.py timer 3 --time 08:00 --days weekdays --action on --enable
    python mqtt-cli.py timer 3 --time 18:30 --days Mon,Wed,Fri --action off --enable
    python mqtt-cli.py timer 3 --mode sunset --time -0:30 --action on --enable
    python mqtt-cli.py timer 3 --clear              empty the slot again
    python mqtt-cli.py timers                       list all 16 slots
    python mqtt-cli.py timers --enable-all          arm every slot
    python mqtt-cli.py time --set-tz +8:00          timer times are DEVICE local

A timer fires only when the global Timer switch AND the slot's own Enable are both
on, so remember `python mqtt-cli.py timers --enable-all`.

Exit codes: 0 ok / 1 error / 2 timeout / 3 missing dependency.
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
DEF_USER = os.getenv("MQTT_USER", "mqtt")
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


def _hint_prefix() -> str | None:
    """What to put in front of an action when telling the user what to run.

    None (the default, and what every shortcut keeps) means "name my neighbour":
    the hint becomes mqtt-6FCE2C-timers.py, which is the file to double-click.
    Set to "python mqtt-cli.py" by the argument-driven build, where no per-action
    file exists and the honest hint is `python mqtt-cli.py timers --enable-all`.

    Deliberately settable rather than baked in: the same engine body is spliced
    into both artefacts, so the difference has to be decided at run time.
    """
    return _HINT_PREFIX


_HINT_PREFIX: str | None = None


def shortcut_name(device: str, action: str) -> str:
    """The file name a shortcut script would have for this device and action.

    Only used to make hints point at a runnable file rather than at a bare
    action: "run mqtt-6FCE2C-timers.py --enable-all" tells the user what to type.

    In the argument-driven build (cli\\mqtt-cli.py) there is no per-action file to
    point at, so the hint switches to "mqtt-cli.py <action>". _hint_prefix() is
    set by the generator's wrapper; the shortcuts never touch it, so their hints
    keep naming their own neighbours.
    """
    if _hint_prefix() is not None:
        return "%s %s" % (_hint_prefix(), action)
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
        """Publish a command and return every reply it produces.

        Stops early once the device has gone quiet for `quiet` seconds, so a
        single-response command does not cost a full `--timeout` wait.
        """
        self.reset_state()
        self.publish(command, payload)
        deadline = time.time() + (timeout or self.timeout)
        last_seen = time.time()
        count = 0
        with self._cv:
            while time.time() < deadline:
                if len(self.replies) > count:
                    count = len(self.replies)
                    last_seen = time.time()
                elif count and time.time() - last_seen >= quiet:
                    break
                self._cv.wait(0.15)
        return list(self.replies)

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
            return self._fail("timers",
                              self._offline_note() or "no reply to `Timers`")
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
            return self._fail("time",
                              self._offline_note() or "no reply to `Status 7`")
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
            if self.online is False:
                # settle() has already given the retained LWT its moment, so this
                # is not a guess: nothing is subscribed to answer `Status 0`, and
                # publishing into an empty room buys nothing but a longer wait.
                self._report("status", None, self._offline_note(), ok=False)
                return 2
            state = self.query_state(self._timeout_for(action))
            if state is None:
                note = (self._error_note() or self._offline_note()
                        or "timeout: no reply to `Status 0`")
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
            note = (self._error_note() or self._offline_note()
                    or "timeout: no reply from the device")
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

        if self.online is False:
            # Not subscribed at the broker means an explicit `Status 0` poll
            # cannot reach the plug any better than the command just did. Report
            # the cause the broker already handed us rather than spending a
            # second wait to learn the same thing.
            return None, None, None

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
        if self.online is False:
            # Everything below asks the device questions, and there is nobody
            # there to answer them. Say why once, and stop -- walking the rest of
            # the diagnostics against a plug that is off the air produces a page
            # of question marks that look like findings.
            print("note       : %s" % self._offline_note())
            return 2

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

    def _offline_note(self) -> str | None:
        """Why nothing came back, when the broker has already told us.

        `tele/<topic>/LWT` is retained, so the plug's own last will reaches us
        the moment we subscribe -- `settle()` gives it that moment. When it
        reads Offline the plug is not on the broker at all: the command is
        published into an empty room and no answer can arrive, however long we
        wait. Reporting "timeout" there sends the reader hunting for a fault on
        this PC, which is the one place the fault is not.

        None means "no verdict": the device is online, or no LWT has arrived
        yet and the generic notes should stand.
        """
        if self.online is not False:
            return None
        return ("the plug is OFFLINE -- the broker's retained `LWT` for %s says "
                "Offline, so it is not connected to MQTT at all (no power, Wi-Fi "
                "dropped, or it has hung). Nothing answered because nothing was "
                "listening; this PC, the network and the password are all fine. "
                "Check the plug's power, then its own web page."
                % (self.tele + "/LWT"))


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

    p.add_argument("--host", default=DEF_HOST)
    p.add_argument("--port", type=int, default=DEF_PORT)
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
        p.set_defaults(port=8883)           # keep the port in sync with --tls
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

if __name__ == "__main__":
    _HINT_PREFIX = "python mqtt-cli.py"
    raise SystemExit(main(sys.argv[1:]))

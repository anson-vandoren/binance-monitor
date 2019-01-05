# MIT License
#
# Copyright (C) 2019 Anson VanDoren
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons
# to whom the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice (including the next paragraph) shall
# be included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
# PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE
# FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import os
from typing import List

import toml
from logbook import Logger

from binance_monitor.util import is_yes_response

USER_FOLDER = os.path.join(os.path.expanduser("~"), ".binance-monitor")
LOG_FILENAME = os.path.join(USER_FOLDER, "logs", "app.log")
API_KEY_FILENAME = os.path.join(USER_FOLDER, "config", "api_cred.json")
ACCOUNT_STORE_FOLDER = os.path.join(USER_FOLDER, "account_data")
PREFERENCES = os.path.join(USER_FOLDER, "preferences.toml")

log = Logger(__name__.split(".", 1)[-1])


def get_preferences() -> dict:
    try:
        return toml.load(PREFERENCES)
    except (IOError, toml.TomlDecodeError):
        log.info(f"{PREFERENCES} could not be opened or decoded for preferences")
        return {"title": "binance-monitor preferences"}


def save_preferences(prefs: dict) -> None:
    with open(PREFERENCES, "w") as toml_file:
        toml.dump(prefs, toml_file)


def get_blacklist():
    return get_preferences()["blacklist"] or None


def save_blacklist(new_blacklist: List):
    prefs = get_preferences()
    prefs.update({"blacklist": new_blacklist})
    save_preferences(prefs)


def try_update_blacklist(found_symbols: List):
    saved_blacklist = get_blacklist()
    if not saved_blacklist:
        return

    unblacklist = [symbol for symbol in found_symbols if symbol in saved_blacklist]

    if not unblacklist:
        return

    if is_yes_response(f"Unblacklist these symbols: {unblacklist}?"):
        remove_from_blacklist(unblacklist)


def remove_from_blacklist(symbols: List) -> None:
    if not isinstance(symbols, list):
        symbols = [symbols]

    symbols = set(symbols)
    current_blacklist = set(get_blacklist())

    if symbols and current_blacklist:
        new_blacklist = list(current_blacklist - symbols)
        save_blacklist(new_blacklist)

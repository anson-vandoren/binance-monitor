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
import json
import os
from typing import Any, Dict, List, Tuple

import toml
from logbook import Logger

from binance_monitor import util
from binance_monitor.util import is_yes_response

USER_FOLDER = os.path.join(os.path.expanduser("~"), ".binance-monitor")
LOG_FILENAME = os.path.join(USER_FOLDER, "logs", "app.log")
API_KEY_FILENAME = os.path.join(USER_FOLDER, "config", "api_cred.json")
ACCOUNT_STORE_FOLDER = os.path.join(USER_FOLDER, "account_data")
PREFERENCES = os.path.join(USER_FOLDER, "preferences.toml")

log = Logger(__name__.split(".", 1)[-1])


def _load_prefs() -> Dict[str, Any]:
    """Load user preferences from TOML and return as a dict

    :return: dict containing user preferences
    """

    try:
        return dict(toml.load(PREFERENCES))
    except (IOError, toml.TomlDecodeError):
        log.info(f"{PREFERENCES} could not be opened or decoded for preferences")
        return {"title": "binance-monitor preferences"}


def _save_prefs(prefs: dict) -> None:
    """Save a dictionary with user preferences to TOML

    Current preferences file will be overwritten with no checking

    :param prefs: dictionary containing new user preferences
    :return: None
    """
    with open(PREFERENCES, "w") as toml_file:
        toml.dump(prefs, toml_file)


def get_blacklist():
    return _load_prefs().get("blacklist", None)


def save_blacklist(new_blacklist: List):
    prefs = _load_prefs()
    prefs.update({"blacklist": new_blacklist})
    _save_prefs(prefs)


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

    current_blacklist = set(get_blacklist())

    if symbols and current_blacklist:
        new_blacklist = list(current_blacklist - set(symbols))
        save_blacklist(new_blacklist)


def _load_credentials() -> Tuple[str, str]:
    """Try to load API credentials from disk.

    :return: Tuple (key, secret) if loaded successfully, else None
    :raises: IOError if credentials cannot be loaded from disk
    """

    cache_file = API_KEY_FILENAME

    if not os.path.exists(cache_file):
        raise IOError(f"Could not load credentials from {cache_file}")

    with open(cache_file, "r") as cred_file:
        api_credentials = json.load(cred_file)
        log.info("API credentials loaded from disk")

    api_key = api_credentials.get("binance_key", None)
    api_secret = api_credentials.get("binance_secret", None)

    if not api_key or not api_secret:
        log.info("API credentials did not load properly from JSON file")
        raise IOError(f"{cache_file} did not contain valid credentials")

    return api_key, api_secret


def get_credentials() -> Tuple[str, str]:
    """Get Binance API key, secret

    Try to load from cache first. If not found, prompt user

    :return: A tuple with (API key, API secret)
    """
    try:
        return _load_credentials()
    except IOError:
        return _request_credentials()


def _request_credentials() -> Tuple[str, str]:
    """Prompt user to enter API key and secret. Prompt user to save credentials
    to disk for future use (unencrypted)

    :return: A tuple with (key, secret)
    """

    api_key = input("Enter Binance API key: ")
    api_secret = input("Enter Binance API secret: ")

    save_credentials = is_yes_response("\nSave credentials to disk (unencrypted)?")

    if save_credentials:
        cache_file = API_KEY_FILENAME
        cred_json = {"binance_key": api_key, "binance_secret": api_secret}

        with open(util.ensure_dir(cache_file), "w") as cred_file:
            json.dump(cred_json, cred_file)
            log.info(f"Stored credentials to {cache_file}")

    return api_key, api_secret

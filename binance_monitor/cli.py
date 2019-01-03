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

"""CLI argument parsing for Binance Monitor"""
import argparse
import json
import os
import sys
from typing import Dict, Optional

from binance.client import Client
from logbook import Logger, StreamHandler, TimedRotatingFileHandler

from binance_monitor import util

USER_FOLDER = os.path.join(os.path.expanduser("~"), ".binance-monitor")
LOG_FILENAME = os.path.join(USER_FOLDER, "logs", "app.log")
API_KEY_FILENAME = os.path.join(USER_FOLDER, "config", "api_cred.json")


def main():
    # Set up logging for the whole app
    util.ensure_dir(LOG_FILENAME)
    TimedRotatingFileHandler(LOG_FILENAME, bubble=True).push_application()
    StreamHandler(sys.stdout, level="NOTICE", bubble=True).push_application()
    log = Logger(__name__.split(".", 1)[-1])

    log.info("*" * 80)
    log.info("***" + "Starting CLI Parser for binance-monitor".center(74) + "***")
    log.info("*" * 80)

    parser = argparse.ArgumentParser(
        description="CLI for monitoring Binance account information"
    )
    parser.add_argument("--acct_info", help="Display account info", action='store_true')

    if not os.path.exists(API_KEY_FILENAME):
        log.info(f"API credentials not found at {API_KEY_FILENAME}")
        api_credentials = _save_credentials()
        if not api_credentials:
            print("Exiting...")
            return
    else:
        with open(API_KEY_FILENAME, "r") as cred_file:
            api_credentials = json.load(cred_file)
            log.info("API credentials loaded from disk")

    api_key = api_credentials.get("binance_key", None)
    api_secret = api_credentials.get("binance_secret", None)
    if api_key is None or api_secret is None:
        log.info("API credentials did not load properly from JSON file")
        print(
            f"{api_credentials} does not contain API key and secret. Please check the "
            "file and try again, or delete the file and re-enter your credentials "
            "from the CLI"
        )
        return

    args = parser.parse_args()
    if args.acct_info:
        print('Requested account info')
        client = Client(api_key, api_secret)
        info = client.get_account()
        print(info)


def _save_credentials() -> Optional[Dict]:
    # TODO: Consider encrypting API key/secret and requiring a password
    print("Previously saved credentials not found for Binance API. Enter them now?")
    print(f"(Credentials will be saved (unencrypted) to {API_KEY_FILENAME})")
    save_creds = input("[Y/n] ").upper()
    save_creds = len(save_creds) == 0 or save_creds[0] == "Y"
    if not save_creds:
        print("Cannot monitor account status without credentials!")
        print(
            "If you prefer to enter them manually, save them as JSON "
            "{binance_key: key, binance_secret: secret} at "
            f"{API_KEY_FILENAME} and then run the CLI again"
        )
        return None
    else:
        api_key = input("Enter Binance API key: ")
        api_secret = input("Enter Binance API secret: ")

        credentials = {"binance_key": api_key, "binance_secret": api_secret}
        util.ensure_dir(API_KEY_FILENAME)
        with open(API_KEY_FILENAME, "w") as cred_file:
            json.dump(credentials, cred_file)

        return credentials


if __name__ == "__main__":
    ENABLE_LOGGING = True
    main()

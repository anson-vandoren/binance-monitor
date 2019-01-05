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
import time
from typing import Optional, Tuple
from collections import Counter

from binance.client import Client
from logbook import Logger
from tqdm import tqdm

from binance_monitor import exchange, settings, store, util


class AccountMonitor(object):
    def __init__(self, credentials=None, name="default"):
        """Create a Binance account monitor that can access account details

        If neither an initialized client nor valid credentials are passed, an attempt
        will be made to load credentials from cache, or prompt user for them.

        :param credentials: Binance API key and secret (optional)
        """

        self.log = Logger(__name__.split(".", 1)[-1])

        if not credentials:
            try:
                credentials = self._load_credentials()
            except IOError:
                credentials = self._request_credentials()

        self.client = Client(*credentials)
        self.exchange_info = exchange.Exchange(self.client)
        self.name = name
        self.trades = store.TradeStore(name)

    def _load_credentials(self) -> Optional[Tuple[str, str]]:
        """Try to load API credentials from disk.

        :return: Tuple (key, secret) if loaded successfully, else None
        """
        cache_file = settings.API_KEY_FILENAME

        if not os.path.exists(cache_file):
            raise IOError(f"Could not load credentials from {cache_file}")

        with open(cache_file, "r") as cred_file:
            api_credentials = json.load(cred_file)
            self.log.info("API credentials loaded from disk")

        api_key = api_credentials.get("binance_key", None)
        api_secret = api_credentials.get("binance_secret", None)

        if not api_key or not api_secret:
            self.log.info("API credentials did not load properly from JSON file")
            raise IOError(f"{cache_file} did not contain valid credentials")

        return api_key, api_secret

    def _request_credentials(self) -> Tuple[str, str]:

        api_key = input("Enter Binance API key: ")
        api_secret = input("Enter Binance API secret: ")

        print("\nSave credentials to disk (unencrypted)?")
        save_creds = input("[Y/n] ").upper()
        save_creds = len(save_creds) == 0 or save_creds[0] == "Y"

        if save_creds:
            cache_file = settings.API_KEY_FILENAME
            cred_json = {"binance_key": api_key, "binance_secret": api_secret}
            util.ensure_dir(cache_file)
            with open(cache_file, "w") as cred_file:
                json.dump(cred_json, cred_file)
                self.log.info(f"Stored credentials to {cache_file}")

        return api_key, api_secret

    def update_trades(self, symbols):
        wait_time = 1.0 / self.exchange_info.max_request_freq(req_weight=5)
        self.log.info(f"Updating trades with wait_time={wait_time}")
        request_limit = 1000

        if isinstance(symbols, str):
            symbols = [symbols]

        trades = []
        last_called = 0
        for symbol in tqdm(symbols):
            tqdm.write(symbol)
            now = time.perf_counter()
            if now - last_called < wait_time:
                sleep_time = wait_time - (now - last_called)
                time.sleep(sleep_time)
            last_called = time.perf_counter()
            result = self.client.get_my_trades(symbol=symbol, limit=request_limit)

            if not result:
                # No trades for this symbol, try the next one
                continue

            trades.extend(result)

            while len(result) == request_limit:
                now = time.perf_counter()
                if now - last_called < wait_time:
                    sleep_time = wait_time - (now - last_called)
                    self.log.info(f"Waiting for repeat request {sleep_time} sec")
                    time.sleep(sleep_time)
                # Need to pull more. Get the time of the first trade, subtract one,
                # and set that as the last trade time to get to get
                next_end_time = result[0]["time"] - 1
                last_called = time.perf_counter()
                result = self.client.get_my_trades(
                    symbol=symbol, limit=request_limit, endTime=next_end_time
                )
                trades.extend(result)

        if not trades:
            self.log.notice('No symbols to get trades for')
            return

        # Check if blacklist might need to be updated
        symbols_found = list(set([trade['symbol'] for trade in trades]))
        if symbols_found:
            settings.try_update_blacklist(symbols_found)

        # Write results to the store
        self.trades.update(trades)
        self.trades.save()
        trade_counter = dict(Counter([trade['symbol'] for trade in trades]))
        self.log.notice(f"{len(trades)} retrieved and stored on disk: {trade_counter}")

    def force_get_all_active(self, whitelist=None, blacklist=None):
        all_active = self.exchange_info.active_symbols
        if blacklist is not None and whitelist is None:
            self.log.info(f"Skipping {blacklist} while getting all trades")
            all_active = [pair for pair in all_active if pair not in blacklist]
        elif whitelist is not None:
            all_active = [pair for pair in all_active if pair in whitelist]
            self.log.info(f"Only getting trades for whitelisted pairs: {all_active}")
        self.update_trades(all_active)

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

"""Set up single-use or continuous monitors to the BinanceAPI"""
import json
import os
import time
from typing import List, Optional, Tuple, Union

from binance.client import Client
from logbook import Logger
from tqdm import tqdm

from binance_monitor import exchange, settings, store, util
from binance_monitor.util import is_yes_response


class AccountMonitor(object):
    def __init__(self, credentials=None, name="default"):
        """Create a Binance account monitor that can access account details

        If neither an initialized client nor valid credentials are passed, an attempt
        will be made to load credentials from cache, or prompt user for them.

        :param credentials: Binance API key and secret (optional)
        :param name: Nickname for this account. Optional, default value is "default"
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
        :raises: IOError if credentials cannot be loaded from disk
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
        """Prompt user to enter API key and secret. Prompt user to save credentials
        to disk for future use (unencrypted)

        :return: A tuple with (key, secret)
        """

        api_key = input("Enter Binance API key: ")
        api_secret = input("Enter Binance API secret: ")

        save_credentials = is_yes_response("\nSave credentials to disk (unencrypted)?")

        if save_credentials:
            cache_file = settings.API_KEY_FILENAME
            cred_json = {"binance_key": api_key, "binance_secret": api_secret}

            with open(util.ensure_dir(cache_file), "w") as cred_file:
                json.dump(cred_json, cred_file)
                self.log.info(f"Stored credentials to {cache_file}")

        return api_key, api_secret

    def get_trade_history_for(self, symbols: Union[list, str]) -> None:
        """Get full trade history from the API for each symbol in `symbols`

        :param symbols: A single symbol pair, or a list of such pairs, which are listed
            on Binance
        :return: None
        """

        # Get the minimum time to wait between requests to avoid being throttled/banned
        wait_time = 1.0 / self.exchange_info.max_request_freq(req_weight=5)
        limit = 1000
        trades = []
        last_called = 0

        if not isinstance(symbols, list):
            symbols = [symbols]

        for symbol in tqdm(symbols):
            tqdm.write(symbol, end="")  # Print to console above the progress bar

            result = None
            params = {"symbol": symbol, "limit": limit}

            while result is None or len(result) == limit:
                # Wait a while if needed to avoid hitting API rate limits
                now = time.perf_counter()
                delta = now - last_called
                if delta < wait_time:
                    time.sleep(wait_time - delta)

                next_end_time = result[0]["time"] - 1 if result else None
                if next_end_time:
                    params.update({"endTime": next_end_time})

                last_called = time.perf_counter()
                result = self.client.get_my_trades(**params)

                if not result:
                    break

                trades.extend(result)
                tqdm.write(f" : {len(result)}", end="")

            tqdm.write("")

        if not trades:
            self.log.notice("No trades received for given symbols")
            return

        # Check if blacklist might need to be updated
        symbols_found = list(set([trade["symbol"] for trade in trades]))
        if symbols_found:
            settings.try_update_blacklist(symbols_found)

        # Write results to the store
        self.trades.update(trades)
        self.trades.save()
        self.log.notice(f"{len(trades)} trades retrieved and stored on disk")

    def get_all_trades(self, whitelist: List[str] = None, blacklist: List[str] = None):
        """Pull trade history for all symbols on Binance.

        If `whitelist` is given, only get trade history for the list of symbols it contains
        If `blacklist` is given (and no whitelist), get all symbol pairs active on
        Binance *except* the symbols it contains

        :param whitelist:
        :param blacklist:
        :return: None
        """

        all_active = self.exchange_info.active_symbols

        if blacklist is not None and whitelist is None:
            self.log.info(f"Skipping {blacklist} while getting all trades")
            all_active = [pair for pair in all_active if pair not in blacklist]
        elif whitelist is not None:
            all_active = [pair for pair in all_active if pair in whitelist]
            self.log.info(f"Only getting trades for whitelisted pairs: {all_active}")

        self.get_trade_history_for(all_active)

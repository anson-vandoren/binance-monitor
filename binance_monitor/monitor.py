# MIT License
#
# Copyright (C) 2019 Anson VanDoren
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice (including the next paragraph)
# shall be included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""Set up single-use or continuous monitors to the BinanceAPI"""
import atexit
import time
from typing import Dict, List, Optional

from binance.client import Client
from binance.websockets import BinanceSocketManager
from logbook import Logger
from tqdm import tqdm

from binance_monitor import exchange, settings, store
from binance_monitor.base import Asset
from binance_monitor.trade import TaxTrade


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
            credentials = settings.get_credentials()

        self.client = Client(*credentials)
        self.exchange_info = exchange.Exchange(self.client)
        self.name = name
        self.trade_store = store.TradeStore(name)
        self.bsm: Optional[BinanceSocketManager] = None
        self.conn_key = None

        atexit.register(self._stop_user_monitor)

    def start_user_monitor(self):
        self.bsm = BinanceSocketManager(self.client)
        self.conn_key = self.bsm.start_user_socket(self.process_user_update)
        self.bsm.start()
        self.log.notice("Starting account monitor listener. Press Ctrl+C to exit.")

    def _stop_user_monitor(self):
        if self.conn_key is not None:
            self.bsm.stop_socket(self.conn_key)
            self.conn_key = None
            self.log.notice("Account monitor has been shutdown")

    def process_user_update(self, msg: dict):
        update = EventUpdate.create(msg)
        if isinstance(update, OrderUpdate) and update.is_trade_event:
            self.trade_store.add_trade(update.trade)
            print(update.trade)
            settings.Blacklist.remove(update.symbol)

    def get_trade_history_for(self, symbols: List) -> None:
        """Get full trade history from the API for each symbol in `symbols`

        :param symbols: A single symbol pair, or a list of such pairs, which are listed
            on Binance
        :return: None
        """

        # Get the minimum time to wait between requests to avoid being throttled/banned
        wait_time = 1.0 / self.exchange_info.max_request_freq(req_weight=5)
        limit = 1000
        trades: List[Dict] = []
        last_called = 0.0

        for symbol in tqdm(symbols):
            tqdm.write(symbol, end="")  # Print to console above the progress bar

            result = None
            params = {"symbol": symbol, "limit": limit}

            while result is None or len(result) == limit:
                # Wait a while if needed to avoid hitting API rate limits
                delta = time.perf_counter() - last_called
                if delta < wait_time:
                    time.sleep(wait_time - delta)

                if result is not None:
                    next_end_time = result[0]["time"] - 1
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
            settings.Blacklist.remove(symbols_found)

        # Write results to the store
        tax_trades = [TaxTrade.from_historic_trades(result) for result in trades]
        self.trade_store.update(tax_trades)
        self.log.notice(f"{len(trades)} trades retrieved and stored on disk")

    def get_all_trades(self, force_all=False):
        """Pull trade history for all symbols on Binance that are not blacklisted.

        If *force_all* is True, pull history regardless of blacklist
        """

        blacklist = settings.Blacklist.get() if not force_all else None
        all_active = settings.read_symbols("active")

        if blacklist is not None:
            self.log.info(f"Skipping {blacklist} while getting all trades")
            all_active = [pair for pair in all_active if pair not in blacklist]

        self.get_trade_history_for(all_active)


class EventUpdate:
    def __init__(self, api_payload: Dict):
        if not isinstance(api_payload, dict):
            raise ValueError(
                f"EventUpdate expected as a dict but got {type(api_payload)}"
            )
        self.payload = api_payload
        self.event_timestamp = int(api_payload["E"])
        self.event_type = self.__class__.__name__

    @staticmethod
    def create(api_payload):
        event_types = {
            "outboundAccountInfo": AccountUpdate,
            "executionReport": OrderUpdate,
        }
        return event_types[api_payload["e"]](api_payload)


class AccountUpdate(EventUpdate):
    def __init__(self, api_payload: Dict):
        super().__init__(api_payload)

        self.last_updated_timestamp = int(api_payload["u"])
        self.balances = [Asset(asset) for asset in api_payload["B"]]


class OrderUpdate(EventUpdate):
    def __init__(self, api_payload: Dict):
        super().__init__(api_payload)

        self.symbol = api_payload["s"]
        print(
            f"OrderUpdate: executionType={api_payload['x']}\texecutionStatus={api_payload['X']}"
        )

    @property
    def trade(self) -> TaxTrade:
        if not self.is_trade_event:
            raise AttributeError("This order update is not a trade event")

        return TaxTrade.from_order_update(self.payload)

    @property
    def is_trade_event(self) -> bool:
        is_trade = self.payload["x"] == "TRADE" and self.payload["X"] in [
            "PARTIALLY_FILLED",
            "FILLED",
        ]
        did_execute = float(self.payload["l"]) > 0 and float(self.payload["L"]) > 0
        has_trade_id = self.payload["t"] != -1
        return is_trade and did_execute and has_trade_id

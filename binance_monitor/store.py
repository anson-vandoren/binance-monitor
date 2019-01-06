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
from typing import Optional, Dict, List, Any

import pandas as pd
from binance.client import Client
from logbook import Logger

from binance_monitor import util
from binance_monitor.settings import ACCOUNT_STORE_FOLDER

class TradeStore:
    TRADE_COLS = [
        "symbol",
        "id",
        "orderId",
        "price",
        "qty",
        "commission",
        "commissionAsset",
        "time",
        "isBuyer",
        "isMaker",
        "isBestMatch",
    ]

    def __init__(self, acct_name):
        self.log = Logger(__name__.split(".", 1)[-1])
        self.name = acct_name
        self.file_path = os.path.join(ACCOUNT_STORE_FOLDER, self.name) + ".h5"

        self.trades: Optional[pd.DataFrame] = None
        try:
            util.ensure_dir(self.file_path)
            self.trades: pd.DataFrame = pd.read_hdf(self.file_path, key="trades")
        except (KeyError, IOError) as e:
            self.log.warn(f"Could not read {self.file_path} because {e}")

    def save(self):
        with pd.HDFStore(self.file_path, mode="a") as store:
            store.put("trades", self.trades, format="table", append=False)

    def last_known_trade_timestamp(self) -> Optional[int]:
        if self.trades is None:
            return None

        if self.trades.empty:
            return None

        return self.trades["time"].max()

    def update(self, trade_list: List[Dict[str, Any]]) -> None:
        new_trades = pd.DataFrame(trade_list, columns=self.TRADE_COLS)

        for col in ["id", "orderId", "price", "qty", "commission", "time"]:
            new_trades[col] = pd.to_numeric(new_trades[col])

        if self.trades is not None:
            self.trades = self.trades.append(
                new_trades, ignore_index=True, verify_integrity=True, sort=True
            )
        else:
            self.trades = (
                new_trades.drop_duplicates("id")
                .sort_values("time")
                .reset_index(drop=True)
            )

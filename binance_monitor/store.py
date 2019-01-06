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
from typing import List, Optional

import pandas as pd
from logbook import Logger

from binance_monitor import util
from binance_monitor.settings import ACCOUNT_STORE_FOLDER
from binance_monitor.trade import TaxTrade

pd.set_option("precision", 9)


class TradeStore:
    log = Logger(__name__.split(".", 1)[-1])

    def __init__(self, acct_name):
        self.nickname = acct_name
        self.file_path = os.path.join(ACCOUNT_STORE_FOLDER, self.nickname) + ".h5"
        util.ensure_dir(self.file_path)

        self._trades: Optional[pd.DataFrame]
        try:
            self._trades: pd.DataFrame = pd.read_hdf(self.file_path, key="taxtrades")
        except (KeyError, IOError) as exc:
            self._trades = None
            self.log.warn(f"Could not read {self.file_path} because {exc}")

        self.col_names = TaxTrade.COL_NAMES

    @property
    def trades(self) -> pd.DataFrame:
        self.clean()
        return self._trades

    def save(self) -> None:
        """Write out trade tax events to HDF file.

        This will overwrite any trade tax data already in the file, but will leave
        any other HDFStore keys untouched
        """

        if self.trades is not None:
            with pd.HDFStore(self.file_path, mode="a") as store:
                store.put("taxtrades", self.trades, format="table", append=False)

    def clean(self) -> None:
        """Remove duplicates from in-memory DataFrame, sort by *dtime*, and
        reset the index
        """

        if self._trades is not None and not self._trades.empty:
            self._trades = (
                self._trades.drop_duplicates()
                .sort_values("dtime")
                .reset_index(drop=True)
            )

    def last_known_trade_timestamp(self) -> Optional[pd.Timestamp]:
        """Return last known trade from in-memory DataFrame

        :return: pandas.Timestamp of the latest trade recorded if there are any
            records in the DataFrame, otherwise None
        """

        if self.trades is not None and not self.trades.empty:
            return self.trades["dtime"].max()

        return None

    def update(self, trade_list: List[TaxTrade]) -> None:
        new_trades = [trade.as_dict for trade in trade_list]
        trade_df = pd.DataFrame(new_trades, columns=self.col_names)

        for col in ["buy_amount", "sell_amount", "fee_amount"]:
            trade_df[col] = pd.to_numeric(trade_df[col])

        if self.trades is not None:
            self._trades = self.trades.append(
                trade_df, ignore_index=True, verify_integrity=True, sort=True
            )
        else:
            self._trades = (
                trade_df.drop_duplicates().sort_values("dtime").reset_index(drop=True)
            )

    def to_csv(self):
        if self.trades is None:
            return
        csv_file = os.path.splitext(self.file_path)[0] + ".csv"

        self.trades.to_csv(
            csv_file, float_format="%.9f", index=False, columns=TaxTrade.COL_NAMES
        )

    def add_trade(self, new_trade: TaxTrade):
        new_df = new_trade.to_dataframe()
        self._trades = self.trades.append(
            new_df, ignore_index=True, verify_integrity=True, sort=True
        )
        self.log.info(f"Added new tax trade to the store: {new_trade.as_dict}")
        self.save()

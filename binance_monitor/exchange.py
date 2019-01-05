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

from typing import List

import pandas as pd
from binance.client import Client
from logbook import Logger


class Exchange:
    def __init__(self, client: Client = None):
        self.log = Logger(__name__.split(".", 1)[-1])

        exchange_info = client.get_exchange_info()
        self.last_updated_time = exchange_info.get("serverTime", None)
        self.rate_limits = exchange_info.get("rateLimits", None)
        self.filters = exchange_info.get("exchangeFilters", None)
        self.symbols = exchange_info.get("symbols", None)
        self.active_symbols = [
            symbol["symbol"] for symbol in self.symbols if symbol["status"] == "TRADING"
        ]
        self.inactive_symbols = [
            symbol["symbol"] for symbol in self.symbols if symbol["status"] != "TRADING"
        ]

    def max_request_freq(self, req_weight: int = 1) -> float:
        """Get smallest allowable frequency for API calls.
        The return value is the maximum number of calls allowed per second
        :param req_weight: (int) weight assigned to this type of request
            Default: 1-weight
        :return: float of the maximum calls permitted per second
        """

        # Pull Binance exchange metadata (including limits) either from cached value, or
        # from the server if cached data is too old
        request_limits = self._req_limits()

        for rate in request_limits:
            # Convert JSON response components (e.g.) "5" "minutes" to a Timedelta
            interval = pd.Timedelta(f"{rate['intervalNum']} {rate['interval']}")
            # Frequency (requests/second) is, e.g., 5000 / 300 sec or 1200 / 60 sec
            rate["req_freq"] = int(rate["limit"]) / interval.total_seconds()

        max_allowed_freq = None

        for limit in request_limits:
            # RAW_REQUESTS type should be treated as a request weight of 1
            weight = req_weight if limit["rateLimitType"] == "REQUEST_WEIGHT" else 1
            this_allowed_freq = limit["req_freq"] / weight

            if max_allowed_freq is None:
                max_allowed_freq = this_allowed_freq
            else:
                max_allowed_freq = min(max_allowed_freq, this_allowed_freq)

        self.log.info(
            f"Maximum permitted request frequency for weight {req_weight} is "
            f"{max_allowed_freq} / sec"
        )

        return 0 if max_allowed_freq is None else max_allowed_freq

    def _req_limits(self) -> List:
        return [rate for rate in self.rate_limits if "REQUEST" in rate["rateLimitType"]]

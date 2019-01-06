import datetime
from decimal import Decimal
from typing import Optional, Union, List, Dict, Any
from dateutil import tz

from binance_monitor.base import Symbol

import pandas as pd

pd.set_option("precision", 9)


class TaxTrade:
    """Information about a trade required for tax purposes

    Based on https://github.com/probstj/ccGains.git project
    """

    def __init__(
        self,
        kind: str,
        dtime: Union[str, pd.Timestamp],
        buy_currency: str,
        buy_amount: Union[str, Decimal],
        sell_currency: str,
        sell_amount: Union[str, Decimal],
        fee_currency: str,
        fee_amount: Union[str, Decimal],
        exchange: str = "",
        mark: str = "",
        comment: str = "",
        default_timezone=Optional[datetime.tzinfo],
    ):
        """Create a trade object compatible with the ccGains tax library

        All parameters may be strings; the numerical values will be converted
        to decimal.Decimal values, and *dtime* to a datetime.

        :param kind: a string denoting the kind of transaction, which may be e.g.
            "trade", "withdrawal", "deposit". Not currently used, so it can be
            any comment

        :param dtime: a string or datetime object denoting the date and time of the
            transaction. A string will be parsed with pandas.Timestamp. A number is not
            allowed since Binance uses milliseconds since Epoch, but many other libraries
            use seconds since Epoch. Please convert numbers to datetime-like first

        :param buy_currency: for a buy-type transaction, this is the base currency,
            and for a sell-type transaction this is the quote currency

        :param buy_amount: the amount of *buy_currency* bought. This value excludes any
            transaction fees, and is the amount fully available after the transaction

        :param sell_currency: for a buy-type transaction, this is the quote currency,
            and for a sell-type transaction this is the base currency

        :param sell_amount: the amount of *sell_currency* sold

        :param fee_currency: currency in which fees were charged. May be *buy_currency*,
            *sell_currency*, or an exchange-specific coin

        :param fee_amount: the amount of fees paid for this transaction. May have any
            sign, and the absolute value will be used in all cases

        :param exchange: optionally, the name of the exchange which initiated this
            transaction

        :param mark: optionally, a transaction ID, for example

        :param comment: optionally, any user-defined note about the transaction

        :param default_timezone: this parameter is ignored if there is timezone data
            included in *dtime*. Otherwise, if *default_timezone* is None (default),
            the time data in *dtime* will be interpreted as time in the local timezone
            according to the locale setting; otherwise it must be a tzinfo subclass
            (from dateutil.tz or pytz), which will be added to *dtime*
        """

        self.kind = kind
        self.buycur = buy_currency
        self.sellcur = sell_currency
        self.feecur = fee_currency
        self.exchange = exchange
        self.mark = mark
        self.comment = comment

        self.buyval = Decimal(buy_amount)
        self.sellval = Decimal(sell_amount)
        self.feeval = abs(Decimal(fee_amount))

        if self.sellval < 0 or self.buyval < 0 or self.feeval < 0:
            raise ValueError(
                "Ambiguity: Expected buy_amount, sell_amount and fee_amount all to be positive"
            )

        if isinstance(dtime, (int, float)):
            raise ValueError(
                "Ambiguity: unable to parse dtime from a number as it "
                "may be either seconds or milliseconds from Epoch"
            )

        self.dtime = pd.Timestamp(dtime)
        # Add default timezone if not included
        if self.dtime.tzinfo is None:
            self.dtime = self.dtime.tz_localize(
                tz.tzlocal() if default_timezone is None else default_timezone
            )
        # Internally, save as UTC
        self.dtime = self.dtime.tz_convert("UTC")

    COL_NAMES = [
        "kind",
        "dtime",
        "buy_currency",
        "buy_amount",
        "sell_currency",
        "sell_amount",
        "fee_currency",
        "fee_amount",
        "exchange",
        "mark",
        "comment",
    ]

    @property
    def as_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "dtime": self.dtime,
            "buy_currency": self.buycur,
            "buy_amount": self.buyval,
            "sell_currency": self.sellcur,
            "sell_amount": self.sellval,
            "fee_currency": self.feecur,
            "fee_amount": self.feeval,
            "exchange": self.exchange,
            "mark": self.mark,
            "comment": self.comment,
        }

    def to_dataframe(self):
        df = pd.DataFrame(self.as_dict, index=[0], columns=self.COL_NAMES)
        for col in ["buy_amount", "sell_amount", "fee_amount"]:
            df[col] = pd.to_numeric(df[col])
        return df

    def to_csv_line(self, delimiter=", ", end="\n") -> str:
        strings = []
        for val in self.as_dict.values():
            if isinstance(val, Decimal):
                strings.append(f"{float(val):0.8f}")
            else:
                strings.append(str(val))
        return delimiter.join(strings) + end

    @property
    def csv_header(self) -> List[str]:
        return list(self.as_dict.keys())

    @staticmethod
    def from_order_update(payload: Dict[str, Any]):
        is_buy = payload["S"] == "BUY"
        symbol = Symbol(payload["s"])

        base_qty = Decimal(payload["l"])
        quote_qty = Decimal(payload["Y"])

        kind = f"{payload['o']} {payload['S']}"
        dtime = pd.Timestamp(payload["T"], unit="ms", tzinfo=tz.tzutc())
        exchange = "Binance"
        mark = payload["t"]
        comment = ""

        buy_currency = symbol.base if is_buy else symbol.quote
        buy_amount = base_qty if is_buy else quote_qty

        sell_currency = symbol.quote if is_buy else symbol.base
        sell_amount = quote_qty if is_buy else base_qty

        fee_currency = payload["N"]
        fee_amount = Decimal(payload["n"])

        kwargs = {
            "kind": kind,
            "dtime": dtime,
            "buy_currency": buy_currency,
            "buy_amount": buy_amount,
            "sell_currency": sell_currency,
            "sell_amount": sell_amount,
            "fee_currency": fee_currency,
            "fee_amount": fee_amount,
            "exchange": exchange,
            "mark": mark,
            "comment": comment,
        }

        return TaxTrade(**kwargs)

    @staticmethod
    def from_historic_trades(payload: Dict[str, Any]) -> "TaxTrade":

        is_buy = payload["isBuyer"] is True
        symbol = Symbol(payload["symbol"])

        base_qty = Decimal(payload["qty"])
        quote_qty = base_qty * Decimal(payload["price"])

        kind = "BUY" if is_buy else "SELL"
        dtime = pd.Timestamp(payload["time"], unit="ms", tzinfo=tz.tzutc())
        exchange = "Binance"
        mark = payload["id"]
        comment = ""

        buy_currency = symbol.base if is_buy else symbol.quote
        buy_amount = base_qty if is_buy else quote_qty

        sell_currency = symbol.quote if is_buy else symbol.base
        sell_amount = quote_qty if is_buy else base_qty

        fee_currency = payload["commissionAsset"]
        fee_amount = Decimal(payload["commission"])

        kwargs = {
            "kind": kind,
            "dtime": dtime,
            "buy_currency": buy_currency,
            "buy_amount": buy_amount,
            "sell_currency": sell_currency,
            "sell_amount": sell_amount,
            "fee_currency": fee_currency,
            "fee_amount": fee_amount,
            "exchange": exchange,
            "mark": mark,
            "comment": comment,
        }

        return TaxTrade(**kwargs)

    def __str__(self):
        is_buy = "BUY" in self.kind.upper()
        msg = f"{self.dtime}\n"
        msg += f"  kind: {self.kind}\n"
        if is_buy:
            msg += (
                f"Bought: {self.buyval:.8f} {self.buycur}\n"
                f"   for: {self.sellval:.8f} {self.sellcur}\n"
            )
        else:
            msg += (
                f"  Sold: {self.sellval:.8f} {self.sellcur}\n"
                f"   for: {self.buyval:.8f} {self.buycur}"
            )

        msg += (
            f"   fee: {self.feeval:.8f} {self.feecur}\n"
            f"on {self.exchange} with ID={self.mark}\n"
        )
        return msg

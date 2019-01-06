class Symbol:
    QUOTE_ASSETS = ["BTC", "ETH", "USDT", "TUSD", "PAX", "BNB"]

    def __init__(self, symbol: str):
        for quote in self.QUOTE_ASSETS:
            quote_start = symbol.find(quote)
            if len(symbol) == quote_start + len(quote):  # Quote asset is right-most
                self.base = symbol[:quote_start]
                self.quote = symbol[quote_start:]
                return
        raise KeyError(f"Couldn't find a quote asset for '{symbol}'")


class Asset:
    def __init__(self, api_asset: dict):
        if not isinstance(api_asset, dict):
            raise ValueError(
                f"Asset constructor expected a dict, but got {type(api_asset)}"
            )

        self.asset = api_asset["a"]
        self.free = api_asset["f"]
        self.locked = api_asset["l"]

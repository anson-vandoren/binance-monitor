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
import sys

import logbook

from binance_monitor import monitor, settings, util
from binance_monitor.util import is_yes_response
from binance_monitor.settings import LOG_FILENAME


def main():
    # Set up logging for the whole app
    util.ensure_dir(LOG_FILENAME)
    logbook.TimedRotatingFileHandler(LOG_FILENAME, bubble=True).push_application()
    logbook.StreamHandler(sys.stdout, level="NOTICE", bubble=True).push_application()
    log = logbook.Logger(__name__.split(".", 1)[-1])

    log.info("*" * 80)
    log.info("***" + "Starting CLI Parser for binance-monitor".center(74) + "***")
    log.info("*" * 80)

    parser = argparse.ArgumentParser(
        description="CLI for monitoring Binance account information"
    )
    parser.add_argument("--acct_info", help="Display account info", action="store_true")
    parser.add_argument(
        "--blacklist",
        help="Blacklist (don't get trades for) listed symbol pairs",
        nargs="*",
    )

    args = parser.parse_args()

    acct_monitor = monitor.AccountMonitor()

    saved_blacklist = settings.get_preferences().get("blacklist", None)
    if args.blacklist:
        blacklist = sorted(args.blacklist)
    else:
        blacklist = None

    if blacklist is not None:
        if "ALL" in blacklist or "all" in blacklist:
            print("Are you sure you want to blacklist all symbols?")
            blacklist_all = input("[Y]/n").upper()
            if blacklist_all == "\n" or blacklist_all[0] == "Y":
                blacklist = (
                    acct_monitor.exchange_info.active_symbols
                    + acct_monitor.exchange_info.inactive_symbols
                )

    if blacklist is not None and saved_blacklist != blacklist:
        print("Add to saved blacklist? ")
        save_prefs = input("[Y]/n ")
        if save_prefs == "\n" or save_prefs.upper()[0] == "Y":
            print(saved_blacklist, blacklist)
            if saved_blacklist is None:
                new_blacklist = blacklist
            else:
                new_blacklist = list(set(saved_blacklist + blacklist))
            new_blacklist = sorted(new_blacklist)
            log.info(f"Old blacklist: {saved_blacklist}")
            log.info(f"New blacklist: {new_blacklist}")
            new_prefs = settings.get_preferences()
            new_prefs.update({"blacklist": new_blacklist})
            settings.save_preferences(new_prefs)
    elif blacklist is None and saved_blacklist:
        use_saved = is_yes_response('Use saved blacklist?')
        if use_saved:
            blacklist = saved_blacklist

    if args.acct_info:
        print("Requested account info")

        acct_monitor.force_get_all_active(blacklist=blacklist)


if __name__ == "__main__":
    ENABLE_LOGGING = True
    main()

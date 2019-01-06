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
import time

import logbook
from twisted.internet import reactor

from binance_monitor import monitor, settings, util
from binance_monitor.settings import LOG_FILENAME
from binance_monitor.util import is_yes_response


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
    parser.add_argument(
        "--update", help="Update trades from server", action="store_true"
    )
    parser.add_argument(
        "--force",
        help="Update trades for all symbols, regardless of blacklist",
        action="store_true",
    )
    parser.add_argument("--listen", help="Listen for new trades", action="store_true")
    parser.add_argument("--blacklist", help="Add symbol(s) to blacklist", nargs="*")
    parser.add_argument(
        "--whitelist", help="Remove symbol(s) from blacklist", nargs="*"
    )
    parser.add_argument(
        "--csv", help="Write out CSV file of trades (from cache)", action="store_true"
    )

    args = parser.parse_args()

    acct_monitor = monitor.AccountMonitor()

    blacklist_from_cli(args.blacklist or None)
    whitelist_from_cli(args.whitelist or None)

    force_all = True if args.force else False

    if args.update:
        acct_monitor.get_all_trades(force_all=force_all)
        acct_monitor.trade_store.save()

    if args.listen:
        acct_monitor.start_user_monitor()

        while True:
            try:
                time.sleep(60 * 60 * 24)
            except KeyboardInterrupt:
                print("\nExit requested...")
                break

    if args.csv:
        acct_monitor.trade_store.to_csv()

    if reactor.running:
        reactor.callFromThread(reactor.stop)


def blacklist_from_cli(blacklist):
    if not blacklist:
        return settings.Blacklist.get()

    blacklist = [symbol.upper() for symbol in blacklist]

    if "ALL" in blacklist:
        if is_yes_response("Are you sure you want to blacklist all symbols?"):
            blacklist = settings.read_symbols("all")
            settings.Blacklist.set(blacklist)
            return blacklist

    if "NONE" in blacklist:
        if is_yes_response("Are you sure you want to clear all blacklisted symbols?"):
            blacklist = []
            settings.Blacklist.set(blacklist)
            return blacklist

    settings.Blacklist.add(blacklist)

    return settings.Blacklist.get()


def whitelist_from_cli(whitelist):
    if not whitelist:
        return settings.Blacklist.get()

    whitelist = [symbol.upper() for symbol in whitelist]

    if "ALL" in whitelist:
        if is_yes_response("Are you sure you want to whitelist all symbols?"):
            blacklist = []
            settings.Blacklist.set(blacklist)
            return blacklist

    if "NONE" in whitelist:
        if is_yes_response("Are you sure you want to remove all whitelisted symbols?"):
            blacklist = settings.read_symbols("all")
            settings.Blacklist.set(blacklist)
            return blacklist

    settings.Blacklist.remove(whitelist)

    return settings.Blacklist.get()


if __name__ == "__main__":

    main()
    print("Main Done")

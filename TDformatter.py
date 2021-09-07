import pandas as pd
import numpy as np
import json
from flatten_json import flatten
import time
import atexit
from pprint import pprint
from datetime import datetime
from datetime import date
from tda.client import Client
from tda.streaming import StreamClient
from tda.auth import easy_client
from tda import auth
from tda.orders import equities
from tda.orders.common import Duration, Session


class TDformatter:

    class Quote_formatter:
        """
        Creates json of quotes.
        """

        def __init__(self, response):
            self.data = response.json()

        def to_df(self):
            """
            Returns formatted pandas DataFrame from formatted json of
            quotes created with Quote_formatter.
            """
            return pd.DataFrame(self.data).T

    class History_formatter:
        """
        Creates json of history. 
        """

        def __init__(self, response):
            self.data = response.json()
            self.candles = self.data['candles']
            self.ticker = self.data['symbol']

        def to_df(self):
            """
            Returns formatted pandas DataFrame from formatted json of
            history created with History_formatter.
            """
            self.dataframe = pd.DataFrame(self.candles)
            self.dataframe['symbol'] = self.ticker
            self.dataframe.set_index('datetime', inplace=True)
#             Converts time since epoch to a datetime object with second accuracy (any more is unneccessary)
#             and sets it as index.
            self.dataframe.index = pd.to_datetime(
                (self.dataframe.index/1000).astype('int64'), unit='s')
            return self.dataframe

    class Chain_formatter:
        """
        Creates json of options chains.  Can take call &/or put chains, if given 
        both will return tuple of calls, puts.
        """

        def __init__(self, response):
            self.data = response.json()
#             Check if the options_chain response contains calls, if empty then set flag to false
            if self.data['callExpDateMap'] != {}:
                self.calls = self.data['callExpDateMap'].values()
                self.calls_exists = True
            else:
                self.calls_exists = False

#             Check if the options_chain response contains puts, if empty then set flag to false.
            if self.data['putExpDateMap'] != {}:
                self.puts = self.data['putExpDateMap'].values()
                self.puts_exists = True
            else:
                self.puts_exists = False

        def to_df(self):
            """
            Returns formatted pandas DataFrame from formatted json of
            options chain created with Chain_formatter.
            """
#             Gets today's date for use in index.
            today = datetime.now().strftime('%m-%d-%Y')

#             Checks if options_chain response contains calls, if not then skips.
            if self.calls_exists:
                self.calls_list = []
#             **Very inefficient triple for loop, should be revised if possible**
                for i in self.calls:
                    for j in i.values():
                        for k in j:
                            self.calls_list.append(k)
                self.calls_df = pd.DataFrame(self.calls_list)
                self.calls_df.set_index('description', inplace=True)
                self.calls_df['Date'] = today
#                 Removes garbage responses with -999 deltas
                self.calls_df[self.calls_df['delta'] != -999.0]

#             Checks if options_chain response contains puts, if not then skips.
            if self.puts_exists:
                self.puts_list = []
#             **Very inefficient triple for loop, should be revised if possible**
                for i in self.puts:
                    for j in i.values():
                        for k in j:
                            self.puts_list.append(k)
                self.puts_df = pd.DataFrame(self.puts_list)
                self.puts_df.set_index('description', inplace=True)
                self.puts_df['Date'] = today
#                 Removes garbage responses with -999 deltas
                self.puts_df[self.puts_df['delta'] != -999.0]

#            Determines return values based on if calls &/or puts exists.
            if self.calls_exists and self.puts_exists:
                return self.calls_df, self.puts_df
            elif self.calls_exists and not self.puts_exists:
                return self.calls_df
            elif not self.calls_exists and self.puts_exists:
                return self.puts_df

    class Account_formatter:
        """
        Creates json of account info.
        """

        def __init__(self, response):
            self.data = response.json()

        def to_df(self):
            """
            Returns formatted pandas DataFrame from formatted json of
            account info created with Account_formatter.
            """
            account_df_list = []
            for d in self.data:
                account_info_json = flatten(d['securitiesAccount'], '.')
                df = pd.DataFrame(account_info_json, index=[0])
                df.set_index('accountId', inplace=True)
                account_df_list.append(df)
            account_info_df = pd.concat(account_df_list)
            # The flattend column names contain an odd .0, this is remove here,
            # this appears to be a bug/?feature? caused by the flatten_json package
            new_labels = [name.replace('.0', '')
                          for name in list(account_info_df.columns)]
            account_info_df.columns = new_labels
            return account_info_df

    class Transaction_history_formatter:
        """
        Creates json of transaction history. Can take
        a single or multiple responses (for multiple accounts).
        """

        def __init__(self, response):
            if type(response) is list:
                self.data = [response1.json() for response1 in response]
            else:
                self.data = response.json()

        def to_df(self):
            """Returns formatted pandas DataFrame from formatted json of
            transaction history created with
            Transaction_history_formatter.
            """
            if type(self.data) is list:
                transaction_history_list = list(
                    map(pd.json_normalize, self.data))
                transaction_history_df = pd.concat(transaction_history_list)
            else:
                transaction_history_df = pd.json_normalize(self.data)

            transaction_history_df.set_index('transactionId', inplace=True)
            return transaction_history_df

    class Watchlist_formatter:
        """
        Creates json of chosen watchlist.  Must pass
        the name of a watchlist or an error will be raised with
        a list of watchlist names.
        """

        def __init__(self, response, watchlist=None):
            self.data = response.json()
            self.watchlist = watchlist
            # If no watchlist name is specified an error is raised here with
            # a list of the names of the available watchlists
            if not self.watchlist:
                raise ValueError(
                    f"Please choose a watchlist: {list(pd.DataFrame(self.data)['name'].values)}")

        def to_df(self):
            """
            Returns formatted pandas DataFrame from formatted json of
            chosen watchlist.
            """
            watchlist = pd.DataFrame(self.data)
            watchlist.set_index('name', inplace=True)
            watchlist_df = pd.json_normalize(
                watchlist.loc[self.watchlist]['watchlistItems'])
            watchlist_df.set_index('instrument.symbol', inplace=True)
            return watchlist_df

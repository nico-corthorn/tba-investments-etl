# import os
# import sys
# import traceback
# from datetime import datetime

# import numpy as np
# import pandas as pd
# import pandas_datareader as pdr
# from pandas.tseries.offsets import BDay

# from tbainvestetl.utils import sql_manager
# from tbainvestetl.utils.utils import compute


# class Scraper:
#     def __init__(self):
#         self.sql_manager = sql_manager.ManagerSQL()
#         self.today = pd.datetime.today().date()
#         self.last_business_date = (self.today - BDay(1)).date()
#         self.min_date = pd.to_datetime("1960-01-01").date()
#         self.elements = self.get_elements_to_download()

#     def get_elements_to_download(self):
#         """Overwrite this method with child class definition."""
#         return []

#     def process(self):
#         compute(self.elements, self.scrape)

#     def scrape(self, args):
#         """Overwrite this method with child class definition."""


# class TiingoScraper(Scraper):
#     def get_elements_to_download(self):
#         data = self.sql_manager.select("assets_tiingo")
#         data = data[["ticker", "end_date"]]
#         data_last = self.sql_manager.select_query(
#             """
#                 SELECT ticker, MAX(trade_date) last_date
#                 FROM prices_tiingo
#                 GROUP BY ticker
#             """
#         )
#         data = data.merge(data_last, how="outer", left_on="ticker", right_on="ticker")
#         cond1 = data["last_date"].isnull()  # No record
#         cond2 = (
#             data["last_date"] < data["end_date"]
#         )  # Ticker is gone and not all info is in db
#         cond3 = data["end_date"].isnull() & (
#             data["last_date"] < self.last_business_date
#         )  # Ticker still trades, and new info is available
#         cond = cond1 | cond2 | cond3
#         data = data.loc[cond]
#         lst = data.reindex().values.tolist()
#         return lst[:1000]

#     def scrape(self, args):
#         t0 = datetime.now()
#         ticker = args[0]
#         # end_date = args[1]
#         last_date = args[2]
#         has_last = not np.isnan(last_date)
#         if has_last:
#             min_date = last_date
#         else:
#             min_date = self.min_date
#         try:
#             api_key = os.environ.get("TIINGO_API_KEY")
#             data = pdr.get_data_tiingo(
#                 ticker, min_date, self.last_business_date, api_key=api_key
#             )
#             # adjClose adjHigh adjLow adjOpen adjVolume
#             # close divCash high low open splitFactor volume
#             data = data.reset_index()
#             rename = {
#                 "symbol": "ticker",
#                 "date": "trade_date",
#                 "open": "price_open",
#                 "close": "price_close",
#                 "adjClose": "adj_close",
#                 "divCash": "div_cash",
#                 "splitFactor": "split",
#             }
#             data.rename(columns=rename, inplace=True)
#             cols = [
#                 "ticker",
#                 "trade_date",
#                 "price_open",
#                 "price_close",
#                 "volume",
#                 "adj_close",
#                 "div_cash",
#                 "split",
#             ]
#             data = data[cols]
#             data["trade_date"] = data["trade_date"].dt.date
#             data.columns = [col.lower() for col in data.columns]

#             if has_last:
#                 data = data.loc[data["trade_date"] > last_date]

#             # Upload data to db
#             self.sql_manager.upload_df_chunks("prices_tiingo", data)
#             t1 = datetime.now()
#             print(
#                 f"Download successful for {ticker} ({(t1 - t0).total_seconds():.2f} sec)"
#             )

#         except Exception:
#             t1 = datetime.now()
#             print(f"Download failed for {ticker} ({(t1 - t0).total_seconds():.2f} sec)")
#             exc_type, exc_value, exc_tb = sys.exc_info()
#             traceback.print_exception(exc_type, exc_value, exc_tb)

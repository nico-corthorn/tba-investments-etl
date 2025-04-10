import csv
from abc import ABC
from datetime import datetime

import numpy as np
import pandas as pd

from tbainvestetl.alpha import api
from tbainvestetl.domain_models.io import SQLParams
from tbainvestetl.utils import date_utils, sql_manager, utils

URL_BASE = "https://www.alphavantage.co/query?function="


class AlphaTable(ABC):
    def __init__(
        self,
        table_name: str,
        primary_keys: list,
        scraper: api.AlphaScraper,
        sql_params: SQLParams,
    ):
        self.table_name = table_name
        self.primary_keys = primary_keys
        self.scraper = scraper
        self.sql = sql_manager.ManagerSQL(sql_params)

    def _get_db_data(self, symbol: str) -> pd.DataFrame:
        query = f"select * from {self.table_name} where symbol = '{symbol}'"
        db_data = self.sql.select_query(query)
        return db_data

    def get_assets_to_refresh(self, asset_types):
        """Returns DataFrame with unique tickers from asset_table"""

        # Get full assets table
        query = "select * from assets_alpha"
        assets = self.sql.select_query(query)

        # Filter and drop duplicates
        assets = (
            assets.loc[assets.asset_type.isin(asset_types)]
            .sort_values(by=["symbol", "status", "delisting_date"])
            .drop_duplicates(subset="symbol", keep="first")
            .reset_index(drop=True)
        )

        return assets

    def filter_assets_by_max_date(self, assets, date_col, last_reference_date_fun):
        # Get last available date in db prices table
        query = f"""
            select symbol, max({date_col}) max_date
            from {self.table_name}
            group by symbol
        """
        assets_max_date = self.sql.select_query(query)

        assets = assets.merge(assets_max_date, how="left", left_on="symbol", right_on="symbol")

        # if active, last date in db (max_date) == self.last_business_date
        cond_last_bd = assets.max_date >= last_reference_date_fun(datetime.today())
        cond_delisted = assets.max_date >= assets.delisting_date.map(last_reference_date_fun)
        cond_updated = cond_last_bd | cond_delisted
        assets = assets.loc[~cond_updated]

        return assets

    def get_db_dates_missing(self, api_data_input, db_data_input):
        api_data = api_data_input.copy()
        db_data = db_data_input.copy()
        api_data["api_exist"] = 1
        db_data["db_exist"] = 1

        # Check whether and what to upload
        api_dates_df = api_data[self.primary_keys + ["api_exist"]].drop_duplicates().astype(str)
        db_dates_df = db_data[self.primary_keys + ["db_exist"]].drop_duplicates().astype(str)

        dates_df = api_dates_df.merge(
            db_dates_df,
            how="outer",
            left_on=self.primary_keys,
            right_on=self.primary_keys,
        )

        # Get dates missing in db
        db_missing = dates_df[dates_df.db_exist.isnull()][self.primary_keys]

        return db_missing


class AlphaTableAssets(AlphaTable):
    def update_all(self, date_input=None):
        """Updates assets_alpha table as of date_input with listed and delisted
        stocks and ETFs.

            Parameters
            ----------
            date_input: datetime.datetime
                Date to use for API call of listed and delisted
            assets_alpha_table: str
                Name of assets table. Default should be kept in most cases

            Returns
            -------
            None

            Side effects
            ------------
            Deletes assets_alpha content and then updates the table
            with data from the API using date_input
        """

        # Date
        if date_input is None:
            date_input = datetime.now()

        # Download listing status
        data = self.get_api_data(date_input)

        # Update assets table
        self.sql.clean_table(self.table_name)
        self.sql.upload_df_chunks(self.table_name, data)

    def get_api_data(self, date_input):
        # Download active
        data_active = self._download_active_listings()

        # Download delisted
        data_delist = self._download_delisted(date_input)

        # Concatenate
        data = data_active.append(data_delist).reset_index(drop=True)

        # Rename columns
        data.columns = [utils.camel_to_snake(col) for col in data.columns]

        # Fix missing values in delisting_date column
        data.loc[data.delisting_date == "null", "delisting_date"] = None

        # Include lud
        data["lud"] = datetime.now()

        return data

    def _download_active_listings(self) -> pd.DataFrame:
        """Hit AlphaVantage API to get active listings

        Returns
        -------
        pd.DataFrame
            DataFrame with listings that are active
        """

        url = "{URL_BASE}LISTING_STATUS&apikey=demo"

        download = self.scraper.hit_api(url)
        decoded_content = download.content.decode("utf-8")
        cr = csv.reader(decoded_content.splitlines(), delimiter=",")
        my_list = list(cr)
        data = pd.DataFrame(my_list[1:], columns=my_list[0])

        return data

    def _download_delisted(self, date_input: datetime) -> pd.DataFrame:
        """Hit AlphaVantage API to get delisted assets

        Parameters
        ----------
        date_input : datetime
            Date at which the delisting snapshot is taken

        Returns
        -------
        pd.DataFrame
            DataFrame with listings that were delisted as of given date

        """

        url = "{URL_BASE}LISTING_STATUS&date={dte}&state=delisted&apikey={api_key}"
        dte = date_input.strftime("%Y-%m-%d")
        download = self.scraper.hit_api(url, dte=dte)
        decoded_content = download.content.decode("utf-8")
        cr = csv.reader(decoded_content.splitlines(), delimiter=",")
        my_list = list(cr)
        data = pd.DataFrame(my_list[1:], columns=my_list[0])

        return data


class AlphaTablePrices(AlphaTable):
    def get_assets(self, validate: bool, asset_types: list):
        assets = self.get_assets_to_refresh(asset_types)
        if not validate:
            assets = self.filter_assets_by_max_date(
                assets, "date", date_utils.get_last_business_date
            )
        assets = assets.reset_index(drop=True)
        return assets

    def update_list(self, symbols: list, size: str):
        print(f"Updating prices for {symbols}")
        for symbol in symbols:
            self.update(symbol, size)

    def update(self, symbol: str, size: str):
        print(f"Updating prices for {symbol}")

        # Get API prices
        api_prices = self.get_api_data(symbol, size)

        if api_prices is not None:
            if api_prices.shape[0] > 0:
                # Get database prices
                db_prices = self._get_db_data(symbol)

                # Check whether and what to upload
                (
                    should_upload,
                    clean_db_table,
                    api_prices_upload,
                ) = self.get_api_prices_to_upload(api_prices, db_prices, size)
                print(f"should_upload = {should_upload}")
                print(f"clean_db_table = {clean_db_table}")

                if should_upload:
                    if api_prices_upload.empty:
                        # Fetch full history
                        api_prices_upload = self.get_api_data(symbol, size="full")

                    if clean_db_table:
                        # DB information has to be deleted for symbol

                        # Clean symbol rows
                        query = f"delete from {self.table_name} where symbol = '{symbol}'"
                        print(f"Cleaning {symbol}: {query}")
                        self.sql.query(query)
                    else:
                        date_min = api_prices_upload.date.min()
                        query = f"""
                        delete from {self.table_name} 
                        where symbol = '{symbol}'
                            and date >= '{date_min}'
                        """
                        print(f"Selective cleaning {symbol}: {query}")
                        self.sql.query(query)

                    # Upload to database
                    assert api_prices_upload.shape[0] > 0
                    print(f"Uploading {api_prices_upload.shape[0]} dates for {symbol}")
                    self.sql.upload_df_chunks(self.table_name, api_prices_upload)

                else:
                    print(f"Database already up to date for {symbol}")

    def get_api_data(self, symbol, size="full"):
        """Hit AlphaVantage API to get prices of symbol

        Parameters
        ----------
        symbol : str
        size: str
            compact or full

        Returns
        -------
        pd.DataFrame or None
            DataFrame with prices in API, according to given size
            If it fails to retrieve prices successfully, returns None
        """

        url = (
            "{URL_BASE}TIME_SERIES_DAILY_ADJUSTED"
            "&symbol={symbol}&outputsize={size}&apikey={api_key}"
        )

        try:
            # Hit API
            download = self.scraper.hit_api(url, symbol=symbol, size=size)
            prices_json = download.json()

            # Transform into formatted pandas DataFrame
            if "Time Series (Daily)" in prices_json:
                prices = pd.DataFrame(prices_json["Time Series (Daily)"], dtype="float").T

                # Remove enumeration at beginning of columns (e.g. "1. open")
                col_rename = {col: col[3:].replace(" ", "_") for col in prices.columns}
                prices.rename(columns=col_rename, inplace=True)

                # Date as a column
                prices = prices.reset_index().rename(columns={"index": "date"})

                # Include symbol and put as first column
                prices["symbol"] = symbol
                cols = list(prices.columns[-1:]) + list(prices.columns[:-1])
                prices = prices[cols]

                # Change to appropriate variable types
                dtypes = {
                    "symbol": "object",
                    "date": "datetime64[ns]",
                }
                prices = prices.astype(dtypes)
                prices["date"] = prices.date.dt.date

                # Last update date
                prices["lud"] = datetime.now()

                return prices

            raise ValueError(
                "Json file did not have 'Time Series (Daily)' as key. "
                "File content is:\n {prices_json}"
            )

        except Exception as e:
            print(f"Download failed for {symbol}. \nurl: {url}")
            print(e)
            return None

    def get_api_prices_to_upload(
        self,
        api_prices_input: pd.DataFrame,
        db_prices: pd.DataFrame,
        size: str,
    ):
        """Returns whether the data from the API should be included in the db,
        whether to clean all the db data for the symbol and the API data to
        upload, if any.

            Parameters
            ----------
            api_prices_input : pd.DataFrame
                API data including symbol, close, adjusted_close, etc
            db_prices: pd.DataFrame
                Data from the database with the same columns as api_prices

            Returns
            -------
            should_upload: bool
                True if there is data in the API to upload for the symbol.
                Otherwise False
            clean_db_table: bool
                True if the prices_alpha table should be cleaned of the underlying
                symbol. Otherwise False
            api_prices: pd.DataFrame
                API data that can be directly uploaded to prices_alpha in the db
        """

        # Original df will not be changed
        api_prices = api_prices_input.copy()

        # Check and copy api_prices_input
        assert api_prices.shape[0] > 0

        # Symbol
        api_symbols = api_prices.symbol.unique()
        db_symbols = db_prices.symbol.unique()
        assert (
            len(api_symbols) == 1
        ), f"Only one symbol in api_prices per update. symbols={api_symbols}"
        assert (
            len(db_symbols) <= 1
        ), f"At most one symbol in db_prices per update. symbols={db_symbols}"
        if len(db_symbols) == 1:
            assert db_symbols == api_symbols

        db_dates_missing = self.get_db_dates_missing(api_prices, db_prices).date

        # should_upload is True if there are API dates missing in db
        should_upload = False

        # clean_db_table is True if the table has to be cleaned of symbol data
        clean_db_table = False

        # Empty DataFrame
        empty_df = pd.DataFrame(columns=api_prices.columns)

        if len(db_dates_missing) == 0:
            # There is nothing to upload
            api_prices = empty_df

            # Returning False, False, Empty DataFrame
            return should_upload, clean_db_table, api_prices

        # There are API dates missing in the db
        should_upload = True

        # Get dates in db that are potentially valid
        db_dates_valid = db_prices.loc[db_prices.date.astype(str) < db_dates_missing.min()]

        if db_dates_valid.shape[0] == 0:
            # There are no valid dates in the db for the symbol.
            # Any rows related to the symbol should be erased
            # and the full history should be uploaded

            clean_db_table = True

            if size != "full":
                # If the API data collected is not the full history
                # return False, meaning the upload has to be repeated
                # with the full history
                api_prices = empty_df

            return should_upload, clean_db_table, api_prices

        # Database has data for dates that are valid if no split or dividend
        # has ocurred since. To be validated later.

        # The date up to which db data might be kept is the following
        date_upload = db_dates_valid.date.max()

        # Check if prices and coefficients are the same in date_upload
        cols_equal = [
            "symbol",
            "date",
            "close",
            "adjusted_close",
            "dividend_amount",
            "split_coefficient",
        ]
        db_cond = db_prices.date == date_upload
        api_cond = api_prices.date == date_upload
        db_prices_row = db_prices.loc[db_cond, cols_equal].reset_index(drop=True)
        api_prices_row = api_prices.loc[api_cond, cols_equal].reset_index(drop=True)

        if db_prices_row.equals(api_prices_row):
            # There is perfect continuation of the prices and coefficients
            # I.e. there was no split or dividend that would require
            # a retrospective adjustment of prices
            api_prices = api_prices.loc[api_prices["date"] > date_upload]

        else:
            # There was a split or dividend
            # All history should be downloaded
            clean_db_table = True

            if size != "full":
                api_prices = empty_df

            return should_upload, clean_db_table, api_prices

        return should_upload, clean_db_table, api_prices


class AlphaTablePricesMonthly(ABC):
    def __init__(self, table_name: str, sql_params: SQLParams):
        self.table_name = table_name
        self.sql = sql_manager.ManagerSQL(sql_params)

    def update_list(self, symbols: list):
        print(f"Updating prices for {symbols}")
        for symbol in symbols:
            self.update(symbol)

    def update(self, symbol: str):
        print(f"Updating monthly prices for {symbol}")

        # Get daily prices
        prices_daily = self.sql.select_query(
            f"select * from prices_alpha where symbol = '{symbol}'"
        )

        if prices_daily.shape[0] > 0:
            prices_monthly = self._get_prices_monthly(prices_daily)

            if prices_monthly.shape[0] > 0:
                # Clean symbol in monthly table
                delete_query = f"delete from {self.table_name} where symbol = '{symbol}'"
                self.sql.query(delete_query)

                # Upload to database
                print(f"Uploading {prices_monthly.shape[0]} months for {symbol}")
                self.sql.upload_df_chunks(self.table_name, prices_monthly)

            else:
                print(f"No valid monthly prices can be computed for {symbol}")

        else:
            print(f"No daily prices found for {symbol}")

    def _get_prices_monthly(self, prices_daily):
        # Compute monthly
        prices_daily["date"] = pd.to_datetime(prices_daily.date)
        prices_daily = prices_daily.sort_values(by=["symbol", "date"])
        prices_daily["previous_adjusted_close"] = prices_daily.groupby("symbol")[
            "adjusted_close"
        ].shift(1)
        prices_daily["daily_return"] = (
            prices_daily.adjusted_close / prices_daily.previous_adjusted_close - 1
        )
        prices_daily["daily_cont_return"] = np.log(1 + prices_daily.daily_return)
        agg_map = {
            "volume": np.sum,
            "daily_cont_return": np.sum,
            "daily_return": np.std,
            "symbol": len,
        }
        agg_rename = {
            "volume": "monthly_volume",
            "daily_cont_return": "monthly_cont_return",
            "daily_return": "monthly_return_std",
            "symbol": "day_count",
        }

        # Last monthly values
        prices_monthly_last = prices_daily.set_index("date").groupby("symbol").resample("BM").last()

        # Aggregate monthly values
        prices_monthly_agg = (
            prices_daily.set_index("date")
            .groupby("symbol")
            .resample("BM")
            .agg(agg_map)
            .rename(columns=agg_rename)
        )
        prices_monthly_agg["monthly_return"] = np.exp(prices_monthly_agg["monthly_cont_return"]) - 1

        # Join monthly values
        prices_monthly = prices_monthly_last.join(prices_monthly_agg)

        # Format and filter columns
        prices_monthly.rename(columns={"lud": "source_lud"}, inplace=True)
        prices_monthly["lud"] = datetime.now()
        prices_monthly = prices_monthly.drop(columns="symbol").reset_index()
        cols = [
            "symbol",
            "date",
            "open",
            "high",
            "low",
            "close",
            "adjusted_close",
            "monthly_volume",
            "monthly_return_std",
            "monthly_return",
            "day_count",
            "source_lud",
            "lud",
        ]
        missing_data_cond = prices_monthly.adjusted_close.isnull()
        one_record_cond = (prices_monthly.day_count == 1) & (prices_monthly.monthly_return == 0)
        prices_monthly = prices_monthly.loc[~missing_data_cond & ~one_record_cond, cols].copy()

        return prices_monthly


class AlphaTableAccounting(AlphaTable):
    """
    Class to update balance_alpha and income_alpha tables
    """

    def __init__(
        self,
        table_name: str,
        url_table_name: str,
        primary_keys: list,
        scraper: api.AlphaScraper,
        accounts: list,
        **kwargs,
    ):
        super().__init__(table_name, primary_keys, scraper, **kwargs)
        self.accounts = accounts
        self.url_table_name = url_table_name

    def get_assets(self, validate: bool, asset_types: list):
        # Get available assets from db
        assets = self.get_assets_to_refresh(asset_types)
        if not validate:
            assets = self.filter_assets_by_max_date(
                assets, "report_date", date_utils.get_last_quarter_date
            )
        assets = assets.reset_index(drop=True)
        return assets

    def update_list(self, symbols: list):
        print(f"Updating {self.table_name} for {symbols}")
        for symbol in symbols:
            self.update(symbol)

    def update(self, symbol: str):
        print(f"Updating {self.table_name} for {symbol}")

        # Get API balance
        api_balance = self.get_api_data(symbol)

        if api_balance is not None:
            if not api_balance.empty:
                # Get database balance
                db_balance = self._get_db_data(symbol)

                # Get dates missing in db
                # db_missing = dates_df[dates_df.lud_db.isnull()][key_cols]
                db_missing = self.get_db_dates_missing(api_balance, db_balance)
                should_upload = not len(db_missing) == 0

                if should_upload:
                    api_balance[self.primary_keys] = api_balance[self.primary_keys].astype(str)
                    api_balance = api_balance.merge(
                        db_missing,
                        how="inner",
                        left_on=self.primary_keys,
                        right_on=self.primary_keys,
                    )

                    # Upload to database
                    assert api_balance.shape[0] > 0
                    print(f"Uploading {api_balance.shape[0]} rows for {symbol}")
                    self.sql.upload_df_chunks(self.table_name, api_balance)

                else:
                    print(f"Database already up to date for {symbol}")

            else:
                print(f"api_balance was empty for {symbol}")

    def get_api_data(self, symbol: str):
        """Hit AlphaVantage API to get balance sheet

        Parameters
        ----------
        symbol: str
            symbol or ticker of the asset

        Returns
        -------
        pd.DataFrame or None
            DataFrame with balance sheet
        """

        url = "{URL_BASE}{url_table_name}&symbol={symbol}&apikey={api_key}"

        try:
            download = self.scraper.hit_api(url, symbol=symbol, url_table_name=self.url_table_name)
            data_json = download.json()

            final_cols = [
                "symbol",
                "report_type",
                "report_date",
                "currency",
                "account_name",
                "account_value",
            ]
            key_report_map = {"annualReports": "A", "quarterlyReports": "Q"}

            data_annual = self.wrangle_json(
                symbol,
                data_json,
                "annualReports",
                key_report_map,
                self.accounts,
                final_cols,
            )
            data_quarter = self.wrangle_json(
                symbol,
                data_json,
                "quarterlyReports",
                key_report_map,
                self.accounts,
                final_cols,
            )
            data = data_annual.append(data_quarter)
            data["lud"] = datetime.now()
            data.drop_duplicates(subset=self.primary_keys, inplace=True)
            return data

        except Exception as e:
            print(f"Download failed for {symbol}. \nurl: {url}")
            print(e)
            return None

    def wrangle_json(self, symbol, data_json, key_report, key_report_map, accounts, final_cols):
        data = pd.DataFrame()

        if key_report in data_json:
            for report in data_json[key_report]:
                data_report_lst = [
                    [k, int(float(v))]
                    for k, v in report.items()
                    if k in accounts and v != "None" and utils.is_number(v)
                ]
                currency = report["reportedCurrency"]
                fiscal_date = report["fiscalDateEnding"]
                data_report = pd.DataFrame(
                    data_report_lst, columns=["account_name", "account_value"]
                )
                data_report["symbol"] = symbol
                data_report["report_type"] = key_report_map[key_report]
                data_report["report_date"] = fiscal_date
                if len(currency) <= 3:
                    data_report["currency"] = currency
                else:
                    # Includes case when currency = 'None'
                    data_report["currency"] = ""
                data_report = data_report[final_cols]
                data = data.append(data_report)

        return data

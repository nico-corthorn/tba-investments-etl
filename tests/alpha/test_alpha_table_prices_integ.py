# tests/integration/test_alpha_prices_integration.py

from datetime import datetime

import pytest

from tbainvestetl.alpha import api, table


@pytest.mark.integration
class TestAlphaTablePricesIntegration:
    @pytest.mark.parametrize(
        "symbol",
        [
            "AAPL",
            "MSFT",
        ],
    )
    def test_prices_alpha_update(self, symbol, api_key, sql_params, sql, last_business_date):
        """Test updating price data for a single symbol"""
        # Initialize scraper and price table
        alpha_scraper = api.AlphaScraper(api_key=api_key)
        prices_keys = ["symbol", "date"]
        alpha_prices = table.AlphaTablePrices(
            "prices_alpha", prices_keys, alpha_scraper, sql_params=sql_params
        )

        # Update prices
        print(f"Updating prices for {symbol}")
        alpha_prices.update(symbol, "compact")

        # Validate update
        query = f"select max(date) max_date from prices_alpha where symbol = '{symbol}'"
        results = sql.select_query(query)
        max_date: datetime.date = results.iloc[0]["max_date"]

        # Assert max date in table is at least as recent as last business date
        assert (
            max_date >= last_business_date
        ), f"Max date {max_date} should be >= last business date {last_business_date}"

    @pytest.mark.parametrize(
        "symbol",
        [
            "AMZN",
            "IBM",
        ],
    )
    def test_prices_alpha_monthly_update(
        self, symbol, api_key, sql_params, sql, last_business_date
    ):
        """Test updating monthly price data for a single symbol"""
        # Make sure daily prices are up to date
        alpha_scraper = api.AlphaScraper(api_key=api_key)
        prices_keys = ["symbol", "date"]
        alpha_prices = table.AlphaTablePrices(
            "prices_alpha", prices_keys, alpha_scraper, sql_params=sql_params
        )
        print(f"Updating daily prices for {symbol}")
        alpha_prices.update(symbol, "compact")

        # Update monthly values
        alpha_prices_monthly = table.AlphaTablePricesMonthly(
            "prices_alpha_monthly", sql_params=sql_params
        )
        print(f"Updating monthly prices for {symbol}")
        alpha_prices_monthly.update(symbol)

        # Validate specific columns exist and have proper values
        columns_query = f"""
        SELECT *
        FROM prices_alpha_monthly 
        WHERE symbol = '{symbol}'
        ORDER BY date DESC
        LIMIT 1
        """
        latest_record = sql.select_query(columns_query).iloc[0]
        required_columns = [
            "symbol",
            "date",
            "open",
            "high",
            "low",
            "close",
            "adjusted_close",
            "monthly_volume",
            "monthly_return",
            "monthly_return_std",
            "day_count",
        ]

        # Assertions
        assert latest_record["date"] >= last_business_date
        assert latest_record["day_count"] > 0
        assert latest_record["monthly_return"] >= -1
        for col in required_columns:
            assert col in latest_record.index, f"Missing required column: {col}"
            assert not latest_record[col] is None, f"Value in {col} should not be null"

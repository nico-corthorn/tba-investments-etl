from datetime import date
from unittest.mock import Mock

import pandas as pd
import pytest

from tbainvestetl.alpha.api import AlphaScraper
from tbainvestetl.alpha.table import AlphaTablePrices
from tbainvestetl.domain_models.io import SQLParams


# Fixtures
@pytest.fixture
def mock_scraper():
    return Mock(spec=AlphaScraper)


@pytest.fixture
def mock_sql():
    return Mock()


@pytest.fixture
def price_table(mock_scraper, mock_sql, sql_params: SQLParams):
    table = AlphaTablePrices(
        table_name="prices_alpha",
        primary_keys=["symbol", "date"],
        scraper=mock_scraper,
        sql_params=sql_params,
    )
    table.sql = mock_sql
    return table


@pytest.fixture
def sample_api_prices():
    """Create a sample DataFrame that matches the structure expected by the API"""
    df = pd.DataFrame(
        {
            "symbol": ["AAPL"] * 3,
            "date": [date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3)],
            "close": [100.0, 101.0, 102.0],
            "adjusted_close": [100.0, 101.0, 102.0],
            "dividend_amount": [0.0, 0.0, 0.0],
            "split_coefficient": [1.0, 1.0, 1.0],
        }
    )
    # Ensure correct column order and data types
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df[
        [
            "symbol",
            "date",
            "close",
            "adjusted_close",
            "dividend_amount",
            "split_coefficient",
        ]
    ]
    return df


@pytest.fixture
def sample_db_prices():
    return pd.DataFrame(
        {
            "symbol": ["AAPL"] * 2,
            "date": [date(2024, 1, 1), date(2024, 1, 2)],
            "close": [100.0, 101.0],
            "adjusted_close": [100.0, 101.0],
            "dividend_amount": [0.0, 0.0],
            "split_coefficient": [1.0, 1.0],
        }
    )


# Unit Tests
class TestAlphaTablePrices:
    def test_get_api_data_success(self, price_table, mock_scraper):
        """Test successful API data retrieval"""
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "Time Series (Daily)": {
                "2024-01-02": {
                    "1. open": "100.0",
                    "2. high": "101.0",
                    "3. low": "99.0",
                    "4. close": "100.5",
                    "5. adjusted_close": "100.5",
                    "6. volume": "1000000",
                    "7. dividend_amount": "0.0",
                    "8. split_coefficient": "1.0",
                }
            }
        }
        mock_scraper.hit_api.return_value = mock_response

        # Test
        result = price_table.get_api_data("AAPL", size="compact")

        # Assertions
        assert result is not None
        assert len(result) == 1
        assert result.symbol.iloc[0] == "AAPL"
        assert result.close.iloc[0] == 100.5

    def test_get_api_data_failure(self, price_table, mock_scraper):
        """Test API data retrieval failure"""
        # Mock API response with error
        mock_response = Mock()
        mock_response.json.return_value = {"Error Message": "Invalid API call"}
        mock_scraper.hit_api.return_value = mock_response

        # Test
        result = price_table.get_api_data("INVALID", size="compact")

        # Assertions
        assert result is None

    def test_get_api_prices_to_upload_full_history(self, price_table, sample_api_prices):
        """Test logic for determining what data needs to be uploaded - full history case"""
        # Create empty DataFrame with same columns as api_prices
        db_prices = pd.DataFrame(
            columns=[
                "symbol",
                "date",
                "close",
                "adjusted_close",
                "dividend_amount",
                "split_coefficient",
            ]
        )

        # Test
        (
            should_upload,
            clean_db_table,
            prices_to_upload,
        ) = price_table.get_api_prices_to_upload(sample_api_prices, db_prices, "full")

        # Assertions
        assert should_upload is True
        assert clean_db_table is True
        assert len(prices_to_upload) == len(sample_api_prices)

    def test_get_api_prices_to_upload_partial_update(
        self, price_table, sample_api_prices, sample_db_prices
    ):
        """Test logic for determining what data needs to be uploaded - partial update case"""
        # Test
        (
            should_upload,
            clean_db_table,
            prices_to_upload,
        ) = price_table.get_api_prices_to_upload(sample_api_prices, sample_db_prices, "compact")

        # Assertions
        assert should_upload is True
        assert clean_db_table is False
        assert len(prices_to_upload) == 1  # Only one new date to upload

    @pytest.mark.parametrize(
        "symbol,size", [("AAPL", "compact"), ("MSFT", "full"), ("GOOGL", "compact")]
    )
    def test_update_method(self, price_table, mock_scraper, symbol, size):
        """Test update method with different symbols and sizes"""
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "Time Series (Daily)": {
                "2024-01-02": {
                    "1. open": "100.0",
                    "2. high": "101.0",
                    "3. low": "99.0",
                    "4. close": "100.5",
                    "5. adjusted_close": "100.5",
                    "6. volume": "1000000",
                    "7. dividend_amount": "0.0",
                    "8. split_coefficient": "1.0",
                }
            }
        }
        mock_scraper.hit_api.return_value = mock_response

        # Mock the database response with an empty DataFrame with correct structure
        db_prices = pd.DataFrame(
            columns=[
                "symbol",
                "date",
                "open",
                "high",
                "low",
                "close",
                "adjusted_close",
                "volume",
                "dividend_amount",
                "split_coefficient",
                "lud",
            ]
        )
        price_table.sql.select_query.return_value = db_prices

        # Execute update
        price_table.update(symbol, size)

        # Verify API was called with correct parameters
        # mock_scraper.hit_api.assert_called_once()
        call_args = mock_scraper.hit_api.call_args[1]
        assert call_args["symbol"] == symbol
        assert call_args["size"] == "full"  # If db has no data, it should fetch full history

        # Verify database operations
        assert price_table.sql.upload_df_chunks.called, "Data should be uploaded to database"

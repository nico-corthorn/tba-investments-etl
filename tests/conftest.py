# tests/conftest.py

import functools
import re
from ast import literal_eval
from datetime import datetime
from typing import Any

import pytest
from _pytest.config import Config
from pytz import timezone

from tbainvestetl.domain_models.io import SQLParams, convert_dict_to_sql_params
from tbainvestetl.utils import aws, date_utils, sql_manager

# Set of fixture names that contain sensitive data
SENSITIVE_FIXTURES = {"api_key", "sql_params", "sql"}


class SensitiveDataProtector:
    """Class to manage protection of sensitive fixture data"""

    def __init__(self):
        self.sensitive_fixtures = SENSITIVE_FIXTURES
        self.replacement_text = "[REDACTED]"

    def is_sensitive_fixture(self, name: str) -> bool:
        """Check if a fixture name is marked as sensitive"""
        return name in self.sensitive_fixtures

    def redact_value(self, _value: Any) -> str:
        """Return a redacted representation of a value"""
        return self.replacement_text


def pytest_configure(config: Config) -> None:
    """Register the custom marker and configure the plugin"""
    config.addinivalue_line(
        "markers",
        "sensitive: mark fixture as containing sensitive data that should not be logged",
    )


@pytest.fixture
def sensitive_data_protector():
    """Fixture to provide access to the sensitive data protector"""
    return SensitiveDataProtector()


def sensitive_fixture(func):
    """Decorator to mark fixtures as sensitive and wrap their values"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        # Mark the fixture function as sensitive
        setattr(func, "_is_sensitive", True)
        return result

    return wrapper


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):  # pylint: disable=unused-argument
    """Hook to modify test reports and remove sensitive data"""
    outcome = yield
    report = outcome.get_result()

    if report.longrepr:
        protector = SensitiveDataProtector()

        # Convert longrepr to string if it isn't already
        longrepr_str = str(report.longrepr)

        # Redact sensitive fixture values
        for fixture_name in protector.sensitive_fixtures:
            if fixture_name in longrepr_str:
                # Use regex to find and replace fixture values in the output
                pattern = rf"{fixture_name}=.*?(?=\s|$|\n|\))"
                longrepr_str = re.sub(
                    pattern,
                    f"{fixture_name}={protector.replacement_text}",
                    longrepr_str,
                )

        # Update the report with sanitized output
        if hasattr(report.longrepr, "reprcrash"):
            report.longrepr.reprcrash.message = longrepr_str
        else:
            report.longrepr = longrepr_str


# Updated fixtures using the sensitive_fixture decorator
@pytest.fixture(scope="session")
@sensitive_fixture
def api_key():
    """Fixture to get API key from AWS Secrets"""
    try:
        return literal_eval(aws.get_secret("prod/AlphaApi/key"))["ALPHAVANTAGE_API_KEY"]
    except Exception as e:
        print(f"Failed to get API key: {e}. Returning demo")
        return "demo"


@pytest.fixture(scope="session")
@sensitive_fixture
def sql_params() -> SQLParams:
    """Fixture to get database credentials from AWS Secrets"""
    db_credentials = literal_eval(aws.get_secret("prod/awsportfolio/key"))
    return convert_dict_to_sql_params(db_credentials)


@pytest.fixture
def sql_params_mock():
    return SQLParams(
        dbname="test_db", username="test_user", password="test_pass", host="localhost", port=5432
    )


@pytest.fixture(scope="session")
@sensitive_fixture
def sql(sql_params: SQLParams):
    """Fixture to create SQL manager"""
    return sql_manager.ManagerSQL(sql_params)


@pytest.fixture(scope="session")
def last_business_date():
    """Fixture to get last business date"""
    asof = datetime.now().astimezone(timezone("US/Eastern"))
    return date_utils.get_last_business_date(asof=asof)

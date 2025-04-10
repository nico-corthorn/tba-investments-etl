import json
from ast import literal_eval

from tbainvestetl.alpha import api, table
from tbainvestetl.domain_models.io import convert_dict_to_sql_params
from tbainvestetl.utils import aws


def lambda_handler(event, context):  # pylint: disable=unused-argument
    """Update accounting tables"""
    print("event", event)

    # Example
    # {'symbols': 'AMZN,AAPL,MSFT'}

    # Gather parameters
    symbols = event["symbols"].split(",") if "symbols" in event else []
    print(f"symbols = {symbols}")

    # Decrypts secret using the associated KMS key.
    sql_params = convert_dict_to_sql_params(literal_eval(aws.get_secret("prod/awsportfolio/key")))
    api_key = literal_eval(aws.get_secret("prod/AlphaApi/key"))["ALPHAVANTAGE_API_KEY"]

    alpha_scraper = api.AlphaScraper(api_key=api_key)
    accounting_keys = [
        "symbol",
        "report_type",
        "report_date",
        "currency",
        "account_name",
    ]
    balance_accounts = ["totalAssets", "commonStock", "commonStockSharesOutstanding"]
    alpha_balance = table.AlphaTableAccounting(
        "balance_alpha",
        "BALANCE_SHEET",
        accounting_keys,
        alpha_scraper,
        balance_accounts,
        sql_params=sql_params,
    )
    income_accounts = ["netIncome"]
    alpha_income = table.AlphaTableAccounting(
        "income_alpha",
        "INCOME_STATEMENT",
        accounting_keys,
        alpha_scraper,
        income_accounts,
        sql_params=sql_params,
    )

    if symbols:
        print("Update balance sheet")
        alpha_balance.update_list(symbols)

        print("Update income statement")
        alpha_income.update_list(symbols)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": f"Accounting updated for symbols = {symbols}",
            }
        ),
    }

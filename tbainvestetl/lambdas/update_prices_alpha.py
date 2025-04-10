import json
from ast import literal_eval

from tbainvestetl.alpha import api, table
from tbainvestetl.domain_models.io import convert_dict_to_sql_params
from tbainvestetl.utils import aws


def lambda_handler(event, context):  # pylint: disable=unused-argument
    """Update prices_alpha for symbols given in event."""
    print("event", event)

    # Example
    # {'size': 'compact', 'symbols': 'AMZN,AAPL,MSFT'}

    # Gather parameters
    size = event.get("size", "full")
    symbols = event["symbols"].split(",") if "symbols" in event else []
    print(f"size = {size}")
    print(f"symbols = {symbols}")

    # Decrypts secret using the associated KMS key.
    sql_params = convert_dict_to_sql_params(literal_eval(aws.get_secret("prod/awsportfolio/key")))
    api_key = literal_eval(aws.get_secret("prod/AlphaApi/key"))["ALPHAVANTAGE_API_KEY"]

    alpha_scraper = api.AlphaScraper(api_key=api_key, wait=False)
    prices_keys = ["symbol", "date"]
    alpha_prices = table.AlphaTablePrices(
        "prices_alpha", prices_keys, alpha_scraper, sql_params=sql_params
    )

    if symbols:
        alpha_prices.update_list(symbols, size=size)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": f"Daily prices updated for symbols = {symbols}, size = {size}",
            }
        ),
        "symbols": ",".join(symbols),
        "size": size,
    }

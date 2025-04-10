from ast import literal_eval

import numpy as np
import pandas as pd

from tbainvestetl.alpha import api, table
from tbainvestetl.domain_models.io import convert_dict_to_sql_params
from tbainvestetl.utils import aws, utils


def lambda_handler(event, context):  # pylint: disable=unused-argument
    """Get assets"""
    print("event", event)

    # Example
    # {"ref_table": "prices_alpha"}

    # Inputs
    assert "ref_table" in event
    ref_table = event["ref_table"]
    validate = utils.str2bool(event.get("validate", "false"))
    asset_types = event.get("asset_types", "Stock").split(",")
    max_assets_in_batch = int(event.get("max_assets_in_batch", 75 * 60))
    n_lists_in_batch = int(event.get("n_lists_in_batch", 10))
    size = event.get("size", "full")
    print(f"ref_table = {ref_table}")
    print(f"validate = {validate}")
    print(f"asset_types = {asset_types}")
    print(f"max_assets_in_batch = {max_assets_in_batch}")
    print(f"n_lists_in_batch = {n_lists_in_batch}")
    print(f"size = {size}")

    # Decrypts secret using the associated KMS key.
    sql_params = convert_dict_to_sql_params(literal_eval(aws.get_secret("prod/awsportfolio/key")))
    api_key = literal_eval(aws.get_secret("prod/AlphaApi/key"))["ALPHAVANTAGE_API_KEY"]

    alpha_scraper = api.AlphaScraper(api_key=api_key)

    assets = pd.DataFrame()
    if ref_table == "prices_alpha":
        keys = ["symbol", "date"]
        alpha_prices = table.AlphaTablePrices(ref_table, keys, alpha_scraper, sql_params=sql_params)
        assets = alpha_prices.get_assets(validate, asset_types)
    else:
        accounting_keys = [
            "symbol",
            "report_type",
            "report_date",
            "currency",
            "account_name",
        ]
        balance_accounts = [
            "totalAssets",
            "commonStock",
            "commonStockSharesOutstanding",
        ]
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
        if ref_table == "balance_alpha":
            assets = alpha_balance.get_assets(validate, asset_types)
        elif ref_table == "income_alpha":
            assets = alpha_income.get_assets(validate, asset_types)
        elif ref_table == "accounting":
            assets_balance = alpha_balance.get_assets(validate, asset_types)
            assets_income = alpha_income.get_assets(validate, asset_types)
            assets = list(set(assets_balance.symbol).union(set(assets_income.symbol)))
            assets.sort()

    assets_sublists = []
    if assets.shape[0] > 0:
        total_batches = len(range(0, len(assets), max_assets_in_batch))
        for i, batch_start in enumerate(range(0, len(assets), max_assets_in_batch)):
            symbols_batch: pd.Series = assets.loc[
                batch_start : batch_start + max_assets_in_batch - 1
            ].symbol
            partition_batch = np.array_split(symbols_batch, n_lists_in_batch)
            is_last_batch = i == total_batches - 1
            assets_sublists.append(
                {
                    "batch": [
                        {"symbols": ",".join(list(sublist)), "size": size}
                        for sublist in partition_batch
                    ],
                    "is_last_batch": is_last_batch,
                }
            )

    return {
        "statusCode": 200,
        "body": f"Returning {len(assets_sublists)} batches with {n_lists_in_batch} sublists each.",
        "assets": assets_sublists,
    }

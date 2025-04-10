import json
from ast import literal_eval

from tbainvestetl.alpha import api, table
from tbainvestetl.consolidation import merge
from tbainvestetl.domain_models.io import convert_dict_to_sql_params
from tbainvestetl.utils import aws


def lambda_handler(event, context):  # pylint: disable=unused-argument
    """Update assets table"""

    # Decrypts secret using the associated KMS key.
    sql_params = convert_dict_to_sql_params(literal_eval(aws.get_secret("prod/awsportfolio/key")))
    api_key = literal_eval(aws.get_secret("prod/AlphaApi/key"))["ALPHAVANTAGE_API_KEY"]

    alpha_scraper = api.AlphaScraper(api_key=api_key)
    alpha_assets = table.AlphaTableAssets(
        "assets_alpha",
        [],
        alpha_scraper,
        sql_params=sql_params,
    )
    alpha_assets.update_all()

    merge.merge_alpha_and_wrds_assets(sql_params=sql_params)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "assets updated",
            }
        ),
    }

import json
from ast import literal_eval

from tbainvestetl.domain_models.io import convert_dict_to_sql_params
from tbainvestetl.nyt.nyt_link import NytNewsLinker
from tbainvestetl.utils import aws


def lambda_handler(event, context):  # pylint: disable=unused-argument
    """Update NYT articles."""
    print("event", event)

    # Example
    # {'org_to_asset_table': 'nyt_org_to_asset', 'news_to_asset_table': 'nyt_news_to_asset'}

    # Gather parameters
    org_to_asset_table = event.get("org_to_asset_table", "nyt_org_to_asset")
    news_to_asset_table = event.get("news_to_asset_table", "nyt_news_to_asset")
    print(f"org_to_asset_table = {org_to_asset_table}")
    print(f"news_to_asset_table = {news_to_asset_table}")

    # Decrypts secret using the associated KMS key.
    sql_params = convert_dict_to_sql_params(literal_eval(aws.get_secret("prod/awsportfolio/key")))

    # Update NYT articles
    nyt_linker = NytNewsLinker(org_to_asset_table, news_to_asset_table, sql_params)
    nyt_linker.update_news_links()

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "New York Times article to asset links updated.",
            }
        ),
    }

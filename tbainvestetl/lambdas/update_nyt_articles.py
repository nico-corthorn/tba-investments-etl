import json
from ast import literal_eval

from tbainvestetl.domain_models.io import convert_dict_to_sql_params
from tbainvestetl.nyt.nyt_scrape import NytNewsScraper
from tbainvestetl.utils import aws, utils


def lambda_handler(event, context):  # pylint: disable=unused-argument
    """Update NYT articles."""
    print("event", event)

    # Example
    # {'table_name': 'nyt_archive', 'year_start': 2001, 'clean_table': 'False'}

    # Gather parameters
    table_name = event.get("table_name", "nyt_archive")
    year_start = int(event.get("year_start", 2001))
    clean_table = utils.str2bool(str(event.get("clean_table", False)))
    verbose = utils.str2bool(str(event.get("verbose", False)))
    print(f"table_name = {table_name}")
    print(f"year_start = {year_start}")
    print(f"clean_table = {clean_table}")
    print(f"verbose = {verbose}")

    # Decrypts secret using the associated KMS key.
    sql_params = convert_dict_to_sql_params(literal_eval(aws.get_secret("prod/awsportfolio/key")))
    api_key = literal_eval(aws.get_secret("prod/NYTApi/key"))["NYT_API_KEY"]

    # Update NYT articles
    nyt_scraper = NytNewsScraper(table_name, api_key, sql_params)
    nyt_scraper.nyt_upload_all_articles(year_start, clean_table, verbose)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "New York Times articles updated.",
            }
        ),
    }

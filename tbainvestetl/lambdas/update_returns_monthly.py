import json
from ast import literal_eval

from tbainvestetl.consolidation import merge
from tbainvestetl.domain_models.io import convert_dict_to_sql_params
from tbainvestetl.utils import aws


def lambda_handler(event, context):  # pylint: disable=unused-argument
    """Update returns_monthly table"""

    # Decrypts secret using the associated KMS key.
    sql_params = convert_dict_to_sql_params(literal_eval(aws.get_secret("prod/awsportfolio/key")))

    # Merge and update returns_monthly
    merge.merge_alpha_and_wrds_returns(sql_params=sql_params)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "returns_monthly updated",
            }
        ),
    }

import boto3
from botocore.exceptions import ClientError


def get_secret(secret_name, region_name="us-east-2"):
    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=region_name)

    try:
        secret_response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        raise e

    return secret_response["SecretString"]


def get_s3_file(s3_path: str) -> str:
    """
    Read a file from S3.
    Args:
        s3_path: Path to file in format 'prefix/path/to/file'
    Returns:
        str: Contents of the file
    """
    # Get the default bucket from SageMaker session
    session = boto3.Session()
    account_id = session.client("sts").get_caller_identity().get("Account")
    region = session.region_name
    default_bucket = f"sagemaker-{region}-{account_id}"

    # Create S3 client
    s3_client = session.client("s3")

    # Get the file
    response = s3_client.get_object(Bucket=default_bucket, Key=s3_path)
    return response["Body"].read().decode("utf-8")

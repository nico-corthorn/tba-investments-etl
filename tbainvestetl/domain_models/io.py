from dataclasses import dataclass


@dataclass
class SQLParams:
    """Credentials to an RDS database."""

    dbname: str
    username: str
    password: str
    host: str
    port: int


def convert_dict_to_sql_params(db_credentials: dict) -> SQLParams:
    filtered_db_credentials = {
        key: db_credentials[key] for key in SQLParams.__annotations__ if key in db_credentials
    }
    sql_params = SQLParams(**filtered_db_credentials)
    return sql_params

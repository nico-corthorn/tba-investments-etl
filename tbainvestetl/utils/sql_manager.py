from typing import Optional

import pandas as pd
import psycopg2
from sqlalchemy import create_engine

from tbainvestetl.domain_models.io import SQLParams


class ManagerSQL:
    def __init__(self, sql_params: SQLParams):
        # Basic db parameters
        db_name = sql_params.dbname
        user = sql_params.username
        password = sql_params.password
        host = sql_params.host
        port = sql_params.port

        # Connexion for downloading data
        self.cnxn = psycopg2.connect(
            database=db_name, user=user, password=password, host=host, port=port
        )
        self.cursor = self.cnxn.cursor()

        # Connexion for uploading data
        self.db_url = "postgresql://" + user + ":" + password + "@" + host + "/" + db_name
        self.con = create_engine(self.db_url)

    def select(self, table):
        """Returns table as DataFrame."""
        sql = f"select * from {table}"
        df = pd.read_sql(sql, self.cnxn)
        return df

    def select_query(self, query):
        """Returns query output as DataFrame."""
        df = pd.read_sql(query, self.cnxn)
        return df

    def select_column_list(self, column, table):
        """Returns column values as list."""
        sql = f"select {column} from {table} order by {column}"
        df = pd.read_sql(sql, self.cnxn)
        lst = list(df[column])
        return lst

    def select_distinct_column_list(self, column, table):
        """Returns unique values of column as list."""
        sql = f"select distinct {column} from {table} order by {column}"
        df = pd.read_sql(sql, self.cnxn)
        lst = list(df[column])
        return lst

    def select_distinct_indexed_column_list(self, column, table):
        sql = f"""
            WITH RECURSIVE t AS (
            SELECT MIN({column}) AS {column} FROM {table}
            UNION ALL
            SELECT (SELECT MIN({column}) FROM {table} WHERE {column} > t.{column})
            FROM t WHERE t.{column} IS NOT NULL
            )
            SELECT {column} FROM t WHERE {column} IS NOT NULL
            UNION ALL
            SELECT NULL WHERE EXISTS(SELECT 1 FROM {table} WHERE {column} IS NULL)
            """
        df = pd.read_sql(sql, self.cnxn)
        lst = list(df[column])
        return lst

    def select_as_dictionary(self, column_key, column_value, table):
        """Return dictionary column_key: column_value, column_key must have unique values."""
        sql = f"select {column_key}, {column_value} from {table}"
        df = pd.read_sql(sql, self.cnxn)
        assert df[column_key].is_unique, f"Column {column_key} doesn't have unique values."
        return df.set_index(column_key).to_dict()[column_value]

    def upload_df(self, table, df, chunk_size=1):
        """Uploads data frame to table. Appends information."""
        df.to_sql(
            name=table,
            con=self.con,
            if_exists="append",
            index=False,
            chunksize=chunk_size,
        )

    def upload_df_sequential(self, table, df):
        """Uploads data frame to table. Appends information."""
        for i in range(df.shape[0]):
            df.loc[[df.index[i]], :].to_sql(
                name=table, con=self.con, if_exists="append", index=False
            )

    def upload_df_chunks(self, table, df, chunk_size=1000):
        """
        Uploads data frame to table. Appends information.
        DataFrame index must have been reseted previously.
        """
        ind = list(df.index)
        chunks = [ind[i : i + chunk_size] for i in range(0, len(ind), chunk_size)]
        for chunk in chunks:
            df.loc[chunk, :].to_sql(name=table, con=self.con, if_exists="append", index=False)

    def query(self, query: str, params: Optional[dict] = None):
        """Execute a query with optional named parameters."""
        try:
            with self.cnxn.cursor() as cursor:
                cursor.execute(query, params)
                self.cnxn.commit()
        except Exception as e:
            self.cnxn.rollback()
            raise e

    def clean_table(self, table):
        """Delete all information from the table."""
        self.cursor.execute(f"delete from {table}")
        self.cnxn.commit()

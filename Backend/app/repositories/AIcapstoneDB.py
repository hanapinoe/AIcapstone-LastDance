import mysql.connector
from mysql.connector import pooling
import os
from dotenv import load_dotenv
import json
from typing import Dict, Optional, Tuple


load_dotenv()


_MYSQL_POOL: Optional[pooling.MySQLConnectionPool] = None


def _get_mysql_pool() -> pooling.MySQLConnectionPool:
    global _MYSQL_POOL
    if _MYSQL_POOL is not None:
        return _MYSQL_POOL

    host = os.getenv("DB_HOST")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    database = os.getenv("DB_NAME")
    port = int(os.getenv("DB_PORT", "3306"))

    # Pool helps reduce latency by avoiding reconnecting for every request.
    _MYSQL_POOL = pooling.MySQLConnectionPool(
        pool_name="capstone_pool",
        pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
        pool_reset_session=True,
        host=host,
        user=user,
        password=password,
        database=database,
        port=port,
        connection_timeout=int(os.getenv("DB_CONNECT_TIMEOUT", "10")),
    )
    return _MYSQL_POOL


class DBConnection:
    """
    Database connection class.
    Args:
        host (str): Database host.
        user (str): Database user.
        password (str): Database password.
        database (str): Database name.
    """
    # Connect to the database

    def __init__(self, host, user, password, database):
        self.host = host or os.getenv("DB_HOST")
        self.user = user or os.getenv("DB_USER")
        self.password = password or os.getenv("DB_PASSWORD")
        self.database = database or os.getenv("DB_NAME")

    def get_connection(self):
        """
        Establish and return a database connection.
        Returns:
            connection: Database connection object.
        """
        try:
            # Prefer pooled connections to reduce per-request latency.
            pool = _get_mysql_pool()
            return pool.get_connection()
        except mysql.connector.Error as err:
            raise Exception(f"Connection Error: {err}")


class InteractDB(DBConnection):
    """
    Database interaction class for inserting and querying data.
    Args:
        host (str): Database host.
        user (str): Database user.
        password (str): Database password.
        database (str): Database name.
    """

    _schema_has_column_cache: Dict[Tuple[str, str], bool] = {}

    def __init__(self, host=None, user=None, password=None, database=None):
        super().__init__(host, user, password, database)
        self.dbCon = DBConnection(host, user, password, database)

    def _table_has_column(self, table: str, column: str) -> bool:
        cache_key = (table, column)
        cache = self.__class__._schema_has_column_cache
        if cache_key in cache:
            return bool(cache[cache_key])

        try:
            connection = self.dbCon.get_connection()
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT 1
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = %s
                  AND COLUMN_NAME = %s
                LIMIT 1
                """,
                (table, column),
            )
            found = cursor.fetchone() is not None
            cursor.close()
            connection.close()
            cache[cache_key] = bool(found)
            return bool(found)
        except mysql.connector.Error:
            cache[cache_key] = False
            return False

    # Insert data into a specified table
    def insert_data(self, table: str, data: dict):
        """
        Insert data into the specified table.
        Args:
            table (str): The name of the table to insert data into.
            data (dict): A dictionary containing the data to be inserted.
        Returns:
            int: The ID of the inserted row.
        """
        try:
            connection = self.dbCon.get_connection()
            cursor = connection.cursor()
            if table == "users":
                if "id" in data and data["id"] is not None:
                    sql = f"INSERT INTO {table} (id, username, email) VALUES (%s, %s, %s)"
                    values = (data["id"], data["username"], data["email"])
                else:
                    sql = f"INSERT INTO {table} (username, email) VALUES (%s, %s)"
                    values = (data["username"], data["email"])
            elif table == "requests":
                sql = f"INSERT INTO {table} (user_id, original_query, extracted_fields) VALUES (%s, %s, %s)"
                values = (
                    data['user_id'],
                    data['original_query'],
                    json.dumps(data['extracted_fields'])
                )
            elif table == "recommendations":
                sql = f"""INSERT INTO {table}
                    (request_id, dish_name, dish_type, ingredient,
                    option_json, recommended_options, score, explaination)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
                values = (
                    data['request_id'],
                    data['dish_name'],
                    data['dish_type'],
                    data['ingredient'],
                    json.dumps(data['option_json']),
                    json.dumps(data['recommended_options']),
                    data.get('score'),
                    data.get('explaination')
                )
            else:
                raise Exception("Unknown table name")

            cursor.execute(sql, values)
            inserted_id = cursor.lastrowid
            connection.commit()
            cursor.close()
            connection.close()
            return inserted_id
        except mysql.connector.Error as err:
            print(f"Connection Error: {err}")
            return False
        except KeyError as e:
            print(f"Missing field: {e}")
            return False

    # Query data from a specified table
    def db_query_table(self, column, table):
        """
        Query data from the specified table.
        Args:
            column (str): The column to retrieve.
            table (str): The table to query from.
        Returns:
            list: A list of tuples containing the query results.
        """
        try:
            connection = self.dbCon.get_connection()
            cursor = connection.cursor()
            cursor.execute(
                """SELECT {column} FROM {table}""".format(
                    column=column, table=table)
            )
            results = cursor.fetchall()
            cursor.close()
            connection.close()
            return results
        except mysql.connector.Error as err:
            return f"Error: {err}"

    def user_exists(self, user_id: int) -> bool:
        try:
            connection = self.dbCon.get_connection()
            cursor = connection.cursor()
            cursor.execute(
                "SELECT 1 FROM users WHERE id = %s LIMIT 1", (user_id,))
            row = cursor.fetchone()
            cursor.close()
            connection.close()
            return row is not None
        except mysql.connector.Error:
            return False

    def get_user_id_by_email(self, email: str) -> Optional[int]:
        try:
            connection = self.dbCon.get_connection()
            cursor = connection.cursor()
            cursor.execute(
                "SELECT id FROM users WHERE email = %s LIMIT 1", (email,))
            row = cursor.fetchone()
            cursor.close()
            connection.close()
            if row and isinstance(row, (tuple, list)) and isinstance(row[0], (int, str)):
                try:
                    return int(row[0])
                except (ValueError, TypeError):
                    return None
            return None
        except mysql.connector.Error:
            return None

    def get_user_id(self, username: str, email: str) -> Optional[int]:
        try:
            connection = self.dbCon.get_connection()
            cursor = connection.cursor()
            cursor.execute(
                "SELECT id FROM users WHERE username = %s AND email = %s LIMIT 1",
                (username, email),
            )
            row = cursor.fetchone()
            cursor.close()
            connection.close()
            if row and isinstance(row, (tuple, list)) and isinstance(row[0], (int, str)):
                try:
                    return int(row[0])
                except (ValueError, TypeError):
                    return None
            return None
        except mysql.connector.Error:
            return None

    def get_user_id_by_username(self, username: str) -> Optional[int]:
        try:
            connection = self.dbCon.get_connection()
            cursor = connection.cursor()
            cursor.execute(
                "SELECT id FROM users WHERE username = %s LIMIT 1", (username,))
            row = cursor.fetchone()
            cursor.close()
            connection.close()
            if row and isinstance(row, (tuple, list)) and isinstance(row[0], (int, str)):
                try:
                    return int(row[0])
                except (ValueError, TypeError):
                    return None
            return None
        except mysql.connector.Error:
            return None

    def get_or_create_user(self, username: str, email: str) -> Optional[int]:
        # First try exact match (login-style identity)
        existing_exact_id = self.get_user_id(username, email)
        if existing_exact_id is not None:
            return existing_exact_id

        # Enforce register-style uniqueness: if either username OR email is already taken
        # by a different record, treat as conflict (caller decides how to respond).
        existing_by_username = self.get_user_id_by_username(username)
        existing_by_email = self.get_user_id_by_email(email)
        if existing_by_username is not None or existing_by_email is not None:
            return None

        inserted_id = self.insert_data(
            "users", {"username": username, "email": email})
        return None if inserted_id is False else inserted_id

    def get_user_history(self, user_id: int):
        """Return merged requests + recommendations for a single user."""
        try:
            rec_has_created_at = self._table_has_column(
                "recommendations", "created_at")
            time_expr = "rec.created_at" if rec_has_created_at else "rec.id"
            order_expr = f"{time_expr} DESC, r.id DESC"

            connection = self.dbCon.get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT
                    r.original_query AS request,
                    rec.dish_name AS dish_name,
                    rec.recommended_options AS chosen_option,
                    rec.explaination AS explaination,
                    {time_expr} AS time
                FROM requests r
                LEFT JOIN recommendations rec
                    ON rec.request_id = r.id
                WHERE r.user_id = %s
                ORDER BY {order_expr}
                """.format(time_expr=time_expr, order_expr=order_expr),
                (user_id,),
            )
            rows = cursor.fetchall()
            cursor.close()
            connection.close()
            return rows
        except mysql.connector.Error as err:
            print(f"Connection Error: {err}")
            return []

    def get_user_requests(self, user_id: int):
        """Return request rows for a single user."""
        try:
            connection = self.dbCon.get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT *
                FROM requests
                WHERE user_id = %s
                ORDER BY id DESC
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
            cursor.close()
            connection.close()
            return rows
        except mysql.connector.Error as err:
            print(f"Connection Error: {err}")
            return []

    def get_user_recommendations(self, user_id: int):
        """Return recommendation rows for a single user (filtered via requests)."""
        try:
            rec_has_created_at = self._table_has_column(
                "recommendations", "created_at")
            order_by = "rec.created_at DESC, rec.id DESC" if rec_has_created_at else "rec.id DESC"

            connection = self.dbCon.get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT rec.*
                FROM recommendations rec
                INNER JOIN requests r
                    ON r.id = rec.request_id
                WHERE r.user_id = %s
                ORDER BY {order_by}
                """.format(order_by=order_by),
                (user_id,),
            )
            rows = cursor.fetchall()
            cursor.close()
            connection.close()
            return rows
        except mysql.connector.Error as err:
            print(f"Connection Error: {err}")
            return []

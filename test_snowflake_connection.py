
import os
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

def main():
    connection = None

    try:
        connection = snowflake.connector.connect(
            account=os.environ["SNOWFLAKE_ACCOUNT"],
            user=os.environ["SNOWFLAKE_USER"],
            password=os.environ["SNOWFLAKE_PASSWORD"],
            warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
            database=os.environ["SNOWFLAKE_DATABASE"],
            schema=os.environ["SNOWFLAKE_SCHEMA"],
        )

        cursor = connection.cursor()

        try:
            cursor.execute("""
                SELECT CURRENT_DATABASE(),
                       CURRENT_SCHEMA(),
                       CURRENT_WAREHOUSE()
            """)

            result = cursor.fetchone()
            print("Snowflake connection successful!")
            print(f"Database: {result[0]}")
            print(f"Schema: {result[1]}")
            print(f"Warehouse: {result[2]}")

            cursor.execute("""
                SELECT COUNT(*)
                FROM OPPORTUNITYLENS_DB.APP.OPPORTUNITIES
            """)

            print(f"Opportunity records: {cursor.fetchone()[0]}")

        finally:
            cursor.close()

    except Exception as error:
        print(f"Connection failed: {error}")
        raise

    finally:
        if connection is not None:
            connection.close()

if __name__ == "__main__":
    main()

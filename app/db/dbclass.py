import json
import logging
import asyncpg
import asyncio
from app.utils.logging import get_logger
from app.config import settings

class LibertyDB:
    def __init__(self):
        self.logger= get_logger("DB")

    async def connect(self):
        dsn=f"postgresql://{settings.postgres.POSTGRES_USER}:{settings.postgres.POSTGRES_PASSWORD}@{settings.postgres.POSTGRES_HOST}:{settings.postgres.PORT}/{settings.postgres.POSTGRES_DB}"
        try:
            self.pool = await asyncpg.create_pool(
            min_size=1,
            max_size=10, 
            dsn=dsn
            )
            self.logger.info("Connected to the PostgreSQL database.")
        except Exception as e:
            self.logger.error(f"Error connecting to the database: {e}")
            raise

    async def close(self):
        await self.pool.close()

    ### Execute a SQL query on DB
    async def execute_query(self, sql=None, *args):
        try:
            if sql is None:
                return None
            self.logger.info(f"Executing SQL query: {sql}")
            # Executing the SQL query 
            async with self.pool.acquire() as connection:
                result = await connection.execute(sql, *args)
                return result
        except Exception as e:
            self.logger.error(f"Error executing execute_query: {e}")

    ### Get results from the database
    async def fetch_query(self, sql=None):
        try:
            if sql is None:
                return None
            self.logger.info(f"Executing fetch SQL query: {sql}")
            # Executing the SQL query 
            async with self.pool.acquire() as connection:
                result = await connection.fetch(sql)
                return result
        except Exception as e:
            self.logger.error(f"Error executing fetch_query: {e}")

    ### Check Trigger status and insert if not present
    async def check_trigger_status(self, sql=None):
        try:
            if sql is None:
                return None
            self.logger.info(f"Executing fetch SQL query: {sql}")
            # Executing the SQL query 
            async with self.pool.acquire() as connection:
                result = await connection.fetch(sql)
                return result
        except Exception as e:
            self.logger.error(f"Error executing fetch_query: {e}")


    ### Get Trigger Time
    async def fetch_trigger_time(self):
        try:
            sql = '''
                    SELECT trigger_time FROM nifty.trigger_status
                    where date = CURRENT_DATE
                    order by ctid DESC
                    limit 1                
                ''' 
            if sql is None:
                return None
            self.logger.info(f"Fetching Trigger Time: {sql}")
            # Executing the SQL query 
            async with self.pool.acquire() as connection:
                result = await connection.fetch(sql)
                return result
        except Exception as e:
            self.logger.error(f"Error Fetching Trigger Time: {e}")

    async def update_status(self,status):
        try:
            sql =f'''
                UPDATE nifty.status
                SET status = '{status}'
                WHERE date = CURRENT_DATE
                '''
            self.logger.info(f"Updating Status to {status}.")
            # Executing the SQL query 
            async with self.pool.acquire() as connection:
                result = await connection.execute(sql)
                return True
        except Exception as e:
            self.logger.error(f"Error executing execute_query: {e}")


db = LibertyDB()
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
        dsn=f"postgresql://{settings.postgres.USER}:{settings.postgres.PASSWORD}@{settings.postgres.HOST}:{settings.postgres.PORT}/{settings.postgres.DB}"
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


db = LibertyDB()
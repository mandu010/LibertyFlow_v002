import json
import logging
import asyncpg
import asyncio
import urllib.parse

from app.utils.logging import get_logger
from app.config import settings

class LibertyDB:
    def __init__(self):
        self.logger= get_logger("DB")

    async def connect(self):
        encoded_password = urllib.parse.quote_plus(settings.postgres.POSTGRES_PASSWORD)
        dsn=f"postgresql://{settings.postgres.POSTGRES_USER}:{encoded_password}@{settings.postgres.POSTGRES_HOST}:{settings.postgres.PORT}/{settings.postgres.POSTGRES_DB}"
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
            return None

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
                    SELECT "trigger_time" FROM nifty.trigger_status
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

    async def fetch_swing_trigger_time(self,swing):
        try:
            sql = f'''
                    SELECT "{swing}" FROM nifty.trigger_status
                    where date = CURRENT_DATE
                    order by ctid DESC
                    limit 1                
                '''                 
            # Executing the SQL query 
            async with self.pool.acquire() as connection:
                result = await connection.fetch(sql)
                if result is not None:
                    return str(result[0][swing])
                else:
                    return None
        except Exception as e:
            self.logger.error(f"Error Fetching Trigger Time: {e}")            
            return None
        
    async def fetch_swing_price(self,swing):
        try:
            sql = f'''
                    SELECT "{swing}" FROM nifty.trigger_status
                    where date = CURRENT_DATE
                    order by ctid DESC
                    limit 1                
                '''                 
            # Executing the SQL query 
            async with self.pool.acquire() as connection:
                result = await connection.fetch(sql)
                if result is not None:
                    return float(result[0][swing])
                else:
                    return None
        except Exception as e:
            self.logger.error(f"Error Fetching Swing Price: {e}")
            return None
        
    async def fetch_timestamp(self,orderID):
        try:
            sql = f'''
                    SELECT timestamp FROM nifty.orders
                    where "orderID" = {orderID}
                    limit 1                
                '''                 
            # Executing the SQL query 
            async with self.pool.acquire() as connection:
                result = await connection.fetch(sql)
                if result is not None:
                    return str(result[0]['timestamp'])
                else:
                    return None
        except Exception as e:
            self.logger.error(f"Error Fetching Swing Price: {e}")
            return None


db = LibertyDB()
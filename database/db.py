import aiomysql
import os
import asyncio
import logging
from dotenv import load_dotenv

load_dotenv()

class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        """Initializes the connection pool."""
        try:
            self.pool = await aiomysql.create_pool(
                host=os.getenv("DB_HOST", "localhost"),
                port=int(os.getenv("DB_PORT", 3306)),
                user=os.getenv("DB_USER", "root"),
                password=os.getenv("DB_PASSWORD", ""),
                db=os.getenv("DB_NAME", "isfe_bot_db"),
                autocommit=True,
                cursorclass=aiomysql.DictCursor
            )
            logging.info("✅ Database connection established.")
            
            # Auto-run local init if needed (optional, simplistic migration)
            # await self.initialize_schema() 
        except Exception as e:
            logging.error(f"❌ Failed to connect to database: {e}")
            raise e

    async def close(self):
        """Closes the connection pool."""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            logging.info("Database connection closed.")

    async def execute(self, query, params=None):
        """Executes a modification query (INSERT, UPDATE, DELETE).
        Returns lastrowid for INSERT, rowcount for UPDATE/DELETE."""
        if not self.pool:
            await self.connect()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                # Return rowcount for DELETE/UPDATE, lastrowid for INSERT
                if query.strip().upper().startswith(("DELETE", "UPDATE")):
                    return cur.rowcount
                return cur.lastrowid

    async def fetchrow(self, query, params=None):
        """Fetches a single row."""
        if not self.pool:
            await self.connect()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                return await cur.fetchone()

    async def fetchall(self, query, params=None):
        """Fetches all rows."""
        if not self.pool:
            await self.connect()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                return await cur.fetchall()

    async def initialize_schema(self, schema_path="database/schema.sql"):
        """Runs the schema.sql file to create tables."""
        if not os.path.exists(schema_path):
            logging.warning(f"Schema file {schema_path} not found.")
            return

        with open(schema_path, "r") as f:
            schema = f.read()

        # Split by semicolon to execute individual statements
        statements = [s.strip() for s in schema.split(";") if s.strip()]
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                for statement in statements:
                    try:
                        await cur.execute(statement)
                    except Exception as e:
                        print(f"Error executing schema statement: {e}")

db = Database()

#!/usr/bin/env python3
"""Add nickname_preference column to player_registrations table on remote DB."""
import asyncio
import os
from dotenv import load_dotenv
import aiomysql

load_dotenv()

async def main():
    conn = await aiomysql.connect(
        host=os.getenv("REMOTE_DB_HOST"),
        port=int(os.getenv("REMOTE_DB_PORT", 3306)),
        user=os.getenv("REMOTE_DB_USER"),
        password=os.getenv("REMOTE_DB_PASSWORD"),
        db=os.getenv("REMOTE_DB_NAME"),
    )
    
    async with conn.cursor() as cur:
        try:
            await cur.execute("""
                ALTER TABLE player_registrations 
                ADD COLUMN nickname_preference ENUM('this', 'other', 'combined', 'plain') DEFAULT 'this'
            """)
            print("✅ Added nickname_preference column")
        except Exception as e:
            if "Duplicate column" in str(e):
                print("⚠️ Column already exists")
            else:
                print(f"❌ Error: {e}")
    
    conn.close()

if __name__ == "__main__":
    asyncio.run(main())

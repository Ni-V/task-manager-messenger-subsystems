import asyncio
from database.crud import AsyncORM

if __name__ == "__main__":
    asyncio.run(AsyncORM.create_table())

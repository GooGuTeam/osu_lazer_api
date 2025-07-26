import asyncio
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import create_engine, text
from app.config import settings

async def check_table():
    engine = create_engine(settings.database_url)
    async with AsyncSession(engine) as session:
        try:
            result = await session.exec(text('DESCRIBE chat_messages'))
            rows = result.fetchall()
            print('chat_messages table structure:')
            for row in rows:
                print(row)
        except Exception as e:
            print(f'Error: {e}')
            
        try:
            result = await session.exec(text("SHOW TABLES LIKE '%chat%'"))
            rows = result.fetchall()
            print('\nTables with chat in name:')
            for row in rows:
                print(row)
        except Exception as e:
            print(f'Error: {e}')

if __name__ == "__main__":
    asyncio.run(check_table())

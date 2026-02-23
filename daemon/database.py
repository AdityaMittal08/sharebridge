# daemon/database.py
"""
Asynchronous SQLite database manager for UbuntuShare.
Handles persistent storage for chat messages.
"""
import aiosqlite
import os
import json

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def init_db(self) -> None:
        """Creates the necessary tables if they don't exist."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    peer_id TEXT NOT NULL,
                    is_outgoing BOOLEAN NOT NULL,
                    content TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await db.commit()
            print(f"[Database] SQLite initialized at {self.db_path}")

    async def save_message(self, peer_id: str, is_outgoing: bool, content: str) -> None:
        """Saves a single chat message to the database."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO messages (peer_id, is_outgoing, content) VALUES (?, ?, ?)",
                (peer_id, is_outgoing, content)
            )
            await db.commit()

    async def get_chat_history(self, peer_id: str, limit: int = 50) -> str:
        """Retrieves the last N messages for a specific peer as JSON."""
        async with aiosqlite.connect(self.db_path) as db:
            query = '''
                SELECT * FROM (
                    SELECT is_outgoing, content, timestamp 
                    FROM messages 
                    WHERE peer_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ) ORDER BY timestamp ASC
            '''
            async with db.execute(query, (peer_id, limit)) as cursor:
                rows = await cursor.fetchall()
                history = [
                    {"is_outgoing": bool(row[0]), "content": row[1], "timestamp": row[2]}
                    for row in rows
                ]
                return json.dumps(history)
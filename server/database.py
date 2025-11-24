
import sqlite3
from typing import List, Optional, Tuple


class Database:

    def __init__(self, db_name: str = 'chatapp.db'):
        self.db_name = db_name
        self.db = sqlite3.connect(db_name, check_same_thread=False)
        self.cur = self.db.cursor()
        self._init_tables()

    def _init_tables(self):
        self.cur.execute('''CREATE TABLE IF NOT EXISTS messages
                   (id INTEGER PRIMARY KEY,
                    sender TEXT,
                    receiver TEXT,
                    text TEXT,
                    ts INTEGER,
                    deleted INTEGER DEFAULT 0,
                    groupchat INTEGER DEFAULT 0)''')

        self.cur.execute('''CREATE TABLE IF NOT EXISTS cleared_history
                   (user TEXT,
                    other_user TEXT,
                    cleared_at INTEGER,
                    PRIMARY KEY (user, other_user))''')
        self.db.commit()

    def insert_message(self, sender: str, receiver: str, text: str, ts: int, is_group: bool) -> int:

        self.cur.execute(
            'INSERT INTO messages(sender,receiver,text,ts,groupchat) VALUES(?,?,?,?,?)',
            (sender, receiver, text, ts, 1 if is_group else 0)
        )
        self.db.commit()
        return self.cur.lastrowid

    def delete_message(self, msg_id: str) -> bool:
        self.cur.execute('UPDATE messages SET deleted=1 WHERE id=?', (msg_id,))
        self.db.commit()
        return self.cur.rowcount > 0

    def delete_group_messages(self, group_name: str):
        self.cur.execute(
            'DELETE FROM messages WHERE receiver = ? AND groupchat = 1',
            (group_name,)
        )
        self.db.commit()

    def get_message(self, msg_id: str) -> Optional[Tuple[str, str, int]]:
        self.cur.execute('SELECT sender,receiver,groupchat FROM messages WHERE id=?', (msg_id,))
        return self.cur.fetchone()

    def clear_history(self, user: str, other_user: str, clear_ts: int):
        self.cur.execute(
            'INSERT OR REPLACE INTO cleared_history (user, other_user, cleared_at) VALUES (?, ?, ?)',
            (user, other_user, clear_ts)
        )
        self.db.commit()

    def get_cleared_timestamp(self, user: str, other_user: str) -> int:
        self.cur.execute(
            'SELECT cleared_at FROM cleared_history WHERE user = ? AND other_user = ?',
            (user, other_user)
        )
        row = self.cur.fetchone()
        return row[0] if row else 0

    def get_message_history(self, user: str, chat_with: str, limit: int, is_group: bool) -> List[Tuple]:
        cleared_at = self.get_cleared_timestamp(user, chat_with)

        if is_group:
            self.cur.execute('''SELECT id, sender, receiver, text, ts, deleted
                               FROM messages
                               WHERE groupchat = 1 AND receiver = ? AND ts > ?
                               ORDER BY ts DESC LIMIT ?''',
                            (chat_with, cleared_at, limit))
        else:
            self.cur.execute('''SELECT id, sender, receiver, text, ts, deleted
                               FROM messages
                               WHERE groupchat = 0
                                 AND ((sender = ? AND receiver = ?) OR (sender = ? AND receiver = ?))
                                 AND ts > ?
                               ORDER BY ts DESC LIMIT ?''',
                            (user, chat_with, chat_with, user, cleared_at, limit))

        return list(reversed(self.cur.fetchall()))

    def close(self):
        self.db.close()

    def __repr__(self):
        return f"Database(db_name='{self.db_name}')"

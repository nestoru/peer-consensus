import sqlite3
from datetime import datetime

class DBManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

    def initialize_table(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS responses (
                response_number INTEGER PRIMARY KEY,
                response TEXT NOT NULL,
                convergence REAL NOT NULL,
                timestamp TEXT NOT NULL
            )
        ''')
        self.conn.commit()

    def insert_response(self, response_number: int, response: str, convergence: float):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cursor.execute('''
            INSERT INTO responses (response_number, response, convergence, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (response_number, response, convergence, timestamp))
        self.conn.commit()

    def get_all_responses(self):
        self.cursor.execute('SELECT * FROM responses ORDER BY response_number ASC')
        return self.cursor.fetchall()

    def close(self):
        self.conn.close()


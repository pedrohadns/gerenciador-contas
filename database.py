import sqlite3

def get_db_connection():
    conn = sqlite3.connect('boletos.db')
    # Isso permite acessar colunas pelo nome (ex: linha['sacado'])
    conn.row_factory = sqlite3.Row 
    return conn

def init_db():
    conn = get_db_connection()
    # Cria a tabela se não existir
    conn.execute('''
        CREATE TABLE IF NOT EXISTS boletos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sacado TEXT NOT NULL,
            valor REAL NOT NULL,
            vencimento TEXT NOT NULL,
            status TEXT DEFAULT 'Pendente'
        )
    ''')
    conn.commit()
    conn.close()

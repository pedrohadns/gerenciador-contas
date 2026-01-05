import sqlite3

def get_db_connection():
    conn = sqlite3.connect('sistema_boletos.db')
    # Isso permite acessar colunas pelo nome (ex: linha['sacado'])
    conn.row_factory = sqlite3.Row 
    return conn

def init_db():
    conn = get_db_connection()
    # Cria a tabela se não existir
    conn.execute('''
                 CREATE TABLE IF NOT EXISTS usuarios (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     nome TEXT UNIQUE NOT NULL,
                     foto TEXT
                     )
                 ''')

    conn.execute('''
                 CREATE TABLE IF NOT EXISTS boletos (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     usuario_id INTEGER,
                     vencimento TEXT,
                     status TEXT DEFAULT 'Pendente',

                     empresa TEXT,
                     categoria TEXT,
                     placa TEXT,
                     descricao TEXT,

                     valor_original REAL,
                     juros REAL,
                     tipo_juros TEXT DEFAULT 'R$',
                     multa REAL,
                     valor_total REAL,

                     data_pagamento TEXT,
                     banco_pagamento TEXT,

                     numero_parcelas INTEGER,
                     total_parcelas INTEGER,

                     FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
                     )
    ''')
    conn.commit()
    conn.close()

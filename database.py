import pyodbc
import pandas as pd
import os

# Retrieves the ODBC connection string from Azure Environment Variables
# Example: Driver={ODBC Driver 18 for SQL Server};Server=tcp:yourserver.database.windows.net...
conn_str = os.getenv("AZURE_SQL_CONNECTIONSTRING")

def get_connection():
    conn_str = os.getenv("AZURE_SQL_CONNECTIONSTRING")
    if not conn_str:
        raise ValueError("AZURE_SQL_CONNECTIONSTRING not found!")
    
    try:
        return pyodbc.connect(conn_str)
    except pyodbc.Error:
        # Fallback: Try Driver 17 if Driver 18 is missing
        alt_conn_str = conn_str.replace("ODBC Driver 18", "ODBC Driver 17")
        return pyodbc.connect(alt_conn_str)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # 1. Create table if it doesn't exist (T-SQL Syntax)
    # SQL Server uses IDENTITY(1,1) for auto-incrementing primary keys
    c.execute('''
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'logs')
        CREATE TABLE logs (
            id INT IDENTITY(1,1) PRIMARY KEY,
            user_email NVARCHAR(255),
            log_date DATE,
            activity NVARCHAR(MAX),
            amount DECIMAL(18, 2),
            entity NVARCHAR(MAX),
            payment_mode NVARCHAR(MAX),
            category NVARCHAR(MAX),
            remark NVARCHAR(MAX)
        )
    ''')
    
    # 2. Check for missing columns (SQL Server version of PRAGMA)
    c.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'logs'")
    columns = [row[0] for row in c.fetchall()]
    
    if 'user_email' not in columns:
        print("Migrating database: Adding user_email column...")
        c.execute("ALTER TABLE logs ADD user_email NVARCHAR(255) DEFAULT 'local_test_user@example.com'")
    
    conn.commit()
    conn.close()

def save_entry(user_email, log_date, activity, amount, entity, mode, category, remark):
    conn = get_connection()
    c = conn.cursor()
    # SQL Server uses ? as placeholders just like SQLite
    c.execute("""
        INSERT INTO logs (user_email, log_date, activity, amount, entity, payment_mode, category, remark) 
        VALUES (?,?,?,?,?,?,?,?)
    """, (user_email, log_date, activity, amount, entity, mode, category, remark))
    conn.commit()
    conn.close()

def fetch_user_logs(user_email):
    conn = get_connection()
    query = "SELECT * FROM logs WHERE user_email = ?"
    # Use params to prevent SQL injection
    df = pd.read_sql(query, conn, params=(user_email,))
    conn.close()
    return df

def update_entry(u_date, u_act, u_amt, u_cat, u_ent, u_mod, u_rem, edit_id, user_email):
    conn = get_connection()
    c = conn.cursor()
    # Ensure log_date is included so users can edit the date
    c.execute("""
        UPDATE logs 
        SET log_date=?, activity=?, amount=?, category=?, entity=?, payment_mode=?, remark=? 
        WHERE id=? AND user_email=?
    """, (u_date, u_act, u_amt, u_cat, u_ent, u_mod, u_rem, edit_id, user_email))
    conn.commit()
    conn.close()

def delete_entry(entry_id, user_email):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM logs WHERE id=? AND user_email=?", (entry_id, user_email))
    conn.commit()
    conn.close()
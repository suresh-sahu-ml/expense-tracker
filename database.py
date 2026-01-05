import sqlite3
import pandas as pd

DB_NAME = "tracker_final.db"

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    # 1. Create table if it doesn't exist
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  user_email TEXT,
                  log_date TEXT, activity TEXT, amount REAL, 
                  entity TEXT, payment_mode TEXT, category TEXT, remark TEXT)''')
    
    # 2. SELF-HEALING: Check if 'user_email' column exists in case of old DB file
    c.execute("PRAGMA table_info(logs)")
    columns = [column[1] for column in c.fetchall()]
    if 'user_email' not in columns:
        print("Migrating database: Adding user_email column...")
        c.execute("ALTER TABLE logs ADD COLUMN user_email TEXT DEFAULT 'local_test_user@example.com'")
    
    conn.commit()
    conn.close()

def save_entry(user_email, log_date, activity, amount, entity, mode, category, remark):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""INSERT INTO logs (user_email, log_date, activity, amount, entity, payment_mode, category, remark) 
                 VALUES (?,?,?,?,?,?,?,?)""", (user_email, str(log_date), activity, amount, entity, mode, category, remark))
    conn.commit()
    conn.close()

def fetch_user_logs(user_email):
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM logs WHERE user_email = ?", conn, params=(user_email,))
    conn.close()
    return df

def update_entry(u_act, u_amt, u_cat, u_ent, u_mod, u_rem, edit_id, user_email):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""UPDATE logs SET activity=?, amount=?, category=?, entity=?, payment_mode=?, remark=? 
                 WHERE id=? AND user_email=?""", (u_act, u_amt, u_cat, u_ent, u_mod, u_rem, edit_id, user_email))
    conn.commit()
    conn.close()

def delete_entry(entry_id, user_email):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM logs WHERE id=? AND user_email=?", (entry_id, user_email))
    conn.commit()
    conn.close()
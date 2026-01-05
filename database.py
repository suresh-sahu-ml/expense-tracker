import sqlite3
import pandas as pd

DB_NAME = "tracker_final.db"

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  log_date TEXT, activity TEXT, amount REAL, 
                  entity TEXT, payment_mode TEXT, category TEXT, remark TEXT)''')
    conn.commit()
    conn.close()

def save_entry(log_date, activity, amount, entity, mode, category, remark):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""INSERT INTO logs (log_date, activity, amount, entity, payment_mode, category, remark) 
                 VALUES (?,?,?,?,?,?,?)""", (log_date, activity, amount, entity, mode, category, remark))
    conn.commit()
    conn.close()

def fetch_all_logs():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM logs", conn)
    conn.close()
    return df

def update_entry(u_act, u_amt, u_cat, u_ent, u_mod, u_rem, edit_id):
    conn = get_connection()
    c = conn.cursor()
    # Updated to ensure Activity, Amount, Category, Entity, Mode, and Remark are all saved
    c.execute("""UPDATE logs SET activity=?, amount=?, category=?, entity=?, payment_mode=?, remark=? 
                 WHERE id=?""", (u_act, u_amt, u_cat, u_ent, u_mod, u_rem, edit_id))
    conn.commit()
    conn.close()

def delete_entry(entry_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM logs WHERE id=?", (entry_id,))
    conn.commit()
    conn.close()
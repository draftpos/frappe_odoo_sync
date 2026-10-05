import psycopg2
try:
    conn = psycopg2.connect(dbname='havanoposdesk_odoo', user='odoo', host='localhost')
    cur = conn.cursor()
    cur.execute("DELETE FROM frappe_sync_log;")
    conn.commit()
    print("Logs cleared successfully.")
except Exception as e:
    print(f"Error: {e}")

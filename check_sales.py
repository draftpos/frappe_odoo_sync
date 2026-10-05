import psycopg2
import sys
sys.stdout.reconfigure(encoding='utf-8')
try:
    conn = psycopg2.connect(dbname='havanoposdesk_odoo', user='odoo', host='localhost')
    cur = conn.cursor()
    cur.execute("SELECT id, entity, status, details FROM frappe_sync_log ORDER BY id DESC LIMIT 50;")
    for r in cur.fetchall():
        print(repr(r))
except Exception as e:
    print(f"Error: {e}")

import psycopg2
try:
    conn = psycopg2.connect(dbname='havanoposdesk_odoo', user='odoo', host='localhost')
    cur = conn.cursor()
    cur.execute("SELECT entity, status, details FROM frappe_sync_log WHERE entity LIKE 'Sale%' ORDER BY create_date DESC LIMIT 5;")
    rows = cur.fetchall()
    for r in rows:
        print(r)
except Exception as e:
    print(f"Error: {e}")

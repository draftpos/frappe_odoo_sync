import psycopg2
try:
    conn = psycopg2.connect(dbname='havanoposdesk_odoo', user='odoo', host='localhost')
    cur = conn.cursor()
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'havanoposdesk_sale'")
    print([r[0] for r in cur.fetchall()])
except Exception as e:
    print(f"Error: {e}")

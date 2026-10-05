import psycopg2
conn = psycopg2.connect(dbname='havanoposdesk_odoo', user='odoo', host='localhost')
cur = conn.cursor()
cur.execute("SELECT payment_status, amount_paid_base, amount_total_base, payment_policy FROM havanoposdesk_sale WHERE state IN ('done','confirmed') LIMIT 5;")
for r in cur.fetchall():
    print(r)

import psycopg2, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = psycopg2.connect(dbname='havanoposdesk_odoo', user='odoo', host='localhost')
cur = conn.cursor()
# Get the latest sync run by looking at Sales Invoice and Sales (push) logs
cur.execute("""
    SELECT entity, status, details, create_date 
    FROM frappe_sync_log 
    WHERE entity ILIKE '%sale%' OR entity ILIKE '%Sales%'
    ORDER BY create_date DESC 
    LIMIT 15;
""")
for r in cur.fetchall():
    print(r)

import psycopg2, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = psycopg2.connect(dbname='havanoposdesk_odoo', user='odoo', host='localhost')
cur = conn.cursor()
# Check S0004 sale lines - look for batch_no and serial_no fields
cur.execute("""
    SELECT sl.id, sl.product_id, p.name as product_name, 
           sl.accepted_qty, sl.batch_no, sl.serial_no
    FROM havanoposdesk_sale_line sl
    JOIN havanoposdesk_sale s ON sl.sale_id = s.id
    LEFT JOIN havanoposdesk_product p ON sl.product_id = p.id
    WHERE s.name = 'S0004';
""")
rows = cur.fetchall()
if rows:
    for r in rows:
        print(r)
else:
    # Try without product join in case field name differs
    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'havanoposdesk_sale_line' 
        AND column_name ILIKE '%batch%' OR column_name ILIKE '%serial%';
    """)
    print("Sale line columns with batch/serial:", cur.fetchall())

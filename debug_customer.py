import sys
sys.path.append(r"c:\odoo19")
import odoo
from odoo import tools, api
from odoo.modules.registry import Registry

tools.config.parse_config(['-c', 'c:\\odoo19\\odoo.conf', '-d', 'havanoposdesk_odoo'])
registry = Registry('havanoposdesk_odoo')

with registry.cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    tenant = env['havanoposdesk.tenant'].search([('sync_to_frappe', '=', True)], limit=1)
    engine = env['frappe.sync.engine'].create({})
    
    # Let's inspect the customers
    frappe_custs = engine._frappe_get(tenant, 'Customer', limit=5)
    print("Sample Frappe Customers:", [c.get('name') for c in frappe_custs])
    
    # Try to simulate the payload that fails
    sales = env['havanoposdesk.sale'].search([
        ('tenant_id', '=', tenant.id),
        ('state', 'in', ['done', 'confirmed'])
    ], limit=5, order='id desc')
    
    for sale in sales:
        print(f"\nAnalyzing sale: {sale.name}")
        customer_name = sale.customer.name if sale.customer else 'CASH'
        print(f"Odoo customer name: {customer_name}")
        
        # Build cust_name_to_id
        frappe_custs_all = engine._frappe_get(tenant, 'Customer', limit=2000)
        cust_name_to_id = {}
        for c in frappe_custs_all:
            internal_id = c.get('name', '')
            display_name = c.get('customer_name', internal_id)
            if display_name:
                cust_name_to_id[display_name.lower()] = internal_id
            if internal_id and internal_id.lower() != display_name.lower():
                cust_name_to_id[internal_id.lower()] = internal_id
                
        frappe_customer_id = engine._ensure_frappe_customer_exists(tenant, customer_name, cust_name_to_id)
        print(f"Mapped Frappe Customer ID: {frappe_customer_id}")
        
        # Fetch it back from Frappe to see if it actually exists!
        cust_doc = engine._frappe_get_single(tenant, 'Customer', frappe_customer_id)
        if cust_doc:
            print(f"Customer {frappe_customer_id} EXISTS in Frappe.")
        else:
            print(f"WARNING: Customer {frappe_customer_id} DOES NOT EXIST in Frappe!")

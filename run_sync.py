import sys
import os

# Set up paths to Odoo
sys.path.append(r"c:\odoo19")
import odoo

# Initialize Odoo environment
odoo.tools.config.parse_config(['-c', 'c:\\odoo19\\odoo.conf', '-d', 'havanoposdesk_odoo'])
registry = odoo.registry('havanoposdesk_odoo')

with registry.cursor() as cr:
    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
    
    tenant = env['havanoposdesk.tenant'].search([('sync_to_frappe', '=', True)], limit=1)
    if not tenant:
        print("No tenant found.")
        sys.exit(1)
        
    engine = env['frappe.sync.engine'].create({})
    
    print(f"\n======================================")
    print(f"Running manual sync for tenant: {tenant.name}")
    print(f"======================================\n")
    
    try:
        # Run the sync process
        engine._sync_sales(tenant)
        print("\nSync completed successfully without Python errors!")
    except Exception as e:
        import traceback
        print(f"\nError occurred during sync:")
        traceback.print_exc()
    
    print("\nStopping execution and rolling back changes (stop at end).")
    # Rollback to avoid saving any changes to the database during this manual test
    cr.rollback()

print("Done.")

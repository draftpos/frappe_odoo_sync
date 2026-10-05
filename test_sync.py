tenant = env['havanoposdesk.tenant'].search([('sync_to_frappe', '=', True)], limit=1)
engine = env['frappe.sync.engine'].create({})
print(f"\n======================================")
print(f"Running sync sales for tenant: {tenant.name if tenant else 'None'}")
try:
    if tenant:
        engine._sync_sales(tenant)
        print("Sync complete.")
except Exception as e:
    import traceback
    print(f"Error occurred: {e}")
    traceback.print_exc()
print(f"======================================\n")
env.cr.commit()
raise Exception("STOP")

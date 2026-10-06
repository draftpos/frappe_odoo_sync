from odoo import api, SUPERUSER_ID

def uninstall_hook(env):
    # These fields have Postgres views/dependencies on the live server.
    # By converting them to 'manual' and removing them from this module's data,
    # Odoo will leave the database columns intact when uninstalling the module,
    # preventing psycopg2.errors.DependentObjectsStillExist crashes.
    
    fields_to_keep = [
        'has_variants', 
        'frappe_variant_of', 
        'item_code', 
        'is_active', 
        'serial_no', 
        'batch_no',
        'frappe_synced'
    ]
    
    # Find these fields in the registry
    fields = env['ir.model.fields'].search([('name', 'in', fields_to_keep)])
    
    for field in fields:
        # 1. Detach from frappe_odoo_sync module
        env.cr.execute(
            "DELETE FROM ir_model_data WHERE model='ir.model.fields' AND res_id=%s AND module='frappe_odoo_sync'", 
            (field.id,)
        )
        # 2. Convert to manual fields so Odoo's uninstaller doesn't drop the PostgreSQL columns
        env.cr.execute(
            "UPDATE ir_model_fields SET state='manual' WHERE id=%s", 
            (field.id,)
        )

# -*- coding: utf-8 -*-
{
    'name': 'Frappe / ERPNext Sync Bridge',
    'version': '19.0.2.0',
    'category': 'Technical',
    'summary': 'Full bidirectional sync between Havano POS Desk and Frappe/ERPNext',
    'description': """
Frappe / ERPNext Sync Bridge for Havano POS Desk.

Bidirectional sync using only Python stdlib (no pip packages):

- Products (Frappe Items <-> Odoo havanoposdesk.product)
- UOMs (Frappe UOM <-> Odoo havanoposdesk.uom)
- Customers (Frappe Customers <-> Odoo havanoposdesk.customer)
- Stores (Frappe Warehouse <-> Odoo havanoposdesk.store)
- Sales (Odoo sales -> Frappe Sales Invoice)

Variance sync: updates existing records on both ends when prices, UOM or name change.
Auto-syncs every minute via scheduled action.
    """,
    'depends': ['havanoposdesk_odoo', 'base'],
    'data': [
        'security/ir.model.access.csv',
        'views/frappe_sync_assets.xml',
        'views/frappe_sync_views.xml',
        'data/frappe_sync_cron.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}

# -*- coding: utf-8 -*-
{
    'name': 'Frappe / ERPNext Sync Bridge',
    'version': '19.0.2.0',
    'category': 'Technical',
    'summary': 'Full bidirectional sync between Havano POS Desk and Frappe/ERPNext',
    'description': """
Adds a "Frappe / ERPNext" integration tab to every Tenant in Havano POS Desk.
When enabled, syncs the following entities bidirectionally using only Python stdlib (no pip packages):
  - Products  (Frappe Items -> Odoo havanoposdesk.product)
  - Pricelists (Frappe Price Lists -> Odoo havanoposdesk.pricelist / product.uom.price)
  - Customers  (Frappe Customers -> Odoo havanoposdesk.customer)
  - Inventory  (Frappe Stock -> Odoo havanoposdesk.store)
  - Sales      (Frappe Sales Invoice -> Odoo havanoposdesk.terminal.session.order)
  - Users      (Frappe Users -> Odoo havanoposdesk.saas.users)
  - Stores     (Frappe Warehouse -> Odoo havanoposdesk.store)
  - Payments   (Frappe Payment Entry -> Odoo havanoposdesk.terminal.session.order.line)
    """,
    'depends': ['havanoposdesk_odoo', 'base'],
    'data': [
        'security/ir.model.access.csv',
        'views/frappe_sync_views.xml',
        'data/frappe_sync_cron.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}

# -*- coding: utf-8 -*-
from odoo import models, fields

class TenantFrappeSettings(models.Model):
    _inherit = 'havanoposdesk.tenant'

    sync_to_frappe = fields.Boolean(
        string='Sync to Frappe / ERPNext',
        default=False,
        help="When enabled, this tenant's data will be automatically synced to the configured Frappe instance."
    )

    frappe_url = fields.Char(
        string='Frappe URL', 
        help='e.g., http://127.0.0.1:8002'
    )
    frappe_api_key = fields.Char(string='API Key')
    frappe_api_secret = fields.Char(string='API Secret')
    frappe_sync_log_ids = fields.One2many('frappe.sync.log', 'tenant_id', string='Sync Logs')

    def action_test_frappe_connection(self):
        self.ensure_one()
        return self.env['frappe.sync.engine'].test_connection(self)

    def action_sync_now(self):
        self.ensure_one()
        return self.env['frappe.sync.engine'].sync_tenant(self)

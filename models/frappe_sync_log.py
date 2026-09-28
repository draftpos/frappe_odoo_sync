# -*- coding: utf-8 -*-
from odoo import models, fields, api
class FrappeSyncLog(models.Model):
    _name = 'frappe.sync.log'
    _description = 'Frappe Sync Log'
    _order = 'create_date desc'

    tenant_id = fields.Many2one('havanoposdesk.tenant', string='Tenant', ondelete='cascade', required=True)
    entity = fields.Char('Entity')
    status = fields.Selection([
        ('success', 'Success'),
        ('error', 'Error'),
        ('skipped', 'Existing'),
    ], string='Status')
    details = fields.Text('Details')
    records_synced = fields.Integer('Records Synced', default=0)

    @api.model
    def autovacuum_logs(self, days_to_keep=7):
        date_limit = fields.Datetime.subtract(fields.Datetime.now(), days=days_to_keep)
        logs_to_delete = self.search([('create_date', '<', date_limit)])
        logs_to_delete.unlink()

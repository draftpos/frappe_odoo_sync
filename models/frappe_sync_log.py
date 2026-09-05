# -*- coding: utf-8 -*-
from odoo import models, fields

class FrappeSyncLog(models.Model):
    _name = 'frappe.sync.log'
    _description = 'Frappe Sync Log'
    _order = 'create_date desc'

    tenant_id = fields.Many2one('havanoposdesk.tenant', string='Tenant', ondelete='cascade', required=True)
    entity = fields.Char('Entity')
    status = fields.Selection([('success', 'Success'), ('error', 'Error')], string='Status')
    details = fields.Text('Details')
    records_synced = fields.Integer('Records Synced', default=0)

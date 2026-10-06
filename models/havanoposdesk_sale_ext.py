from odoo import models, fields

class HavanoposdeskSaleLineExt(models.Model):
    _inherit = 'havanoposdesk.sale.line'

    serial_no = fields.Text(string='Serial No', help="Comma or newline separated serial numbers")
    batch_no = fields.Char(string='Batch No')
class HavanoposdeskSaleExt(models.Model):
    _inherit = 'havanoposdesk.sale'

    frappe_synced = fields.Boolean(string='Synced to Frappe', default=False, copy=False)

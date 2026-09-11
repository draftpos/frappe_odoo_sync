from odoo import models, fields, api

class HavanoposdeskProductExt(models.Model):
    _inherit = 'havanoposdesk.product'

    has_variants = fields.Boolean(string='Has Variants', default=False, help="If true, this product acts as a template for other variants.")
    is_variant = fields.Boolean(string='Is Variant', default=False, help="If true, this product is a variant of another product template.")
    template_id = fields.Many2one('havanoposdesk.product', string='Template', domain="[('has_variants', '=', True)]", help="The parent product template.")
    variant_ids = fields.One2many('havanoposdesk.product', 'template_id', string='Variants')
    
    # Store Frappe's variant_of temporarily during sync before linking the relation
    frappe_variant_of = fields.Char(string="Frappe Variant Of", help="Used internally for syncing.")

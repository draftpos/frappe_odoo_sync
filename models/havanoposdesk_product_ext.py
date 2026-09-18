from odoo import models, fields, api

class HavanoposdeskProductExt(models.Model):
    _inherit = 'havanoposdesk.product'

    has_variants = fields.Boolean(
        string='Has Variants',
        compute='_compute_has_variants',
        inverse='_set_has_variants_ext',
        search='_search_has_variants',
        store=True,
        default=False,
    )

    def _set_has_variants_ext(self):
        for record in self:
            if record.is_variant != record.has_variants:
                record.is_variant = record.has_variants

    @api.depends('is_bundle', 'bundle_item_ids', 'bundle_item_ids.qty', 'bundle_item_ids.subtotal_cost', 'bundle_item_ids.subtotal_selling', 'uom_price_ids.price')
    def _compute_bundle_prices(self):
        for record in self:
            if record.is_bundle:
                record.buying_price = sum(item.subtotal_cost for item in record.bundle_item_ids)
                record.selling_price = sum(item.subtotal_selling for item in record.bundle_item_ids)

    template_id = fields.Many2one('havanoposdesk.product', string='Template', domain="[('has_variants', '=', True)]", help="The parent product template.")
    frappe_variant_ids = fields.One2many('havanoposdesk.product', 'template_id', string='Frappe Variants')
    
    # Store Frappe's variant_of temporarily during sync before linking the relation
    frappe_variant_of = fields.Char(string="Frappe Variant Of", help="Used internally for syncing.")


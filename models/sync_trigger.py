from odoo import models, api

def trigger_sync(env):
    cron = env.ref('frappe_odoo_sync.ir_cron_frappe_sync', raise_if_not_found=False)
    if cron:
        cron._trigger()

class HavanoposdeskProduct(models.Model):
    _inherit = 'havanoposdesk.product'

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        trigger_sync(self.env)
        return res

    def write(self, vals):
        res = super().write(vals)
        trigger_sync(self.env)
        return res

class HavanoposdeskUom(models.Model):
    _inherit = 'havanoposdesk.uom'

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        trigger_sync(self.env)
        return res

    def write(self, vals):
        res = super().write(vals)
        trigger_sync(self.env)
        return res

class HavanoposdeskCustomer(models.Model):
    _inherit = 'havanoposdesk.customer'

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        trigger_sync(self.env)
        return res

    def write(self, vals):
        res = super().write(vals)
        trigger_sync(self.env)
        return res

class HavanoposdeskStore(models.Model):
    _inherit = 'havanoposdesk.store'

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        trigger_sync(self.env)
        return res

    def write(self, vals):
        res = super().write(vals)
        trigger_sync(self.env)
        return res

class HavanoposdeskSale(models.Model):
    _inherit = 'havanoposdesk.sale'

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        trigger_sync(self.env)
        return res

    def write(self, vals):
        res = super().write(vals)
        trigger_sync(self.env)
        return res

from odoo import models, fields, api

def trigger_sync(env, tenant=None, immediate=True):
    """Trigger sync safely without ever crashing the current transaction or request."""
    try:
        cron = env.ref('frappe_odoo_sync.ir_cron_frappe_sync', raise_if_not_found=False)
        # If cron is active, trigger cron to pick it up in background
        if cron and cron.active:
            cron._trigger()
            return

        # If cron is inactive (removed/disabled as requested), execute sync immediately
        if immediate:
            engine = env['frappe.sync.engine']
            try:
                with env.cr.savepoint():
                    if tenant:
                        if getattr(tenant, 'sync_to_frappe', False):
                            engine.sync_tenant(tenant)
                    else:
                        engine.cron_sync_all()
            except Exception:
                pass
    except Exception:
        # Never break the primary transaction or HTTP request
        pass



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

class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        trigger_sync(self.env)
        return res

    def write(self, vals):
        res = super().write(vals)
        trigger_sync(self.env)
        return res




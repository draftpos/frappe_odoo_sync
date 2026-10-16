import threading
from odoo import models, fields, api

def _run_sync_async(env, tenant_id=None):
    """Run sync in a separate thread and new DB cursor to avoid blocking HTTP workers."""
    def worker():
        try:
            with env.registry.cursor() as new_cr:
                new_env = api.Environment(new_cr, env.uid, env.context)
                engine = new_env['frappe.sync.engine']
                if tenant_id:
                    tenant = new_env['havanoposdesk.tenant'].browse(tenant_id)
                    if tenant.exists() and tenant.sync_to_frappe:
                        engine.sync_tenant(tenant)
                else:
                    engine.cron_sync_all()
        except Exception:
            pass

    t = threading.Thread(target=worker, daemon=True)
    t.start()

def trigger_sync(env, tenant=None, immediate=True):
    """Trigger sync safely in background without blocking HTTP workers or causing 502 timeouts."""
    try:
        cron = env.ref('frappe_odoo_sync.ir_cron_frappe_sync', raise_if_not_found=False)
        # If cron is active, trigger cron to pick it up in background
        if cron and cron.active:
            cron._trigger()
            return

        # If cron is inactive, run in non-blocking background thread
        if immediate:
            tenant_id = tenant.id if tenant else None
            _run_sync_async(env, tenant_id)
    except Exception:
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




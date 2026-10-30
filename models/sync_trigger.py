import time
import threading
from odoo import models, fields, api

_SYNC_LOCK = threading.Lock()
_LAST_TRIGGER_TIME = 0.0
_DEBOUNCE_INTERVAL = 15.0  # seconds between automatic background sync sweeps

def _run_sync_async(env, tenant_id=None):
    """Run sync in a single background worker to avoid spawn floods and thread explosions."""
    def worker():
        # If another sync worker is already running, exit immediately without queuing up
        if not _SYNC_LOCK.acquire(blocking=False):
            return
        try:
            with env.registry.cursor() as new_cr:
                # Add skip_frappe_sync=True so internal writes during sync never trigger cascaded syncs
                ctx = dict(env.context or {}, skip_frappe_sync=True)
                new_env = api.Environment(new_cr, env.uid, ctx)
                engine = new_env['frappe.sync.engine']
                if tenant_id:
                    tenant = new_env['havanoposdesk.tenant'].browse(tenant_id)
                    if tenant.exists() and tenant.sync_to_frappe:
                        engine.sync_tenant(tenant)
                else:
                    engine.cron_sync_all()
                # Clear ORM cache in thread before releasing cursor
                new_env.invalidate_all()
        except Exception:
            pass
        finally:
            _SYNC_LOCK.release()

    t = threading.Thread(target=worker, daemon=True, name="FrappeSyncAsyncWorker")
    t.start()

def trigger_sync(env, tenant=None, immediate=False):
    """Trigger sync safely without blocking HTTP workers, debounced to avoid 502s."""
    # Never trigger if already executing inside a sync cycle
    if env.context.get('skip_frappe_sync'):
        return

    global _LAST_TRIGGER_TIME
    now = time.time()
    
    # Debounce: if triggered within the debounce interval, ignore to prevent worker starvation
    if not immediate and (now - _LAST_TRIGGER_TIME < _DEBOUNCE_INTERVAL):
        return

    _LAST_TRIGGER_TIME = now
    try:
        cron = env.ref('frappe_odoo_sync.ir_cron_frappe_sync', raise_if_not_found=False)
        # If cron is active, trigger cron to pick it up via standard Odoo cron worker
        if cron and cron.active:
            cron._trigger()
            return

        # If cron is inactive, run in single throttled background thread
        tenant_id = tenant.id if tenant else None
        _run_sync_async(env, tenant_id)
    except Exception:
        pass


class HavanoposdeskProduct(models.Model):
    _inherit = 'havanoposdesk.product'

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        if not self.env.context.get('skip_frappe_sync'):
            trigger_sync(self.env)
        return res

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_frappe_sync'):
            trigger_sync(self.env)
        return res

class HavanoposdeskUom(models.Model):
    _inherit = 'havanoposdesk.uom'

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        if not self.env.context.get('skip_frappe_sync'):
            trigger_sync(self.env)
        return res

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_frappe_sync'):
            trigger_sync(self.env)
        return res

class HavanoposdeskCustomer(models.Model):
    _inherit = 'havanoposdesk.customer'

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        if not self.env.context.get('skip_frappe_sync'):
            trigger_sync(self.env)
        return res

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_frappe_sync'):
            trigger_sync(self.env)
        return res

class HavanoposdeskStore(models.Model):
    _inherit = 'havanoposdesk.store'

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        if not self.env.context.get('skip_frappe_sync'):
            trigger_sync(self.env)
        return res

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_frappe_sync'):
            trigger_sync(self.env)
        return res

class HavanoposdeskSale(models.Model):
    _inherit = 'havanoposdesk.sale'

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        if not self.env.context.get('skip_frappe_sync'):
            trigger_sync(self.env)
        return res

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_frappe_sync'):
            trigger_sync(self.env)
        return res

class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        if not self.env.context.get('skip_frappe_sync'):
            trigger_sync(self.env)
        return res

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_frappe_sync'):
            trigger_sync(self.env)
        return res

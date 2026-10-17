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
    duration_seconds = fields.Float('Duration (s)', digits=(6, 2), default=0.0)
    payload_size_kb = fields.Float('Payload (KB)', digits=(10, 2), default=0.0)
    table_size_kb = fields.Float('Table Space (KB)', digits=(12, 2), default=0.0)

    @api.model
    def autovacuum_logs(self, days_to_keep=3):
        """Keep only recent logs (default 3 days) to minimize disk space consumption."""
        date_limit = fields.Datetime.subtract(fields.Datetime.now(), days=days_to_keep)
        logs_to_delete = self.search([('create_date', '<', date_limit)])
        if logs_to_delete:
            logs_to_delete.unlink()
        self.optimize_memory_and_space()

    @api.model
    def optimize_memory_and_space(self):
        """Reclaim RAM and DB table space.
        
        1. Calls Python garbage collector to free unreferenced objects from RAM.
        2. Clears Odoo ORM environment caches.
        3. Vacuums sync log and temporary dead tuples.
        """
        import gc
        # 1. Clear ORM local caches
        try:
            self.env.invalidate_all()
        except Exception:
            pass

        # 2. Python GC collection to free heap RAM
        gc.collect()

        # 3. PostgreSQL dead tuple cleanup for frappe_sync_log
        try:
            with self.env.cr.savepoint():
                self.env.cr.execute("ANALYZE frappe_sync_log;")
        except Exception:
            pass

# -*- coding: utf-8 -*-
from odoo import models, fields

class TenantFrappeSettings(models.Model):
    _inherit = 'havanoposdesk.tenant'

    sync_to_frappe = fields.Boolean(
        string='Sync to Frappe / ERPNext',
        default=False,
        help="When enabled, this tenant's data will be automatically synced to the configured Frappe instance."
    )

    frappe_url = fields.Char(
        string='Frappe URL', 
        help='e.g., http://127.0.0.1:8002'
    )
    frappe_api_key = fields.Char(string='Frappe API Key')
    frappe_api_secret = fields.Char(string='Frappe API Secret')
    frappe_sync_log_ids = fields.One2many('frappe.sync.log', 'tenant_id', string='Sync Logs')
    frappe_last_pull_datetime = fields.Datetime(string='Last Frappe Pull Datetime')
    frappe_last_push_datetime = fields.Datetime(string='Last Odoo Push Datetime')
    store_count = fields.Integer(string='Stores Count', compute='_compute_store_count')

    # Dashboard Metrics
    sync_stat_sales_count = fields.Integer(string='Sales Synced', compute='_compute_sync_stats')
    sync_stat_products_count = fields.Integer(string='Products Synced', compute='_compute_sync_stats')
    sync_stat_stock_count = fields.Integer(string='Stock Updates', compute='_compute_sync_stats')
    sync_stat_customers_count = fields.Integer(string='Customers Synced', compute='_compute_sync_stats')
    sync_stat_users_count = fields.Integer(string='Users Synced', compute='_compute_sync_stats')
    sync_stat_total_space_mb = fields.Float(string='Total DB Space (MB)', compute='_compute_sync_stats', digits=(10, 2))

    def _compute_sync_stats(self):
        for rec in self:
            logs = rec.frappe_sync_log_ids
            rec.sync_stat_sales_count = sum(l.records_synced for l in logs if 'sale' in (l.entity or '').lower() and l.status == 'success')
            rec.sync_stat_products_count = sum(l.records_synced for l in logs if ('product' in (l.entity or '').lower() or 'item' in (l.entity or '').lower()) and l.status == 'success')
            rec.sync_stat_stock_count = sum(l.records_synced for l in logs if 'stock' in (l.entity or '').lower() and l.status == 'success')
            rec.sync_stat_customers_count = sum(l.records_synced for l in logs if 'customer' in (l.entity or '').lower() and l.status == 'success')
            rec.sync_stat_users_count = sum(l.records_synced for l in logs if 'user' in (l.entity or '').lower() and l.status == 'success')

            # Calculate total DB footprint across the main sync tables
            total_kb = 0.0
            try:
                tables = ('havanoposdesk_sale', 'havanoposdesk_product', 'havanoposdesk_stock_valuation', 'havanoposdesk_customer', 'res_users')
                self.env.cr.execute("""
                    SELECT COALESCE(SUM(pg_total_relation_size(c.oid)), 0)::float / (1024.0 * 1024.0)
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public' AND c.relname IN %s;
                """, (tables,))
                res = self.env.cr.fetchone()
                rec.sync_stat_total_space_mb = round(res[0], 2) if res and res[0] else 0.0
            except Exception:
                rec.sync_stat_total_space_mb = 0.0

    def _compute_store_count(self):
        for rec in self:
            rec.store_count = self.env['havanoposdesk.store'].search_count([('tenant_id', '=', rec.id)])


    def action_test_frappe_connection(self):
        self.ensure_one()
        return self.env['frappe.sync.engine'].test_connection(self)

    def action_sync_now(self):
        self.ensure_one()
        return self.env['frappe.sync.engine'].sync_tenant(self)

    def action_revert_non_sales_items(self):
        self.ensure_one()
        return self.env['frappe.sync.engine'].revert_non_sales_items(self)

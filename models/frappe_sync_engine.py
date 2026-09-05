import json
import time
import urllib.request
import urllib.parse
from odoo import models, fields, api
from odoo import exceptions

class FrappeSyncEngine(models.TransientModel):
    _name = 'frappe.sync.engine'
    _description = 'Frappe Sync Engine'

    @api.model
    def test_connection(self, tenant):
        url = f"{tenant.frappe_url.rstrip('/')}/api/method/frappe.auth.get_logged_user"
        req = urllib.request.Request(url, headers={
            'Authorization': f'token {tenant.frappe_api_key}:{tenant.frappe_api_secret}',
            'Accept': 'application/json'
        })
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                user = data.get('message', '')
                if user:
                    return {
                        'success': True,
                        'message': f'Connected as {user}'
                    }
                else:
                    return {
                        'success': False,
                        'message': 'Connected but no user returned'
                    }
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            raise exceptions.UserError(f'Connection failed: HTTP Error {e.code}: {e.reason}. {err_body}')
        except Exception as e:
            raise exceptions.UserError(f'Connection failed: {str(e)}')

    @api.model
    def cron_sync_all(self):
        tenants = self.env['havanoposdesk.tenant'].search([('sync_to_frappe', '=', True)])
        for tenant in tenants:
            self.sync_tenant(tenant)

    @api.model
    def sync_tenant(self, tenant):
        start_time = time.time()
        try:
            p_res = self._sync_products(tenant)
            c_res = self._sync_customers(tenant)
            s_res = self._sync_stores(tenant)
            sa_res = self._sync_sales(tenant)
            
            p_s, p_sk = p_res['synced'], p_res['skipped']
            c_s, c_sk = c_res['synced'], c_res['skipped']
            s_s, s_sk = s_res['synced'], s_res['skipped']
            sa_s, sa_sk = sa_res['synced'], sa_res['skipped']
            
            msg = f'Synced: {p_s} Products, {c_s} Customers, {s_s} Stores, {sa_s} Sales.\nSkipped (Already in Frappe): {p_sk} Products, {c_sk} Customers, {s_sk} Stores, {sa_sk} Sales.'
            self._log(tenant, 'All Entities', 'success', f'Sync completed in {round(time.time() - start_time, 2)}s\n{msg}')
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sync Complete',
                    'message': msg,
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            self._log(tenant, 'All Entities', 'error', str(e))
            raise exceptions.UserError(f'Sync failed: {str(e)}')

    def _frappe_get(self, tenant, doctype, limit=500):
        url = f"{tenant.frappe_url.rstrip('/')}/api/resource/{urllib.parse.quote(doctype)}?limit_page_length={limit}&fields=[\"*\"]"
        req = urllib.request.Request(url, headers={
            'Authorization': f'token {tenant.frappe_api_key}:{tenant.frappe_api_secret}',
            'Accept': 'application/json'
        })
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode())
                return data.get('data', [])
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            self._log(tenant, doctype, 'error', f'Failed to fetch: HTTP {e.code} - {err_body}')
            return []
        except Exception as e:
            self._log(tenant, doctype, 'error', f'Failed to fetch: {str(e)}')
            return []

    def _frappe_post(self, tenant, doctype, data):
        url = f"{tenant.frappe_url.rstrip('/')}/api/resource/{urllib.parse.quote(doctype)}"
        payload = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers={
            'Authorization': f'token {tenant.frappe_api_key}:{tenant.frappe_api_secret}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                return json.loads(response.read().decode()).get('data', {})
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            self._log(tenant, doctype, 'error', f'Failed to post: HTTP {e.code} - {err_body}')
            return None
        except Exception as e:
            self._log(tenant, doctype, 'error', f'Failed to post: {str(e)}')
            return None

    def _frappe_method_post(self, tenant, method, data):
        """Call a whitelisted Frappe method via POST form-encode."""
        url = f"{tenant.frappe_url.rstrip('/')}/api/method/{method}"
        payload = urllib.parse.urlencode(data).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers={
            'Authorization': f'token {tenant.frappe_api_key}:{tenant.frappe_api_secret}',
            'Accept': 'application/json'
        })
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                return json.loads(response.read().decode()).get('message', {})
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            return {'error': err_body}
        except Exception as e:
            return {'error': str(e)}

    def _log(self, tenant, entity, status, details='', records=0):
        self.env['frappe.sync.log'].create({
            'tenant_id': tenant.id,
            'entity': entity,
            'status': status,
            'details': details,
            'records_synced': records
        })

    def _get_frappe_item_group(self, tenant):
        """Get a safe item group from Frappe."""
        groups = self._frappe_get(tenant, 'Item Group', limit=20)
        # Prefer 'Products' or 'All Item Groups'
        for g in groups:
            if g.get('name', '').lower() in ['products', 'all item groups']:
                return g.get('name')
        return groups[0].get('name') if groups else 'All Item Groups'

    def _get_frappe_customer_group(self, tenant):
        groups = self._frappe_get(tenant, 'Customer Group', limit=10)
        for g in groups:
            if 'all' in g.get('name', '').lower():
                return g.get('name')
        return groups[0].get('name') if groups else 'All Customer Groups'

    def _get_frappe_territory(self, tenant):
        territories = self._frappe_get(tenant, 'Territory', limit=10)
        for t in territories:
            if 'all' in t.get('name', '').lower():
                return t.get('name')
        return territories[0].get('name') if territories else 'All Territories'

    def _get_frappe_uom(self, tenant):
        uoms = self._frappe_get(tenant, 'UOM', limit=20)
        for u in uoms:
            if u.get('name', '').lower() in ['nos', 'each', 'unit', 'piece', 'pcs']:
                return u.get('name')
        return uoms[0].get('name') if uoms else 'Nos'

    def _sync_products(self, tenant):
        """Push Odoo products TO Frappe as Items."""
        # Get existing Frappe items by item_code
        frappe_items = self._frappe_get(tenant, 'Item', limit=1000)
        frappe_item_codes = {i.get('item_code', i.get('name', '')): True for i in frappe_items}

        item_group = self._get_frappe_item_group(tenant)
        stock_uom = self._get_frappe_uom(tenant)

        products = self.env['havanoposdesk.product'].search([
            ('tenant_id', '=', tenant.id),
            ('is_active', '=', True)
        ])

        count = 0
        skipped = 0
        errors = 0
        for product in products:
            code = product.item_code or product.name
            # Skip if already in Frappe
            if code in frappe_item_codes:
                skipped += 1
                continue

            item_data = {
                'item_code': code,
                'item_name': product.name,
                'item_group': item_group,
                'stock_uom': stock_uom,
                'standard_rate': product.selling_price,
                'valuation_rate': product.buying_price,
                'is_stock_item': 1 if product.track_qty else 0,
                'description': product.internal_notes or product.name,
            }
            res = self._frappe_post(tenant, 'Item', item_data)
            if res and res.get('name'):
                count += 1
            else:
                errors += 1

        if count > 0:
            self._log(tenant, 'Item', 'success', f'Pushed {count} products to Frappe (errors: {errors})', count)
        elif errors > 0:
            self._log(tenant, 'Item', 'error', f'Failed to push some items. Check Frappe Item module integrity. Errors: {errors}')
        return {'synced': count, 'skipped': skipped}

    def _sync_customers(self, tenant):
        """Push Odoo customers TO Frappe."""
        frappe_custs = self._frappe_get(tenant, 'Customer', limit=1000)
        frappe_cust_names = {c.get('customer_name', c.get('name', '')): True for c in frappe_custs}

        cust_group = self._get_frappe_customer_group(tenant)
        territory = self._get_frappe_territory(tenant)

        customers = self.env['havanoposdesk.customer'].search([
            ('tenant_id', '=', tenant.id)
        ])

        count = 0
        skipped = 0
        for customer in customers:
            name = customer.name or ''
            if name in frappe_cust_names:
                skipped += 1
                continue

            cust_data = {
                'customer_name': name,
                'customer_type': 'Individual',
                'customer_group': cust_group,
                'territory': territory,
                # Include known mandatory custom fields with safe defaults
                'custom_telephone_number': customer.phone or '0000000000',
                'custom_email_address': customer.email or f'{name.replace(" ", ".").lower()}@noemail.com',
                'custom_customer_tin': '',
                'custom_customer_vat': '',
                'custom_trade_name': name,
                'custom_customer_address': '',
                'custom_street': '',
                'custom_house_no': '',
                'custom_city': '',
                'custom_province': '',
            }
            res = self._frappe_post(tenant, 'Customer', cust_data)
            if res and res.get('name'):
                count += 1

        if count > 0:
            self._log(tenant, 'Customer', 'success', f'Pushed {count} customers to Frappe', count)
        return {'synced': count, 'skipped': skipped}

    def _sync_stores(self, tenant):
        """Push Odoo stores TO Frappe as Warehouses."""
        frappe_warehouses = self._frappe_get(tenant, 'Warehouse', limit=200)
        frappe_wh_names = {w.get('warehouse_name', w.get('name', '')): True for w in frappe_warehouses}

        stores = self.env['havanoposdesk.store'].search([
            ('tenant_id', '=', tenant.id)
        ])

        count = 0
        skipped = 0
        for store in stores:
            name = store.name or ''
            if name in frappe_wh_names:
                skipped += 1
                continue

            wh_data = {
                'warehouse_name': name,
                'company': self._get_frappe_company(tenant),
            }
            res = self._frappe_post(tenant, 'Warehouse', wh_data)
            if res and res.get('name'):
                count += 1

        if count > 0:
            self._log(tenant, 'Warehouse', 'success', f'Pushed {count} stores to Frappe', count)
        return {'synced': count, 'skipped': skipped}

    def _get_frappe_company(self, tenant):
        companies = self._frappe_get(tenant, 'Company', limit=5)
        return companies[0].get('name') if companies else 'Your Company'

    def _ensure_frappe_item_exists(self, tenant, item_code, item_name, item_group, stock_uom):
        """Ensure an item exists in Frappe, create if not."""
        items = self._frappe_get(tenant, 'Item', limit=1)
        # Try to get specific item
        url = f"{tenant.frappe_url.rstrip('/')}/api/resource/Item/{urllib.parse.quote(item_code)}"
        req = urllib.request.Request(url, headers={
            'Authorization': f'token {tenant.frappe_api_key}:{tenant.frappe_api_secret}',
            'Accept': 'application/json'
        })
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return True  # Item exists
        except:
            pass

        # Create it
        item_data = {
            'item_code': item_code,
            'item_name': item_name,
            'item_group': item_group,
            'stock_uom': stock_uom,
            'is_stock_item': 0,
        }
        res = self._frappe_post(tenant, 'Item', item_data)
        return bool(res and res.get('name'))

    def _sync_sales(self, tenant):
        """Push Odoo sales to Frappe as Sales Invoices."""
        frappe_invoices = self._frappe_get(tenant, 'Sales Invoice', limit=2000)
        synced_sales = {inv.get('po_no'): True for inv in frappe_invoices if inv.get('po_no')}

        sales = self.env['havanoposdesk.sale'].search([
            ('tenant_id', '=', tenant.id),
            ('state', 'in', ['done', 'confirmed'])
        ], limit=50, order='id asc')

        item_group = self._get_frappe_item_group(tenant)
        stock_uom = self._get_frappe_uom(tenant)

        count = 0
        skipped = 0
        for sale in sales:
            if sale.name in synced_sales:
                skipped += 1
                continue
            
            existing_log = self.env['frappe.sync.log'].search([
                ('tenant_id', '=', tenant.id),
                ('entity', '=', f'Sale: {sale.name}'),
                ('status', '=', 'success')
            ], limit=1)

            if existing_log:
                skipped += 1
                continue

            # Build items list - ensure each item exists in Frappe first
            items = []
            for line in sale.line_ids:
                code = line.product_id.item_code or line.product_id.name
                name = line.product_id.name
                # Best-effort: create item in Frappe if missing
                self._ensure_frappe_item_exists(tenant, code, name, item_group, stock_uom)
                items.append({
                    'item_code': code,
                    'item_name': name,
                    'qty': line.accepted_qty or 1.0,
                    'rate': line.rate or 0.0,
                    'uom': stock_uom,
                })

            if not items:
                continue

            customer_name = sale.customer.name if sale.customer else 'CASH'

            data = {
                'customer': customer_name,
                'po_no': sale.name,
                'items': items,
                'update_stock': 0,
                'set_posting_time': 1,
                'posting_date': str(sale.posting_date) if sale.posting_date else str(fields.Date.today()),
                'docstatus': 1,
            }

            res = self._frappe_post(tenant, 'Sales Invoice', data)
            if res and res.get('name'):
                self._log(tenant, f'Sale: {sale.name}', 'success', f'Pushed as {res.get("name")}', 1)
                count += 1
            else:
                self._log(tenant, f'Sale: {sale.name}', 'error', 'Failed to push to Frappe')

        if count > 0:
            self._log(tenant, 'Sales Invoice', 'success', f'Pushed {count} sales to Frappe', count)
        return {'synced': count, 'skipped': skipped}


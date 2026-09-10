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
            # 1. Sync UOMs first so Frappe has them before products/sales reference them
            self._sync_uoms(tenant)

            # 2. Pull Frappe Items → Odoo (bidirectional product sync)
            pull_res = self._pull_products_from_frappe(tenant)
            
            # 3. Pull Frappe Users → Odoo
            u_pull_res = self._pull_users_from_frappe(tenant)

            # 4. Pull Frappe Warehouses → Odoo Stores
            st_pull_res = self._pull_stores_from_frappe(tenant)

            # 5. Push Odoo data → Frappe
            p_res = self._sync_products(tenant)
            c_res = self._sync_customers(tenant)
            s_res = self._sync_stores(tenant)
            sa_res = self._sync_sales(tenant)
            u_push_res = self._sync_users(tenant)

            pull_s, pull_sk = pull_res['synced'], pull_res['skipped']
            u_pull_s, u_pull_sk = u_pull_res['synced'], u_pull_res['skipped']
            st_pull_s, st_pull_sk = st_pull_res['synced'], st_pull_res['skipped']
            
            p_s, p_sk = p_res['synced'], p_res['skipped']
            c_s, c_sk = c_res['synced'], c_res['skipped']
            s_s, s_sk = s_res['synced'], s_res['skipped']
            sa_s, sa_sk = sa_res['synced'], sa_res['skipped']
            u_push_s, u_push_sk = u_push_res['synced'], u_push_res['skipped']

            msg = (
                f'Pulled from Frappe: {pull_s} Products (skipped: {pull_sk}), {u_pull_s} Users (skipped: {u_pull_sk}), {st_pull_s} Stores (skipped: {st_pull_sk}).\n'
                f'Pushed to Frappe: {p_s} Products, {c_s} Customers, {s_s} Stores, {sa_s} Sales, {u_push_s} Users.\n'
                f'Skipped (already in Frappe): {p_sk} Products, {c_sk} Customers, {s_sk} Stores, {sa_sk} Sales, {u_push_sk} Users.'
            )
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
            try:
                self._log(tenant, 'All Entities', 'error', str(e))
            except Exception:
                pass  # Never let a failed log write mask the real error
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

    def _frappe_post(self, tenant, doctype, data, silent_409=False):
        """POST a new document to Frappe.

        If *silent_409* is True, a 409 Conflict (DuplicateEntryError) is
        treated as "already exists" and returns {'exists': True} without
        writing an error log entry.
        """
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
            if e.code == 409 and silent_409:
                # Record already exists in Frappe — not an error
                return {'exists': True}
            err_body = e.read().decode()
            self._log(tenant, doctype, 'error', f'Failed to post: HTTP {e.code} - {err_body}')
            return None
        except Exception as e:
            self._log(tenant, doctype, 'error', f'Failed to post: {str(e)}')
            return None

    def _frappe_put(self, tenant, doctype, doc_name, data):
        """PUT (update) an existing document in Frappe.

        Adds an empty 'Expect' header to suppress urllib's default
        'Expect: 100-continue' which causes HTTP 417 on many servers.
        """
        url = f"{tenant.frappe_url.rstrip('/')}/api/resource/{urllib.parse.quote(doctype)}/{urllib.parse.quote(str(doc_name))}"
        payload = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(url, data=payload, method='PUT', headers={
            'Authorization': f'token {tenant.frappe_api_key}:{tenant.frappe_api_secret}',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Expect': '',  # Suppress 'Expect: 100-continue' — prevents HTTP 417
        })
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                return json.loads(response.read().decode()).get('data', {})
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode()
            except Exception:
                err_body = str(e)
            try:
                self._log(tenant, doctype, 'error', f'Failed to update: HTTP {e.code} - {err_body}')
            except Exception:
                pass
            return None
        except Exception as e:
            try:
                self._log(tenant, doctype, 'error', f'Failed to update: {str(e)}')
            except Exception:
                pass
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
        """Write a sync log entry inside its own savepoint.

        Using a savepoint ensures that a failed log write (e.g. cursor in an
        aborted transaction) never rolls back work already done by the caller.
        """
        try:
            with self.env.cr.savepoint():
                self.env['frappe.sync.log'].create({
                    'tenant_id': tenant.id,
                    'entity': entity,
                    'status': status,
                    'details': details,
                    'records_synced': records
                })
        except Exception:
            pass  # Log failures must never crash the sync

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

    def _get_frappe_uom(self, tenant, preferred_name=None):
        """Return the best matching UOM name from Frappe.

        If *preferred_name* is given, look for an exact (case-insensitive)
        match first so we honour the product's actual UOM.  Fall back to
        'Nos' / 'Each' / first available UOM if nothing matches.
        """
        uoms = self._frappe_get(tenant, 'UOM', limit=100)
        uom_map = {u.get('name', '').lower(): u.get('name') for u in uoms}

        if preferred_name:
            # Exact match (case-insensitive)
            match = uom_map.get(preferred_name.lower())
            if match:
                return match

        # Generic fallbacks
        for fallback in ['nos', 'each', 'unit', 'piece', 'pcs']:
            if fallback in uom_map:
                return uom_map[fallback]

        return uoms[0].get('name') if uoms else 'Nos'

    def _sync_uoms(self, tenant):
        """Push Odoo UOMs to Frappe's UOM doctype so items can reference them.

        Uses a high limit when fetching existing Frappe UOMs to reduce cache
        misses.  Any 409 Conflict (UOM already exists) is silently ignored.
        """
        frappe_uoms = self._frappe_get(tenant, 'UOM', limit=500)
        frappe_uom_names = {u.get('name', '').lower(): u.get('name') for u in frappe_uoms}

        odoo_uoms = self.env['havanoposdesk.uom'].search([('tenant_id', '=', tenant.id)])
        pushed = 0
        for uom in odoo_uoms:
            if uom.name.lower() in frappe_uom_names:
                continue  # Already exists — skip without hitting the API
            # silent_409=True: if it sneaked in between our fetch and the POST, ignore it
            res = self._frappe_post(tenant, 'UOM', {'uom_name': uom.name}, silent_409=True)
            if res and res.get('name'):
                pushed += 1
            # res == {'exists': True} means it was already there — also fine
        if pushed:
            self._log(tenant, 'UOM', 'success', f'Pushed {pushed} UOMs to Frappe', pushed)

    def _get_or_create_odoo_uom(self, tenant, uom_name):
        """Find an existing havanoposdesk.uom by name (case-insensitive) or create it."""
        if not uom_name:
            uom_name = 'Each'
        uom = self.env['havanoposdesk.uom'].sudo().search([
            ('tenant_id', '=', tenant.id),
            ('name', '=ilike', uom_name.strip())
        ], limit=1)
        if not uom:
            uom = self.env['havanoposdesk.uom'].sudo().create({
                'name': uom_name.strip(),
                'tenant_id': tenant.id,
            })
        return uom

    def _get_or_create_odoo_category(self, tenant, group_name):
        """Find or create a havanoposdesk.category matching *group_name*."""
        if not group_name:
            return self.env['havanoposdesk.category'].sudo().search(
                [('tenant_id', '=', tenant.id)], limit=1
            )
        cat = self.env['havanoposdesk.category'].sudo().search([
            ('tenant_id', '=', tenant.id),
            ('name', '=ilike', group_name.strip())
        ], limit=1)
        if not cat:
            # Try to create it; if the name is too generic just grab the first
            try:
                cat = self.env['havanoposdesk.category'].sudo().create({
                    'name': group_name.strip(),
                    'tenant_id': tenant.id,
                })
            except Exception:
                cat = self.env['havanoposdesk.category'].sudo().search(
                    [('tenant_id', '=', tenant.id)], limit=1
                )
        return cat

    def _pull_products_from_frappe(self, tenant):
        """Pull Frappe Items → Odoo as havanoposdesk.product records.

        Full variance sync — creates new products AND updates ALL changed
        fields on existing ones:
          item_code, name, selling_price, buying_price, uom_id,
          track_qty, is_active, barcode, internal_notes, category_id,
          discount_percentage.

        Logs:
          'success'  — product created or updated
          'skipped'  — product exists and nothing changed (shown as 'Existing')
          'error'    — create/update failed
        """
        frappe_items = self._frappe_get(tenant, 'Item', limit=2000)
        if not frappe_items:
            return {'synced': 0, 'skipped': 0}

        # Build lookup: item_code → Odoo product record
        existing_products = self.env['havanoposdesk.product'].sudo().search([
            ('tenant_id', '=', tenant.id)
        ])
        code_to_product = {p.item_code: p for p in existing_products if p.item_code}
        name_to_product = {p.name.lower(): p for p in existing_products}

        # Default category fallback
        default_category = self.env['havanoposdesk.category'].sudo().search([
            ('tenant_id', '=', tenant.id)
        ], limit=1)

        # Default store for new products
        default_store = self.env['havanoposdesk.store'].sudo().search([
            ('tenant_id', '=', tenant.id)
        ], limit=1)

        created = 0
        updated = 0
        skipped = 0
        errors = 0

        for item in frappe_items:
            item_code    = (item.get('item_code') or item.get('name') or '').strip()
            item_name    = (item.get('item_name') or item_code).strip()
            frappe_sell  = float(item.get('standard_rate') or 0.0)
            frappe_buy   = float(item.get('valuation_rate') or 0.0)
            frappe_track = bool(item.get('is_stock_item', 1))
            frappe_active = not bool(item.get('disabled', 0))
            frappe_notes  = (item.get('description') or '').strip()
            frappe_barcode = (item.get('barcode') or '').strip()
            frappe_group   = (item.get('item_group') or '').strip()
            frappe_discount = float(item.get('discount_percentage') or 0.0)

            if not item_code:
                continue

            # Resolve UOM
            uom_name = item.get('stock_uom') or 'Each'
            uom = self._get_or_create_odoo_uom(tenant, uom_name)

            # Resolve category from Frappe item_group
            if frappe_group:
                category = self._get_or_create_odoo_category(tenant, frappe_group)
            else:
                category = default_category

            # --- UPDATE existing product (variance sync) ---
            odoo_product = code_to_product.get(item_code) or name_to_product.get(item_name.lower())
            if odoo_product:
                update_vals = {}

                if abs(odoo_product.selling_price - frappe_sell) > 0.001:
                    update_vals['selling_price'] = frappe_sell
                if abs(odoo_product.buying_price - frappe_buy) > 0.001:
                    update_vals['buying_price'] = frappe_buy
                if odoo_product.track_qty != frappe_track:
                    update_vals['track_qty'] = frappe_track
                if odoo_product.is_active != frappe_active:
                    update_vals['is_active'] = frappe_active
                if uom.id and odoo_product.uom_id.id != uom.id:
                    update_vals['uom_id'] = uom.id
                if frappe_notes and odoo_product.internal_notes != frappe_notes:
                    update_vals['internal_notes'] = frappe_notes
                if frappe_barcode and odoo_product.barcode != frappe_barcode:
                    update_vals['barcode'] = frappe_barcode
                if category and odoo_product.category_id.id != category.id:
                    update_vals['category_id'] = category.id
                if frappe_discount and abs(odoo_product.discount_percentage - frappe_discount) > 0.001:
                    update_vals['discount_percentage'] = frappe_discount
                # Keep name in sync if Frappe item_name changed
                if item_name and odoo_product.name != item_name:
                    update_vals['name'] = item_name

                if update_vals:
                    try:
                        with self.env.cr.savepoint():
                            odoo_product.sudo().write(update_vals)
                        updated += 1
                    except Exception as e:
                        errors += 1
                        self._log(tenant, 'Item (pull)', 'error',
                                  f'Failed to update "{item_name}" ({item_code}): {str(e)}')
                else:
                    # No changes — log as 'Existing' (skipped)
                    skipped += 1
                    self._log(tenant, f'Item: {item_code}', 'skipped',
                              f'Product "{item_name}" already up to date in Odoo')
                continue

            # --- CREATE new product ---
            try:
                vals = {
                    'item_code': item_code,
                    'name': item_name,
                    'selling_price': frappe_sell,
                    'buying_price': frappe_buy,
                    'track_qty': frappe_track,
                    'is_active': frappe_active,
                    'uom_id': uom.id,
                    'tenant_id': tenant.id,
                    'internal_notes': frappe_notes,
                    'discount_percentage': frappe_discount,
                }
                if category:
                    vals['category_id'] = category.id
                if frappe_barcode:
                    vals['barcode'] = frappe_barcode
                if default_store:
                    vals['store_ids'] = [(4, default_store.id)]

                with self.env.cr.savepoint():
                    new_prod = self.env['havanoposdesk.product'].sudo().create(vals)
                code_to_product[item_code] = new_prod
                name_to_product[item_name.lower()] = new_prod
                created += 1
            except Exception as e:
                errors += 1
                self._log(tenant, 'Item (pull)', 'error',
                          f'Failed to create "{item_name}" ({item_code}): {str(e)}')

        total = created + updated
        if total > 0 or errors > 0:
            self._log(tenant, 'Item (pull)', 'success' if total > 0 else 'error',
                      f'Frappe → Odoo: {created} created, {updated} updated, {skipped} existing, {errors} errors',
                      total)
        return {'synced': total, 'skipped': skipped}

    def _sync_products(self, tenant):
        """Push Odoo products TO Frappe as Items.

        Full variance sync — creates new AND updates changed fields:
          item_name, standard_rate, valuation_rate, stock_uom,
          is_stock_item, description, barcode.

        Logs 'skipped' (shown as 'Existing') when nothing changed.
        """
        frappe_items_list = self._frappe_get(tenant, 'Item', limit=2000)
        frappe_item_map = {}
        for i in frappe_items_list:
            code = i.get('item_code') or i.get('name', '')
            if code:
                frappe_item_map[code] = i

        item_group   = self._get_frappe_item_group(tenant)
        fallback_uom = self._get_frappe_uom(tenant)

        products = self.env['havanoposdesk.product'].search([
            ('tenant_id', '=', tenant.id),
            ('is_active', '=', True)
        ])

        created = 0
        updated = 0
        skipped = 0
        errors = 0

        for product in products:
            code = product.item_code or product.name
            product_uom_name = product.uom_id.name if product.uom_id else None
            stock_uom = self._get_frappe_uom(tenant, preferred_name=product_uom_name) if product_uom_name else fallback_uom

            if code in frappe_item_map:
                # --- UPDATE existing Frappe item if values differ ---
                existing    = frappe_item_map[code]
                update_data = {}

                if abs(float(existing.get('standard_rate') or 0.0) - product.selling_price) > 0.001:
                    update_data['standard_rate'] = product.selling_price
                if abs(float(existing.get('valuation_rate') or 0.0) - product.buying_price) > 0.001:
                    update_data['valuation_rate'] = product.buying_price
                if (existing.get('item_name') or '') != product.name:
                    update_data['item_name'] = product.name
                if (existing.get('stock_uom') or '').lower() != stock_uom.lower():
                    update_data['stock_uom'] = stock_uom
                if bool(existing.get('is_stock_item', 1)) != product.track_qty:
                    update_data['is_stock_item'] = 1 if product.track_qty else 0
                odoo_barcode = product.barcode or ''
                if odoo_barcode and (existing.get('barcode') or '') != odoo_barcode:
                    update_data['barcode'] = odoo_barcode
                odoo_notes = product.internal_notes or ''
                if odoo_notes and (existing.get('description') or '') != odoo_notes:
                    update_data['description'] = odoo_notes

                if update_data:
                    res = self._frappe_put(tenant, 'Item', code, update_data)
                    if res and res.get('name'):
                        updated += 1
                    else:
                        errors += 1
                else:
                    # Nothing changed — log as Existing
                    skipped += 1
                    self._log(tenant, f'Item: {code}', 'skipped',
                              f'Product "{product.name}" already up to date in Frappe')
            else:
                # --- CREATE new Frappe item ---
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
                if product.barcode:
                    item_data['barcode'] = product.barcode
                res = self._frappe_post(tenant, 'Item', item_data)
                if res and res.get('name'):
                    created += 1
                else:
                    errors += 1
                    self._log(tenant, 'Item', 'error',
                              f'Failed to push "{product.name}" (code={code}, uom={stock_uom})')

        total = created + updated
        if total > 0 or errors > 0:
            self._log(tenant, 'Item (push)', 'success' if total > 0 else 'error',
                      f'Odoo → Frappe: {created} created, {updated} updated, {skipped} existing, {errors} errors',
                      total)
        return {'synced': total, 'skipped': skipped}

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

    def _pull_stores_from_frappe(self, tenant):
        """Pull Frappe Warehouses -> Odoo Stores (havanoposdesk.store)"""
        frappe_warehouses = self._frappe_get(tenant, 'Warehouse', limit=500)
        if not frappe_warehouses:
            return {'synced': 0, 'skipped': 0}

        odoo_stores = self.env['havanoposdesk.store'].sudo().search([('tenant_id', '=', tenant.id)])
        name_to_store = {s.name.lower(): s for s in odoo_stores if s.name}

        created = 0
        updated = 0
        skipped = 0
        errors = 0

        for f_wh in frappe_warehouses:
            wh_name = f_wh.get('warehouse_name') or f_wh.get('name')
            if not wh_name or wh_name == 'All Warehouses':
                continue
                
            is_active = not bool(f_wh.get('disabled', 0))

            odoo_store = name_to_store.get(wh_name.lower())
            if odoo_store:
                if odoo_store.active != is_active:
                    try:
                        with self.env.cr.savepoint():
                            odoo_store.sudo().write({'active': is_active})
                        updated += 1
                    except Exception as e:
                        errors += 1
                        self._log(tenant, 'Store (pull)', 'error', f'Failed to update "{wh_name}": {str(e)}')
                else:
                    skipped += 1
                continue

            # Create new store in Odoo
            try:
                vals = {
                    'name': wh_name,
                    'tenant_id': tenant.id,
                    'active': is_active,
                }
                with self.env.cr.savepoint():
                    new_store = self.env['havanoposdesk.store'].sudo().create(vals)
                name_to_store[wh_name.lower()] = new_store
                created += 1
            except Exception as e:
                errors += 1
                self._log(tenant, 'Store (pull)', 'error', f'Failed to create "{wh_name}": {str(e)}')

        total = created + updated
        if total > 0 or errors > 0:
            self._log(tenant, 'Store (pull)', 'success' if total > 0 else 'error', 
                      f'Frappe → Odoo: {created} created, {updated} updated, {skipped} existing, {errors} errors', total)
        return {'synced': total, 'skipped': skipped}

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

    def _ensure_frappe_warehouse_exists(self, tenant, store_name, wh_name_to_id):
        """Ensure a warehouse exists in Frappe, create if not."""
        if not store_name:
            store_name = 'Main Store'
            
        # If it's already mapped, we have the Frappe ID
        for wh_name, wh_id in wh_name_to_id.items():
            if wh_name.lower() == store_name.lower():
                return wh_id
                
        # Create it in Frappe
        wh_data = {
            'warehouse_name': store_name,
            'company': self._get_frappe_company(tenant),
        }
        res = self._frappe_post(tenant, 'Warehouse', wh_data)
        if res and res.get('name'):
            wh_name_to_id[store_name] = res.get('name')
            return res.get('name')
        return None

    def _sync_sales(self, tenant):
        """Push Odoo sales to Frappe as Sales Invoices."""
        frappe_invoices = self._frappe_get(tenant, 'Sales Invoice', limit=2000)
        synced_sales = {inv.get('po_no'): True for inv in frappe_invoices if inv.get('po_no')}

        # Fetch Frappe warehouses to map to Odoo stores
        frappe_whs = self._frappe_get(tenant, 'Warehouse', limit=500)
        wh_name_to_id = {w.get('warehouse_name', w.get('name', '')): w.get('name') for w in frappe_whs}

        sales = self.env['havanoposdesk.sale'].search([
            ('tenant_id', '=', tenant.id),
            ('state', 'in', ['done', 'confirmed'])
        ], limit=50, order='id asc')

        item_group = self._get_frappe_item_group(tenant)
        fallback_uom = self._get_frappe_uom(tenant)

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
                product = line.product_id
                code = product.item_code or product.name
                name = product.name
                # Resolve the line's UOM (product UOM or fallback)
                line_uom_name = product.uom_id.name if product.uom_id else None
                line_uom = self._get_frappe_uom(tenant, preferred_name=line_uom_name) if line_uom_name else fallback_uom
                # Best-effort: create item in Frappe if missing
                self._ensure_frappe_item_exists(tenant, code, name, item_group, line_uom)
                items.append({
                    'item_code': code,
                    'item_name': name,
                    'qty': line.accepted_qty or 1.0,
                    'rate': line.rate or 0.0,
                    'uom': line_uom,
                })

            if not items:
                continue

            customer_name = sale.customer.name if sale.customer else 'CASH'
            store_name = sale.store or (sale.store_id.name if sale.store_id else '')
            frappe_wh_id = self._ensure_frappe_warehouse_exists(tenant, store_name, wh_name_to_id)

            data = {
                'customer': customer_name,
                'po_no': sale.name,
                'items': items,
                'update_stock': 1,
                'set_posting_time': 1,
                'posting_date': str(sale.posting_date) if sale.posting_date else str(fields.Date.today()),
                'docstatus': 1,
            }
            if frappe_wh_id:
                data['set_warehouse'] = frappe_wh_id

            res = self._frappe_post(tenant, 'Sales Invoice', data)
            if res and res.get('name'):
                self._log(tenant, f'Sale: {sale.name}', 'success', f'Pushed as {res.get("name")}', 1)
                count += 1
            else:
                self._log(tenant, f'Sale: {sale.name}', 'error', 'Failed to push to Frappe')

        if count > 0:
            self._log(tenant, 'Sales Invoice', 'success', f'Pushed {count} sales to Frappe', count)
        return {'synced': count, 'skipped': skipped}

    def _pull_users_from_frappe(self, tenant):
        """Pull Frappe Users -> Odoo res.users (tenant specific)"""
        frappe_users = self._frappe_get(tenant, 'User', limit=1000)
        if not frappe_users:
            return {'synced': 0, 'skipped': 0}

        odoo_users = self.env['res.users'].sudo().search([('tenant_id', '=', tenant.id)])
        login_to_user = {u.login.lower(): u for u in odoo_users}

        created = 0
        updated = 0
        skipped = 0
        errors = 0

        # Don't sync internal Frappe users
        ignore_emails = ['Administrator', 'Guest']

        for f_user in frappe_users:
            email = (f_user.get('email') or f_user.get('name') or '').strip()
            if not email or email in ignore_emails or '@' not in email:
                continue

            # In Frappe, full_name is often calculated from first_name + last_name
            f_first = (f_user.get('first_name') or '').strip()
            f_last = (f_user.get('last_name') or '').strip()
            f_name = f_user.get('full_name') or f"{f_first} {f_last}".strip() or email
            f_active = bool(f_user.get('enabled', 1))

            odoo_user = login_to_user.get(email.lower())
            
            if odoo_user:
                update_vals = {}
                if odoo_user.name != f_name:
                    update_vals['name'] = f_name
                if odoo_user.active != f_active:
                    update_vals['active'] = f_active

                if update_vals:
                    try:
                        with self.env.cr.savepoint():
                            odoo_user.sudo().write(update_vals)
                        updated += 1
                    except Exception as e:
                        errors += 1
                        self._log(tenant, 'User (pull)', 'error', f'Failed to update "{email}": {str(e)}')
                else:
                    skipped += 1
                    self._log(tenant, f'User: {email}', 'skipped', f'User "{email}" already up to date in Odoo')
                continue

            # CREATE
            try:
                # Assign default values suitable for POS cashiers in Havano
                vals = {
                    'name': f_name,
                    'login': email,
                    'active': f_active,
                    'tenant_id': tenant.id,
                    'havano_role': 'cashier',
                    'saas_state': 'verified', 
                }
                with self.env.cr.savepoint():
                    new_user = self.env['res.users'].sudo().create(vals)
                login_to_user[email.lower()] = new_user
                created += 1
            except Exception as e:
                errors += 1
                self._log(tenant, 'User (pull)', 'error', f'Failed to create "{email}": {str(e)}')

        total = created + updated
        if total > 0 or errors > 0:
            self._log(tenant, 'User (pull)', 'success' if total > 0 else 'error', 
                      f'Frappe → Odoo: {created} created, {updated} updated, {skipped} existing, {errors} errors', total)
        return {'synced': total, 'skipped': skipped}

    def _sync_users(self, tenant):
        """Push Odoo res.users -> Frappe User"""
        frappe_users_list = self._frappe_get(tenant, 'User', limit=1000)
        frappe_user_map = {}
        for u in frappe_users_list:
            email = u.get('email') or u.get('name')
            if email:
                frappe_user_map[email.lower()] = u

        odoo_users = self.env['res.users'].sudo().search([('tenant_id', '=', tenant.id)])

        created = 0
        updated = 0
        skipped = 0
        errors = 0

        for user in odoo_users:
            if not user.login or '@' not in user.login:
                continue

            email = user.login.lower()
            name_parts = user.name.split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''

            if email in frappe_user_map:
                existing = frappe_user_map[email]
                update_data = {}

                # Variance checks
                if (existing.get('first_name') or '') != first_name:
                    update_data['first_name'] = first_name
                if (existing.get('last_name') or '') != last_name:
                    update_data['last_name'] = last_name
                if bool(existing.get('enabled', 1)) != user.active:
                    update_data['enabled'] = 1 if user.active else 0

                if update_data:
                    res = self._frappe_put(tenant, 'User', email, update_data)
                    if res and res.get('name'):
                        updated += 1
                    else:
                        errors += 1
                else:
                    skipped += 1
                    self._log(tenant, f'User: {email}', 'skipped', f'User "{email}" already up to date in Frappe')
            else:
                user_data = {
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'enabled': 1 if user.active else 0,
                    'send_welcome_email': 0,
                }
                res = self._frappe_post(tenant, 'User', user_data)
                if res and res.get('name'):
                    created += 1
                else:
                    errors += 1
                    self._log(tenant, 'User', 'error', f'Failed to push user "{email}"')

        total = created + updated
        if total > 0 or errors > 0:
            self._log(tenant, 'User (push)', 'success' if total > 0 else 'error', 
                      f'Odoo → Frappe: {created} created, {updated} updated, {skipped} existing, {errors} errors', total)
        return {'synced': total, 'skipped': skipped}

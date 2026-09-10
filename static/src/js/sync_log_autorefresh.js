/** @odoo-module **/
import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { useEffect } from "@odoo/owl";

/**
 * Auto-refresh patch for frappe.sync.log list views.
 * Reloads the list every 60 seconds so sync results appear live.
 */
patch(listView.Controller.prototype, {
    setup() {
        super.setup(...arguments);
        if (this.props.resModel === "frappe.sync.log") {
            useEffect(() => {
                const interval = setInterval(() => {
                    if (this.model) {
                        this.model.load();
                    }
                }, 60000); // 60 seconds
                return () => clearInterval(interval);
            }, () => []);
        }
    },
});

/** @odoo-module **/

import { WebClient } from "@web/webclient/webclient";
import { useService } from "@web/core/utils/hooks";
import { CustomeNavBar } from "./navbar/navbar";

export class WebClientCustome extends WebClient {
    static components = {
        ...WebClient.components,
        NavBar: CustomeNavBar,
    };
    setup() {
        super.setup();
        this.hm = useService("home_menu");
    }
    _loadDefaultApp() {
        return this.hm.toggle(true);
    }
}

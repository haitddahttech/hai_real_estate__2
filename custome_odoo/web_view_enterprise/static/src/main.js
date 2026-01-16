/** @odoo-module **/

import { startWebClient } from "@web/start";
import { WebClientCustome } from "./webclient/webclient";

/**
 * This file starts the enterprise webclient. In the manifest, it replaces
 * the community main.js to load a different webclient class
 * (WebClientCustome instead of WebClient)
 */
startWebClient(WebClientCustome);

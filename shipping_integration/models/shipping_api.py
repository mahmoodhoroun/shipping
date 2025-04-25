import requests
import json
from odoo import models, fields, api
import logging

class ShippingAPI(models.Model):
    _name = 'shipping.api'
    _description = 'Shipping API Integration'

    auth_cookie = fields.Char(string="Auth Cookie")
    csrf_token = fields.Char(string="CSRF-TOKEN")


    @api.model
    def authenticate(self):
        url = "https://api.cathedis.delivery/login.jsp"
        payload = json.dumps({
            "username": "SEBINFO",
            "password": "zV38Zqj2"
        })
        headers = {'Content-Type': 'application/json'}

        response = requests.post(url, headers=headers, data=payload)
        if response.status_code == 200:
            # Extract cookies
            jsessionid = response.cookies.get('JSESSIONID')
            csrf_token = response.cookies.get('CSRF-TOKEN')

            if jsessionid and csrf_token:
                # Save cookies in Odoo's system parameters
                self.env['ir.config_parameter'].sudo().set_param('shipping_api.jsessionid', jsessionid)
                self.env['ir.config_parameter'].sudo().set_param('shipping_api.csrf_token', csrf_token)
                logging.info("Authentication successful. Cookies saved.")
            else:
                logging.warning("Authentication response did not include both JSESSIONID and CSRF-TOKEN.")
        else:
            # Handle error logging
            logging.error("Authentication failed with status code: %s", response.status_code)

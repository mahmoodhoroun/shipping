import requests
import json
from odoo import models, fields, api
import logging
import base64
import os
from odoo.exceptions import UserError
from odoo.modules.module import get_module_resource
from werkzeug.urls import url_encode
import pexpect

delivery_counter = 1
_logger = logging.getLogger(__name__)
class StockPicking(models.Model):
    _inherit = 'stock.picking'

    delivery_id = fields.Char(string="Delivery ID")
    subject = fields.Char(string="Subject", default="DIVERS")
    paymentType = fields.Char(string="Payment Type", default="ESPECES")
    caution = fields.Char(string="Caution", default="0")
    fragile = fields.Char(string="Fragile", default="0")
    allowOpening = fields.Char(string="Allow Opening", default="1")
    rangeWeight = fields.Selection(selection=[
            ("ONE_FIVE", "Between 1Kg and 5Kg"),
            ("SIX_TEN", "Between 6Kg and 10Kg"),
            ("ELEVEN_TWENTY_NINE", "Between 11Kg and 29Kg"),
            ('MORE_30', 'More than 30Kg'),],string="Range Weight", default="ONE_FIVE")
    new_state = fields.Selection(
        selection=[('delivered', 'Sent to Cathedis'),
                    ('delivery_print', 'Delivery Printed'),
                    ('delivery_pickup', 'Delivery Picked Up')])

    print = fields.Boolean(string="Print", default=False)

    def call_shipping_api(self):
        for rec in self:
            if rec.caution not in ['0', '1'] and rec.fragile not in ['0', '1'] and rec.allowOpening not in ['0', '1']:
                raise UserError("Make sure that Caution, Fragile and Allow Opening is 0 or 1")
            # print(self.caution)
            # print(self.caution)
            # print(self.caution)
            # Retrieve cookies from system parameters
            if not rec.delivery_id:
                jsessionid = self.env['ir.config_parameter'].sudo().get_param('shipping_api.jsessionid')
                csrf_token = self.env['ir.config_parameter'].sudo().get_param('shipping_api.csrf_token')

                if not jsessionid or not csrf_token:
                    _logger.warning("Cookies are missing. Authentication might have failed.")
                    return

                url = "https://api.cathedis.delivery/ws/action"
                payload = json.dumps({
                    "action": "delivery.api.save",
                    "data": {
                        "context": {
                            "delivery": {
                                "recipient": rec.partner_id.name,
                                "city": rec.partner_id.city,
                                "sector": rec.partner_id.zip or "",
                                "phone": rec.partner_id.phone or rec.partner_id.mobile,
                                "amount": str(rec.sale_id.amount_total),
                                "caution": rec.caution,
                                "fragile": rec.fragile,
                                "declaredValue": str(rec.sale_id.amount_total),
                                "address": rec.partner_id.street or "",
                                "nomOrder": rec.sale_id.name,
                                "comment": "",
                                "rangeWeight": str(rec.rangeWeight),
                                "subject": rec.subject,
                                "paymentType": rec.paymentType,
                                "deliveryType": "Livraison CRBT",
                                "packageCount": "1",
                                "allowOpening": rec.allowOpening,
                                "tags": ""
                            }
                        }
                    }
                })
                _logger.info(payload)
                headers = {
                    'Content-Type': 'application/json',
                    'Cookie': f'CSRF-TOKEN={csrf_token}; JSESSIONID={jsessionid}'
                }

                response = requests.post(url, headers=headers, data=payload)

                if response.status_code == 200:
                    response_data = response.json()
                    # Extract the delivery ID from the response data
                    delivery_id = response_data.get("data", [{}])[0].get("values", {}).get("delivery", {}).get("id")

                    if delivery_id:
                        rec.delivery_id = str(delivery_id)  # Store the delivery ID in the field
                        _logger.info("API call successful. Delivery ID: %s", delivery_id)
                        rec.new_state = 'delivered'
                    else:
                        _logger.warning("Delivery ID not found in the response.")
                        _logger.info("*****************************")
                        _logger.info(response_data)

                        raise ValueError("Delivery ID not found in the response.")
                else:
                    _logger.error("API call failed with status %s: %s", response.status_code, response.text)
                    raise ValueError("Delivery ID not found in the response.%s: %s", response.status_code, response.text)

    def action_generate_delivery_pdf(self):
        ids = [int(rec.delivery_id) for rec in self]
        global delivery_counter

        # Fetch the authentication cookies
        jsessionid = self.env['ir.config_parameter'].sudo().get_param('shipping_api.jsessionid')
        csrf_token = self.env['ir.config_parameter'].sudo().get_param('shipping_api.csrf_token')
        media_dir = '/home/mahmood/PycharmProjects/odoo17-3/custom_addons/shipping_integration/static/media'

        # Validate the required configuration parameters
        if not jsessionid or not csrf_token:
            raise UserError("Authentication cookies are missing. Please ensure the scheduled authentication is running correctly.")
        if not media_dir:
            raise UserError("The media directory is not properly configured.")

        # Prepare the payload and headers for the API call
        url = "https://api.cathedis.delivery/ws/action"
        payload = {
            "action": "delivery.print.bl4x4",
            "data": {
                "context": {
                    "_ids": ids,
                    "_model": "com.tracker.delivery.db.Delivery",
                }
            },
        }
        headers = {
            'Content-Type': 'application/json',
            'Cookie': f'CSRF-TOKEN={csrf_token}; JSESSIONID={jsessionid}',
        }
        response = requests.post(url, json=payload, headers=headers)

        if response.status_code == 200:
            response_data = response.json()
            pdf_path = response_data.get("data", [{}])[0].get("view", {}).get("views", [{}])[0].get("name")
            if pdf_path:
                # Fetch and save the PDF
                pdf_url = f"https://api.cathedis.delivery/{pdf_path}"
                pdf_response = requests.get(pdf_url, stream=True, headers=headers)

                # Define the path to save the PDF inside the container
                os.makedirs(media_dir, exist_ok=True)
                file_name = f"delivery_{delivery_counter}.pdf"
                file_path = os.path.join(media_dir, file_name)
                file_url = f"/shipping_integration/static/media/{file_name}"
                
                delivery_counter += 1

                # Save the file
                with open(file_path, 'wb') as pdf_file:
                    for chunk in pdf_response.iter_content(chunk_size=1024):
                        pdf_file.write(chunk)

                # Automate the SSH connection and password entry using pexpect
                try:
                    ssh_command = "ssh root@10.19.0.5 'sh /usr/local/bin/move_and_fix_permissions.sh'"
                    child = pexpect.spawn(ssh_command)
                    
                    # Expect the password prompt
                    child.expect("password:")
                    # Send the password
                    child.sendline("newStrongPass123")
                    # Wait for the command to complete
                    child.expect(pexpect.EOF)
                    
                    # Print the output for debugging (optional)
                    output = child.before.decode()
                    print("SSH Output:", output)

                except pexpect.ExceptionPexpect as e:
                    raise UserError(f"Failed to execute SSH command: {e}")

                for rec in self:
                    rec.print = True

                return {
                    'type': 'ir.actions.act_url',
                    'url': file_url,
                    'target': 'new',
                }
            else:
                raise UserError("PDF URL not found in the response.")
        else:
            raise UserError(f"Failed to fetch PDF URL with status code: {response.status_code}")
    def action_refresh_pickup_request(self):
        ids = []
        for rec in self:
            ids.append(int(rec.delivery_id))
            rec.new_state = 'delivery_print'

        # Retrieve cookies from system parameters
        jsessionid = self.env['ir.config_parameter'].sudo().get_param('shipping_api.jsessionid')
        csrf_token = self.env['ir.config_parameter'].sudo().get_param('shipping_api.csrf_token')

        if not jsessionid or not csrf_token:
            raise UserError("Authentication cookies are missing. Please ensure the scheduled authentication is running correctly.")

        # Set the required URL and headers
        url = "https://api.cathedis.delivery/ws/action"
        headers = {
            'Content-Type': 'application/json',
            'Cookie': f'CSRF-TOKEN={csrf_token}; JSESSIONID={jsessionid}'
        }

        # Define the payload with sample values; adjust as needed
        payload = json.dumps({
            "action": "action-refresh-pickup-request",
            "model": "com.tracker.pickup.db.PickupRequest",
            "data": {
                "context": {
                    "ids": ids,  # Adjust these values dynamically if needed
                    "pickupPointId": 26301      # Adjust this value as required
                }
            }
        })

        # Make the POST request
        response = requests.post(url, headers=headers, data=payload)

        # Check the response and handle errors
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get("status") == 0:
                for rec in self:
                    rec.new_state = 'delivery_pickup'
                return response_data  # Successful response
            else:
                raise UserError(f"API Error: {response_data}")
        else:
            raise UserError(f"Failed to call API. Status Code: {response.status_code}, Response: {response.text}")
import requests
from bs4 import BeautifulSoup
import logging

from odoo import models, api, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

BNA_URL = "https://www.bna.com.ar/Personas"


class ResCurrency(models.Model):
    _inherit = "res.currency"

    @api.model
    def _get_bna_rate(self):
        """Obtiene la cotización del dólar desde BNA (Divisas)."""
        try:
            response = requests.get(BNA_URL, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            
            results = soup.find(id="divisas")
            if not results:
                raise UserError('No se encontró la tabla de divisas en BNA')
            
            rows = results.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                if cells and "Dolar U.S.A" in cells[0].text:
                    compra = cells[1].text.strip().replace(',', '.')
                    venta = cells[2].text.strip().replace(',', '.')
                    rate = float(compra)
                    _logger.info(f"Cotización BNA USD - Compra: {compra}, Venta: {venta}")
                    return rate
            
            raise UserError('No se encontró el Dólar U.S.A. en la tabla de divisas')
            
        except requests.RequestException as e:
            _logger.error(f"Error de conexión con BNA: {e}")
            raise UserError(f'Error al conectar con BNA: {e}')
        except Exception as e:
            _logger.error(f"Error al obtener cotización BNA: {e}")
            raise UserError(f'Error al procesar cotización BNA: {e}')

    @api.model
    def _cron_update_currency_rate_bna(self):
        """Cron job para actualizar la cotización del dólar desde BNA."""
        companies = self.env['res.company'].search([
            ('currency_rate_service', '=', 'bna')
        ])
        
        if not companies:
            _logger.info("No hay compañías configuradas para usar BNA")
            return
        
        rate = self._get_bna_rate()
        if not rate:
            return
        
        usd_currency = self.search([('name', '=', 'USD')], limit=1)
        if not usd_currency:
            _logger.warning("No se encontró la moneda USD en el sistema")
            return
        
        today = fields.Date.today()
        
        for company in companies:
            existing_rate = self.env['res.currency.rate'].search([
                ('currency_id', '=', usd_currency.id),
                ('company_id', '=', company.id),
                ('name', '=', today),
            ], limit=1)
            
            inverse_rate = 1.0 / rate
            
            if existing_rate:
                existing_rate.write({'rate': inverse_rate})
                _logger.info(f"Actualizada tasa USD para {company.name}: {rate} ARS")
            else:
                self.env['res.currency.rate'].create({
                    'currency_id': usd_currency.id,
                    'company_id': company.id,
                    'name': today,
                    'rate': inverse_rate,
                })
                _logger.info(f"Creada tasa USD para {company.name}: {rate} ARS")
        
        return True

    def action_update_rate_bna(self):
        """Acción manual para actualizar la cotización desde BNA."""
        self._cron_update_currency_rate_bna()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Cotización BNA',
                'message': 'Cotización actualizada correctamente',
                'sticky': False,
                'type': 'success',
            }
        }
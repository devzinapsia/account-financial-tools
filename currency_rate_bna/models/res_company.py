from odoo import models, fields
import requests
from bs4 import BeautifulSoup
import logging

_logger = logging.getLogger(__name__)

BNA_URL = "https://www.bna.com.ar/Personas"


class ResCompany(models.Model):
    _inherit = 'res.company'

    currency_provider = fields.Selection(
        selection_add=[('bna', '[AR] BNA - Banco Nación Argentina (Zinapsia)')],
        ondelete={'bna': 'set null'}
    )

    def _parse_bna_data(self, available_currencies):
        """Método llamado por el sistema de Odoo para obtener tasas desde BNA."""
        rslt = {}
        available_currency_names = available_currencies.mapped('name')
        
        try:
            response = requests.get(BNA_URL, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            
            results = soup.find(id="divisas")
            if not results:
                _logger.error('No se encontró la tabla de divisas en BNA')
                return rslt
            
            rows = results.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                if cells and "Dolar U.S.A" in cells[0].text:
                    compra = float(cells[1].text.strip().replace(',', '.'))
                    if 'USD' in available_currency_names:
                        rslt['USD'] = (1.0 / compra, fields.Date.today())
                    break
            
            # Agregar ARS como moneda base
            if 'ARS' in available_currency_names:
                rslt['ARS'] = (1.0, fields.Date.today())
                    
        except Exception as e:
            _logger.error(f"Error BNA: {e}")
        
        return rslt
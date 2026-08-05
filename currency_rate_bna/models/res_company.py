from odoo import models, fields, api
import requests
from bs4 import BeautifulSoup
import logging

_logger = logging.getLogger(__name__)

BNA_URL = "https://www.bna.com.ar/Personas"

# Headers de navegador real: BNA usa un WAF (F5) que puede rechazar
# clientes sin User-Agent / Accept de navegador.
BNA_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
}


class ResCompany(models.Model):
    _inherit = 'res.company'

    currency_provider = fields.Selection(
        selection_add=[('bna', '[AR] BNA - Banco Nación Argentina (Zinapsia)')],
        ondelete={'bna': 'set null'}
    )

    def update_currency_rates(self):
        """El módulo l10n_ar_currency_update (ARCA/AFIP, auto_install) pisa
        currency_provider a 'afip' para toda compañía AR mediante su propio
        _compute_currency_provider, sin respetar una selección manual de 'bna'.
        Nos auto-corregimos acá, justo antes de ejecutar la actualización real,
        para no depender del orden de carga de módulos ni de cuándo se
        dispara ese compute.
        """
        ar_bna_companies = self.filtered(
            lambda c: c.country_id.code == 'AR' and c.currency_provider == 'afip'
        )
        if ar_bna_companies:
            _logger.warning(
                "currency_provider fue sobrescrito a 'afip' (probablemente por "
                "l10n_ar_currency_update / ARCA). Restaurando 'bna' para: %s",
                ", ".join(ar_bna_companies.mapped('name')),
            )
            ar_bna_companies.currency_provider = 'bna'
        return super().update_currency_rates()

    def _parse_bna_data(self, available_currencies):
        """Método llamado por el sistema de Odoo para obtener tasas desde BNA."""
        rslt = {}
        available_currency_names = available_currencies.mapped('name')

        try:
            session = requests.Session()
            response = session.get(BNA_URL, headers=BNA_HEADERS, timeout=10)

            if response.status_code != 200:
                _logger.error(
                    "Error BNA: status_code=%s body=%.300s",
                    response.status_code, response.text,
                )
                return rslt

            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            results = soup.find(id="divisas")
            if not results:
                _logger.error(
                    "No se encontró la tabla de divisas en BNA (posible cambio "
                    "de estructura de la página). Primeros 300 caracteres: %.300s",
                    response.text,
                )
                return rslt

            rows = results.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                if cells and "Dolar U.S.A" in cells[0].text:
                    # Obtener la cotización de venta es la celda 2. Si queres compra, usa cells[1]
                    cotiz = float(cells[2].text.strip().replace(',', '.'))
                    if 'USD' in available_currency_names:
                        rslt['USD'] = (1.0 / cotiz, fields.Date.today())
                    break

            # Agregar ARS como moneda base
            if 'ARS' in available_currency_names:
                rslt['ARS'] = (1.0, fields.Date.today())

        except Exception as e:
            _logger.error("Error BNA: %s", e)

        return rslt
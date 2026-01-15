# -*- coding: utf-8 -*-
from odoo import models, fields, tools

# --- INICIO DEL DEBUG ---
import logging
_logger = logging.getLogger(__name__)
_logger.info("\n\n" + "="*50)
_logger.info(">>> ¡HOLA! ODOO ESTÁ CARGANDO EL ARCHIVO PROJECTED_FLOW_REPORT.PY <<<")
_logger.info("="*50 + "\n\n")
# --- FIN DEL DEBUG ---

class ProjectedFlowReport(models.Model):
    _name = "projected.flow.report"
    _description = "Reporte de Flujos Proyectados"
    _auto = False  # Esto indica que se basa en una Vista SQL, no una tabla normal
    _order = 'date_maturity asc'

    # Definimos los campos que vamos a mapear desde la consulta SQL
    move_id = fields.Many2one('account.move', string="Asiento Contable", readonly=True)
    name = fields.Char(string="Etiqueta", readonly=True)
    ref = fields.Char(string="Referencia", readonly=True)
    partner_id = fields.Many2one('res.partner', string="Empresa", readonly=True)
    account_id = fields.Many2one('account.account', string="Cuenta", readonly=True)
    
    # Fechas clave para la proyección
    date = fields.Date(string="Fecha Contable", readonly=True)
    date_maturity = fields.Date(string="Fecha Vencimiento", readonly=True)
    
    # Importes
    amount_residual = fields.Monetary(string="Importe Pendiente", currency_field='currency_id', readonly=True)
    currency_id = fields.Many2one('res.currency', string="Moneda", readonly=True)
    company_id = fields.Many2one('res.company', string="Compañía", readonly=True)
    
    # Tipo de flujo para agrupar (Cobrar vs Pagar)
    account_type = fields.Selection([
        ('asset_receivable', 'A Cobrar (Clientes)'),
        ('liability_payable', 'A Pagar (Proveedores)'),
    ], string="Tipo de Cuenta", readonly=True)

    def init(self):
        """
        Esta función se ejecuta al instalar/actualizar el módulo.
        Crea la vista SQL en PostgreSQL.
        """
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    aml.id AS id,
                    aml.move_id AS move_id,
                    aml.name AS name,
                    aml.ref AS ref,
                    aml.partner_id AS partner_id,
                    aml.account_id AS account_id,
                    aml.date AS date,
                    -- Si no tiene fecha de vencimiento, usamos la fecha contable
                    COALESCE(aml.date_maturity, aml.date) AS date_maturity,
                    aml.amount_residual AS amount_residual,
                    aml.currency_id AS currency_id,
                    aml.company_id AS company_id,
                    aa.account_type AS account_type
                FROM
                    account_move_line aml
                    JOIN account_account aa ON aml.account_id = aa.id
                    JOIN account_move am ON aml.move_id = am.id
                WHERE
                    -- Solo asientos publicados (no borradores)
                    aml.parent_state = 'posted'
                    -- Solo cuentas de cobrar y pagar (Mayores de clientes/proveedores)
                    AND aa.account_type IN ('asset_receivable', 'liability_payable')
                    -- Solo lo que tiene saldo pendiente (Flujo futuro)
                    AND aml.amount_residual != 0
                    -- Excluir conciliaciones totales (opcional, reforzado por residual != 0)
                    AND aml.reconciled IS FALSE
            )
        """ % self._table)
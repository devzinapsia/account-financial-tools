# Impedir borrador en facturas electrónicas por web service (ARCA) — Odoo 19

Este módulo desarrollado por **Zinapsia** añade una capa de seguridad crítica al flujo de facturación electrónica en Odoo 18. Su objetivo es garantizar la integridad legal de los comprobantes fiscales, impidiendo que documentos que ya poseen un **CAE (Código de Autorización Electrónico)** o autorización de AFIP puedan ser revertidos manualmente al estado "Borrador".

## 🚀 Funcionalidades Principales

* **Bloqueo de Reversión:** Detecta intentos de ejecutar la acción "Cambiar a Borrador" en facturas y notas de crédito de clientes.
* **Solo diarios con web service:** El bloqueo aplica únicamente cuando el diario de la factura tiene un web service de ARCA (WSFE, WSFEX, WSBFE, o cualquier otro agregado por módulos de terceros, como WSMTXCA) **y** la factura tiene CAE.
* **Diarios sin web service no se bloquean:** Las facturas de diarios "Factura en línea", preimpresos, etc. pueden volver a borrador aunque se les haya cargado un CAE manualmente (por ejemplo, comprobantes emitidos en un sistema externo).
* **Mensajes de Error Informativos:** Si un usuario intenta resetear una factura validada ante el fisco, el sistema lanza una excepción clara indicando el nombre del documento y su respectivo CAE.
* **Cumplimiento Fiscal:** Asegura que las correcciones de documentos autorizados se realicen exclusivamente mediante Notas de Crédito/Débito, manteniendo la trazabilidad exigida por los organismos fiscales.

## 🛠 Mejoras Técnicas (Zinapsia Edition)

* **Override Seguro de `action_draft`:** Implementación técnica limpia que utiliza `super()` para heredar la lógica nativa, asegurando total compatibilidad con otros módulos de la localización argentina.
* **Optimización V18:** Código refactorizado para el motor de Odoo 18, utilizando validaciones del lado del servidor que previenen la manipulación de datos desde la interfaz o llamadas API externas.
* **Detección Inteligente de Tipos:** El bloqueo se aplica de forma selectiva únicamente a documentos de salida (`out_invoice`, `out_refund`), permitiendo flexibilidad en facturas de proveedores si fuera necesario.

## 📦 Instalación

1.  Clona este repositorio en tu directorio de addons:
    ```bash
    git clone [https://github.com/devzinapsia/account-financial-tools.git](https://github.com/devzinapsia/account-financial-tools.git)
    ```
2.  Asegúrate de que la carpeta del módulo se llame `account_prevent_draft`.
3.  Actualiza la lista de aplicaciones en tu instancia de Odoo (Modo Desarrollador).
4.  Instala el módulo `account_prevent_draft`.

## 📖 Modo de Uso

1.  Dirígete al módulo de **Facturación** o **Contabilidad**.
2.  Selecciona una factura de cliente que ya haya sido validada y posea **CAE**.
3.  Intenta hacer clic en el botón **Restablecer a Borrador**.
4.  El sistema mostrará una alerta de validación impidiendo la acción y sugiriendo el uso de una nota de crédito para la anulación legal del comprobante.

## ⚖️ Licencia

Este módulo se distribuye bajo la licencia **LGPL-3**.

---
Desarrollado con ❤️ por **Zinapsia**.
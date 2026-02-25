# Partner Financial Defaults (Odoo V18/V19)

Este módulo desarrollado por **Zinapsia** permite centralizar y automatizar la configuración contable de los contactos en Odoo 18. Su objetivo es minimizar errores de carga manual y agilizar el proceso de facturación mediante la predefinición de reglas de negocio por partner, asegurando la integridad de los asientos contables.

## 🚀 Funcionalidades Principales

* **Cuentas Contables por Defecto:** Define cuentas de ingresos y gastos específicas para cada partner. Cuando se agrega una línea de factura sin producto, el sistema inyecta automáticamente la cuenta configurada en la ficha del contacto.
* **Impuestos Predeterminados:** Configura múltiples impuestos (ej. IVA 21% + Percepciones) para que se apliquen automáticamente en las líneas de factura, ideal para proveedores con regímenes especiales de retención/percepción.
* **Smart Auto-Update:** Capacidad opcional para que el sistema actualice automáticamente la cuenta por defecto en la ficha del contacto basándose en la última factura validada.
* **Control de Automatización:** Checkboxes granulares para habilitar o deshabilitar la actualización automática de cuentas, permitiendo un control total sobre la ficha del partner.

## 🛠 Mejoras Técnicas (Zinapsia Edition)

* **Optimización V18:** Refactorización completa utilizando `@api.onchange` y `@api.depends` sincronizados para evitar el reseteo de valores por parte del motor de impuestos nativo de Odoo 18.
* **Eliminación de Conflictos:** Se ha removido la lógica de descripciones automáticas para garantizar que el motor de búsqueda de cuentas de Odoo no entre en conflicto con las personalizaciones de Zinapsia.
* **Traducciones Integradas:** Etiquetas de interfaz definidas directamente en Python para garantizar una experiencia de usuario en español sin dependencias de archivos externos.

## 📦 Instalación

1.  Clona este repositorio en tu directorio de addons:
    ```bash
    git clone [https://github.com/devzinapsia/account-financial-tools.git](https://github.com/devzinapsia/account-financial-tools.git)
    ```
2.  Asegúrate de que la carpeta del módulo se llame `account_partner_defaults`.
3.  Actualiza la lista de aplicaciones en tu instancia de Odoo (Modo Desarrollador).
4.  Instala el módulo `account_partner_defaults`.

## 📖 Modo de Uso

1.  Navega a **Contactos** y selecciona un registro.
2.  En la pestaña **Contabilidad**, localiza la sección **Configuración Financiera por Defecto (Zinapsia)**.
3.  Define las cuentas contables y los impuestos predeterminados para compras y ventas.
4.  Al crear una factura y agregar una línea sin producto, Odoo completará automáticamente la cuenta y los impuestos con los valores definidos.

## ⚖️ Licencia

Este módulo se distribuye bajo la licencia **LGPL-3**.

---
Desarrollado con ❤️ por **Zinapsia**.
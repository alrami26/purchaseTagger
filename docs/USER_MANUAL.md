# Manual de uso - Etiquetador de compras PDF v1.0

## 1. Requisitos

- Python 3.7 o superior.
- `tkinter`, normalmente incluido con Python.
- Dependencias de `requirements.txt`.

Instalación recomendada:

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Para ejecutar pruebas o generar el ejecutable:

```bash
pip install -r requirements-dev.txt
```

## 2. Abrir la aplicación

Desde la carpeta del proyecto:

```bash
python purchase_tagger_app.py
```

La ventana debe abrirse con el título `Etiquetador de compras PDF v1.0`.

## 3. Importar estados de cuenta

1. En la vista `Importar`, seleccione el banco.
2. Seleccione el tipo de cuenta disponible para ese banco.
3. Presione `Buscar y etiquetar`.
4. Elija uno o varios archivos de estado de cuenta soportados.

La aplicación extrae las compras, detecta moneda y monto, aplica etiquetas por palabras clave y muestra un resumen de importación.

Soporte de la versión 1.0:

| Banco | Crédito | Débito |
|---|---:|---:|
| BAC | Sí | Sí |
| Promerica | Sí | No |
| BCR | No | Sí |

Formatos soportados:

- BAC y Promerica: PDF.
- BCR débito: HTML, HTM y el archivo XLS exportado por BCR cuando contiene una tabla HTML.

## 4. Revisar y filtrar compras

Use la vista `Compras` para revisar la tabla importada.

Filtros disponibles:

- Búsqueda por texto en cualquier columna visible.
- Moneda.
- Mes.
- Etiqueta.

Los indicadores superiores muestran totales, filas visibles, compras sin etiqueta, cantidad de monedas y etiquetas sobre presupuesto.

## 5. Administrar etiquetas

Use la vista `Etiquetas` para mantener la clasificación.

Cada etiqueta puede tener:

- Nombre.
- Palabras clave.
- Tipo de presupuesto.
- Periodo.
- Categoría padre.
- Monto planificado.
- Naturaleza del gasto.
- Propósito financiero.

Las palabras clave se comparan sin distinguir mayúsculas/minúsculas contra la descripción de la compra.

## 6. Categorías padre

En la pestaña `Categorías` puede agregar, renombrar o eliminar categorías padre. La categoría `Sin clasificar` está protegida y se usa como valor predeterminado cuando una etiqueta no tiene categoría.

## 7. Importar y exportar etiquetas JSON

En la vista `Etiquetas`:

- `Exportar JSON` guarda la configuración actual en un archivo reutilizable.
- `Importar JSON` agrega etiquetas nuevas, añade palabras clave faltantes y actualiza metadatos de etiquetas existentes.

Formato principal:

```json
{
  "Supermercado": {
    "keywords": ["WALMART", "AUTOMERCADO"],
    "limit": 250000,
    "planned_amount": 250000,
    "budget_type": "Expense",
    "parent_category": "Alimentación",
    "budget_period": "monthly",
    "expense_nature": "variable",
    "financial_purpose": "Necesidad"
  }
}
```

## 8. Ver resúmenes

Use la vista `Resúmenes` y seleccione una moneda específica. Los reportes evitan mezclar monedas distintas en un mismo total.

Reportes disponibles:

- `Gasto por etiqueta`.
- `Gasto mensual`.
- `Gasto acumulado`.
- `Presupuesto vs gasto por etiqueta`.
- `Gasto promedio por etiqueta/mes`.
- `Gasto por tipo de presupuesto`.
- `Gasto por categoría padre`.
- `Gasto por propósito financiero`.

La tabla de gasto promedio agrupa etiquetas bajo su categoría padre y marca en rojo las filas que superan el presupuesto.

## 9. Exportar CSV

En la vista `Compras`, ajuste los filtros y presione `Exportar`. El CSV contiene las filas visibles en ese momento.

## 10. Datos y respaldos

Durante desarrollo, `tags.json` vive junto al código. En una aplicación empaquetada, la configuración se guarda en el perfil del usuario:

- Windows: `%APPDATA%\PurchaseTagger\tags.json`
- macOS: `~/Library/Application Support/PurchaseTagger/tags.json`
- Linux: `$XDG_CONFIG_HOME/PurchaseTagger/tags.json` o `~/.config/PurchaseTagger/tags.json`

Cada guardado crea un respaldo `tags.json.bak` junto al archivo activo.

## 11. Generar ejecutable

```bash
pip install -r requirements-dev.txt
python -m PyInstaller purchase_tagger_app.spec
```

Los artefactos se crean en `build/` y `dist/`.

Para generar un instalador compartible de Windows y un paquete portable:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\installer\build_installer.ps1
```

El instalador `dist\PurchaseTagger-v1.0-Setup.exe` instala la aplicación para el usuario actual en `%LOCALAPPDATA%\Programs\PurchaseTagger` y crea accesos directos en el Escritorio y el Menú Inicio.

## 12. Solución de problemas

Si no se abre la aplicación, confirme que instaló las dependencias y ejecute:

```bash
python -m compileall purchase_tagger_app.py purchase_extractor.py tag_store.py summary.py ui_state.py money.py views version.py
```

Si no se extraen compras, revise que el banco y tipo de cuenta seleccionados coincidan con el archivo. Los formatos soportados en v1.0 son los de la tabla de bancos anterior.

Si los totales parecen incorrectos, revise el filtro de moneda y confirme que los montos del archivo hayan sido leídos con el signo esperado.

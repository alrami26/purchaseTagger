# Changelog

## 1.0 - 2026-06-08

Primera versión estable del Etiquetador de compras PDF.

### Incluye

- Importación de uno o varios estados de cuenta PDF.
- Soporte para BAC en crédito y débito, y Promerica en crédito.
- Etiquetado automático por palabras clave configurables.
- Administración de etiquetas, categorías padre y metadatos de presupuesto.
- Filtros por búsqueda, moneda, mes y etiqueta.
- Vistas de resumen por etiqueta, mes, acumulado, presupuesto, categoría y propósito financiero.
- Tabla de gasto promedio por etiqueta/mes con agrupación por categoría padre.
- Importación y exportación de etiquetas en JSON.
- Exportación de compras filtradas a CSV.
- Receta de empaquetado con PyInstaller.
- Suite automatizada con `pytest`.

### Verificación de release

- `python -m compileall purchase_tagger_app.py purchase_extractor.py tag_store.py summary.py ui_state.py money.py views version.py`
- `python -m pytest -q`

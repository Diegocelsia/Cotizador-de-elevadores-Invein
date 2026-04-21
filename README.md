# Cotizador Elevador INVEIN — Guía operativa

Aplicación Streamlit para cotizar elevadores. Esta guía explica cómo ejecutar localmente y desplegar gratuitamente en Streamlit Community Cloud.

**Resumen clave**
- Frontend: Streamlit
- Persistencia: SQLite por defecto (demo) — PostgreSQL mediante `DATABASE_URL` (producción)
- Ejecutable principal: [app.py](app.py)

**Dependencias principales**
- Definidas en [requirements.txt](requirements.txt). He eliminado duplicados innecesarios para reducir tamaño.

**Estructura relevante**
- Código: [app.py](app.py), [database.py](database.py), [models.py](models.py)
- Importadores y catálogos: [importer.py](importer.py), [lamina_catalog.py](lamina_catalog.py), [pricing_factor_catalog.py](pricing_factor_catalog.py), [technical_capacities.py](technical_capacities.py)
- Generador PDF: [pdf_generator.py](pdf_generator.py)
- Datos: `data/` (archivos Excel y logos)

## Ejecución local (rápida)
1. Crear y activar entorno virtual:
   - `python -m venv venv`  
   - `venv\Scripts\activate` (Windows)
2. Instalar dependencias: `pip install -r requirements.txt`
3. (Opcional, recomendado para primer uso) Inicializar base de datos: `python init_db.py`
4. (Opcional) Crear usuario administrador: `python create_admin.py`
5. (Opcional) Importar datos desde Excel: `python importer.py`
6. Ejecutar la aplicación: `streamlit run app.py`

Notas:
- Por defecto la app usa SQLite en `invein.db`. Esto es suficiente para demos locales.
- Si prefieres PostgreSQL, exporta `DATABASE_URL` antes de ejecutar:
  - `set DATABASE_URL=postgresql://usuario:password@host:5432/dbname` (Windows)

## Despliegue gratis recomendado — Streamlit Community Cloud
1. Sube el repositorio a GitHub.
2. En Streamlit Cloud, crea una nueva app apuntando al `app.py` del repo.
3. Añade `requirements.txt` en la configuración (ya en repo).  
4. (Opcional) En Secrets configura `DATABASE_URL` si vas a usar PostgreSQL.

Consejos de despliegue:
- Para demos, no configures `DATABASE_URL`: Streamlit Cloud correrá la app con SQLite (no persistente entre restarts).
- Para persistencia real, configura `DATABASE_URL` hacia una base externa (p. ej. PostgreSQL en ElephantSQL o servicios similares).

## Cambios de limpieza recomendados
- El archivo `invein.db` es una base de datos local; no es necesario incluirlo en el repo. Añádelo a `.gitignore` si controlas versión.
- Ya eliminé un duplicado en `requirements.txt` para evitar instalar `bcrypt` dos veces.

## Verificación y mantenimiento
- Prueba local completa: ejecutar `python init_db.py` → `python create_admin.py` → `python importer.py` → `streamlit run app.py` y validar flujo de login e importación.
- Si usas PostgreSQL, asegúrate de tener `psycopg2-binary` instalado y `DATABASE_URL` correcto.

Si quieres, hago ahora:
- Auditoría automática de imports para listar paquetes realmente usados y proponer `requirements.txt` final.
- Añadir `.gitignore` con `venv/` y `invein.db`.
- Ejecutar cambios y pruebas mínimas en los archivos (sin tocar tu entorno).
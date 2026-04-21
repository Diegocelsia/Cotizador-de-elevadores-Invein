
# Cotizador Elevador INVEIN — Guía de uso y despliegue

Proyecto es un cotizador técnico y comercial de elevadores, desarrollado en Python con Streamlit. Guía clara y actualizada para ejecutarlo localmente o desplegarlo.

---

## Ejecución local paso a paso

1. **Clona el repositorio y entra a la carpeta:**
  ```sh
  https://github.com/Diegocelsia/Cotizador-de-elevadores-Invein.git
  cd tu_repo
  ```

2. **Crea y activa un entorno virtual:**
  ```sh
  python -m venv venv
  venv\Scripts\activate  # En Windows
  # source venv/bin/activate  # En Linux/Mac
  ```

3. **Instala las dependencias:**
  ```sh
  pip install -r requirements.txt
  ```

4. **Inicializa la base de datos y el usuario comercial:**
  ```sh
  python init_db.py
  python create_admin.py
  ```

5. **Importa los datos base (precios y materiales):**
  ```sh
  python importer.py
  ```

6. **Ejecuta la aplicación:**
  ```sh
  streamlit run app.py
  ```

7. **Accede desde tu navegador:**
  - Abre [http://localhost:8501](http://localhost:8501)
  - Usuario: `Invein`  |  Contraseña: `Invein2026*`



## 📁 Estructura del proyecto

- `app.py` — Interfaz principal (Streamlit)
- `database.py`, `models.py` — ORM y modelos de datos
- `importer.py` — Importa datos desde Excel (`data/Lamina.xlsx`, `data/Material.xlsx`)
- `create_admin.py`, `init_db.py` — Inicialización y usuario comercial
- `data/` — Archivos Excel y recursos
- `requirements.txt` — Dependencias

---

## Notas y tips

- **Base de datos:** Por defecto usa `invein.db` (SQLite). Para producción, configura `DATABASE_URL` a PostgreSQL.
- **No subas `invein.db` ni `venv/` a GitHub:** Añádelos a `.gitignore`.
- **Reimporta datos si cambias los Excel:** Ejecuta de nuevo `python importer.py`.
- **¿Problemas?**
  - Revisa la consola de Streamlit para mensajes de error.
  - Asegúrate de tener los archivos Excel en la carpeta `data/`.

---

## Prueba rápida

```sh
python init_db.py
python create_admin.py
python importer.py
streamlit run app.py
```

---

## requirements.txt sugerido

```
streamlit>=1.28.0
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.0
passlib[bcrypt,argon2]>=1.7.0
plotly>=5.14.0
reportlab>=4.0.0
openpyxl>=3.1.0,<3.2
xlrd>=2.0.1
pypdf>=4.2.0
```

---

## Licencia y contacto

- Proyecto privado para INVEIN.
- Contacto: suarezdiego297@gmail.com

---

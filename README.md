# epg-discovery-la
Generador y actualizador automático de guías de programación (EPG / XMLTV) para los canales de Discovery Networks América Latina (Discovery Kids, Discovery Channel, Home &amp; Health, ID, Turbo, Animal Planet).

# EPG Discovery Networks América Latina

Este repositorio contiene la automatización para procesar, estructurar y generar guías de programación (EPG) en formato XMLTV a partir de los archivos CSV mensuales proporcionados por Tapkit para las señales de Discovery Networks en América Latina.

## 📺 Canales Soportados

* **Discovery Kids** (`DKLA_EPG.xml`)
* **Discovery Channel** *(Próximamente)*
* **Discovery Home & Health** *(Próximamente)*
* **Investigation Discovery (ID)** *(Próximamente)*
* **Discovery Turbo** *(Próximamente)*
* **Animal Planet** *(Próximamente)*

## ⚙️ Funcionamiento

1. **Autenticación:** Conexión automatizada a la API de Tapkit.
2. **Extracción:** Consulta y descarga del archivo CSV más reciente para cada red/región.
3. **Procesamiento:**
   * Decodificación de texto y corrección de caracteres especiales (tildes, `ñ`).
   * Limpieza de títulos locales (`LOCAL_SERIES_NAME` y `LOCAL_PROGRAM_NAME`) y sinopsis (`LOCAL_PROGRAM_DESCRIPTION`).
   * Normalización de estampas de tiempo en formato ISO / XMLTV (`YYYYMMDDHHMMSS +HHMM`).
4. **Generación:** Exportación de archivos XMLTV compatibles con IPTV y reproductores multimedia.

## 🚀 Automatización

El proceso se ejecuta periódicamente de forma automática a través de **GitHub Actions**.

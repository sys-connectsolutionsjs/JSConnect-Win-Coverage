# JSConnect-Win-Coverage

Aplicación de escritorio para validar en instantes cobertura y score crediticio de clientes en un call center de un proveedor de internet.

---

## Español

### ¿Qué es?
Aplicación de escritorio para Windows que acelera la validación de clientes. Consulta en milisegundos:
- **Cobertura de servicio** a partir de coordenadas (latitud, longitud).
- **Score crediticio** por documento: DNI (8 dígitos), RUC (11 dígitos) o Carnet de Extranjería (9 caracteres, puede incluir letras).

En lugar de scrapear HTML, replica directamente las llamadas HTTP (JSON) a la API interna del sistema de validación, sin cargar página, sin mapa ni navegador.

### Características
- Consulta directa a la API interna (rápido y ligero).
- Entrada de coordenadas en formato `-11.956037627741102, -77.04065381800075`.
- Detección automática del tipo de documento.
- Sesión automática con re-login cuando expira.
- Credenciales guardadas cifradas con el Administrador de Credenciales de Windows.
- Sistema de activación por código (solo personal autorizado).
- Botón de actualizaciones contra GitHub Releases.
- Ejecutable único, portable, anclable a la barra de tareas.

### Requisitos
- Windows 10.
- Python 3.14+ (solo para desarrollo; el .exe final no necesita Python).

### Uso
1. Ejecuta `JSConnect-Win-Coverage.exe` (o `python main.py` en desarrollo).
2. Actívalo con el código proporcionado por el encargado.
3. Ingresa las coordenadas y/o el documento del cliente.
4. Pulsa **Validar** → resultado de cobertura y score al instante.

### Desarrollo
```powershell
pip install -r requirements-dev.txt
python -m playwright install chromium   # solo para tools/captura.py
python main.py
```

### Build del .exe
```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

### Publicar una versión (Release)
```powershell
powershell -ExecutionPolicy Bypass -File publish-release.ps1
```
El Release se publica con el .exe y su checksum SHA-256. La app detecta la nueva
versión comparando el commit del Release con el embebido en el ejecutable.

### Seguridad y avisos
- Cada usuario usa su propia credencial del sistema de validación.
- Sin certificado de firma, Windows SmartScreen pedirá **Más información → Ejecutar
  de todas formas** la primera vez.
- Repositorio público sin licencia: todos los derechos reservados (ver Licencia).

### Licencia
Todos los derechos reservados. Este repositorio no incluye licencia de uso,
modificación ni distribución.

### Implementaciones futuras
Mapa interactivo de cobertura · Ofertas/catálogo de venta · Instalador con
auto-actualización · Servidor de activación en línea · Validación por lotes
(CSV/Excel) · Historial/CRM básico. Detalle en `AGENTS.md`.

---

## English

### What is it?
A Windows desktop application that speeds up customer validation in an internet
provider call center. It queries in milliseconds:
- **Service coverage** from coordinates (latitude, longitude).
- **Credit score** by document: DNI (8 digits), RUC (11 digits) or Foreigner Card
  (9 characters, may include letters).

Instead of scraping HTML, it directly replicates the HTTP (JSON) calls to the
provider's internal validation API — no page loading, no map, no browser.

### Features
- Direct internal API calls (fast and lightweight).
- Coordinates input as `-11.956037627741102, -77.04065381800075`.
- Automatic document type detection.
- Automatic session management with re-login on expiry.
- Credentials stored encrypted via Windows Credential Manager.
- Activation-code licensing (authorized staff only).
- Update button against GitHub Releases.
- Single portable executable, pinnable to the taskbar.

### Requirements
- Windows 10.
- Python 3.14+ (development only; the final .exe does not need Python).

### Usage
1. Run `JSConnect-Win-Coverage.exe` (or `python main.py` in development).
2. Activate with the code provided by the manager.
3. Enter the coordinates and/or the customer document.
4. Press **Validate** → coverage and score results instantly.

### Development
```powershell
pip install -r requirements-dev.txt
python -m playwright install chromium   # only for tools/captura.py
python main.py
```

### Build the .exe
```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

### Publish a release
```powershell
powershell -ExecutionPolicy Bypass -File publish-release.ps1
```
The release includes the .exe and its SHA-256 checksum. The app detects a new
version by comparing the release commit with the one embedded in the executable.

### Security & notices
- Each user uses their own validation-system credentials.
- Without a signing certificate, Windows SmartScreen will ask for
  **More info → Run anyway** on first launch.
- Public repository with no license: all rights reserved (see License).

### License
All rights reserved. This repository carries no license to use, modify or
distribute its contents.

### Future implementations
Interactive coverage map · Sales offers/catalog · Installer with auto-update ·
Online activation server · Batch validation (CSV/Excel) · Basic history/CRM.
Details in `AGENTS.md`.
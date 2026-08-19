# SkillsPropuestas.md — Cola/Historial de skills a crear

Fecha de creación: 2026-08-19 · Proyecto: JSConnect-Win-Coverage

## Qué es esto
**COLA/HISTORIAL** de tareas repetitivas y errores típicos del proyecto. Sirve
de base para crear **skills personalizadas** en el futuro. Es HISTORIAL hasta
que se cree una skill con esa información; al crearla, se **BORRA** de este
archivo lo ya usado.

## Reglas
- Cualquier tarea repetitiva o error recurrente se registra AQUÍ.
- Cuando se cree una skill que cubra un item, se elimina ese item de este archivo.
- Nunca subir a GitHub datos sensibles (credenciales, tokens, captura.json).

## Entrada: Tests por TDD (obligatorio)
- Los tests se escriben PRIMERO (rojo → falla), luego se implementa lo mínimo
  (verde) y se refactoriza. Todo cambio de comportamiento lleva su test.
- El core usa respuestas simuladas (FakeResponse/FakeSesion) para no hacer
  peticiones HTTP reales en los tests.
- Comandos: `pytest` para tests · `ruff check .` para lint.
- Detalle de la metodología e inventario de tests en `TestingLog.md`.

## Entrada: Errores típicos de entorno Windows + Python
- `pip` / `python` no reconocidos en PowerShell → usar la ruta completa de
  Python (ej: `C:\Users\<user>\AppData\Local\Programs\Python\Python314\python.exe`)
  o añadir al PATH de usuario (`[Environment]::SetEnvironmentVariable("Path", ...)`).
- El stub de Python de Microsoft Store (`WindowsApps\python.exe`) lanza el python
  real y puede confundir guardas de instancia única → excluir ancestros del árbol
  de procesos (ver `tools/captura.py`).
- `pip install -e .` falla con "Multiple top-level packages discovered in a
  flat-layout" → añadir `[tool.setuptools.packages.find]` con `include` en
  `pyproject.toml`.
- `W292` (sin newline al final) → `ruff check . --fix`.
- Después de instalar dependencias nuevas, verificar que el intérprete las vea
  (`pip list` o import directo) antes de correr tests.

## Entrada: Comandos estándar del proyecto
- Instalar: `pip install -r requirements.txt -r requirements-dev.txt`.
- Navegador de captura: `python -m playwright install chromium`.
- Ejecutar app: `python main.py`.
- Probar core: `python tools/probar_core.py` (pide credenciales, no muestra la
  contraseña).
- Concurrencia: `python tools/probar_concurrencia.py --ciclos N --log archivo.log`.
- Build: `powershell -ExecutionPolicy Bypass -File build.ps1`.
- Verificar: `pytest` y `ruff check .`.

## Entrada: Errores típicos de ruff (py314)
- `UP006/UP035/UP045/UP037` → typing moderno: `dict` en vez de `Dict`, `X | None`
  en vez de `Optional`, sin comillas en anotaciones → `from __future__ import
  annotations` + `dict[str, ...]` + `Any | None`.
- `B904` → `raise` dentro de `except` sin encadenar → añadir `from None`.
- `SIM117` → `with` anidados → combinar en un solo `with (...)`.
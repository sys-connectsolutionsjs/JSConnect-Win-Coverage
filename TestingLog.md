# TestingLog.md — Registro de pruebas y metodología

Fecha de creación: 2026-08-18 · Proyecto: JSConnect-Win-Coverage

## Metodología preferida: TDD (semáforo)
- **TDD** = Test-Driven Development: escribir el test PRIMERO (rojo: falla),
  ver la necesidad del cambio en el fallo, implementar lo mínimo para que deje
  de fallar y, al final, refactorizar. El test ya no genera el error (verde).
- Este proyecto usa este flujo: 1) test rojo, 2) implementación, 3) test verde.
- Comando de tests: `pytest` (o `python -m pytest -q`).
- Comando de lint: `ruff check .` (config en pyproject.toml, target py314).
- Convención: cualquier cambio de comportamiento va acompañado de su test.

## Inventario de tests (25 en total)
| Archivo | Casos | Qué cubre |
|---|---|---|
| tests/test_fields.py | varios | parseo de coordenadas y detección DNI/RUC/CE |
| tests/test_captura_guard.py | 4 | guard de instancia única de captura.py |
| tests/test_api.py | 14 | núcleo: login, cobertura, score y su parser |

Nota: `tools/probar_concurrencia.py` NO tiene tests automáticos a propósito (pide
credenciales y hace peticiones reales); se valida con `ruff` e import.

## Bitácora de la sesión de hoy (TDD aplicado)

### Sesión 2026-08-19 (tarde) — Retoma desde otra máquina
- [Entorno] Python 3.14.7 instalado (winget) y añadido al PATH de usuario; tras la
  instalación los comandos `python`/`pip` seguían sin resolver hasta abrir una
  terminal nueva o usar la ruta completa
  (`C:\Users\<user>\AppData\Local\Programs\Python\Python314\python.exe`).
- [Entorno] `pip install -e .` fallaba: "Multiple top-level packages discovered in
  a flat-layout: ['generator', 'validator_app']". → Añadir `[project]` +
  `[tool.setuptools.packages.find]` (`include = ["validator_app*"]`) a
  `pyproject.toml`.
- [Problema] `tests/test_captura_guard.py` no colectaba: `ModuleNotFoundError:
  No module named 'playwright'`. → Instalar dependencias dev (`playwright`,
  `pytest`, `ruff`, `pyinstaller`) + `python -m playwright install chromium`.
- [Problema] `W292` (sin newline al final) en `tools/probar_concurrencia.py`.
  → `ruff check . --fix`.
- [Verificación] 25 tests pasando y ruff limpio en la máquina nueva.

### tests/test_api.py — núcleo (nuevo, 14 casos)
Proceso seguido para cada caso:
1. **Rojo**: se escribió el test primero (responde simuladas con FakeResponse/FakeSesion).
2. **Fallo esperado**: `NotImplementedError` del stub de `api.py` (los tests no podían
   pasar porque el core no existía).
3. **Verde**: se construyó `validator_app/core/api.py` + `core/session.py`.
4. **Refactor**: ajustes de estilo/typing por ruff.

### Problemas encontrados y soluciones
| Problema | Causa | Solución |
|---|---|---|
| `test_login_ok` lanzaba `LoginError` y hacia peticiones HTTP reales | `login()` crea la sesión con `session.crear_sesion()` (sesión real), ignorando el `FakeSesion` que el test asignaba a `_sesion` | Mockear `validator_app.core.session.crear_sesion` con `unittest.mock.patch(..., return_value=FakeSesion)` |
| `test_score_parsea_reporte` fallaba con `AttributeError: 'str' object has no attribute 'get'` | El test codificaba el reporte Equifax con DOBLE `json.dumps`, pero la respuesta real es de UNA sola capa: `data` = `json.dumps(reporte)` (el `json.loads` de `data` ya devuelve el dict) | Verificar la codificación real leyendo el body crudo de `tools/captura.json`; corregir el fixture a una sola codificación |
| Mismos `AttributeError` en `test_score_payload_incluye_documento` y `test_validar_flow_con_cobertura` | Misma causa: fixture doble-codificado | Misma solución (fixture corregido) |
| `E501` líneas >100 | Test muy largo | Partir la línea / extraer variable |
| `RUF059` variable desempaquetada sin uso | `metodo, url, kwargs = ...` sin usar `metodo`/`url` en algunos asserts | Usar `_` (dummy) en el desempaquetado |
| `W292` sin salto de línea al final | Write sin newline final | `ruff check . --fix` |
| `SIM117` `with` anidados | Dos `with` consecutivos | Combinar en un solo `with (...)` con paréntesis |
| `UP006/UP035/UP045/UP037` | ruff target py314 exige typing moderno: `dict` en vez de `Dict`, `X \| None` en vez de `Optional`, sin comillas en anotaciones | `from __future__ import annotations` + `dict[str, ...]` + `Any \| None` |
| `B904` | `raise` dentro de `except` sin encadenar | Añadir `from None` |

### Descubrimiento técnico clave (parser del score)
- La respuesta de `score_cliente` es `{"response":"success","data":"<JSON-string>"}`
  donde `<JSON-string>` es el reporte SOAP de Equifax. Tras `json.loads(respuesta)["data"]`,
  un único `json.loads(...)` ya devuelve el dict (NO doble-codificado).
- Puntaje en `ns3ResumenScoreRP3.Puntaje` (ej: 423), `NivelRiesgo`, y deuda en
  `ResumenDeuda.DeudaTotal`. El parser usa una búsqueda recursiva robusta.

## Cómo probar manualmente contra la API real
- `python tools/probar_core.py` → pide usuario/contraseña, coordenadas y documento;
  ejecuta login → cobertura → score. NO muestra la contraseña (getpass).

## Pendiente de pruebas
- Prueba de concurrencia (4-5 máquinas, misma cuenta): ver `PlanesAprobados.md`.
- Prueba real del core con credenciales del responsable (probar_core.py).
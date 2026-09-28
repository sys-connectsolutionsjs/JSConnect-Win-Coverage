# Diagramas UML (PlantUML)

Diagramas técnicos complementarios a `docs/arquitectura.md`. Todos incluyen
`_comun.puml` (tema compartido) y un `footer` con el SHA corto contra el que
se verificaron por última vez — si el código avanza y el diagrama no, el
footer queda desactualizado a propósito, como señal.

| Archivo | Contenido |
|---|---|
| `01-actividad-validacion.puml` | Flujo de validación en la app del agente (activación, cobertura y/o score por separado). |
| `02-estados-sesion-proxy.puml` | Estados de la sesión WinForce dentro del proxy (auto-relogin, keepalive, caducidad). |
| `03-casos-de-uso.puml` | Casos de uso del agente y del owner. |
| `04-clases-principales.puml` | Clases y módulos: núcleo, proxy, agente y consola owner. |
| `05-componentes.puml` | Componentes por máquina (agente, proxy, estación owner) y servicios externos. |
| `06-despliegue.puml` | Topología de despliegue de producción. |
| `07-secuencia-renovacion-sesion.puml` | Secuencia de renovación de la cookie PHPSESSID (extensión Chrome vs. consola owner). |
| `08-actividad-owner.puml` | Actividad de `JSConnect-Win-Owner.exe`: activación, servicio/sesión, credenciales. |

## Renderizar

- VS Code: extensión "PlantUML" (Alt+D previsualiza el archivo abierto).
- CLI: `plantuml docs/diagramas/*.puml` (requiere Java + Graphviz).

## Mantenerlos honestos

`tests/test_diagramas.py` valida sintaxis básica (`@startuml`/`@enduml`,
`!include _comun.puml`) y que los nombres de clase citados sigan existiendo en
el código. No valida el contenido semántico: cuando cambie un flujo importante,
actualiza el diagrama a mano y refresca el `footer` con el SHA nuevo.

# TraspasoInmediato.md — Plan futuro: traspaso rápido del proxy entre dos PC

Fecha de creación: 2026-09-21 · Proyecto: JSConnect-Win-Coverage

> **Este documento es un plan, no una implementación.** Nada de lo que describe
> está construido todavía. Existe para que, el día que alguien decida que hace
> falta un traspaso rápido del proxy entre dos PC, no tenga que investigar desde
> cero las decisiones y descartes que ya se discutieron. Si eres quien retoma
> esto: bienvenido, que te vaya bien, y ojalá este documento te ahorre una tarde.

---

## Resumen ejecutivo (30 segundos)

| Pregunta | Respuesta corta |
|---|---|
| ¿Tokens iguales en ambas PC generándolos por separado (semilla compartida)? | **No.** Ver sección 1: convierte el secreto en algo débil y no rotable. |
| ¿Cómo se logra el mismo token en ambas PC entonces? | Generarlo una vez, **copiar el archivo** a la segunda PC. Ver sección 2. |
| ¿Qué bloquea de verdad un traspaso rápido — los tokens? | No. **La IP del proxy.** Los agentes apuntan a una IP fija; cambiarla es el cuello de botella real. Ver sección 3. |
| ¿Hace falta clonar todo el repo en la PC de respaldo? | Hoy sí (decisión vigente). La opción más alineada con "traspaso inmediato" es compilar el proxy como `.exe`, sin hacerlo todavía. Ver sección 4. |
| ¿Cuándo implementar esto? | Cuando alguien lo priorice. Ver "Decisiones abiertas" al final. |

---

## Origen de este documento

El 2026-09-21, en la misma sesión donde se agregó el panel de credenciales de la
consola owner (Mostrar/Copiar/Rotar, commit `9367775`) y se restringió `/admin/*` a
loopback, el owner planteó un escenario: la PC que aloje el proxy probablemente
termine siendo la del **gerente de ventas**, que no siempre está en la oficina. Si
esa PC no está disponible, alguien tendría que ir físicamente hasta ella para
levantar el servicio — nada rápido.

La primera idea para resolverlo fue que ambas PC pudieran generar el **mismo**
`proxy_token`/`admin_key` a partir de una "sub-semilla" que dos personas escribieran
al momento de generar. Se descartó por las razones de la sección 1, pero el
problema de fondo (traspaso rápido y sin fricción) sigue siendo válido y vale la
pena resolverlo bien cuando haga falta.

---

## 1. Por qué NO usar una semilla compartida para generar los mismos tokens

La idea: dos personas escriben el mismo número/frase al generar, y de ahí sale
determinísticamente el mismo `proxy_token`/`admin_key` (por ejemplo,
`HMAC(semilla, "proxy_token")`). Técnicamente funciona. El problema es lo que
convierte en secreto real:

- **Hoy** el token es `secrets.token_hex(32)` — 256 bits de un generador
  criptográfico, nunca dicho ni escrito por una persona, vive en un archivo con
  ACL de SYSTEM+Administradores (`validator_app/proxy/secretos.py`,
  `install_service.bat`).
- **Con semilla**, el secreto real pasa a ser la semilla — algo que dos personas
  necesariamente comunican entre sí (de palabra, por chat, en un papel). Mucha
  menos entropía que un CSPRNG, y con una superficie de fuga nueva que hoy no
  existe.
- **Es permanente**: si la semilla se filtra una vez, cualquiera puede
  recalcular el token en cualquier momento futuro, sin tocar ninguna PC. Rotarla
  exige que las dos personas vuelvan a coordinarse una semilla nueva — en ese
  punto ya se hizo el trabajo manual de coordinación que se quería evitar, pero
  con un secreto peor que uno random.

Esto es justo lo opuesto de la decisión tomada el mismo día en `server.py`: hacer
`/admin/*` loopback-only porque el admin key es un secreto crítico (da acceso al
`proxy_token` vía `/admin/config`). No tiene sentido resolver un problema de
conveniencia debilitando esa misma pieza.

**Conclusión: no implementar la semilla compartida bajo ninguna variante.**

---

## 2. La alternativa: sincronizar el archivo, no derivar el secreto

El objetivo real no es "que ambas PC generen el mismo token" — es "que ambas PC
tengan el mismo `config.yaml`". Eso ya se puede lograr hoy, sin código nuevo:

1. Correr `install_service.bat` en la PC A (genera `config.yaml`,
   `proxy_token.txt`, `admin_key.txt` nuevos).
2. Copiar ese `config.yaml` a `validator_app/proxy/` en la PC B, **antes** de
   correr el instalador ahí.
3. Correr `install_service.bat` en la PC B. El paso 5 detecta que `config.yaml`
   ya existe y pregunta **Conservar** (por defecto a los 20 s) o Regenerar —
   elegir **Conservar**. Ambas PC quedan con el mismo `proxy_token`/`admin_key`,
   generados una sola vez con entropía real.

**Costo de este enfoque**: si más adelante se rota un token desde el panel de la
consola owner (`generator/owner_app.py`, `validator_app/proxy/secretos.py::rotar()`),
solo se actualiza el `config.yaml` de la PC donde se ejecutó la rotación. Hay que
recordar copiar el archivo actualizado a la PC de respaldo, o queda desincronizada
y el traspaso fallará con 401 en los agentes.

**Mejora futura opcional (no implementada)**: extender `rotar()` para que, además
de escribir el `config.yaml` local, copie el resultado a una segunda ruta
configurable (una carpeta compartida de la LAN, o la ruta UNC de la PC de
respaldo — `\\PC-RESPALDO\...`). Requeriría decidir qué hacer si la PC de respaldo
está apagada en el momento de rotar (¿cola de sincronización? ¿reintento manual?).
No es complicado, pero no vale la pena construirlo hasta que el traspaso mismo se
priorice.

---

## 3. El problema real: la IP del proxy (esto sí bloquea un traspaso rápido)

Aunque los tokens estén sincronizados, cada agente tiene configurada la **IP**
del proxy (`ProxyConfig.proxy_url`, guardada en el keyring de cada agente vía
`⚙ Configuración → Configurar Proxy`). Si el proxy se muda de la PC A a la PC B
— que casi seguro tiene otra IP en la LAN — **hay que reconfigurar cada agente**
(15 PC hoy, meta 35). Eso es mucho más lento que el problema de los tokens, y es
el verdadero cuello de botella de un "traspaso inmediato".

Opciones evaluadas para una LAN de oficina de este tamaño (sin gastar en
infraestructura nueva):

- **Recomendada: reserva DHCP + hostname interno.** Reservar en el router una IP
  fija para cada PC candidata (A y B), y mantener una entrada de hostname interno
  (`proxy.oficina.local`, vía el DNS del router o un archivo `hosts` distribuido)
  que apunte a la IP activa. Los agentes se configuran una sola vez apuntando al
  **hostname**, no a la IP. El día del traspaso, el costo baja a "cambiar 1
  registro" en vez de "reconfigurar 35 agentes".
- **Alternativa sin DNS propio**: mantener el hostname en el archivo `hosts` de
  Windows de cada agente, con un script nuevo (`tools/actualizar_proxy_host.ps1`,
  no existe aún) que lo reescriba remotamente, o que el agente lo relea al
  reintentar una conexión fallida. Más frágil que un DNS/router centralizado
  (depende de que el script llegue a las 35 PC), pero no requiere tocar el
  router.
- **Descartado**: balanceador de carga o IP virtual (tipo keepalived/VRRP) para
  que ambas PC compartan una sola IP activa. Sobra para 15-35 agentes en una LAN
  de oficina, Windows no lo trae nativo, y añade una pieza más para mantener y
  depurar sin necesidad real a esta escala.

---

## 4. Empaquetado: ¿hace falta el repo completo en la PC de respaldo?

Evaluado el 2026-09-21, sin implementar nada. Hechos verificados en el código:

- `validator_app/proxy/winsw.xml` arranca el servicio con
  `python -m validator_app.proxy.server`, con el **repo completo** como
  `workingdirectory`.
- `server.py` importa `validator_app.core` además de `validator_app.proxy` —
  **no basta con copiar solo la carpeta `proxy/`**, como sugiere de forma un poco
  optimista un comentario del paso 1 en `docs/proxy-deploy.md`.

Tres caminos evaluados:

1. **Compilar el proxy como `.exe` con PyInstaller** (`build-proxy.ps1`, no
   existe — sería el equivalente de `build-owner.ps1`/`build.ps1` para el
   servidor). Elimina la dependencia de tener Python instalado en la PC de
   respaldo: es la opción que más se acerca a un "traspaso inmediato" real.
   Pendiente de validar antes de construirlo: si `winsw` puede lanzar un `.exe`
   onefile en vez de `python -m ...` (cambiar `<executable>`/`<arguments>` en
   `winsw.xml`), y si `playwright`/Chromium (usados por el login asistido) siguen
   funcionando empaquetados con PyInstaller.
2. **Script que copia solo lo necesario** (`validator_app/core`,
   `validator_app/proxy`, `requirements.txt`, `requirements-proxy.txt`,
   `install_service.bat`) a una carpeta nueva, sin `git clone`. Menos trabajo que
   compilar, pero la PC de respaldo sigue necesitando Python 3.12+ instalado.
3. **Seguir clonando el repo completo** — es la decisión vigente hoy. No pesa
   mucho (sin `.venv`/`dist`/`build`, que son gitignored), pero carga
   documentación y tests que el servicio nunca usa en producción.

**Recomendación si se prioriza esto**: ir directo a la opción 1 (compilar como
`.exe`). La opción 2 es un paso intermedio que no resuelve el problema de fondo
(seguir dependiendo de que la PC de respaldo tenga Python bien instalado) y solo
tiene sentido si compilar resulta más costoso de lo esperado.

---

## 5. Runbook del traspaso (una vez resueltas las secciones 2-4)

Con `config.yaml` sincronizado (sección 2), hostname interno resuelto (sección 3)
y el proxy instalable/instalado en ambas PC (sección 4), el traspaso el día que
haga falta sería:

1. Confirmar que la PC A no responde (`GET /health` falla, o `sc query
   JSWinProxy` no está `RUNNING` y no hay forma de reiniciarlo remotamente).
2. En la PC B: si el servicio ya estaba preinstalado (recomendado, aunque no
   corriendo), solo iniciarlo (`sc start JSWinProxy` o el botón de la consola
   owner). Si no estaba instalado, correr `install_service.bat` — con
   `config.yaml` ya copiado, conserva los tokens.
3. Repuntar el hostname interno (`proxy.oficina.local`) a la IP de la PC B.
4. Confirmar `GET http://proxy.oficina.local:8080/health` desde un agente.
5. Si no existe hostname interno todavía (sección 3 sin implementar): avisar a
   los agentes con la IP nueva — ver `docs/proxy-deploy.md`, sección
   "Configuración de Agentes", opción B (script por keyring) para hacerlo masivo
   en vez de PC por PC.

---

## Decisiones abiertas

A resolver cuando se priorice implementar este plan:

- ¿Failover **manual** (alguien nota que el proxy cayó y ejecuta el runbook) es
  suficiente, o hace falta una alerta automática? La Etapa R ya tiene eventos de
  Windows (101/102) para sesión WinForce muerta/viva — podría extenderse un
  evento similar para "proxy no responde", en vez de construir monitoreo nuevo.
- ¿Vale la pena instalar el servicio `JSWinProxy` en **ambas** PC desde ya
  (aunque solo uno corra a la vez, el otro detenido), para que el traspaso sea
  "prender servicio" en vez de "instalar desde cero"? Reduce el tiempo de
  traspaso pero duplica el mantenimiento (dos instalaciones a las que aplicar
  actualizaciones).
- ¿Quién tiene autoridad para ejecutar el traspaso (solo el owner, o también el
  gerente de ventas u otra persona)? Afecta si el runbook de la sección 5 necesita
  o no acceso administrativo amplio en ambas PC.

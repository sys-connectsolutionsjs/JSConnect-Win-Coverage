# vpn.md — Cómo conectar a los asesores remotos con el proxy

> Documento de **decisión** (2026-11-06). Reúne todas las alternativas evaluadas para que los
> asesores que trabajan desde casa usen la app igual que los de la oficina. Sirve de base para el
> documento Word con el que se elige. **No hay nada implementado todavía.**
>
> Los precios salen de páginas de terceros a la fecha indicada: **confirmarlos en la página
> oficial de cada proveedor antes de pagar o comprometerse** (ver [Fuentes](#13-fuentes)).

---

## 1. Resumen de una página

**Situación.** Hoy hay 50 agentes. Más de 25 trabajan en remoto con **su propia PC**, y se
esperan entre 100 y 200 usuarios. El proxy (la PC de la oficina que habla con WinForce y Equifax)
solo atiende a la red local (LAN). Hay que llevarlo a los remotos **sin gastar dinero** (o solo
unos pocos dólares al año) y **sin abrirlo a cualquiera en internet**.

**Lo que descarta el presupuesto.** El plan gratuito de Tailscale es de 6 usuarios y solo para
uso no comercial. Los planes que cobran por usuario (Tailscale ~US$8, NetBird Cloud ~US$6,
Cloudflare Access ~US$7 pasados los 50) costarían entre US$300 y US$1,600 al mes.

**Las tres opciones finalistas (US$0 o casi):**

| | A. NetBird propio en Oracle Free | B. Headscale propio en Oracle Free | C. Cloudflare Tunnel |
|---|---|---|---|
| Costo | US$0 (dominio opcional ~US$12 al año) | US$0 (dominio opcional) | ~US$10–12 al año (dominio) |
| Qué instala el asesor | App de NetBird | App oficial de Tailscale | **Nada** |
| ¿El proxy queda en internet? | No | No | **Sí** (detrás de Cloudflare) |
| Panel web para administrar | **Sí, oficial** | No oficial (de la comunidad) | Sí (Cloudflare) |
| Aislar a los asesores entre sí | Sí (políticas en el panel) | Sí (archivo de reglas) | No aplica (no hay red entre ellos) |
| Riesgo principal | Oracle reclama la máquina gratuita | El mismo | Token filtrado = acceso desde el mundo |

**Recomendación (criterio del owner): A — NetBird propio en Oracle Cloud Always Free.** Las
condiciones son pasar la cuenta de Oracle a *Pay As You Go* con una alerta de presupuesto,
y hacer copias semanales. Si Oracle no resulta viable, el plan B es NetBird en un VPS de
~US$5 al mes.

**En cualquier caso** hay que hacer en la app, antes de dar acceso a los remotos: **tokens por
asesor, revocables** (hoy hay uno solo para todos), un límite de consultas y un registro de
quién consulta qué (sección 4).

---

## 2. Requisitos y reglas de negocio

- **Cantidad**: más de 25 remotos hoy; hasta 100–200 usuarios a futuro. La opción tiene que
  costar lo mismo con 20 que con 200.
- **Equipos**: la **PC personal** de cada asesor. La empresa no controla esos equipos, que
  pueden tener virus, software pirata o familiares usándolos.
- **Presupuesto**: US$0. Se acepta "unos pocos dólares al año" o "muy pocos al mes".
- **Sensibilidad**: el proxy, en la práctica, es una **puerta a datos crediticios** de personas
  reales (DNI → score de Equifax). Tratar esos datos sin control es un riesgo legal para la
  empresa (Ley 29733 de Protección de Datos Personales del Perú) y pone en peligro la cuenta de
  WinForce, de la que depende todo el call center.
- **Lo que no puede pasar**:
  1. Que el proxy quede abierto a internet sin protección.
  2. Que un asesor llegue a la PC de otro asesor o a la red de la oficina.
  3. Que no se pueda cortar el acceso a **un** asesor que se va, sin afectar a los demás.
- **Lo que ya existe** en el proxy (`validator_app/proxy/`):
  - escucha en HTTP, puerto 8080;
  - acepta solo IPs de `allowed_networks`, que **ya incluye `100.64.0.0/10`**, el rango que usan
    Tailscale, Headscale y NetBird;
  - exige la cabecera `X-Proxy-Token`, con **un token compartido** por todos los agentes;
  - `/admin/*` solo responde desde la propia PC (loopback).
  - Detalle en [docs/arquitectura.md](docs/arquitectura.md).

---

## 3. Glosario técnico

| Término | Qué significa aquí |
|---|---|
| **VPN** | Red privada virtual: un "cable" cifrado entre dos equipos a través de internet. Para el proxy, el asesor remoto queda como si estuviera en la oficina. |
| **WireGuard** | El protocolo de cifrado que usan NetBird, Tailscale y Headscale. Es gratuito, moderno y auditado. Nadie de estas opciones "inventa" su propio cifrado. |
| **Mesh / P2P** | Los equipos se conectan **directo** entre sí (peer to peer), sin pasar el tráfico por un servidor central. |
| **Plano de control ("la central")** | El servidor que **reparte las llaves** y las reglas: quién existe, quién puede hablar con quién. No transporta las consultas. Es lo que se instala en Oracle (NetBird o Headscale). |
| **Plano de datos** | El tráfico real (las consultas a la app). Va cifrado de equipo a equipo. |
| **NAT** | El router de casa "esconde" varios equipos detrás de una sola IP. Por eso no se puede entrar a una PC doméstica desde afuera sin ayuda. |
| **CGNAT** | Lo mismo, pero hecho por el proveedor de internet (muy común en el Perú con móvil y algunos ISP). Dificulta aún más la conexión directa. |
| **NAT traversal / STUN** | Técnicas para que dos equipos detrás de NAT se encuentren y conecten directo. STUN es el servicio que le dice a cada equipo cuál es su IP pública. |
| **Relay (DERP / TURN)** | Si la conexión directa falla (NAT estricto), el tráfico cifrado pasa por un servidor de relevo. Tailscale y Headscale lo llaman DERP; NetBird usa su propio relay o TURN. El relay **no puede leer** el tráfico. |
| **IP pública** | La dirección con la que un equipo se ve desde internet. La central necesita una fija; la VM de Oracle la tiene. |
| **VPS / VM** | Una computadora virtual alquilada (o gratuita) en un centro de datos, encendida 24/7. |
| **Dominio / DNS** | Un nombre (p. ej. `vpn.empresa.com`) que apunta a una IP. Hace falta para tener HTTPS. |
| **DDNS (DuckDNS)** | Un servicio gratuito que da un subdominio (p. ej. `empresa-vpn.duckdns.org`) y lo mantiene apuntando a tu IP. |
| **TLS / HTTPS / Let's Encrypt** | Cifrado de la conexión web. Let's Encrypt emite los certificados gratis y de forma automática. |
| **ACL / políticas** | Reglas del tipo "el grupo *asesores* solo puede llegar al *proxy* por el puerto 8080". |
| **Setup key / clave de preautorización** | Una clave que se entrega al asesor para que su equipo se una a la red sin crearle usuario a mano. Puede vencer y asignar un grupo automáticamente. |
| **mTLS** | TLS "mutuo": además del servidor, **el cliente** presenta un certificado. Sin certificado, ni siquiera se completa la conexión. |
| **ZTNA / SASE** | "Zero Trust": cada persona entra solo a la aplicación que necesita, verificando su identidad y su equipo, en vez de entrar a toda la red. Es lo que usan las empresas grandes. |
| **Port forwarding** | Configurar el router para que lo que llega de internet a un puerto se envíe a una PC de adentro. Equivale a abrir una puerta. |
| **Docker / docker compose** | Forma estándar de instalar servidores "empaquetados". NetBird se instala así. |

---

## 4. Lo que vale para cualquier opción

1. **Tokens por asesor, revocables.**
   - Hoy todos comparten un solo `proxy_token`. Con PCs personales, ese token **se va a
     filtrar** tarde o temprano (un ex-asesor, una captura de pantalla, un virus).
   - Con un token por asesor, se corta a uno sin tocar a los demás y se sabe quién hizo cada
     consulta.
   - Encaja con la idea "Servidor de activación en línea" ([Roadmap.md](Roadmap.md)).
2. **Límite de consultas por token** (por minuto y por día). Frena el abuso y protege la cuenta
   de WinForce de volúmenes raros.
3. **Registro** de qué token consultó qué y cuándo. Sirve para auditar y para la Ley 29733.
4. **Aislamiento**: un asesor solo puede llegar al proxy, puerto 8080. Nunca a otro asesor ni a
   la LAN de la oficina.
5. **En la PC del proxy**:
   - el cliente VPN se instala **como servicio de Windows**, para que arranque aunque nadie
     inicie sesión (como ya se hace con el proxy);
   - la regla de firewall `JSWinProxy API` ya admite `100.64.0.0/10`.
6. **En el agente remoto**: solo cambia la URL del proxy a la IP de la VPN, por ejemplo
   `http://100.x.y.z:8080`.
   - Que siga siendo HTTP dentro del túnel es aceptable, porque WireGuard ya cifra todo.
   - En la opción C (Cloudflare) la URL sería `https://proxy.dominio.com`.

---

## 5. Opción A — NetBird propio en Oracle Cloud Always Free (preferida)

### 5.1 Cómo funciona
```
 Asesor en casa (PC personal)            Oracle Cloud (gratis)              Oficina
 ┌───────────────────────┐   llaves y   ┌──────────────────────┐  llaves  ┌──────────────────┐
 │ App NetBird           │◄──reglas────►│ Central NetBird      │◄────────►│ PC del proxy     │
 │ App JSConnect agente  │              │ (panel web, relay)   │          │ NetBird (servicio)│
 └──────────┬────────────┘              └──────────────────────┘          │ Proxy :8080       │
            │        túnel WireGuard cifrado, directo (o vía relay)       └────────┬─────────┘
            └─────────────────────────────────────────────────────────────────────►┘
```
La central solo coordina. Las consultas van **directo y cifradas** del asesor al proxy. El
proxy **no abre ningún puerto** en el router de la oficina.

### 5.2 "La máquina gratuita": Oracle Cloud Always Free
- Oracle regala, sin límite de tiempo, una cuota de servidores:
  - **VM ARM Ampere A1**: 3,000 OCPU-hora y 18,000 GB-hora al mes, equivalentes a
    **4 núcleos y 24 GB de RAM** encendidos todo el mes.
  - **Aviso**: varias fuentes de 2026 reportan un **recorte a 2 núcleos / 12 GB desde agosto
    de 2026**. No lo pude confirmar en una página oficial de Oracle. Aun así, NetBird pide
    1 núcleo y 2 GB, así que sobra.
  - 200 GB de disco y 10 TB al mes de tráfico de salida.
  - También hay VMs AMD "micro" de 1 GB de RAM: **no alcanzan** para NetBird.
- Piden **tarjeta** al registrarse, solo para verificar identidad.
- La **región principal** se elige al registrarse y **no se puede cambiar**. Conviene una de
  Sudamérica (Bogotá, Santiago o São Paulo) para tener menor latencia. Igual, solo coordina: el
  tráfico va directo.
- Es frecuente el error **"Out of capacity"** al crear la VM A1 en regiones populares. Se
  reintenta más tarde o en otro dominio de disponibilidad.

### 5.3 El riesgo: que Oracle "reclame" la máquina
- Según su documentación, Oracle **puede reclamar** (apagar o borrar) instancias Always Free que
  considere **inactivas**: en un periodo de 7 días, CPU por debajo del 20 % en el percentil 95.
  Algunas fuentes agregan red y memoria por debajo del 20 %.
- **Un servidor NetBird casi no usa CPU, así que encaja en esa definición.** Este es el riesgo
  real de la opción.
- Algunas fuentes (sin confirmar) dicen que una cuenta sin actividad por más de 30 días se trata
  como abandonada.
- **Mitigación principal**: pasar la cuenta a **Pay As You Go (PAYG)**.
  - La reclamación por inactividad aplica a las cuentas solo-gratuitas.
  - En PAYG los recursos Always Free **siguen sin costo**.
  - El riesgo nuevo es pagar si alguien crea algo fuera de la cuota. Se controla con:
    1. una **alerta de presupuesto** en US$1, que avisa por correo apenas haya un cobro;
    2. no crear nada que no diga "Always Free-eligible";
    3. que solo una persona tenga acceso a la consola de Oracle.
  - Confirmar en la documentación de Oracle al momento de registrarse.
- **No recomendado**: scripts que "ocupan" la CPU para que no parezca inactiva. Van contra el
  espíritu de los términos y pueden terminar en el cierre de la cuenta.

### 5.4 "Las copias": qué son y cómo se recupera todo
La idea es que perder la máquina gratuita sea **una molestia de una hora, no un desastre**.
- **Copia 1: el disco completo de la VM.**
  - Oracle permite programar *backups* del volumen de arranque.
  - Restaurarlo levanta la misma máquina tal cual estaba.
  - Mantenerse dentro de la cuota gratuita de almacenamiento.
- **Copia 2: solo los datos de NetBird** (la importante).
  - Qué se copia:
    - la base de datos de NetBird (usuarios, equipos registrados, grupos, políticas, setup keys);
    - el `docker-compose.yml`;
    - los archivos de configuración que genera el instalador.
  - Una tarea programada semanal la comprime y la descarga fuera de Oracle: a la PC del owner o
    a un Google Drive.
- **Si Oracle borra la máquina**:
  1. Crear otra VM (en Oracle o en un VPS barato).
  2. Instalar docker y restaurar la copia 2.
  3. Apuntar el dominio a la IP nueva (en DuckDNS es un clic).
  - Con los datos restaurados, **los asesores no reinstalan ni reconfiguran nada**: sus equipos
    se reconectan solos.
  - Sin copia, todos se vuelven a registrar con una setup key nueva (molesto con 200 personas).
  - Tiempo estimado: **~1 hora**, con el procedimiento escrito de antemano.

### 5.5 Cómo es NetBird por dentro (2026)
- Código abierto, edición comunitaria **sin límite de usuarios ni equipos**.
  - La licencia comercial self-hosted (~€2,000 al año hasta 50 usuarios) **no hace falta**.
- Desde la **v0.62** trae **usuarios locales**: ya no exige instalar un proveedor de identidad
  aparte (Keycloak, Zitadel). Desde la **v0.65** los servicios principales van en **un solo
  contenedor**.
- **Instalación**: el script oficial `getting-started.sh` con la variable `NETBIRD_DOMAIN`.
  Después se abre el dominio en el navegador y se crea la cuenta de administrador.
- **Requisitos**:
  - Linux (la VM de Oracle con Ubuntu), mínimo 1 CPU y 2 GB;
  - Docker con docker compose v2, y jq;
  - un dominio que apunte a la IP de la VM;
  - puertos abiertos: **TCP 80 y 443, UDP 3478**.
- **Trampa conocida de Oracle**: los puertos hay que abrirlos **en dos lugares**:
  1. la *Security List* de la red virtual (VCN), en la consola web;
  2. el firewall `iptables` que trae la imagen Ubuntu de Oracle.
  - Si falta el segundo, "todo parece bien pero nada conecta".
- **Dominio**:
  - gratis con un subdominio DuckDNS;
  - o uno propio (~US$10–15 al año), que además sirve para la opción C y se ve más profesional.

### 5.6 El día a día
- **Alta de un asesor**:
  1. En el panel se crea una **setup key** reutilizable, con vencimiento y grupo automático
     `asesores-remotos`.
  2. El asesor instala NetBird para Windows (MSI) y ejecuta
     `netbird up --management-url https://<dominio> --setup-key <clave>`. Se le puede entregar
     un `.bat` que lo haga.
  3. Se activa la **aprobación de equipos**: cada equipo nuevo espera a que el owner lo acepte
     en el panel.
- **Reglas (lo más importante)**:
  - NetBird crea una política por defecto **"Default" (todos con todos)**. **Hay que borrarla**,
    o los asesores se verían entre sí.
  - En su lugar se crea `asesores-remotos → proxy`, solo **TCP 8080**.
  - Conviene **no** empujar DNS a los equipos de los asesores, para no alterar sus PCs
    personales.
- **Baja de un asesor**: borrar su equipo en el panel y revocar su token del proxy (sección 4).
- **Mantenimiento**: actualizar una vez al mes (`docker compose pull` + reinicio) y revisar que
  la copia semanal se haya hecho.
- **Detalle**: si un asesor ya usa Tailscale personal, comparte el rango `100.64.0.0/10` y puede
  haber choques. Se resuelve caso por caso.

### 5.7 Si la central se cae
- Los túneles ya establecidos pueden seguir funcionando un rato.
- **Nadie nuevo puede entrar** y los equipos que dependen del relay (NAT estricto) se cortan.
- Los asesores de la oficina **no se ven afectados**: siguen por la LAN.

### 5.8 Salidas
- **NetBird Cloud**, con la misma app en los asesores: gratis hasta 5 usuarios; Team ~US$6 por
  usuario al mes.
- **Plan B de costo bajo**: la misma instalación en un VPS barato (~US$4–6 al mes, p. ej.
  Hetzner), restaurando las copias.

---

## 6. Opción B — Headscale propio en Oracle Cloud Always Free

- **Qué es**: una versión libre y gratuita de **la central de Tailscale**. Los asesores usan la
  **app oficial de Tailscale**, que es muy pulida, pero conectada a nuestra central.
- **Máquina, riesgo y copias**: igual que en la opción A (secciones 5.2–5.4).
  - Aquí los datos son una base SQLite y un `config.yaml`.
  - Es más liviano que NetBird.
- **Windows**: la app de Tailscale se apunta a la central propia con
  `tailscale login --login-server https://<dominio>` o con la clave de registro `LoginURL`. Las
  altas usan **claves de preautorización**.
- **Reglas**: un archivo de texto (formato HuJSON) con las ACL. Es flexible, pero se edita a mano.
- **Relays**: por defecto usa los relays DERP públicos de Tailscale (gratis). También se puede
  montar uno propio.
- **Administración**: por **comandos** (`headscale nodes list`, `headscale nodes delete`...).
  Hay paneles hechos por la comunidad (Headplane, headscale-ui), pero **no son oficiales**:
  pueden dejar de mantenerse.
- **Por qué no es la recomendada**: el owner prefiere un panel oficial para administrar a 100–200
  asesores. Además, es poco probable mudarse a Tailscale de pago (~US$8 por usuario), así que la
  ventaja de "mismo cliente que Tailscale" pesa poco.

---

## 7. Opción C — Cloudflare Tunnel

- **Cómo funciona**:
  - En la PC del proxy se instala `cloudflared` como servicio de Windows.
  - Abre una conexión **saliente** hacia Cloudflare (no se abre ningún puerto del router).
  - Cloudflare publica el proxy en `https://proxy.<dominio>` con HTTPS y protección contra
    ataques de saturación (DDoS).
- **Ventaja grande**: **no se instala nada en las PCs personales**. Muchos asesores no querrán
  una VPN de la empresa en su computadora.
- **Costo**:
  - el túnel es gratis;
  - hace falta un dominio administrado en Cloudflare (~US$10–12 al año);
  - el portero de identidad **Cloudflare Access** (correo + código antes de llegar al proxy) es
    gratis **hasta 50 usuarios**. Pasado eso cuesta ~US$7 por usuario al mes, y se paga **por
    todos**, sin cobro parcial (200 usuarios ≈ US$1,400 al mes).
- **El riesgo**:
  - sin Access, el proxy queda **en internet**, protegido solo por nuestro token;
  - cualquiera que obtenga un token puede consultar desde cualquier parte del mundo;
  - los bots escanean y prueban;
  - una falla de seguridad en FastAPI o en nuestro código quedaría al alcance de todos.
- **Requisito antes de abrir**: los puntos 1–3 de la sección 4 (tokens por asesor, límite,
  registro) **no son opcionales** aquí. `/admin` nunca se publica.
- **Frente a A**: más simple para el asesor, pero más expuesta. La seguridad descansa por
  completo en nuestro código.

---

## 8. Otras alternativas (descartadas o de referencia)

| Alternativa | Costo | Por qué no (o cuándo sí) |
|---|---|---|
| **Headscale/NetBird en la propia PC del proxy** (port forwarding + DuckDNS) | US$0 | Si se va la luz o el internet de la oficina, se caen los remotos. Hay que abrir puertos en el router. Ninguno de los dos corre nativo en Windows (habría que usar WSL o Docker). |
| **WireGuard "pelado" en el router** (algunos MikroTik o TP-Link lo traen) | US$0 | 200 archivos de configuración a mano, sin panel. Aislar a los asesores entre sí es difícil. |
| **mTLS: certificados por asesor** | US$0 | Muy seguro: sin certificado no hay conexión. Se podría emitir junto con la activación RSA actual. Pero exige desarrollo en la app y abrir un puerto. Bueno como capa extra a futuro. |
| **Abrir el proxy directo a internet** | US$0 | **No recomendado**: token en claro por HTTP, token único, escaneos de bots y la PC del proxy dentro de la LAN de la oficina. Si algún día se hiciera, como mínimo: HTTPS, tokens por asesor, límite, registro y `/admin` cerrado. |
| **Tailscale de pago** (Standard ~US$8 por usuario) | 50 → ~US$400/mes · 200 → ~US$1,600/mes | Cero mantenimiento, pero fuera de presupuesto. Su plan gratuito (6 usuarios, no comercial) no aplica. |
| **NetBird Cloud** (Team ~US$6 por usuario) | 50 → ~US$300/mes · 200 → ~US$1,200/mes | Salida de emergencia de la opción A. |
| **AnyDesk / TeamViewer** | $ | Es acceso remoto a una PC, no una red. No escala. |

### Cómo lo hacen las empresas grandes
- **Antes**: VPN "a toda la red", con equipos dedicados como FortiGate SSL-VPN, Cisco AnyConnect
  o Palo Alto GlobalProtect.
- **Ahora**: **Zero Trust (ZTNA / SASE)**, con Zscaler, Cloudflare One o Netskope.
  - Cada persona entra solo a la aplicación que necesita, con su cuenta corporativa (Microsoft
    Entra ID, Okta) y **doble factor**.
  - Se revisa que el equipo esté sano y la empresa entrega **laptops administradas**.
  - Cuesta US$7–20 o más por usuario al mes.
- NetBird, Tailscale y Headscale son la versión pequeña y barata de esa misma idea.

### ¿Hacer una VPN propia desde cero?
- **Inventar el cifrado: no.** Es el error clásico de seguridad; hasta los expertos fallan.
- Lo que sí es razonable es **armarla con piezas probadas**: WireGuard (el cifrado) más una
  central que reparta llaves y reglas. **Eso es exactamente lo que son NetBird y Headscale.**
- Instalar uno de ellos ya es "tener nuestra propia VPN". Escribir esa central nosotros serían
  meses de trabajo y quedaría menos segura.

---

## 9. Tabla comparativa final

| Criterio | A. NetBird + Oracle | B. Headscale + Oracle | C. Cloudflare Tunnel | NetBird en VPS | Tailscale de pago |
|---|---|---|---|---|---|
| Costo con 50 remotos | US$0 (+ dominio opc.) | US$0 (+ dominio opc.) | ~US$1/mes (dominio) | ~US$5/mes | ~US$400/mes |
| Costo con 200 remotos | US$0 | US$0 | ~US$1/mes sin Access · ~US$1,400/mes con Access | ~US$5/mes | ~US$1,600/mes |
| Costo anual (200) | US$0–12 | US$0–12 | ~US$12 (sin Access) | ~US$60 | ~US$19,200 |
| Se instala en la PC personal | App NetBird | App Tailscale | Nada | App NetBird | App Tailscale |
| Proxy expuesto a internet | No | No | Sí | No | No |
| Panel web oficial | Sí | No | Sí | Sí | Sí |
| Aislamiento entre asesores | Políticas en el panel | Archivo ACL | No hay red entre ellos | Políticas en el panel | Panel |
| Esfuerzo inicial | Medio (Linux + docker) | Medio (Linux) | Bajo | Medio | Bajo |
| Mantenimiento | Actualizar al mes + revisar copias | Igual | Casi nulo (app: tokens) | Igual que A | Nulo |
| Riesgo principal | Oracle reclama la VM | El mismo | Token filtrado | El proveedor sube el precio | Costo |
| Mitigación | PAYG + alerta US$1 + copias | Igual | Tokens por asesor + límite + registro | Copias | — |
| Si falla | Restaurar copia en VM nueva (~1 h) | Igual | Apagar el túnel | Restaurar copia | — |

---

## 10. Recomendación

**Opción A: NetBird propio en Oracle Cloud Always Free.**
1. Cuenta de Oracle en **Pay As You Go**, con **alerta de presupuesto en US$1** y una sola
   persona con acceso.
2. **Copias semanales** de los datos de NetBird fuera de Oracle, con el procedimiento de
   restauración escrito y probado una vez.
3. Política "Default" borrada; solo `asesores-remotos → proxy` por TCP 8080; aprobación de
   equipos activada.
4. Antes de abrir a los remotos, **tokens por asesor** (sección 4).

**Condición**: que se mantenga en US$0 o en "unos pocos dólares al año" (el dominio). Si Oracle
no resulta viable (sin capacidad, cuenta rechazada, reclamaciones), pasar a **NetBird en un VPS
de ~US$5 al mes**.

---

## 11. Trabajo derivado en la app (no se hace ahora)

Cada punto lleva su propio plan, con TDD (ver [TestingLog.md](TestingLog.md)):
- **Tokens del proxy por asesor**, revocables desde la consola owner. Hoy el `proxy_token` es
  único y está en `config.yaml`.
- **Límite de consultas** por token.
- **Registro de consultas** por token (para auditar; sin guardar más datos personales de los
  necesarios).
- **Configurar la URL del proxy** en el agente remoto (se relaciona con la tarea 7 de
  [AGENTS.md](AGENTS.md): leer URL y token de un archivo).
- Actualizar [docs/arquitectura.md](docs/arquitectura.md) y
  [docs/escalabilidad-remota.md](docs/escalabilidad-remota.md) cuando se elija la opción.

---

## 12. Preguntas para el dueño y pasos siguientes

**Preguntas**:
1. ¿Se acepta registrar una tarjeta de la empresa en Oracle (no cobra si se respeta la cuota) y
   pasar la cuenta a Pay As You Go?
2. ¿Se compra un dominio propio (~US$12 al año) o se usa uno gratuito de DuckDNS?
3. ¿Los asesores aceptan instalar una app de VPN en su PC personal? (Si muchos se niegan, la
   opción C gana peso.)
4. ¿Quién administra el panel (altas, bajas, aprobaciones) y quién revisa las copias?
5. ¿Hay alguna política de la empresa o de WinForce sobre consultar desde fuera de la oficina?

**Pasos siguientes**:
1. Elegir la opción (documento Word).
2. **Prueba piloto**: central + PC del proxy + 2 asesores remotos, durante una semana.
3. Implementar los tokens por asesor (sección 11).
4. Despliegue gradual al resto de los remotos.

---

## 13. Fuentes

Consultadas el 2026-11-06. Son de terceros salvo que se indique. **Confirmar precios y
condiciones en las páginas oficiales.**
- Oracle, recursos Always Free (oficial): <https://docs.oracle.com/iaas/Content/FreeTier/resourceref.htm>
- Límites y recorte reportado de Oracle Always Free: <https://space-node.net/blog/oracle-cloud-always-free-limits-2026>
- NetBird, repositorio oficial: <https://github.com/netbirdio/netbird>
- NetBird v0.62, usuarios locales (oficial): <https://netbird.io/knowledge-hub/local-users-simplified-idp>
- NetBird, quickstart (oficial): <https://docs.netbird.io/agent-network/quickstart>
- Precios de Tailscale 2026 y alternativas self-hosted: <https://wz-it.com/en/blog/tailscale-pricing-2026-headscale-netbird-self-hosted/>
- Precios de NetBird: <https://costbench.com/software/business-vpn/netbird/>
- Plan gratuito de Cloudflare Zero Trust: <https://costbench.com/software/business-vpn/cloudflare-zero-trust/free-plan/>

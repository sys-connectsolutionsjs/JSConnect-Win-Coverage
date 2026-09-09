// Extension "Renovar sesion WinForce" — service worker (MV3).
//
// El owner trabaja normal en su Chrome (ya logueado en WinForce). Cuando el proxy
// reporta la sesion muerta, el icono muestra un badge rojo "!". Un clic lee la
// PHPSESSID (chrome.cookies ve las cookies HttpOnly) y la manda al proxy local.
//
// El puerto 8080 lo sustituye install_service.bat por el real de config.yaml.

const PROXY = "http://127.0.0.1:8080";
const WINFORCE = "https://appwinforce.win.pe";

function badge(text, color) {
  chrome.action.setBadgeText({ text });
  if (color) chrome.action.setBadgeBackgroundColor({ color });
}

function notificar(mensaje) {
  chrome.action.setTitle({ title: mensaje });
  chrome.notifications.create({
    type: "basic",
    iconUrl: chrome.runtime.getURL("icon.png"),
    title: "Renovar sesion WinForce",
    message: mensaje,
  });
}

async function leerPhpSessid() {
  const c = await chrome.cookies.get({ url: WINFORCE, name: "PHPSESSID" });
  return c && c.value ? c.value : null;
}

async function renovar() {
  const php = await leerPhpSessid();
  if (!php) {
    notificar("No hay sesion de WinForce en este navegador. Inicia sesion primero y vuelve a pulsar.");
    return;
  }
  try {
    const r = await fetch(PROXY + "/local/renovar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ php_sessid: php }),
    });
    let detalle = "";
    try {
      const j = await r.json();
      detalle = j.detail || j.message || "";
    } catch (_) {}
    if (r.ok) {
      badge("", "#0a7d2c");
      notificar("Sesion del proxy renovada. Listo.");
    } else {
      notificar("El proxy rechazo la sesion (" + (detalle || r.status) + "). Reinicia sesion en WinForce y reintenta.");
    }
  } catch (e) {
    notificar("No se pudo contactar al proxy. Comprueba que el servicio JSWinProxy este encendido.");
  }
}

async function revisarEstado() {
  let vivaAhora;
  try {
    const r = await fetch(PROXY + "/local/estado");
    const j = await r.json();
    vivaAhora = !!j.session_alive;
    if (vivaAhora) {
      badge("", "#0a7d2c");
    } else {
      badge("!", "#c0392b");
      chrome.action.setTitle({ title: "La sesion del proxy murio. Pulsa para renovar." });
    }
  } catch (e) {
    badge("?", "#7f8c8d");
    return; // proxy inalcanzable: no sabemos el estado, no notificamos
  }

  // Toast del SO SOLO en la transicion (no cada 5 min). El estado anterior vive
  // en storage.session porque el service worker MV3 se duerme entre alarmas.
  const { sesionViva: vivaAntes } = await chrome.storage.session.get("sesionViva");
  await chrome.storage.session.set({ sesionViva: vivaAhora });
  if (vivaAntes === undefined || vivaAntes === vivaAhora) return;
  if (vivaAhora) {
    notificar("La sesion del proxy se renovo sola. Todo en orden.");
  } else {
    notificar("La sesion del proxy con WinForce caduco. Pulsa este icono para renovarla.");
  }
}

chrome.action.onClicked.addListener(renovar);
chrome.alarms.create("estado", { periodInMinutes: 5 });
chrome.alarms.onAlarm.addListener((a) => {
  if (a.name === "estado") revisarEstado();
});
chrome.runtime.onInstalled.addListener(revisarEstado);
chrome.runtime.onStartup.addListener(revisarEstado);

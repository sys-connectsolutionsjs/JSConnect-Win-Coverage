"""Huella estable de la PC (MachineGuid + CPU del registro) y huellas legacy."""

import types

import pytest

from validator_app.activation import fingerprint


@pytest.fixture(autouse=True)
def _base(monkeypatch):
    monkeypatch.setattr(fingerprint, "_machine_guid", lambda: "GUID-1")
    monkeypatch.setattr(fingerprint, "_cpu_registro", lambda: "AMD64 Family 25|Ryzen 5")
    monkeypatch.setattr(fingerprint, "_mac", lambda: "AA:BB:CC:DD:EE:FF")
    monkeypatch.setenv("PROCESSOR_IDENTIFIER", "AMD64 Family 25")
    monkeypatch.setattr(fingerprint, "_cim_cache", None)


def _salida(texto):
    return types.SimpleNamespace(stdout=texto, returncode=0)


def _sin_procesos(monkeypatch):
    def prohibido(*a, **k):
        raise AssertionError("la huella estable no debe lanzar procesos")

    monkeypatch.setattr(fingerprint.subprocess, "run", prohibido)


def test_huella_estable_no_lanza_procesos(monkeypatch):
    _sin_procesos(monkeypatch)
    assert fingerprint.obtener_huella() == fingerprint._formatear("GUID-1|AMD64 Family 25|Ryzen 5")


def test_huella_estable_no_depende_de_mac_ni_de_volumen(monkeypatch):
    _sin_procesos(monkeypatch)
    antes = fingerprint.obtener_huella()
    monkeypatch.setattr(fingerprint, "_mac", lambda: "11:22:33:44:55:66")
    monkeypatch.setattr(fingerprint, "_volume_serial_legacy", lambda: "USB-123")
    assert fingerprint.obtener_huella() == antes


def test_huella_cambia_con_otro_equipo(monkeypatch):
    antes = fingerprint.obtener_huella()
    monkeypatch.setattr(fingerprint, "_machine_guid", lambda: "GUID-2")
    assert fingerprint.obtener_huella() != antes


def test_formato_de_la_huella():
    huella = fingerprint.obtener_huella()
    assert len(huella) == 19 and huella.count("-") == 3


def test_legacy_con_wmic_y_huella_antigua_sin_wmic(monkeypatch):
    def wmic(args, **kwargs):
        if args[1] == "cpu":
            return _salida("ProcessorId       \r\n178BFBFF00A50F00  \r\n")
        return _salida(
            "DriveLetter  SerialNumber  \r\n             1111\r\nC:           3402271654\r\n"
        )

    monkeypatch.setattr(fingerprint, "_hay_wmic", lambda: True)
    monkeypatch.setattr(fingerprint.subprocess, "run", wmic)

    assert fingerprint.huellas_legacy() == {
        fingerprint._formatear("GUID-1|AA:BB:CC:DD:EE:FF|178BFBFF00A50F00|3402271654"),
        fingerprint._formatear("GUID-1|AA:BB:CC:DD:EE:FF|AMD64 Family 25|"),
    }


def test_legacy_sin_wmic_lee_cim_sin_abrir_ventana(monkeypatch):
    llamadas = []

    def runner(args, **kwargs):
        llamadas.append((args, kwargs))
        return _salida("178BFBFF00A50F00|3402271654\r\n")

    monkeypatch.setattr(fingerprint, "_hay_wmic", lambda: False)
    monkeypatch.setattr(fingerprint.subprocess, "run", runner)

    assert fingerprint._formatear(
        "GUID-1|AA:BB:CC:DD:EE:FF|178BFBFF00A50F00|3402271654"
    ) in fingerprint.huellas_legacy()
    assert len(llamadas) == 1  # una sola llamada a PowerShell, cacheada
    args, kwargs = llamadas[0]
    assert args[0] == "powershell"
    assert kwargs["creationflags"] == fingerprint._SIN_VENTANA
    assert kwargs["stdin"] == fingerprint.subprocess.DEVNULL


def test_legacy_si_powershell_falla_cae_a_processor_identifier(monkeypatch):
    def falla(*a, **k):
        raise OSError("sin powershell")

    monkeypatch.setattr(fingerprint, "_hay_wmic", lambda: False)
    monkeypatch.setattr(fingerprint.subprocess, "run", falla)
    assert fingerprint._cpu_legacy() == "AMD64 Family 25"
    assert fingerprint._volume_serial_legacy() == ""

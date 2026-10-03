"""Huella de la PC sin `wmic` (Windows 11 24H2+ ya no lo trae)."""

import types

import pytest

from validator_app.activation import fingerprint


@pytest.fixture(autouse=True)
def _base(monkeypatch):
    monkeypatch.setattr(fingerprint, "_machine_guid", lambda: "GUID-1")
    monkeypatch.setattr(fingerprint, "_mac", lambda: "AA:BB:CC:DD:EE:FF")
    monkeypatch.setenv("PROCESSOR_IDENTIFIER", "AMD64 Family 25")
    monkeypatch.setattr(fingerprint, "_cim_cache", None)


def _salida(texto):
    return types.SimpleNamespace(stdout=texto, returncode=0)


def test_sin_wmic_lee_cpu_y_volumen_por_cim_sin_abrir_ventana(monkeypatch):
    llamadas = []

    def runner(args, **kwargs):
        llamadas.append((args, kwargs))
        return _salida("178BFBFF00A50F00|3402271654\r\n")

    monkeypatch.setattr(fingerprint, "_hay_wmic", lambda: False)
    monkeypatch.setattr(fingerprint.subprocess, "run", runner)

    assert fingerprint._cpu() == "178BFBFF00A50F00"
    assert fingerprint._volume_serial() == "3402271654"
    assert len(llamadas) == 1  # una sola llamada a PowerShell, cacheada
    args, kwargs = llamadas[0]
    assert args[0] == "powershell"
    assert kwargs["creationflags"] == fingerprint._SIN_VENTANA


def test_cim_y_wmic_dan_la_misma_huella_con_los_mismos_valores(monkeypatch):
    """Una PC de Windows 10 (con wmic) que pasa a Windows 11 (sin wmic) conserva
    su huella: CIM lee los mismos valores de WMI."""

    def wmic(args, **kwargs):
        if args[1] == "cpu":
            return _salida("ProcessorId       \r\n178BFBFF00A50F00  \r\n")
        return _salida(
            "DriveLetter  SerialNumber  \r\n             1111\r\nC:           3402271654\r\n"
        )

    monkeypatch.setattr(fingerprint, "_hay_wmic", lambda: True)
    monkeypatch.setattr(fingerprint.subprocess, "run", wmic)
    huella_wmic = fingerprint.obtener_huella()

    monkeypatch.setattr(fingerprint, "_hay_wmic", lambda: False)
    monkeypatch.setattr(
        fingerprint.subprocess, "run", lambda a, **k: _salida("178BFBFF00A50F00|3402271654")
    )
    assert fingerprint.obtener_huella() == huella_wmic


def test_sin_wmic_acepta_tambien_la_huella_de_versiones_anteriores(monkeypatch):
    monkeypatch.setattr(fingerprint, "_hay_wmic", lambda: False)
    monkeypatch.setattr(
        fingerprint.subprocess, "run", lambda a, **k: _salida("178BFBFF00A50F00|3402271654")
    )
    legacy = fingerprint._formatear("GUID-1|AA:BB:CC:DD:EE:FF|AMD64 Family 25|")

    huellas = fingerprint.huellas_compatibles()

    assert huellas == {fingerprint.obtener_huella(), legacy}


def test_con_wmic_solo_la_huella_actual(monkeypatch):
    monkeypatch.setattr(fingerprint, "_hay_wmic", lambda: True)
    monkeypatch.setattr(fingerprint.subprocess, "run", lambda a, **k: _salida(""))
    assert fingerprint.huellas_compatibles() == {fingerprint.obtener_huella()}


def test_si_powershell_falla_cae_a_processor_identifier(monkeypatch):
    def falla(*a, **k):
        raise OSError("sin powershell")

    monkeypatch.setattr(fingerprint, "_hay_wmic", lambda: False)
    monkeypatch.setattr(fingerprint.subprocess, "run", falla)
    assert fingerprint._cpu() == "AMD64 Family 25"
    assert fingerprint._volume_serial() == ""

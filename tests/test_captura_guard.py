import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

import captura


def test_stub_padre_no_bloquea():
    mi_pid = 200
    procesos = [
        {"ProcessId": 100, "ParentProcessId": 0, "CommandLine": "cmd.exe"},
        {
            "ProcessId": 101,
            "ParentProcessId": 100,
            "CommandLine": "WindowsApps/python.exe tools/captura.py",
        },
        {
            "ProcessId": 200,
            "ParentProcessId": 101,
            "CommandLine": "pythoncore/python.exe tools/captura.py",
        },
    ]
    assert captura._buscar_otra_instancia(procesos, mi_pid) is False


def test_segunda_instancia_real_bloquea():
    mi_pid = 300
    procesos = [
        {
            "ProcessId": 101,
            "ParentProcessId": 100,
            "CommandLine": "WindowsApps/python.exe tools/captura.py",
        },
        {
            "ProcessId": 200,
            "ParentProcessId": 101,
            "CommandLine": "pythoncore/python.exe tools/captura.py",
        },
        {
            "ProcessId": 300,
            "ParentProcessId": 101,
            "CommandLine": "pythoncore/python.exe tools/captura.py",
        },
    ]
    assert captura._buscar_otra_instancia(procesos, mi_pid) is True


def test_proceso_no_captura_no_bloquea():
    mi_pid = 200
    procesos = [
        {
            "ProcessId": 150,
            "ParentProcessId": 100,
            "CommandLine": "python.exe main.py",
        },
        {
            "ProcessId": 200,
            "ParentProcessId": 100,
            "CommandLine": "pythoncore/python.exe tools/captura.py",
        },
    ]
    assert captura._buscar_otra_instancia(procesos, mi_pid) is False


def test_es_ancestro_directo():
    arbol = {200: 101, 101: 100, 100: 0}
    assert captura._es_ancestro(arbol, 101, 200) is True
    assert captura._es_ancestro(arbol, 100, 200) is True
    assert captura._es_ancestro(arbol, 200, 200) is False
    assert captura._es_ancestro(arbol, 999, 200) is False

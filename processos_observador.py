"""Grupo nativo do Windows que encerra somente a árvore desta coleta.

https://learn.microsoft.com/windows/win32/procthread/job-objects
"""
import ctypes
from ctypes import wintypes as w
import os


class Limites(ctypes.Structure):
    _fields_ = [("tempo_processo", ctypes.c_int64), ("tempo_job", ctypes.c_int64),
                ("flags", w.DWORD), ("min_ws", ctypes.c_size_t),
                ("max_ws", ctypes.c_size_t), ("ativos", w.DWORD),
                ("afinidade", ctypes.c_size_t), ("prioridade", w.DWORD),
                ("classe", w.DWORD)]


class LimitesEstendidos(ctypes.Structure):
    _fields_ = [("basicos", Limites), ("io", ctypes.c_uint64 * 6),
                ("mem_processo", ctypes.c_size_t), ("mem_job", ctypes.c_size_t),
                ("pico_processo", ctypes.c_size_t), ("pico_job", ctypes.c_size_t)]


class GrupoProcessos:
    def __init__(self):
        self.handle = None
        if os.name != "nt":
            return
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        for nome, args, resultado in [
            ("CreateJobObjectW", [ctypes.c_void_p, w.LPCWSTR], w.HANDLE),
            ("SetInformationJobObject", [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD], w.BOOL),
            ("OpenProcess", [w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
            ("AssignProcessToJobObject", [w.HANDLE, w.HANDLE], w.BOOL),
            ("CloseHandle", [w.HANDLE], w.BOOL),
        ]:
            funcao = getattr(self.api, nome)
            funcao.argtypes, funcao.restype = args, resultado
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limites = LimitesEstendidos()
        limites.basicos.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limites), ctypes.sizeof(limites)):
            erro = ctypes.WinError(ctypes.get_last_error())
            self.fechar()
            raise erro

    def associar(self, pid):
        if self.handle is None:
            return
        processo = self.api.OpenProcess(0x0101, False, pid)  # SET_QUOTA | TERMINATE
        if not processo:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not self.api.AssignProcessToJobObject(self.handle, processo):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            self.api.CloseHandle(processo)

    def fechar(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def memoria_disponivel_mb():
    if os.name != "nt":
        return None
    class Estado(ctypes.Structure):
        _fields_ = [("tamanho", w.DWORD), ("carga", w.DWORD)] + [
            (nome, ctypes.c_uint64) for nome in
            ("total", "livre", "page_total", "page_livre", "virtual_total", "virtual_livre", "estendida")]
    estado = Estado()
    estado.tamanho = ctypes.sizeof(estado)
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    if not api.GlobalMemoryStatusEx(ctypes.byref(estado)):
        raise ctypes.WinError(ctypes.get_last_error())
    return estado.livre // (1024 * 1024)

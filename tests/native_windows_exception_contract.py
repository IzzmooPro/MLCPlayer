# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Windows native child'lar icin ortak, yuklemesiz SEH siniflandiricisi.

Bu modul `mpv`, PyQt veya urun kodu yuklemez. CPython 3.14 Windows
`faulthandler`, vectored exception handler ile first-chance olaylari daha
sonraki handler yakalamadan once gorebilir. LuaJIT ise Lua runtime error
kodunu `0xe24c4a00 | LUA_ERRRUN(2)` olarak `RaiseException` ile tasir.

Baslik tek basina ASLA muafiyet degildir. Yalniz CPython'in tam rapor
dilbilgisi taninir; kabul karari ayrica caller'da exit 0 ve eksiksiz marker
sozlesmesi ister.
"""

LUAJIT_RUNTIME_ERROR_TRACE = "Windows fatal exception: code 0xe24c4a02"
_C_STACK_HEADER = "Current thread's C stack trace (most recent call first):"


def complete_luajit_faulthandler_reports(stderr):
    """stderr yalniz bir veya daha cok TAM CPython VEH raporu mu?"""
    if not stderr or "\ufffd" in stderr:
        return False

    chunks = stderr.split(LUAJIT_RUNTIME_ERROR_TRACE)
    if chunks[0] != "" or len(chunks) < 2:
        return False

    for chunk in chunks[1:]:
        if not chunk.startswith("\n\n") or not chunk.endswith("\n"):
            return False
        lines = chunk[2:].splitlines()
        try:
            c_stack_at = lines.index(_C_STACK_HEADER)
        except ValueError:
            return False

        python_lines = lines[:c_stack_at]
        c_stack_lines = lines[c_stack_at + 1:]

        # Her thread bolumu AYRI tam olmali. Yalniz "raporda bir yerde"
        # baslik/frame aramak, baska saglam thread'in eksik bolumu aklamasina
        # izin verirdi.
        have_thread = False
        frame_count = 0
        for line in python_lines:
            if not line:
                continue
            is_header = (
                (line.startswith("Thread ") or
                 line.startswith("Current thread ")) and
                line.endswith("(most recent call first):"))
            if is_header:
                if have_thread and frame_count == 0:
                    return False
                have_thread = True
                frame_count = 0
            elif line.startswith("  "):
                if not have_thread:
                    return False
                frame_count += 1
            else:
                return False

        if not have_thread or frame_count == 0 or not c_stack_lines:
            return False
        if any(line and not line.startswith("  ") for line in c_stack_lines):
            return False

    return True

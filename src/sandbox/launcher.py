#!/usr/bin/env python3
"""Sandbox fırlatıcısı: kaynak limitlerini uygular, ayrıcalığı düşürür, exec eder.

**Bu dosya projeden hiçbir şey içe aktarmaz.** Yalnızca standart kütüphane
kullanır ve mutlak yolla çalıştırılır; böylece alt sürecin ortamı (PATH,
PYTHONPATH dahil) tamamen temizlenebilir.

Neden ayrı bir süreç, `preexec_fn` değil: `preexec_fn` çatallama (fork) ile
`exec` arasında çalışır ve çok iş parçacıklı bir süreçte (uvicorn) kilitlenme
riski taşır — Python belgeleri bunu açıkça uyarır. Fırlatıcı ise normal bir
alt süreçtir; limitleri kendi üzerine uygular ve `exec` sonrası hedefe
devreder. Kaynak limitleri `exec` sınırını aşarak korunur.

Çıkış kodları:
    126  fırlatıcı kurulumu başarısız (limit veya ayrıcalık düşürme)
    127  hedef komut bulunamadı
"""

from __future__ import annotations

import argparse
import os
import resource
import sys

MB = 1024 * 1024
SETUP_FAILED = 126
NOT_FOUND = 127


def _fail(message: str) -> None:
    print(f"sandbox-launcher: {message}", file=sys.stderr)
    raise SystemExit(SETUP_FAILED)


def apply_limits(cpu_sec: int, mem_mb: int, nproc: int, fsize_mb: int) -> None:
    """Kaynak tavanlarını sert (hard) limit olarak uygular.

    Bellek tavanı RLIMIT_DATA'dır, RLIMIT_AS DEĞİL: V8 pointer-compression
    için devasa bir sanal adres alanı ayırır ve RLIMIT_AS onu sayarak meşru
    kodu bile öldürür. Ölçüm: tests/manual/rlimit_olcumu.py
    """
    limits = (
        (resource.RLIMIT_CPU, cpu_sec, "CPU"),
        (resource.RLIMIT_DATA, mem_mb * MB, "bellek"),
        (resource.RLIMIT_NPROC, nproc, "süreç sayısı"),
        (resource.RLIMIT_FSIZE, fsize_mb * MB, "dosya boyutu"),
        (resource.RLIMIT_CORE, 0, "çekirdek dökümü"),
    )
    for key, value, label in limits:
        try:
            resource.setrlimit(key, (value, value))
        except (ValueError, OSError) as exc:
            _fail(f"{label} limiti uygulanamadı: {exc}")


def drop_privileges(username: str) -> bool:
    """Ayrıcalıksız kullanıcıya geçer. Root değilsek sessizce atlar.

    Root değilken atlamak bir güvenlik zaafı değildir: zaten ayrıcalıksızız.
    Ama çağıran bunu bilmeli, o yüzden sonuç döndürülür.
    """
    if not username or os.getuid() != 0:
        return False

    import pwd  # yalnızca POSIX'te gerekli

    try:
        entry = pwd.getpwnam(username)
    except KeyError:
        _fail(f"kullanıcı bulunamadı: {username}")

    try:
        os.setgroups([])  # miras alınan ek grupları at
        os.setgid(entry.pw_gid)
        os.setuid(entry.pw_uid)
    except OSError as exc:
        _fail(f"ayrıcalık düşürülemedi: {exc}")

    if os.getuid() == 0 or os.geteuid() == 0:
        _fail("ayrıcalık düşürme sessizce başarısız oldu")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--cpu", type=int, required=True)
    parser.add_argument("--mem-mb", type=int, required=True)
    parser.add_argument("--nproc", type=int, required=True)
    parser.add_argument("--fsize-mb", type=int, required=True)
    parser.add_argument("--user", default="")
    parser.add_argument("--cwd", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)

    args = parser.parse_args(argv)
    command = [a for a in args.command if a != "--"]
    if not command:
        _fail("çalıştırılacak komut verilmedi")

    try:
        os.chdir(args.cwd)
    except OSError as exc:
        _fail(f"çalışma dizinine geçilemedi: {exc}")

    # Sıra önemli: limitler root'ken uygulanır (düşürme sonrası yükseltilemez),
    # ayrıcalık en son bırakılır.
    apply_limits(args.cpu, args.mem_mb, args.nproc, args.fsize_mb)
    drop_privileges(args.user)

    try:
        os.execvp(command[0], command)
    except FileNotFoundError:
        print(f"sandbox-launcher: komut bulunamadı: {command[0]}", file=sys.stderr)
        return NOT_FOUND
    except OSError as exc:
        _fail(f"komut çalıştırılamadı: {exc}")
    return SETUP_FAILED  # execvp başarılıysa buraya ulaşılmaz


if __name__ == "__main__":
    raise SystemExit(main())

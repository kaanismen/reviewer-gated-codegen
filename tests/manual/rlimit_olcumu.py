"""Sandbox kaynak limitlerinin fiilen uygulandığını ÖLÇEN elle çalıştırılan betik.

Neden var: `PROJECT.md` §6 "rlimit'ler uygulanır" diye iddia ediyor. Bu iddia
Docker Desktop / WSL2 altında doğrulanmadan yazılmıştı ve AI çalışma
günlüğünün denetim tablosunda "doğrulanmadı" olarak işaretliydi. Bu betik o
satırı kapatır ve iddiayı yeniden üretilebilir kılar.

Çalıştırma:
    docker compose exec atolye python tests/manual/rlimit_olcumu.py

Otomatik test paketinin parçası DEĞİLDİR: konteyner ayrıcalıkları ve
gerçek kaynak tüketimi gerektirir, saniyeler sürer. Otomatik karşılıkları
`tests/test_security.py` içindedir (Faz 2).
"""

import os
import pwd
import resource
import subprocess

RUNNER = pwd.getpwnam("runner")
MB = 1024**2
HELLO = "console.log('calisti')"


def preexec(limits, drop_privs=True):
    def _apply():
        for key, value in limits.items():
            resource.setrlimit(getattr(resource, key), (value, value))
        if drop_privs:
            os.setgid(RUNNER.pw_gid)
            os.setuid(RUNNER.pw_uid)

    return _apply


def run(label, code, limits=None, drop_privs=True, timeout=8, argv=()):
    try:
        done = subprocess.run(
            ["node", *argv, "-e", code],
            preexec_fn=preexec(limits or {}, drop_privs),
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd="/tmp",
            env={"PATH": "/usr/local/bin:/usr/bin:/bin"},
        )
        outcome = f"rc={done.returncode}"
        if done.returncode < 0:
            outcome += f" sinyal={-done.returncode}"
        text = (done.stderr or done.stdout).strip().splitlines()
        detail = text[0][:78] if text else ""
    except subprocess.TimeoutExpired:
        outcome, detail = "ZAMAN ASIMI", f"{timeout} sn icinde bitmedi"
    print(f"  {label:<44} {outcome:<20} {detail}")


print("A) Mesru kod engellenmemeli — beklenen: rc=0")
run("limitsiz, root", HELLO, drop_privs=False)
run("limitsiz, runner", HELLO)
run("RLIMIT_CPU=5", HELLO, {"RLIMIT_CPU": 5})
run("RLIMIT_NPROC=32", HELLO, {"RLIMIT_NPROC": 32})
run("RLIMIT_FSIZE=10MB", HELLO, {"RLIMIT_FSIZE": 10 * MB})
run("RLIMIT_DATA=512MB  <- kullandigimiz", HELLO, {"RLIMIT_DATA": 512 * MB})

print("\nB) RLIMIT_AS neden KULLANILMIYOR — mesru kod bile ayakta kalamiyor")
print("   V8, pointer-compression icin devasa SANAL adres alani ayirir;")
print("   bu alan yerlesik bellek degildir ama RLIMIT_AS onu sayar.")
run("RLIMIT_AS=128MB (beklenen: bozulur)", HELLO, {"RLIMIT_AS": 128 * MB})
run("RLIMIT_AS=512MB (beklenen: bozulur)", HELLO, {"RLIMIT_AS": 512 * MB})
run("RLIMIT_AS=4GB   (ancak burada calisir)", HELLO, {"RLIMIT_AS": 4096 * MB})

print("\nC) Kotu kod gercekten durduruluyor mu — beklenen: hepsi olduruldu")
run("CPU=3 vs sonsuz dongu", "while(true){Math.sqrt(Math.random())}",
    {"RLIMIT_CPU": 3}, timeout=15)
run("FSIZE=1MB vs 50MB dosya yazimi",
    "require('fs').writeFileSync('/tmp/big.bin',Buffer.alloc(50*1024*1024))",
    {"RLIMIT_FSIZE": 1 * MB})
run("DATA=256MB vs sinirsiz ayirma",
    "const a=[];for(;;){a.push(Buffer.alloc(16*1024*1024))}",
    {"RLIMIT_DATA": 256 * MB}, timeout=15)
run("LIMITSIZ ayirma (duvar saati son katman)",
    "const a=[];for(;;){a.push(Buffer.alloc(16*1024*1024))}", {}, timeout=10)

print("\nD) Ayricalik dusurme")
run("uid/gid raporu", "console.log('uid='+process.getuid()+' gid='+process.getgid())")
run("root dosyasina yazma denemesi",
    "try{require('fs').writeFileSync('/etc/kanit','x');console.log('YAZDI - KOTU')}"
    "catch(e){console.log('engellendi: '+e.code)}")

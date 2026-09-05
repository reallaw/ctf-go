#!/usr/bin/env python3
"""Агент деплоя на VPS: слушает Firestore и пересоздаёт сервис команды по кнопке.

Для КАЖДОЙ команды запускается свой агент. Он подписывается на документ
teams/{teamId} и при изменении поля deploySeq:
  1. пишет teams/{teamId}.code в файл instances/{teamId}/app.py;
  2. (пере)создаёт docker-контейнер команды на её порту (bind-mount app.py,
     поэтому пересборка образа не нужна — только перезапуск);
  3. прогоняет эталонный чекер (уязвимости + SLA);
  4. пишет обратно deployStatus / deployVulns / deploySla / deployLog —
     игрок видит результат на странице «Мой код».

Запуск (пример):
  export GOOGLE_APPLICATION_CREDENTIALS=~/live-ctf/serviceAccount.json
  export GOOGLE_CLOUD_PROJECT=ctf-go
  python3 scripts/deploy_agent.py --team team-alpha --container alpha \
      --port 8001 --public-host 89.39.121.189

Держите процесс живым (tmux/systemd). По одному агенту на команду.
"""

import argparse
import os
import subprocess
import threading
import time

import firebase_admin
from firebase_admin import firestore

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHALLENGE_DIR = os.path.join(REPO, "challenges", "01-securenotes")
IMAGE = "securenotes"


def sh(cmd: list[str], timeout: int = 300) -> tuple[int, str]:
    """Запуск команды, возврат (код, объединённый stdout+stderr)."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr)
    except subprocess.TimeoutExpired:
        return 124, f"timeout: {' '.join(cmd)}"


def ensure_image() -> str:
    code, out = sh(["docker", "build", "-t", IMAGE, CHALLENGE_DIR])
    return out if code != 0 else "образ готов"


def redeploy(team_id: str, container: str, port: int, code: str, secret: str,
             public_host: str) -> dict:
    """Записывает код и пересоздаёт контейнер команды. Возвращает результат."""
    inst_dir = os.path.join(REPO, "instances", team_id)
    os.makedirs(inst_dir, exist_ok=True)
    app_path = os.path.join(inst_dir, "app.py")
    with open(app_path, "w") as f:
        f.write(code)

    log = []
    # Пересоздаём контейнер: код монтируем внутрь, пересборка образа не требуется.
    sh(["docker", "rm", "-f", container])
    rc, out = sh([
        "docker", "run", "-d", "--restart=always",
        "-p", f"{port}:8000",
        "-e", f"SECRET_KEY={secret}",
        "-v", f"{app_path}:/app/app.py:ro",
        "--name", container, IMAGE,
    ])
    log.append(out.strip())
    if rc != 0:
        return {"status": "error", "log": "\n".join(log)[-4000:],
                "vulns": None, "sla": None}

    # Ждём подъёма сервиса.
    base = f"http://{public_host}:{port}"
    checker = os.path.join(CHALLENGE_DIR, "checker.py")
    up = False
    for _ in range(20):
        rc, _o = sh(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                     f"{base}/health"], timeout=8)
        if _o.strip() == "200":
            up = True
            break
        time.sleep(0.5)
    if not up:
        # частая причина — синтаксическая ошибка в коде игрока
        _rc, dl = sh(["docker", "logs", "--tail", "30", container])
        log.append("Сервис не поднялся. Логи контейнера:\n" + dl)
        return {"status": "error", "log": "\n".join(log)[-4000:],
                "vulns": None, "sla": False}

    # Чекер: сколько уязвимостей осталось и жив ли сервис.
    rc_exp, out_exp = sh(["python3", checker, "exploit", base])
    rc_sla, out_sla = sh(["python3", checker, "sla", base])
    vulns = None
    for line in out_exp.splitlines():
        if "активных уязвимостей" in line:
            try:
                vulns = int(line.split(":")[1].strip().split("/")[0])
            except Exception:
                pass
    sla_ok = rc_sla == 0
    log.append(out_exp.strip())
    log.append(out_sla.strip())
    return {"status": "ok", "log": "\n".join(log)[-4000:],
            "vulns": vulns, "sla": sla_ok}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", required=True, help="teamId, напр. team-alpha")
    ap.add_argument("--container", required=True, help="имя docker-контейнера")
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--public-host", required=True, help="IP/домен VPS для чекера")
    ap.add_argument("--secret", default=None, help="SECRET_KEY сервиса (по умолчанию из team)")
    args = ap.parse_args()

    firebase_admin.initialize_app(
        options={"projectId": os.environ.get("GOOGLE_CLOUD_PROJECT", "ctf-go")}
    )
    db = firestore.client()
    ref = db.collection("teams").document(args.team)

    print(f"[agent:{args.team}] сборка образа…")
    print(f"[agent:{args.team}] {ensure_image()}")

    state = {"seq": None}
    done = threading.Event()

    def on_snapshot(docs, changes, read_time):
        for snap in docs:
            data = snap.to_dict() or {}
            seq = int(data.get("deploySeq", 0))
            # Первый снимок только запоминает текущий seq (без деплоя на старте).
            if state["seq"] is None:
                state["seq"] = seq
                print(f"[agent:{args.team}] слежу, текущий deploySeq={seq}")
                return
            if seq == state["seq"]:
                return
            state["seq"] = seq
            code = data.get("code") or ""
            if not code.strip():
                continue
            secret = args.secret or f"{args.team}-secret"
            print(f"[agent:{args.team}] деплой #{seq}…")
            ref.update({"deployStatus": "deploying"})
            res = redeploy(args.team, args.container, args.port, code, secret,
                           args.public_host)
            ref.update({
                "deployStatus": res["status"],
                "deployVulns": res["vulns"],
                "deploySla": res["sla"],
                "deployLog": res["log"],
                "lastDeployAt": int(time.time()),
            })
            print(f"[agent:{args.team}] готово: {res['status']} "
                  f"vulns={res['vulns']} sla={res['sla']}")

    ref.on_snapshot(on_snapshot)
    print(f"[agent:{args.team}] запущен. Ctrl+C для выхода.")
    try:
        while not done.wait(1):
            pass
    except KeyboardInterrupt:
        print("выход")


if __name__ == "__main__":
    main()

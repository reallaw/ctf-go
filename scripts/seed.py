#!/usr/bin/env python3
"""Наполняет Firestore демо-данными для live-ctf.

Рассчитан на Firebase Emulator Suite. Требует переменные окружения эмулятора:
  FIRESTORE_EMULATOR_HOST=localhost:8080
  FIREBASE_AUTH_EMULATOR_HOST=localhost:9099   (нужно только для --with-users)
  GOOGLE_CLOUD_PROJECT=live-ctf-demo

Создаёт:
  * соревнование demo-comp (status=running);
  * команды team-alpha и team-beta с URL их сервисов;
  * (опц.) пользователей-игроков и админа, привязанных к командам.

Запуск:
  python scripts/seed.py
  python scripts/seed.py --with-users \
      --alpha-url http://localhost:8001 --beta-url http://localhost:8002
"""

import argparse
import os

import firebase_admin
from firebase_admin import auth, firestore

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "live-ctf-demo")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--alpha-url", default="http://localhost:8001")
    ap.add_argument("--beta-url", default="http://localhost:8002")
    ap.add_argument("--with-users", action="store_true",
                    help="создать демо-пользователей (нужен Auth-эмулятор)")
    args = ap.parse_args()

    if "FIRESTORE_EMULATOR_HOST" not in os.environ:
        print("ВНИМАНИЕ: FIRESTORE_EMULATOR_HOST не задан — скрипт пойдёт в облако!")

    firebase_admin.initialize_app(options={"projectId": PROJECT})
    db = firestore.client()

    # Команды.
    db.collection("teams").document("team-alpha").set(
        {"name": "Alpha", "members": [], "serviceUrl": args.alpha_url,
         "attackPts": 0, "defensePts": 0, "slaPts": 0}
    )
    db.collection("teams").document("team-beta").set(
        {"name": "Beta", "members": [], "serviceUrl": args.beta_url,
         "attackPts": 0, "defensePts": 0, "slaPts": 0}
    )

    # Соревнование.
    db.collection("competitions").document("demo-comp").set(
        {"name": "Демо AD-CTF", "status": "running", "currentRound": 0,
         "roundDurationSec": 300, "challengeIds": ["01-securenotes"]}
    )
    print("Созданы: команды team-alpha, team-beta; соревнование demo-comp.")

    if args.with_users:
        _seed_users(db)


def _seed_users(db):
    """Создаёт админа и двух игроков (пароль у всех: password123)."""
    users = [
        ("admin@live.ctf", "Организатор", "admin", None),
        ("alpha@live.ctf", "Игрок Alpha", "player", "team-alpha"),
        ("beta@live.ctf", "Игрок Beta", "player", "team-beta"),
    ]
    for email, name, role, team in users:
        try:
            u = auth.create_user(email=email, password="password123")
        except Exception:
            u = auth.get_user_by_email(email)
        db.collection("users").document(u.uid).set(
            {"displayName": name, "role": role, "teamId": team}
        )
        if team:
            db.collection("teams").document(team).update(
                {"members": firestore.ArrayUnion([u.uid])}
            )
        print(f"  пользователь {email} ({role}) -> {team or '—'}")
    print("Пароль для всех демо-аккаунтов: password123")


if __name__ == "__main__":
    main()

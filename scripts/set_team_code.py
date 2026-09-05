#!/usr/bin/env python3
"""Инициализирует поле teams/{teamId}.code исходным (уязвимым) кодом задания.

Нужно один раз, чтобы редактор «Мой код» в браузере открылся с кодом сервиса,
а не пустым. Берёт код из challenges/01-securenotes/app.py.

  export GOOGLE_APPLICATION_CREDENTIALS=~/live-ctf/serviceAccount.json
  export GOOGLE_CLOUD_PROJECT=ctf-go
  python3 scripts/set_team_code.py                 # всем командам
  python3 scripts/set_team_code.py team-alpha      # только одной
"""

import os
import sys

import firebase_admin
from firebase_admin import firestore

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(REPO, "challenges", "01-securenotes", "app.py")


def main():
    code = open(APP).read()
    firebase_admin.initialize_app(
        options={"projectId": os.environ.get("GOOGLE_CLOUD_PROJECT", "ctf-go")}
    )
    db = firestore.client()

    only = sys.argv[1] if len(sys.argv) > 1 else None
    teams = ([db.collection("teams").document(only)]
             if only else
             [s.reference for s in db.collection("teams").stream()])
    for ref in teams:
        ref.update({"code": code, "deploySeq": 0, "deployStatus": "idle"})
        print(f"код записан в {ref.id}")


if __name__ == "__main__":
    main()

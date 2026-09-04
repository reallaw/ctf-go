"""Начисление очков attack-defense CTF.

Три составляющие итогового счёта команды:
  * attack  — за украденные и сданные флаги соперников;
  * defense — за раунды, в которых флаг команды никто не украл;
  * sla     — за работоспособный (прошедший проверку чекера) сервис.

Модуль работает поверх Firestore-транзакций, чтобы параллельные сабмиты
не затирали счёт друг друга.
"""

from __future__ import annotations

from firebase_admin import firestore

# Базовые ставки очков. Вынесены в константы, чтобы правила были прозрачны.
ATTACK_POINTS = 100      # за каждый уникальный украденный флаг
DEFENSE_POINTS = 50      # за раунд без утечки твоего флага
SLA_POINTS = 20          # за раунд с живым сервисом


def _team_ref(db, team_id: str):
    return db.collection("teams").document(team_id)


def award_attack(db, attacker_team_id: str, points: int = ATTACK_POINTS) -> None:
    """Атомарно увеличивает очки атаки команды."""
    _team_ref(db, attacker_team_id).update(
        {"attackPts": firestore.Increment(points)}
    )


def award_defense(db, team_id: str, points: int = DEFENSE_POINTS) -> None:
    _team_ref(db, team_id).update({"defensePts": firestore.Increment(points)})


def award_sla(db, team_id: str, points: int = SLA_POINTS) -> None:
    _team_ref(db, team_id).update({"slaPts": firestore.Increment(points)})


def total_score(team_doc: dict) -> int:
    """Удобный помощник: суммарный счёт из документа команды."""
    return (
        int(team_doc.get("attackPts", 0))
        + int(team_doc.get("defensePts", 0))
        + int(team_doc.get("slaPts", 0))
    )

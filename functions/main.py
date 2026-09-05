"""Cloud Functions платформы live-ctf (Python).

HTTPS-эндпоинты для клиента (React) и запланированный чекер раундов.
Клиент вызывает функции как callable (firebase/functions httpsCallable) — это даёт
проверенный контекст авторизации (request.auth) без ручного разбора токенов.

Вся запись очков/флагов/сабмитов идёт ТОЛЬКО здесь через Admin SDK, поэтому
Firestore-правила запрещают клиенту писать в эти коллекции напрямую.
"""

from __future__ import annotations

import time

from firebase_admin import auth, firestore, initialize_app
from firebase_functions import https_fn, options, scheduler_fn

import checker
import scoring

initialize_app()

# CORS для локального фронтенда/эмулятора. В проде замените на свой домен.
_CORS = options.CorsOptions(cors_origins="*", cors_methods=["GET", "POST"])


def _db():
    return firestore.client()


def _require_auth(req: https_fn.CallableRequest):
    if req.auth is None:
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode.UNAUTHENTICATED,
            "Требуется вход в систему.",
        )
    return req.auth.uid


def _user_doc(db, uid: str) -> dict:
    snap = db.collection("users").document(uid).get()
    if not snap.exists:
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode.FAILED_PRECONDITION,
            "Профиль пользователя не найден.",
        )
    return snap.to_dict()


def _require_admin(db, uid: str) -> dict:
    user = _user_doc(db, uid)
    if user.get("role") != "admin":
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode.PERMISSION_DENIED,
            "Действие доступно только администратору.",
        )
    return user


# --------------------------------------------------------------------------- #
# Игрок: регистрация URL своего сервиса                                        #
# --------------------------------------------------------------------------- #
@https_fn.on_call(cors=_CORS)
def register_service(req: https_fn.CallableRequest) -> dict:
    """Команда регистрирует URL своей развёрнутой копии уязвимого сервиса."""
    uid = _require_auth(req)
    db = _db()
    user = _user_doc(db, uid)
    team_id = user.get("teamId")
    if not team_id:
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode.FAILED_PRECONDITION,
            "Пользователь не привязан к команде.",
        )

    url = (req.data or {}).get("serviceUrl", "").strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            "Ожидается корректный http(s) URL сервиса.",
        )

    db.collection("teams").document(team_id).update({"serviceUrl": url})
    return {"ok": True, "teamId": team_id, "serviceUrl": url}


# --------------------------------------------------------------------------- #
# Игрок: сдача украденного флага                                              #
# --------------------------------------------------------------------------- #
@https_fn.on_call(cors=_CORS)
def submit_flag(req: https_fn.CallableRequest) -> dict:
    """Проверяет сданный флаг и, если он валиден, начисляет очки атаки.

    Защита от типовых злоупотреблений:
      * нельзя сдать собственный флаг;
      * нельзя сдать просроченный флаг;
      * нельзя повторно сдать уже засчитанный флаг (idempotent);
      * сравнение по хешу — сырой флаг в БД не хранится.
    """
    uid = _require_auth(req)
    db = _db()
    user = _user_doc(db, uid)
    attacker_team_id = user.get("teamId")
    if not attacker_team_id:
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode.FAILED_PRECONDITION,
            "Пользователь не привязан к команде.",
        )

    flag = (req.data or {}).get("flag", "").strip()
    if not flag:
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode.INVALID_ARGUMENT, "Пустой флаг."
        )

    h = checker.flag_hash(flag)
    now = int(time.time())

    matches = list(
        db.collection("flags")
        .where(filter=firestore.FieldFilter("valueHash", "==", h))
        .limit(1)
        .stream()
    )

    def _record(accepted: bool, points: int, reason: str) -> dict:
        db.collection("submissions").add(
            {
                "attackerTeamId": attacker_team_id,
                "flagHash": h,
                "accepted": accepted,
                "points": points,
                "reason": reason,
                "ts": now,
            }
        )
        return {"accepted": accepted, "points": points, "reason": reason}

    if not matches:
        return _record(False, 0, "Неизвестный или неверный флаг.")

    flag_snap = matches[0]
    fdoc = flag_snap.to_dict()

    if fdoc["victimTeamId"] == attacker_team_id:
        return _record(False, 0, "Нельзя сдавать собственный флаг.")
    if now > int(fdoc.get("expiresAt", 0)):
        return _record(False, 0, "Флаг просрочен.")

    # Один и тот же флаг команда не может сдать дважды — проверяем по паре
    # (флаг, атакующий). Разные команды могут украсть один флаг независимо.
    dup = list(
        db.collection("submissions")
        .where(filter=firestore.FieldFilter("flagHash", "==", h))
        .where(filter=firestore.FieldFilter("attackerTeamId", "==", attacker_team_id))
        .where(filter=firestore.FieldFilter("accepted", "==", True))
        .limit(1)
        .stream()
    )
    if dup:
        return _record(False, 0, "Этот флаг уже сдан вашей командой.")

    # Валидный флаг: начисляем атаку и помечаем чужой флаг украденным (снимет
    # у жертвы очки защиты за этот раунд).
    scoring.award_attack(db, attacker_team_id)
    flag_snap.reference.update({"stolen": True})
    return _record(True, scoring.ATTACK_POINTS, "Флаг принят.")


# --------------------------------------------------------------------------- #
# Игрок: сохранить код своего сервиса и запросить деплой                       #
# --------------------------------------------------------------------------- #
@https_fn.on_call(cors=_CORS)
def save_and_deploy(req: https_fn.CallableRequest) -> dict:
    """Сохраняет код сервиса команды в Firestore и увеличивает счётчик деплоя.

    Реальный редеплой контейнера делает агент на VPS (scripts/deploy_agent.py),
    который слушает поле deploySeq и по его изменению пересобирает/перезапускает
    сервис команды, а затем пишет обратно результат (deployVulns, deploySla, log).
    """
    uid = _require_auth(req)
    db = _db()
    user = _user_doc(db, uid)
    team_id = user.get("teamId")
    if not team_id:
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode.FAILED_PRECONDITION,
            "Пользователь не привязан к команде.",
        )
    code = (req.data or {}).get("code", "")
    if not code.strip():
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode.INVALID_ARGUMENT, "Пустой код."
        )
    if len(code) > 200_000:
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode.INVALID_ARGUMENT, "Код слишком большой."
        )
    db.collection("teams").document(team_id).update(
        {
            "code": code,
            "deploySeq": firestore.Increment(1),
            "deployStatus": "pending",
            "deployRequestedAt": int(time.time()),
        }
    )
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Админ: управление командами, игроками и соревнованием                        #
# --------------------------------------------------------------------------- #
@https_fn.on_call(cors=_CORS)
def admin_create_team(req: https_fn.CallableRequest) -> dict:
    """Создаёт команду с нулевым счётом."""
    uid = _require_auth(req); db = _db(); _require_admin(db, uid)
    data = req.data or {}
    team_id = (data.get("teamId") or "").strip()
    name = (data.get("name") or team_id).strip()
    if not team_id:
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode.INVALID_ARGUMENT, "Не указан teamId.")
    db.collection("teams").document(team_id).set(
        {"name": name, "members": [], "serviceUrl": data.get("serviceUrl", ""),
         "attackPts": 0, "defensePts": 0, "slaPts": 0,
         "deploySeq": 0, "deployStatus": "idle"},
        merge=True,
    )
    return {"ok": True, "teamId": team_id}


@https_fn.on_call(cors=_CORS)
def admin_list_players(req: https_fn.CallableRequest) -> dict:
    """Список пользователей с их командами и ролями — для распределения."""
    uid = _require_auth(req); db = _db(); _require_admin(db, uid)
    players = []
    for snap in db.collection("users").stream():
        u = snap.to_dict()
        players.append({
            "uid": snap.id, "displayName": u.get("displayName"),
            "role": u.get("role"), "teamId": u.get("teamId"),
        })
    return {"players": players}


@https_fn.on_call(cors=_CORS)
def admin_assign_player(req: https_fn.CallableRequest) -> dict:
    """Привязывает игрока (по email или uid) к команде."""
    uid = _require_auth(req); db = _db(); _require_admin(db, uid)
    data = req.data or {}
    team_id = (data.get("teamId") or "").strip()
    email = (data.get("email") or "").strip()
    target_uid = (data.get("uid") or "").strip()
    if not team_id:
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode.INVALID_ARGUMENT, "Не указан teamId.")
    if email and not target_uid:
        try:
            target_uid = auth.get_user_by_email(email).uid
        except Exception:
            raise https_fn.HttpsError(
                https_fn.FunctionsErrorCode.NOT_FOUND,
                f"Пользователь {email} не найден (сначала пусть зарегистрируется).")
    if not target_uid:
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode.INVALID_ARGUMENT, "Нужен email или uid.")
    db.collection("users").document(target_uid).set({"teamId": team_id}, merge=True)
    db.collection("teams").document(team_id).update(
        {"members": firestore.ArrayUnion([target_uid])})
    return {"ok": True, "uid": target_uid, "teamId": team_id}


@https_fn.on_call(cors=_CORS)
def admin_set_status(req: https_fn.CallableRequest) -> dict:
    """Запускает или останавливает соревнование (status: running/stopped)."""
    uid = _require_auth(req); db = _db(); _require_admin(db, uid)
    data = req.data or {}
    comp_id = data.get("competitionId")
    status = data.get("status")
    if not comp_id or status not in ("running", "stopped"):
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            "Нужны competitionId и status=running|stopped.")
    db.collection("competitions").document(comp_id).set(
        {"status": status}, merge=True)
    return {"ok": True, "competitionId": comp_id, "status": status}


# --------------------------------------------------------------------------- #
# Админ: старт нового тика раунда вручную                                      #
# --------------------------------------------------------------------------- #
@https_fn.on_call(cors=_CORS)
def admin_start_round(req: https_fn.CallableRequest) -> dict:
    uid = _require_auth(req)
    db = _db()
    _require_admin(db, uid)

    data = req.data or {}
    comp_id = data.get("competitionId")
    if not comp_id:
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            "Не указан competitionId.",
        )
    comp = db.collection("competitions").document(comp_id).get().to_dict() or {}
    challenge_ids = comp.get("challengeIds") or ["01-securenotes"]
    return checker.run_round(db, comp_id, challenge_ids[0])


# --------------------------------------------------------------------------- #
# Запланированный чекер: тик раунда для всех активных соревнований             #
# --------------------------------------------------------------------------- #
@scheduler_fn.on_schedule(schedule="every 5 minutes")
def scheduled_round(event: scheduler_fn.ScheduledEvent) -> None:
    db = _db()
    active = (
        db.collection("competitions")
        .where(filter=firestore.FieldFilter("status", "==", "running"))
        .stream()
    )
    for snap in active:
        comp = snap.to_dict()
        challenge_ids = comp.get("challengeIds") or ["01-securenotes"]
        checker.run_round(db, snap.id, challenge_ids[0])

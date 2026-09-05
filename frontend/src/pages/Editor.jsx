// «Мой код» — встроенный редактор сервиса команды. Игрок правит app.py прямо
// в браузере и жмёт «Сохранить и задеплоить»: код уходит в Firestore через
// callable save_and_deploy, агент на VPS перезапускает контейнер и прогоняет
// чекер, а результат (уязвимости/SLA/лог) прилетает обратно в этот экран.
import { useEffect, useState } from "react";
import { doc, onSnapshot } from "firebase/firestore";
import { httpsCallable } from "firebase/functions";
import CodeMirror from "@uiw/react-codemirror";
import { python } from "@codemirror/lang-python";
import { db, functions } from "../firebase.js";
import { useAuth } from "../auth.jsx";

export default function Editor() {
  const { profile } = useAuth();
  const teamId = profile?.teamId;
  const [code, setCode] = useState("");
  const [team, setTeam] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!teamId) return;
    return onSnapshot(doc(db, "teams", teamId), (s) => {
      const data = s.exists() ? s.data() : null;
      setTeam(data);
      // Код подгружаем один раз, чтобы не затирать правки игрока обновлениями статуса.
      if (data && !loaded) {
        setCode(data.code || "# Код сервиса ещё не инициализирован.\n");
        setLoaded(true);
      }
    });
  }, [teamId, loaded]);

  async function deploy() {
    setBusy(true); setMsg(null);
    try {
      const call = httpsCallable(functions, "save_and_deploy");
      await call({ code });
      setMsg({ ok: true, text: "Отправлено на деплой. Ждём агент…" });
    } catch (err) {
      setMsg({ ok: false, text: err.message });
    } finally {
      setBusy(false);
    }
  }

  if (!teamId) {
    return <div className="container"><div className="card">Вы не привязаны к команде.</div></div>;
  }

  const status = team?.deployStatus || "idle";
  const statusLabel = {
    idle: "не деплоился", pending: "в очереди…", deploying: "деплой идёт…",
    ok: "успешно", error: "ошибка",
  }[status] || status;

  return (
    <div className="container">
      <div className="card">
        <h1>Мой код — SecureNotes</h1>
        <p className="muted">
          Правь код своего сервиса и жми «Сохранить и задеплоить». Цель обороны — закрыть
          уязвимости (стремиться к 0/4), не сломав сервис (SLA должен остаться OK).
        </p>
        <div style={{ border: "1px solid var(--border)", borderRadius: 8, overflow: "hidden" }}>
          <CodeMirror
            value={code}
            height="440px"
            theme="dark"
            extensions={[python()]}
            onChange={(v) => setCode(v)}
          />
        </div>
        <div style={{ marginTop: 12, display: "flex", gap: 12, alignItems: "center" }}>
          <button className="btn" disabled={busy} onClick={deploy}>
            Сохранить и задеплоить
          </button>
          <span className="muted">Статус: <strong>{statusLabel}</strong></span>
          {team?.lastDeployAt && (
            <span className="muted">
              · {new Date(team.lastDeployAt * 1000).toLocaleTimeString()}
            </span>
          )}
        </div>
        {msg && <div className={`msg ${msg.ok ? "ok" : "bad"}`}>{msg.text}</div>}
      </div>

      <div className="card">
        <h2>Результат последнего деплоя</h2>
        <p>
          Уязвимости:{" "}
          <span className={`badge ${team?.deployVulns === 0 ? "ok" : "bad"}`}>
            {team?.deployVulns ?? "—"}/4
          </span>{" "}
          · SLA:{" "}
          <span className={`badge ${team?.deploySla ? "ok" : "bad"}`}>
            {team?.deploySla === undefined ? "—" : team?.deploySla ? "OK" : "FAIL"}
          </span>
        </p>
        {team?.deployLog && (
          <pre style={{ maxHeight: 220, overflow: "auto" }}><code>{team.deployLog}</code></pre>
        )}
      </div>
    </div>
  );
}

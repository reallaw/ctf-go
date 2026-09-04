// Регистрация URL развёрнутого сервиса команды (вызов callable register_service).
import { useEffect, useState } from "react";
import { doc, onSnapshot } from "firebase/firestore";
import { httpsCallable } from "firebase/functions";
import { db, functions } from "../firebase.js";
import { useAuth } from "../auth.jsx";

export default function TeamService() {
  const { profile } = useAuth();
  const teamId = profile?.teamId;
  const [url, setUrl] = useState("");
  const [current, setCurrent] = useState(null);
  const [msg, setMsg] = useState(null);

  useEffect(() => {
    if (!teamId) return;
    return onSnapshot(doc(db, "teams", teamId), (s) =>
      setCurrent(s.exists() ? s.data().serviceUrl : null)
    );
  }, [teamId]);

  async function save(e) {
    e.preventDefault();
    setMsg(null);
    try {
      const call = httpsCallable(functions, "register_service");
      await call({ serviceUrl: url.trim() });
      setMsg({ ok: true, text: "URL сохранён." });
      setUrl("");
    } catch (err) {
      setMsg({ ok: false, text: err.message });
    }
  }

  if (!teamId) {
    return <div className="container"><div className="card">Вы не привязаны к команде.</div></div>;
  }

  return (
    <div className="container">
      <div className="card">
        <h1>Мой сервис</h1>
        <p className="muted">
          Укажите публичный URL вашей копии сервиса. По нему ходит чекер (раздаёт флаги
          и проверяет SLA), а соперники атакуют его.
        </p>
        <p>Текущий URL: <code>{current || "не задан"}</code></p>
        <form onSubmit={save}>
          <label>URL сервиса</label>
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://team1.example.com  или  http://localhost:8000"
          />
          <button className="btn" disabled={!url.trim()}>Сохранить</button>
          {msg && <div className={`msg ${msg.ok ? "ok" : "bad"}`}>{msg.text}</div>}
        </form>
      </div>
    </div>
  );
}

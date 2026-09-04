// Админка: список соревнований и ручной запуск тика раунда (callable admin_start_round).
import { useEffect, useState } from "react";
import { collection, onSnapshot } from "firebase/firestore";
import { httpsCallable } from "firebase/functions";
import { db, functions } from "../firebase.js";

export default function Admin() {
  const [comps, setComps] = useState([]);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    return onSnapshot(collection(db, "competitions"), (snap) =>
      setComps(snap.docs.map((d) => ({ id: d.id, ...d.data() })))
    );
  }, []);

  async function startRound(compId) {
    setBusy(true); setMsg(null);
    try {
      const call = httpsCallable(functions, "admin_start_round");
      const res = await call({ competitionId: compId });
      const s = res.data;
      setMsg({ ok: true, text: `Раунд ${s.round}: посажено флагов ${s.planted}, SLA ok ${s.slaOk}` });
    } catch (err) {
      setMsg({ ok: false, text: err.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="container">
      <div className="card">
        <h1>Администрирование</h1>
        <p className="muted">
          Запуск тика раунда: генерируются флаги, сажаются в сервисы команд, проверяется SLA.
          В проде это делает и запланированная функция каждые 5 минут.
        </p>
        {msg && <div className={`msg ${msg.ok ? "ok" : "bad"}`}>{msg.text}</div>}
      </div>
      <div className="card">
        <h2>Соревнования</h2>
        <table>
          <thead><tr><th>ID</th><th>Название</th><th>Статус</th><th>Раунд</th><th></th></tr></thead>
          <tbody>
            {comps.map((c) => (
              <tr key={c.id}>
                <td><code>{c.id}</code></td>
                <td>{c.name}</td>
                <td><span className={`badge ${c.status === "running" ? "ok" : "bad"}`}>{c.status}</span></td>
                <td>{c.currentRound || 0}</td>
                <td>
                  <button className="btn" disabled={busy} onClick={() => startRound(c.id)}>
                    Запустить раунд
                  </button>
                </td>
              </tr>
            ))}
            {comps.length === 0 && <tr><td colSpan={5} className="muted">Нет соревнований (запустите seed).</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

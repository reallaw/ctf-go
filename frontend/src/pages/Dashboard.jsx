// Кабинет игрока: статус команды, форма сдачи флага, последние сабмиты.
import { useEffect, useState } from "react";
import { collection, doc, onSnapshot, orderBy, query, where } from "firebase/firestore";
import { db } from "../firebase.js";
import { useAuth } from "../auth.jsx";
import FlagSubmitForm from "../components/FlagSubmitForm.jsx";
import RoundTimer from "../components/RoundTimer.jsx";

export default function Dashboard() {
  const { profile } = useAuth();
  const [team, setTeam] = useState(null);
  const [subs, setSubs] = useState([]);
  const teamId = profile?.teamId;

  useEffect(() => {
    if (!teamId) return;
    const unsubTeam = onSnapshot(doc(db, "teams", teamId), (s) =>
      setTeam(s.exists() ? s.data() : null)
    );
    const q = query(
      collection(db, "submissions"),
      where("attackerTeamId", "==", teamId),
      orderBy("ts", "desc")
    );
    const unsubSubs = onSnapshot(q, (snap) =>
      setSubs(snap.docs.slice(0, 10).map((d) => d.data()))
    );
    return () => { unsubTeam(); unsubSubs(); };
  }, [teamId]);

  if (!teamId) {
    return (
      <div className="container">
        <div className="card">
          <h2>Вы ещё не в команде</h2>
          <p className="muted">
            Попросите организатора привязать ваш аккаунт к команде (seed-скрипт или админка).
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="container">
      <div className="card">
        <h1>{team?.name || teamId}</h1>
        <p className="muted"><RoundTimer /></p>
        <p>
          Атака: <strong>{team?.attackPts || 0}</strong> ·
          {" "}Защита: <strong>{team?.defensePts || 0}</strong> ·
          {" "}SLA: <strong>{team?.slaPts || 0}</strong>
        </p>
      </div>

      <div className="card">
        <h2>Сдать флаг</h2>
        <FlagSubmitForm />
      </div>

      <div className="card">
        <h2>Последние попытки</h2>
        <table>
          <thead><tr><th>Время</th><th>Результат</th><th>Очки</th><th>Комментарий</th></tr></thead>
          <tbody>
            {subs.map((s, i) => (
              <tr key={i}>
                <td>{new Date(s.ts * 1000).toLocaleTimeString()}</td>
                <td>
                  <span className={`badge ${s.accepted ? "ok" : "bad"}`}>
                    {s.accepted ? "принят" : "отклонён"}
                  </span>
                </td>
                <td>{s.points}</td>
                <td className="muted">{s.reason}</td>
              </tr>
            ))}
            {subs.length === 0 && <tr><td colSpan={4} className="muted">Пока нет попыток.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// Табло: realtime-подписка на коллекцию teams, сортировка по суммарному счёту.
import { useEffect, useState } from "react";
import { collection, onSnapshot } from "firebase/firestore";
import { db } from "../firebase.js";

export default function ScoreTable() {
  const [teams, setTeams] = useState([]);

  useEffect(() => {
    return onSnapshot(collection(db, "teams"), (snap) => {
      const rows = snap.docs.map((d) => {
        const t = d.data();
        const attack = t.attackPts || 0;
        const defense = t.defensePts || 0;
        const sla = t.slaPts || 0;
        return { id: d.id, name: t.name || d.id, attack, defense, sla, total: attack + defense + sla };
      });
      rows.sort((a, b) => b.total - a.total);
      setTeams(rows);
    });
  }, []);

  return (
    <table>
      <thead>
        <tr>
          <th>#</th><th>Команда</th><th>Атака</th><th>Защита</th><th>SLA</th><th>Итого</th>
        </tr>
      </thead>
      <tbody>
        {teams.map((t, i) => (
          <tr key={t.id}>
            <td>{i + 1}</td><td>{t.name}</td><td>{t.attack}</td>
            <td>{t.defense}</td><td>{t.sla}</td><td><strong>{t.total}</strong></td>
          </tr>
        ))}
        {teams.length === 0 && (
          <tr><td colSpan={6} className="muted">Пока нет команд.</td></tr>
        )}
      </tbody>
    </table>
  );
}

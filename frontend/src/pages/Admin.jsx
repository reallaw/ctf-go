// Админка: управление соревнованием (старт/стоп/раунд), создание команд и
// распределение игроков по командам — всё через callable-функции.
import { useEffect, useState } from "react";
import { collection, onSnapshot } from "firebase/firestore";
import { httpsCallable } from "firebase/functions";
import { db, functions } from "../firebase.js";

function useCollection(name) {
  const [rows, setRows] = useState([]);
  useEffect(() => onSnapshot(collection(db, name), (s) =>
    setRows(s.docs.map((d) => ({ id: d.id, ...d.data() })))), [name]);
  return rows;
}

export default function Admin() {
  const comps = useCollection("competitions");
  const teams = useCollection("teams");
  const [players, setPlayers] = useState([]);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [newTeam, setNewTeam] = useState({ id: "", name: "" });

  async function callFn(name, data, okText) {
    setBusy(true); setMsg(null);
    try {
      const res = await httpsCallable(functions, name)(data);
      setMsg({ ok: true, text: okText ? okText(res.data) : "Готово" });
      return res.data;
    } catch (err) {
      setMsg({ ok: false, text: err.message });
    } finally {
      setBusy(false);
    }
  }

  async function loadPlayers() {
    const d = await callFn("admin_list_players", {}, () => "Список игроков обновлён");
    if (d?.players) setPlayers(d.players);
  }
  useEffect(() => { loadPlayers(); /* eslint-disable-next-line */ }, []);

  const teamName = (id) => teams.find((t) => t.id === id)?.name || id || "—";

  return (
    <div className="container">
      <div className="card">
        <h1>Администрирование</h1>
        {msg && <div className={`msg ${msg.ok ? "ok" : "bad"}`}>{msg.text}</div>}
      </div>

      {/* Соревнования: старт/стоп + запуск раунда */}
      <div className="card">
        <h2>Соревнования</h2>
        <table>
          <thead><tr><th>ID</th><th>Название</th><th>Статус</th><th>Раунд</th><th>Действия</th></tr></thead>
          <tbody>
            {comps.map((c) => (
              <tr key={c.id}>
                <td><code>{c.id}</code></td>
                <td>{c.name}</td>
                <td><span className={`badge ${c.status === "running" ? "ok" : "bad"}`}>{c.status}</span></td>
                <td>{c.currentRound || 0}</td>
                <td style={{ display: "flex", gap: 8 }}>
                  {c.status === "running" ? (
                    <button className="btn ghost" disabled={busy}
                      onClick={() => callFn("admin_set_status", { competitionId: c.id, status: "stopped" }, () => "Остановлено")}>
                      Стоп
                    </button>
                  ) : (
                    <button className="btn" disabled={busy}
                      onClick={() => callFn("admin_set_status", { competitionId: c.id, status: "running" }, () => "Запущено")}>
                      Старт игры
                    </button>
                  )}
                  <button className="btn" disabled={busy}
                    onClick={() => callFn("admin_start_round", { competitionId: c.id },
                      (d) => `Раунд ${d.round}: флагов ${d.planted}, SLA ok ${d.slaOk}`)}>
                    Запустить раунд
                  </button>
                </td>
              </tr>
            ))}
            {comps.length === 0 && <tr><td colSpan={5} className="muted">Нет соревнований (запустите seed).</td></tr>}
          </tbody>
        </table>
      </div>

      {/* Команды: создание */}
      <div className="card">
        <h2>Команды</h2>
        <div style={{ display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap" }}>
          <div>
            <label>ID команды</label>
            <input value={newTeam.id} placeholder="team-gamma"
              onChange={(e) => setNewTeam({ ...newTeam, id: e.target.value })} />
          </div>
          <div>
            <label>Название</label>
            <input value={newTeam.name} placeholder="Gamma"
              onChange={(e) => setNewTeam({ ...newTeam, name: e.target.value })} />
          </div>
          <button className="btn" disabled={busy || !newTeam.id.trim()}
            onClick={async () => {
              await callFn("admin_create_team", { teamId: newTeam.id.trim(), name: newTeam.name.trim() },
                () => "Команда создана");
              setNewTeam({ id: "", name: "" });
            }}>Создать команду</button>
        </div>
        <table style={{ marginTop: 12 }}>
          <thead><tr><th>Команда</th><th>Игроков</th><th>Сервис</th></tr></thead>
          <tbody>
            {teams.map((t) => (
              <tr key={t.id}>
                <td>{t.name} <span className="muted">({t.id})</span></td>
                <td>{(t.members || []).length}</td>
                <td className="muted">{t.serviceUrl || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Игроки: распределение по командам */}
      <div className="card">
        <h2>Игроки
          <button className="btn ghost" style={{ marginLeft: 12 }} disabled={busy}
            onClick={loadPlayers}>Обновить</button>
        </h2>
        <table>
          <thead><tr><th>Имя</th><th>Роль</th><th>Команда</th><th>Назначить в</th></tr></thead>
          <tbody>
            {players.map((p) => (
              <tr key={p.uid}>
                <td>{p.displayName || p.uid}</td>
                <td>{p.role}</td>
                <td>{teamName(p.teamId)}</td>
                <td>
                  <select disabled={busy} defaultValue=""
                    onChange={(e) => e.target.value &&
                      callFn("admin_assign_player", { uid: p.uid, teamId: e.target.value },
                        () => "Игрок назначен").then(loadPlayers)}>
                    <option value="">— выбрать —</option>
                    {teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                  </select>
                </td>
              </tr>
            ))}
            {players.length === 0 && <tr><td colSpan={4} className="muted">Нажмите «Обновить».</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

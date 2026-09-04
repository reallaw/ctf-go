// Форма сдачи украденного флага. Вызывает callable-функцию submit_flag.
import { useState } from "react";
import { httpsCallable } from "firebase/functions";
import { functions } from "../firebase.js";

export default function FlagSubmitForm() {
  const [flag, setFlag] = useState("");
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setMsg(null);
    try {
      const call = httpsCallable(functions, "submit_flag");
      const res = await call({ flag: flag.trim() });
      const { accepted, points, reason } = res.data;
      setMsg({ ok: accepted, text: accepted ? `Принято! +${points} очков` : reason });
      if (accepted) setFlag("");
    } catch (err) {
      setMsg({ ok: false, text: err.message || "Ошибка запроса" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <label>Флаг соперника</label>
      <input
        value={flag}
        onChange={(e) => setFlag(e.target.value)}
        placeholder="LIVECTF{...}"
      />
      <button className="btn" disabled={busy || !flag.trim()}>Сдать флаг</button>
      {msg && <div className={`msg ${msg.ok ? "ok" : "bad"}`}>{msg.text}</div>}
    </form>
  );
}

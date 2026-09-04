// Вход / регистрация. При регистрации создаём профиль users/{uid} с ролью player.
// Привязка к команде выполняется организатором (seed/админка).
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
} from "firebase/auth";
import { doc, setDoc } from "firebase/firestore";
import { auth, db } from "../firebase.js";

export default function Login() {
  const nav = useNavigate();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [err, setErr] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setErr(null);
    try {
      if (mode === "register") {
        const cred = await createUserWithEmailAndPassword(auth, email, password);
        await setDoc(doc(db, "users", cred.user.uid), {
          displayName: name || email,
          role: "player",
          teamId: null,
        });
      } else {
        await signInWithEmailAndPassword(auth, email, password);
      }
      nav("/dashboard");
    } catch (e2) {
      setErr(e2.message);
    }
  }

  return (
    <div className="container">
      <div className="card" style={{ maxWidth: 420, margin: "0 auto" }}>
        <h2>{mode === "login" ? "Вход" : "Регистрация"}</h2>
        <form onSubmit={submit}>
          {mode === "register" && (
            <>
              <label>Отображаемое имя</label>
              <input value={name} onChange={(e) => setName(e.target.value)} />
            </>
          )}
          <label>Email</label>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <label>Пароль</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <button className="btn" style={{ width: "100%" }}>
            {mode === "login" ? "Войти" : "Создать аккаунт"}
          </button>
          {err && <div className="msg bad">{err}</div>}
        </form>
        <p className="muted">
          {mode === "login" ? "Нет аккаунта?" : "Уже есть аккаунт?"}{" "}
          <a href="#" onClick={(e) => { e.preventDefault(); setMode(mode === "login" ? "register" : "login"); }}>
            {mode === "login" ? "Зарегистрироваться" : "Войти"}
          </a>
        </p>
      </div>
    </div>
  );
}

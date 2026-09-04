import { Link, Navigate, Route, Routes } from "react-router-dom";
import { signOut } from "firebase/auth";
import { auth } from "./firebase.js";
import { AuthProvider, useAuth } from "./auth.jsx";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Scoreboard from "./pages/Scoreboard.jsx";
import ChallengeView from "./pages/ChallengeView.jsx";
import TeamService from "./pages/TeamService.jsx";
import Admin from "./pages/Admin.jsx";

function Nav() {
  const { user, profile } = useAuth();
  return (
    <div className="nav">
      <strong>live-ctf</strong>
      <Link to="/">Табло</Link>
      {user && <Link to="/dashboard">Кабинет</Link>}
      {user && <Link to="/challenge">Задание</Link>}
      {user && <Link to="/service">Мой сервис</Link>}
      {profile?.role === "admin" && <Link to="/admin">Админ</Link>}
      <span className="spacer" />
      {user ? (
        <>
          <span className="muted">{profile?.displayName || user.email}</span>
          <button className="btn ghost" onClick={() => signOut(auth)}>Выйти</button>
        </>
      ) : (
        <Link to="/login">Войти</Link>
      )}
    </div>
  );
}

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="container">Загрузка…</div>;
  return user ? children : <Navigate to="/login" replace />;
}

function AdminOnly({ children }) {
  const { profile, loading } = useAuth();
  if (loading) return <div className="container">Загрузка…</div>;
  return profile?.role === "admin" ? children : <Navigate to="/" replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <Nav />
      <Routes>
        <Route path="/" element={<Scoreboard />} />
        <Route path="/login" element={<Login />} />
        <Route path="/dashboard" element={<Protected><Dashboard /></Protected>} />
        <Route path="/challenge" element={<Protected><ChallengeView /></Protected>} />
        <Route path="/service" element={<Protected><TeamService /></Protected>} />
        <Route path="/admin" element={<AdminOnly><Admin /></AdminOnly>} />
      </Routes>
    </AuthProvider>
  );
}

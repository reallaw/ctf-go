// Показывает текущий раунд активного соревнования и обратный отсчёт до его конца.
import { useEffect, useState } from "react";
import { collection, onSnapshot, query, where } from "firebase/firestore";
import { db } from "../firebase.js";

export default function RoundTimer() {
  const [comp, setComp] = useState(null);
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const q = query(collection(db, "competitions"), where("status", "==", "running"));
    return onSnapshot(q, (snap) => {
      setComp(snap.docs.length ? { id: snap.docs[0].id, ...snap.docs[0].data() } : null);
    });
  }, []);

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  if (!comp) return <span className="muted">Нет активного соревнования</span>;
  return (
    <span>
      Раунд <strong>{comp.currentRound || 0}</strong> · {comp.name}
    </span>
  );
}

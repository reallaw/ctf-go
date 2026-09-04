import ScoreTable from "../components/ScoreTable.jsx";
import RoundTimer from "../components/RoundTimer.jsx";

export default function Scoreboard() {
  return (
    <div className="container">
      <div className="card">
        <h1>Табло</h1>
        <p className="muted"><RoundTimer /></p>
      </div>
      <div className="card">
        <ScoreTable />
      </div>
    </div>
  );
}

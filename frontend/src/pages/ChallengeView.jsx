// Брифинг первого задания для игроков.
export default function ChallengeView() {
  return (
    <div className="container">
      <div className="card">
        <h1>Задание 01 — SecureNotes</h1>
        <p className="badge ok">базовый уровень</p>
        <p>
          Мини-сервис заметок на Flask + SQLite. Каждый раунд game-master кладёт в сервис
          <strong> флаг</strong> формата <code>LIVECTF&#123;...&#125;</code> в приватную
          заметку бота <code>gamemaster</code>.
        </p>
        <h2>Что делать</h2>
        <ol>
          <li>Развернуть свою копию (Docker / локально) и указать её URL на странице «Мой сервис».</li>
          <li><strong>Defense:</strong> найти и закрыть уязвимости, не сломав API (иначе минус SLA).</li>
          <li><strong>Attack:</strong> достать флаг из сервиса соперника и сдать в кабинете.</li>
        </ol>
        <h2>API</h2>
        <pre><code>{`GET  /health
POST /register  {username, password}
POST /login     {username, password} -> {token}
POST /notes     {title, body}  (Bearer) -> {id}
GET  /notes/mine             (Bearer)
GET  /notes/<id>             (Bearer)
GET  /search?q=...           (Bearer)
GET  /debug`}</code></pre>
        <p className="muted">
          Классы уязвимостей для поиска: инъекции, контроль доступа, секреты/крипто,
          раскрытие информации. Само-проверка: <code>python checker.py exploit URL</code>.
        </p>
      </div>
    </div>
  );
}

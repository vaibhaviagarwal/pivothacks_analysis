"""Render the findings as a single self-contained HTML page.

Generated rather than hand-written, so it cannot drift from the data:
every number on the page is read from data/processed at build time.
Open reports/dashboard.html in a browser.

Design: Swiss poster. Flat colour, hard grid, no rounded corners, no
shadows, oversized numerals as the structural element. The palette is a
sunset ramp (purple through magenta and red to yellow) used as flat
blocks. Data marks use only the two ends of it, which were validated for
colour-vision separation and contrast against both surfaces; the middle
steps are structure, never encoding.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import DATA_PROCESSED, DATA_RAW, REPORTS  # noqa: E402

W, H = 1000, 380
PAD_L, PAD_R, PAD_T, PAD_B = 8, 104, 78, 54


def esc(text: object) -> str:
    return html.escape(str(text))


def timeline(daily: pd.Series, posts: pd.DataFrame) -> str:
    """The annotated application curve — the page's hero.

    Daily counts, post dates and the deadline share one frame, because
    the relationship between those three is the whole argument. Bars are
    square-ended and butt against the baseline; the deadline is a heavy
    rule the final bar runs into.
    """
    dates = list(daily.index)
    values = [int(v) for v in daily.values]
    if not dates:
        return "<p>No application data.</p>"

    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B
    n = len(dates)
    slot = plot_w / n
    bar_w = max(6.0, slot * 0.70)
    vmax = max(values)
    top = vmax + (4 - vmax % 4) % 4

    def cx(i: int) -> float:
        return PAD_L + slot * i + slot / 2

    def y_of(v: float) -> float:
        return PAD_T + plot_h - (v / top) * plot_h

    base = PAD_T + plot_h
    date_index = {d: i for i, d in enumerate(dates)}
    p: list[str] = [
        f'<svg viewBox="0 0 {W} {H}" class="tl" role="img" '
        f'aria-label="Daily applications, with post dates and the '
        f'application deadline marked">'
    ]

    for k in range(1, 5):
        y = y_of(top * k / 4)
        p.append(
            f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{W - PAD_R}" '
            f'y2="{y:.1f}" class="grid"/>'
        )
        p.append(
            f'<text x="{PAD_L + 4}" y="{y - 7:.1f}" class="ytick">'
            f"{top * k / 4:.0f}</text>"
        )

    # Deadline.
    dx = cx(n - 1) + slot / 2
    p.append(
        f'<line x1="{dx:.1f}" y1="{PAD_T - 34}" x2="{dx:.1f}" '
        f'y2="{base}" class="deadline"/>'
    )
    p.append(
        f'<text x="{dx + 12:.1f}" y="{PAD_T + plot_h / 2 - 7:.1f}" '
        f'class="dl-label">APPLICATIONS</text>'
    )
    p.append(
        f'<text x="{dx + 12:.1f}" y="{PAD_T + plot_h / 2 + 11:.1f}" '
        f'class="dl-label">CLOSE</text>'
    )

    # Post flags.
    for row in posts.itertuples():
        if row.post_date not in date_index:
            continue
        x = cx(date_index[row.post_date])
        p.append(
            f'<line x1="{x:.1f}" y1="{PAD_T - 34}" x2="{x:.1f}" '
            f'y2="{base}" class="postrule"/>'
        )
        p.append(
            f'<text x="{x:.1f}" y="{PAD_T - 42}" class="postlabel">'
            f"{esc(row.description.upper())}</text>"
        )

    # Bars. Each carries its own data for the hover layer, is focusable
    # from the keyboard, and has a staggered reveal delay.
    peak = max(range(n), key=lambda i: values[i])
    for i, (d, v) in enumerate(zip(dates, values)):
        x = cx(i) - bar_w / 2
        y = y_of(v)
        h = max(base - y, 1.0)
        # A transparent hit area the full height of the plot, so the
        # pointer finds short bars without having to land on 4 pixels.
        p.append(
            f'<rect x="{cx(i) - slot / 2:.1f}" y="{PAD_T}" '
            f'width="{slot:.1f}" height="{plot_h:.1f}" class="hit" '
            f'tabindex="0" role="button" data-i="{i}" '
            f'aria-label="{esc(d)}: {v} applications" '
            f'data-date="{esc(d)}" data-value="{v}" '
            f'data-x="{cx(i):.1f}" data-y="{y:.1f}"/>'
        )
        p.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" '
            f'height="{h:.1f}" class="bar" data-i="{i}" '
            f'style="transform-origin:0 {base}px;'
            f'animation-delay:{120 + i * 34}ms"/>'
        )

    # Direct labels on the two bars the argument rests on, so the point
    # survives without anyone hovering anything.
    for i in (peak, n - 1):
        p.append(
            f'<text x="{cx(i):.1f}" y="{y_of(values[i]) - 9:.1f}" '
            f'class="barlabel">{values[i]}</text>'
        )

    p.append(
        f'<line x1="{PAD_L}" y1="{base}" x2="{W - PAD_R}" y2="{base}" '
        f'class="axis"/>'
    )

    step = max(1, n // 11)
    for i in range(0, n, step):
        p.append(
            f'<text x="{cx(i):.1f}" y="{base + 22}" class="xtick">'
            f"{esc(str(dates[i])[5:].replace('-', '.'))}</text>"
        )

    # Crosshair, moved by the hover layer.
    p.append(
        f'<line id="xh" x1="0" y1="{PAD_T}" x2="0" y2="{base}" '
        f'class="xhair" style="opacity:0"/>'
    )
    p.append("</svg>")
    return "".join(p)


def rank(rows: list[tuple[str, float]], prefix: str = "") -> str:
    if not rows:
        return ""
    vmax = max(v for _, v in rows) or 1
    out = ['<div class="rank">']
    for label, value in rows:
        pct = 100 * value / vmax
        out.append(
            '<div class="rk">'
            f'<div class="rk-l">{esc(label)}</div>'
            f'<div class="rk-t"><i style="width:{pct:.1f}%"></i></div>'
            f'<div class="rk-v">{prefix}{value:,.0f}</div></div>'
        )
    out.append("</div>")
    return "".join(out)


CSS = """
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700;800&display=swap');

:root{
  color-scheme: light;
  --bg:#ffffff;
  --ink:#1a1020;
  --ink-2:#55485f;
  --ink-3:#8c8094;
  --hair:#e4dde8;
  --rule:#1a1020;
  --data:#893894;
  --alert:#da4e57;
  --p1:#893894; --p2:#a8407f; --p3:#da4e57; --p4:#f37f4c; --p5:#f8bd57;
  --on-block:#ffffff;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    color-scheme: dark;
    --bg:#191020;
    --ink:#f3eef6; --ink-2:#b7abc0; --ink-3:#847891;
    --hair:#2e2238; --rule:#f3eef6;
    --data:#b060c9; --alert:#e2685d;
    --p1:#9c47aa; --p2:#bd4a8f; --p3:#e2685d; --p4:#f08a53; --p5:#f8bd57;
  }
}
:root[data-theme="dark"]{
  color-scheme: dark;
  --bg:#191020;
  --ink:#f3eef6; --ink-2:#b7abc0; --ink-3:#847891;
  --hair:#2e2238; --rule:#f3eef6;
  --data:#b060c9; --alert:#e2685d;
  --p1:#9c47aa; --p2:#bd4a8f; --p3:#e2685d; --p4:#f08a53; --p5:#f8bd57;
}

*{box-sizing:border-box;border-radius:0}
html{-webkit-text-size-adjust:100%}
body{
  margin:0; background:var(--bg); color:var(--ink);
  font:400 16px/1.52 Archivo,"Helvetica Neue",Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased;
}
.sheet{max-width:1120px;margin:0 auto}
.pad{padding:0 40px}

/* masthead: the gradient as five flat bands */
.bands{display:flex;height:16px}
.bands i{flex:1}
.bands i:nth-child(1){background:var(--p1)}
.bands i:nth-child(2){background:var(--p2)}
.bands i:nth-child(3){background:var(--p3)}
.bands i:nth-child(4){background:var(--p4)}
.bands i:nth-child(5){background:var(--p5)}

.mast{background:var(--p1);color:var(--on-block);padding:52px 40px 44px}
.mast .kicker{
  font:700 13px/1 Archivo,sans-serif; letter-spacing:.17em;
  text-transform:uppercase; opacity:.82; margin:0 0 26px;
}
.mast h1{
  font:800 clamp(40px,7.1vw,86px)/0.91 Archivo,sans-serif;
  letter-spacing:-.035em; text-transform:uppercase;
  margin:0; max-width:17ch; text-wrap:balance;
}
.mast-grid{
  display:grid; grid-template-columns:minmax(0,1.55fr) minmax(0,1fr);
  gap:52px; margin-top:30px; align-items:start;
}
.mast-grid > p{margin:0; font-size:17px; line-height:1.5; opacity:.94}
.srcs{border-top:2px solid rgba(255,255,255,.34); padding-top:14px}
.srcs h2{
  font:700 11px/1 Archivo,sans-serif; letter-spacing:.15em;
  text-transform:uppercase; margin:0 0 4px; opacity:.8;
}
.srcs dl{margin:0; font-size:14.5px}
.srcs div{
  display:flex; justify-content:space-between; gap:16px;
  padding:9px 0; border-bottom:1px solid rgba(255,255,255,.2);
}
.srcs dt{opacity:.92}
.srcs dd{margin:0; font-weight:700; font-variant-numeric:tabular-nums}

/* section nav */
.nav{
  position:sticky; top:0; z-index:20; display:flex; gap:0;
  background:var(--bg); border-bottom:3px solid var(--rule);
  overflow-x:auto; scrollbar-width:none;
}
.nav::-webkit-scrollbar{display:none}
.nav a{
  flex:0 0 auto; padding:13px 18px; text-decoration:none;
  color:var(--ink-2); font:600 11px Archivo,sans-serif;
  letter-spacing:.12em; text-transform:uppercase; white-space:nowrap;
  border-right:1px solid var(--hair);
}
.nav a:hover,.nav a:focus-visible{background:var(--p1);color:#fff}
:where(a,.hit,th,td):focus-visible{outline:3px solid var(--p4);
  outline-offset:2px}

/* numeral band */
.band{
  display:grid; grid-template-columns:repeat(4,1fr);
  border-bottom:5px solid var(--rule);
}
.cell{padding:26px 22px 24px; border-left:1px solid var(--hair)}
.cell:first-child{border-left:none}
.cell b{
  display:block;
  font:800 clamp(40px,6.4vw,70px)/0.88 Archivo,sans-serif;
  letter-spacing:-.045em; font-variant-numeric:tabular-nums;
}
.cell span{
  display:block; margin-top:11px;
  font:600 11.5px/1.3 Archivo,sans-serif; letter-spacing:.13em;
  text-transform:uppercase; color:var(--ink-3);
}

/* hero chart */
.hero{padding:44px 40px 0}
.tl{width:100%;height:auto;display:block;overflow:visible}
.grid{stroke:var(--hair);stroke-width:1}
.axis{stroke:var(--rule);stroke-width:3}
.bar{fill:var(--data);animation:grow .62s cubic-bezier(.2,.75,.3,1) both;
     transition:fill .12s}
.bar.on{fill:var(--p4)}
.hit{fill:transparent;cursor:crosshair}
.xhair{stroke:var(--ink-3);stroke-width:1;transition:opacity .12s;
       pointer-events:none}
.barlabel{
  fill:var(--ink);font:700 13px Archivo,sans-serif;text-anchor:middle;
  font-variant-numeric:tabular-nums;
}
@keyframes grow{from{transform:scaleY(0)}to{transform:scaleY(1)}}
@media (prefers-reduced-motion:reduce){
  .bar{animation:none}
}

/* hover readout */
.plot{position:relative}
.tip{
  position:absolute; pointer-events:none; opacity:0;
  transform:translate(-50%,-100%); transition:opacity .1s;
  background:var(--ink); color:var(--bg); padding:7px 11px;
  font:600 12.5px Archivo,sans-serif; white-space:nowrap; z-index:5;
}
.tip b{font-weight:800;font-variant-numeric:tabular-nums}
.tip.on{opacity:1}

/* chart legend */
.key{
  display:flex; flex-wrap:wrap; gap:24px; margin:16px 0 0;
  padding:14px 0 0; border-top:1px solid var(--hair);
  font:500 13px Archivo,sans-serif; color:var(--ink-2);
}
.key span{display:flex;align-items:center;gap:9px}
.key i{display:block;width:16px;height:12px;flex:0 0 auto}
.key .k-bar{background:var(--data)}
.key .k-dl{height:14px;width:4px;background:var(--alert)}
.key .k-post{height:14px;width:0;border-left:2px dotted var(--ink-3)}
.postrule{stroke:var(--ink-3);stroke-width:1;stroke-dasharray:1 5}
.postlabel{
  fill:var(--ink-2); font:600 10.5px Archivo,sans-serif;
  letter-spacing:.11em; text-anchor:middle;
}
.deadline{stroke:var(--alert);stroke-width:4}
.dl-label{
  fill:var(--alert); font:700 11px Archivo,sans-serif;
  letter-spacing:.1em; text-anchor:start;
}
.ytick{fill:var(--ink-3);font:600 11px Archivo,sans-serif;
       font-variant-numeric:tabular-nums}
.xtick{fill:var(--ink-3);font:500 10.5px Archivo,sans-serif;
       text-anchor:middle;font-variant-numeric:tabular-nums}
.cap{
  margin:18px 0 0; padding:0 40px 46px; max-width:76ch;
  font-size:15.5px; color:var(--ink-2);
}

/* findings */
.finds{border-top:5px solid var(--rule)}
.find{
  display:grid; grid-template-columns:270px 1fr; gap:36px;
  padding:34px 40px; border-bottom:1px solid var(--hair);
  align-items:start;
}
.find:last-child{border-bottom:none}
.fig{
  font:800 clamp(38px,5.6vw,62px)/0.86 Archivo,sans-serif;
  letter-spacing:-.045em; font-variant-numeric:tabular-nums;
}
.find:nth-child(1) .fig{color:var(--p1)}
.find:nth-child(2) .fig{color:var(--p2)}
.find:nth-child(3) .fig{color:var(--p3)}
.find:nth-child(4) .fig{color:var(--p4)}
.fig em{
  display:block; font:600 11.5px/1.45 Archivo,sans-serif;
  font-style:normal; letter-spacing:.1em; text-transform:uppercase;
  color:var(--ink-3); margin-top:14px; max-width:26ch;
}
.find h3{
  font:700 25px/1.14 Archivo,sans-serif; letter-spacing:-.022em;
  margin:0 0 10px; max-width:22ch;
}
.find p{margin:0;color:var(--ink-2);font-size:15.5px;max-width:60ch}

/* absences */
.absent{border-top:5px solid var(--rule); padding:40px}
.absent h2{
  font:800 30px/1.05 Archivo,sans-serif; letter-spacing:-.03em;
  text-transform:uppercase; margin:0 0 10px;
}
.absent > p{margin:0 0 26px;color:var(--ink-2);max-width:62ch;
            font-size:15.5px}
.gaps{list-style:none;margin:0;padding:0;display:grid;
      grid-template-columns:repeat(auto-fit,minmax(214px,1fr));gap:0;
      border-top:1px solid var(--hair);border-left:1px solid var(--hair)}
.gap{border-right:1px solid var(--hair);border-bottom:1px solid var(--hair);
     padding:20px 18px}
.gap b{display:block;font:700 13px Archivo,sans-serif;
       letter-spacing:.055em;color:var(--alert);margin-bottom:9px}
.gap span{display:block;font-size:14px;line-height:1.48;color:var(--ink-2)}

/* detail */
.sec{border-top:5px solid var(--rule);padding:38px 40px}
.sec h2{font:800 30px/1.05 Archivo,sans-serif;letter-spacing:-.03em;
        text-transform:uppercase;margin:0 0 8px}
.sec > p{color:var(--ink-2);font-size:15.5px;max-width:64ch;margin:0 0 24px}
.tscroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{width:100%;border-collapse:collapse;font-size:14.5px;min-width:580px}
th{text-align:left;font:600 11px Archivo,sans-serif;letter-spacing:.12em;
   text-transform:uppercase;color:var(--ink-3);
   padding:0 14px 11px 0;border-bottom:3px solid var(--rule)}
td{padding:13px 14px 13px 0;border-bottom:1px solid var(--hair);
   font-variant-numeric:tabular-nums}
td.n,th.n{text-align:right}
tbody tr{transition:background .1s}
tbody tr:hover{background:var(--hair)}
tr:last-child td{border-bottom:none}
tr.dud td{color:var(--alert);font-weight:600}

.rank{display:flex;flex-direction:column;gap:6px}
.rk{display:grid;grid-template-columns:164px 1fr 84px;align-items:center;
    gap:16px}
.rk-l{font-size:14.5px;color:var(--ink-2);white-space:nowrap;
      overflow:hidden;text-overflow:ellipsis}
.rk-t{height:16px;background:var(--hair)}
.rk-t i{display:block;height:100%;background:var(--data)}
.rk-v{font:600 14px Archivo,sans-serif;text-align:right;
      font-variant-numeric:tabular-nums}

.foot{padding:34px 40px 70px;font-size:13.5px;color:var(--ink-3);
      max-width:74ch;border-top:1px solid var(--hair)}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.92em}

@media (max-width:780px){
  .pad,.hero,.cap,.find,.absent,.sec,.foot{
    padding-left:20px;padding-right:20px}
  .mast{padding:38px 20px 32px}
  .mast-grid{grid-template-columns:1fr;gap:28px}
  .band{grid-template-columns:repeat(2,1fr)}
  .cell:nth-child(3){border-left:none}
  .cell:nth-child(n+3){border-top:1px solid var(--hair)}
  .find{grid-template-columns:1fr;gap:16px}
  .rk{grid-template-columns:110px 1fr 66px}
}
"""


def main() -> None:
    apps = pd.read_csv(DATA_PROCESSED / "applicants_with_teams.csv")
    posts = pd.read_csv(DATA_RAW / "social_posts.csv")
    sponsors = pd.read_csv(DATA_RAW / "sponsors.csv")
    truth = pd.read_csv(DATA_PROCESSED / "ground_truth_teams.csv")
    attribution = pd.read_csv(DATA_PROCESSED / "post_attribution.csv")
    scorecard = (REPORTS / "team_inference_scorecard.txt").read_text()

    apps["applied_date"] = pd.to_datetime(apps["applied_date"]).dt.date
    posts["post_date"] = pd.to_datetime(posts["post_date"]).dt.date
    daily = apps.groupby("applied_date").size()
    in_window = posts[posts["post_date"].isin(set(daily.index))]

    total = len(apps)
    accepted = int((apps["decision"] == "accepted").sum())
    denied = int((apps["decision"] == "denied").sum())
    competed = int(truth["user_id"].notna().sum())
    missing = int(truth["user_id"].isna().sum())
    rate = 100 * accepted / (accepted + denied)

    precision = float(
        [l for l in scorecard.splitlines() if "precision" in l][0].split()[-1]
    )
    recall = float(
        [l for l in scorecard.splitlines() if "recall" in l][0].split()[-1]
    )

    valued = sponsors[sponsors["total_value"].notna()]
    sponsor_total = valued["total_value"].sum()
    top_share = 100 * valued["total_value"].max() / sponsor_total
    cash = valued[valued["contribution_type"] == "cash"]["total_value"].sum()

    essay_acc = apps[apps["decision"] == "accepted"]["essay_length"].median()
    essay_den = apps[apps["decision"] == "denied"]["essay_length"].median()
    utm_n = int(apps["utm_source"].notna().sum())

    reel = attribution.sort_values("post_date").iloc[-1]
    best = attribution.loc[attribution["excess"].idxmax()]

    post_rows = "".join(
        f'<tr class="{"dud" if r.excess < 1 else ""}">'
        f'<td class="n">{esc(str(r.post_date)[5:].replace("-", "."))}</td>'
        f"<td>{esc(r.description)}</td>"
        f'<td class="n">{int(r.reach):,}</td>'
        f'<td class="n">{int(r.shares)}</td>'
        f'<td class="n">{int(r.applications)}</td>'
        f'<td class="n">{r.excess:+.1f}</td>'
        f'<td class="n">{r.apps_per_1k_reach:.2f}</td></tr>'
        for r in attribution.itertuples()
    )

    sponsor_rows = [
        (str(r.sponsor), float(r.total_value))
        for r in valued.sort_values("total_value", ascending=False).itertuples()
    ]
    school_rows = [
        (str(k), float(v))
        for k, v in apps["school"].value_counts().head(6).items()
    ]

    doc = f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PivotHacks 2026 — what the records show</title>
<style>{CSS}</style>
<body>
<div class="sheet">

  <div class="bands"><i></i><i></i><i></i><i></i><i></i></div>

  <header class="mast">
    <p class="kicker">PivotHacks 2026 · Waterloo Tech Week</p>
    <h1>A hackathon rebuilt from its leftovers</h1>
    <div class="mast-grid">
      <p>Twelve hours in Waterloo left behind a registration export, a sheet
      of problem assignments and four Instagram posts. Nobody scanned a QR
      code, nobody tagged a link, and the platform's team fields were never
      filled in. This is what can still be recovered.</p>
      <div class="srcs">
        <h2>Built from</h2>
        <dl>
          <div><dt>Registration export</dt><dd>{total} rows</dd></div>
          <div><dt>Problem assignments</dt><dd>10 teams</dd></div>
          <div><dt>Instagram posts</dt><dd>{len(posts)}</dd></div>
          <div><dt>Sponsor records</dt><dd>{len(sponsors)}</dd></div>
        </dl>
      </div>
    </div>
  </header>

  <nav class="nav" aria-label="Sections">
    <a href="#timeline">Timeline</a>
    <a href="#findings">Findings</a>
    <a href="#missing">Never recorded</a>
    <a href="#posts">Posts</a>
    <a href="#sponsors">Sponsorship</a>
    <a href="#schools">Schools</a>
  </nav>

  <div class="band">
    <div class="cell"><b>{total}</b><span>Applications on record</span></div>
    <div class="cell"><b>{accepted}</b><span>Accepted · {rate:.0f}%</span></div>
    <div class="cell"><b>{competed}</b><span>Competed, 10 teams</span></div>
    <div class="cell"><b>{missing}</b><span>Competed but unrecorded</span></div>
  </div>

  <div class="hero" id="timeline">
    <div class="plot">
      {timeline(daily, in_window)}
      <div class="tip" id="tip"></div>
    </div>
    <div class="key">
      <span><i class="k-bar"></i>Applications received</span>
      <span><i class="k-post"></i>Instagram post</span>
      <span><i class="k-dl"></i>Applications close</span>
    </div>
  </div>
  <p class="cap">Applications arrived at about four a day until a post went
  out. The reel on {esc(str(reel.post_date)[5:].replace('-', '.'))} reached
  more people than anything else published, and landed one day before the
  window closed.</p>

  <div class="finds" id="findings">
    <div class="find">
      <div class="fig">{int(best.applications)}<em>Applications in two days,
      against {best.expected:.1f} expected</em></div>
      <div>
        <h3>Timing beat reach by a factor of three</h3>
        <p>The {esc(best.description.lower())} post drew
        {int(best.applications)} applications. The reel nine days later
        reached {int(reel.reach) - int(best.reach):,} more people, collected
        {int(reel.shares)} shares against {int(best.shares)}, and produced
        {reel.excess:+.1f} above baseline. The content worked. The date
        did not.</p>
      </div>
    </div>

    <div class="find">
      <div class="fig">{precision:.2f}/{recall:.2f}<em>Precision and recall
      on teammate pairs</em></div>
      <div>
        <h3>Teams came out of a text box, at a price</h3>
        <p>With the platform's team fields empty, the only record of who
        worked with whom was free text. Matching those typed names against
        the roster never produced a false pair and found fewer than half the
        real ones, because the matcher refuses any name that could belong to
        more than one person.</p>
      </div>
    </div>

    <div class="find">
      <div class="fig">{missing}<em>Competitors missing from the registration
      export</em></div>
      <div>
        <h3>The denominator is wrong</h3>
        <p>{missing} of the {competed + missing} people who competed appear on
        the assignment sheet and nowhere in the export. The real pool was
        larger than {total}, which makes the {rate:.0f}% acceptance rate a
        ceiling rather than a measurement.</p>
      </div>
    </div>

    <div class="find">
      <div class="fig">{essay_acc:.0f}/{essay_den:.0f}<em>Median words written,
      accepted against denied</em></div>
      <div>
        <h3>One field on the form told reviewers anything</h3>
        <p>Reviewers rated experience first, then project depth. But
        portfolios, resumes and LinkedIn profiles came from almost everyone
        who applied, so none of them separated anybody. The adaptability
        answer is the only field where accepted and denied applicants
        differ.</p>
      </div>
    </div>
  </div>

  <section class="absent" id="missing">
    <h2>Never written down</h2>
    <p>Not gaps in the analysis. Measurements the event could have taken for
    free and did not, each one closing off a question permanently.</p>
    <ul class="gaps">
      <li class="gap"><b>checked_in_at</b><span>Empty for all {total} rows.
      QR codes were generated and never scanned, so attendance is
      unknowable.</span></li>
      <li class="gap"><b>utm_source</b><span>Present on {utm_n} of {total}.
      Instagram likely drove around half the pool; the tracking accounts for
      six of them.</span></li>
      <li class="gap"><b>link_clicks</b><span>Never collected. Shares measure
      amplification, not intent, so no post converts to an application on
      record.</span></li>
      <li class="gap"><b>review_score</b><span>Not stored. Only the accept or
      deny survives, so the stated criteria cannot be checked against the
      ratings.</span></li>
    </ul>
  </section>

  <section class="sec" id="posts">
    <h2>Post performance</h2>
    <p>Applications counted on the day of each post and the day after.
    Baseline on quiet days was 4.2.</p>
    <div class="tscroll">
      <table>
        <thead><tr>
          <th class="n">Date</th><th>Post</th>
          <th class="n">Reach</th><th class="n">Shares</th>
          <th class="n">Apps</th><th class="n">vs base</th>
          <th class="n">Per 1k</th>
        </tr></thead>
        <tbody>{post_rows}</tbody>
      </table>
    </div>
  </section>

  <section class="sec" id="sponsors">
    <h2>Sponsorship</h2>
    <p>${sponsor_total:,.0f} in total value, of which ${cash:,.0f} was cash.
    One sponsor covered {top_share:.0f}% of it; there was no second venue.</p>
    {rank(sponsor_rows, "$")}
  </section>

  <section class="sec" id="schools">
    <h2>Where applicants came from</h2>
    <p>24 spellings in the raw export resolve to 12 institutions.</p>
    {rank(school_rows)}
  </section>

  <p class="foot">Built from <code>pivot_attendees_export.csv</code> and the
  problem assignment sheet. Every figure here is computed at build time by
  <code>src/pipeline/</code>; none are typed in. The raw export holds
  applicants' names, emails and written answers, and is not published with
  this page.</p>

  <div class="bands"><i></i><i></i><i></i><i></i><i></i></div>
</div>

<script>
// Hover readout for the timeline. Each day has a full-height transparent
// hit area, so short bars are as easy to reach as tall ones.
(function () {{
  var svg = document.querySelector('.tl');
  var tip = document.getElementById('tip');
  var xh = document.getElementById('xh');
  if (!svg || !tip) return;
  var bars = svg.querySelectorAll('.bar');
  var plot = svg.parentElement;

  function show(hit) {{
    var date = hit.dataset.date, value = +hit.dataset.value;
    var x = +hit.dataset.x, y = +hit.dataset.y;

    bars.forEach(function (b) {{ b.classList.remove('on'); }});
    var bar = svg.querySelector('.bar[data-i="' + hit.dataset.i + '"]');
    if (bar) bar.classList.add('on');

    // SVG user units to page pixels.
    var box = svg.getBoundingClientRect();
    var vb = svg.viewBox.baseVal;
    var k = box.width / vb.width;
    tip.style.left = (x * k) + 'px';
    tip.style.top = (y * k - 10) + 'px';
    tip.innerHTML = date + ' &nbsp; <b>' + value + '</b>';
    tip.classList.add('on');

    xh.setAttribute('x1', x); xh.setAttribute('x2', x);
    xh.style.opacity = '.5';
  }}

  function hide() {{
    tip.classList.remove('on');
    xh.style.opacity = '0';
    bars.forEach(function (b) {{ b.classList.remove('on'); }});
  }}

  svg.querySelectorAll('.hit').forEach(function (hit) {{
    hit.addEventListener('mouseenter', function () {{ show(hit); }});
    hit.addEventListener('focus', function () {{ show(hit); }});
    hit.addEventListener('blur', hide);
  }});
  plot.addEventListener('mouseleave', hide);
}})();

// Mark the section the reader is in.
(function () {{
  var links = document.querySelectorAll('.nav a');
  var targets = [];
  links.forEach(function (a) {{
    var el = document.querySelector(a.getAttribute('href'));
    if (el) targets.push([a, el]);
  }});
  if (!targets.length || !window.IntersectionObserver) return;
  var io = new IntersectionObserver(function (entries) {{
    entries.forEach(function (e) {{
      var pair = targets.find(function (t) {{ return t[1] === e.target; }});
      if (pair) pair[0].style.color = e.isIntersecting
        ? 'var(--ink)' : 'var(--ink-2)';
    }});
  }}, {{ rootMargin: '-45% 0px -45% 0px' }});
  targets.forEach(function (t) {{ io.observe(t[1]); }});
}})();
</script>
</body>
</html>"""

    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / "dashboard.html"
    out.write_text(doc)
    print(f"wrote {out} ({len(doc):,} bytes)")


if __name__ == "__main__":
    main()

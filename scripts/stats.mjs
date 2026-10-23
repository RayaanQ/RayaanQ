// Renders assets/stats-{dark,light}.svg from live GitHub data.
// Runs daily in .github/workflows/refresh.yml with the workflow's GITHUB_TOKEN. No dependencies.
// If the API call fails, existing cards are left untouched so the profile never shows broken data.
import { readFile, writeFile, access } from 'node:fs/promises';

const USER = process.env.GH_USER || 'RayaanQ';
const ASSETS = new URL('../assets/', import.meta.url);
const THEMES = {
  dark: { bg: '#0b0b0c', bg2: '#121214', fg: '#ecebe6', fg2: '#b9b8b1', muted: '#7d7c76', node: '236,235,230', accentText: '#d4ff3a',
    levels: ['#1a1a1d', '#2b3a10', '#4d6b12', '#86b81a', '#d4ff3a'] },
  light: { bg: '#f3f1ea', bg2: '#ebe8df', fg: '#111110', fg2: '#3b3a36', muted: '#74726b', node: '17,17,16', accentText: '#3f6a00',
    levels: ['#e2ded3', '#e4f5a8', '#c5f02c', '#8fbf12', '#3f6a00'] },
};
const LEVEL = { NONE: 0, FIRST_QUARTILE: 1, SECOND_QUARTILE: 2, THIRD_QUARTILE: 3, FOURTH_QUARTILE: 4 };
const SANS = "font-family:Grotesk,'Segoe UI',Helvetica,Arial,sans-serif";
const MONO = 'font-family:Mono,ui-monospace,SFMono-Regular,Menlo,Consolas,monospace';
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const fmt = (n) => n.toLocaleString('en-US');

const QUERY = `query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    contributionsCollection {
      contributionCalendar { totalContributions weeks { contributionDays { date contributionCount contributionLevel } } }
    }
    repositories(ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false, first: 100) {
      totalCount
      nodes { stargazerCount languages(first: 10, orderBy: { field: SIZE, direction: DESC }) { edges { size node { name color } } } }
    }
  }
}`;

async function fetchStats() {
  const token = process.env.GITHUB_TOKEN;
  if (!token) throw new Error('GITHUB_TOKEN is not set');
  const res = await fetch('https://api.github.com/graphql', {
    method: 'POST',
    headers: { Authorization: `bearer ${token}`, 'Content-Type': 'application/json', 'User-Agent': 'profile-stats' },
    body: JSON.stringify({ query: QUERY, variables: { login: USER } }),
  });
  const json = await res.json();
  if (!res.ok || json.errors) throw new Error(JSON.stringify(json.errors || json));
  const u = json.data.user;
  const cal = u.contributionsCollection.contributionCalendar;
  const days = cal.weeks.flatMap((w) => w.contributionDays);

  let longest = 0, run = 0;
  for (const d of days) { run = d.contributionCount > 0 ? run + 1 : 0; longest = Math.max(longest, run); }
  let current = 0;
  for (let i = days.length - 1; i >= 0; i--) {
    if (days[i].contributionCount > 0) current++;
    else if (i === days.length - 1) continue; // today may not have activity yet
    else break;
  }

  const langs = new Map();
  for (const r of u.repositories.nodes) {
    for (const e of r.languages.edges) {
      const cur = langs.get(e.node.name) || { size: 0, color: e.node.color || '#888' };
      cur.size += e.size;
      langs.set(e.node.name, cur);
    }
  }
  const totalSize = [...langs.values()].reduce((a, b) => a + b.size, 0) || 1;
  const top = [...langs.entries()].sort((a, b) => b[1].size - a[1].size).slice(0, 5)
    .map(([name, v]) => ({ name, color: v.color, pct: (v.size / totalSize) * 100 }));

  return {
    total: cal.totalContributions,
    repos: u.repositories.totalCount,
    stars: u.repositories.nodes.reduce((a, r) => a + r.stargazerCount, 0),
    followers: u.followers.totalCount,
    longest, current,
    weeks: cal.weeks.slice(-30).map((w) => w.contributionDays.map((d) => LEVEL[d.contributionLevel] ?? 0)),
    top,
  };
}

function render(theme, s, fonts) {
  const t = THEMES[theme];
  const W = 1200, H = 300;
  const b = [];
  b.push(`<rect x=".5" y=".5" width="${W - 1}" height="${H - 1}" rx="18" fill="${t.bg2}" stroke="rgba(${t.node},.14)"/>`);
  b.push(`<text x="32" y="46" font-size="13" fill="${t.accentText}" style="${MONO}" font-weight="500">GITHUB · LAST 12 MONTHS</text>`);

  const stats = [
    [fmt(s.total), 'contributions'], [`${s.current}d`, 'current streak'],
    [`${s.longest}d`, 'longest streak'], [fmt(s.repos), 'public repos'],
    [fmt(s.stars), 'stars earned'], [fmt(s.followers), 'followers'],
  ];
  stats.forEach(([v, label], i) => {
    const x = 32 + (i % 3) * 150, y = 120 + Math.floor(i / 3) * 104;
    b.push(`<g class="pop" style="animation-delay:${(i * 0.08).toFixed(2)}s">
      <text x="${x}" y="${y}" font-size="44" fill="${t.fg}" style="${SANS}" font-weight="600" letter-spacing="-2">${esc(v)}</text>
      <text x="${x}" y="${y + 26}" font-size="14" fill="${t.muted}" style="${MONO}" font-weight="500">${esc(label)}</text></g>`);
  });

  // heatmap
  const hx = 520, hy = 30, cell = 16, gap = 4;
  s.weeks.forEach((week, wi) => {
    week.forEach((lvl, di) => {
      const x = hx + wi * (cell + gap), y = hy + 30 + di * (cell + gap);
      b.push(`<rect class="cell" style="animation-delay:${(wi * 0.03).toFixed(2)}s" x="${x}" y="${y}" width="${cell}" height="${cell}" rx="4" fill="${t.levels[lvl]}"/>`);
    });
  });
  const legendX = hx + 30 * (cell + gap) - 4;
  b.push(`<text x="${legendX - 5 * 18 - 8}" y="46" font-size="12" fill="${t.muted}" style="${MONO}" text-anchor="end">less</text>`);
  t.levels.forEach((c, i) => b.push(`<rect x="${legendX - (5 - i) * 18}" y="35" width="14" height="14" rx="3" fill="${c}"/>`));
  b.push(`<text x="${legendX + 6}" y="46" font-size="12" fill="${t.muted}" style="${MONO}">more</text>`);

  // languages
  const ly = 222, lw = 30 * (cell + gap) - gap;
  let x = hx;
  b.push(`<clipPath id="bar"><rect x="${hx}" y="${ly}" width="${lw}" height="10" rx="5"/></clipPath><g clip-path="url(#bar)">`);
  const sum = s.top.reduce((a, l) => a + l.pct, 0) || 1;
  for (const l of s.top) {
    const w = (l.pct / sum) * lw;
    b.push(`<rect x="${x.toFixed(1)}" y="${ly}" width="${(w + 0.5).toFixed(1)}" height="10" fill="${l.color}"/>`);
    x += w;
  }
  b.push('</g>');
  let tx = hx;
  for (const l of s.top) {
    const label = `${l.name} ${l.pct.toFixed(1)}%`;
    if (tx + 16 + label.length * 7.6 > W - 32) break;
    b.push(`<circle cx="${tx + 5}" cy="${ly + 34}" r="5" fill="${l.color}"/>
      <text x="${tx + 16}" y="${ly + 39}" font-size="14" fill="${t.fg2}" style="${SANS}">${esc(label)}</text>`);
    tx += 16 + label.length * 7.6 + 22;
  }

  const css = `${fonts}
.cell{animation:cell .6s ease both}@keyframes cell{from{opacity:0}to{opacity:1}}
.pop{animation:pop .8s cubic-bezier(.22,1,.36,1) both}@keyframes pop{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}`;
  const desc = `${s.total} contributions in the last year, ${s.current}-day current streak, ${s.longest}-day longest streak, ` +
    `${s.repos} public repos, ${s.stars} stars. Top languages: ${s.top.map((l) => `${l.name} ${l.pct.toFixed(0)}%`).join(', ')}.`;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-labelledby="t d">` +
    `<title id="t">GitHub activity</title><desc id="d">${esc(desc)}</desc><style>${css}</style>${b.join('')}</svg>`;
}

const exists = (u) => access(u).then(() => true, () => false);

try {
  const stats = await fetchStats();
  const fonts = await readFile(new URL('fonts/stats-fonts.css', ASSETS), 'utf8').catch(() => '');
  for (const theme of Object.keys(THEMES)) await writeFile(new URL(`stats-${theme}.svg`, ASSETS), render(theme, stats, fonts));
  console.log(`Rendered stats: ${stats.total} contributions, ${stats.repos} repos, top ${stats.top.map((l) => l.name).join(', ')}`);
  if (process.argv.includes('--json')) console.log(JSON.stringify(stats));
} catch (err) {
  const have = await exists(new URL('stats-dark.svg', ASSETS));
  console.warn(`::warning::Could not refresh stats (${err.message}); ${have ? 'keeping existing cards' : 'no cards yet'}.`);
}

export { render };

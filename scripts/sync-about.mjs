// Applies the description, website and topics in .github/repo-about.json to each repo.
// Runs from .github/workflows/sync-repo-about.yml. Needs a token with repo "Administration: write"
// (the workflow's own GITHUB_TOKEN can't edit repo settings), stored as the REPO_ABOUT_TOKEN secret.
import { readFile } from 'node:fs/promises';

const token = process.env.REPO_ABOUT_TOKEN;
if (!token) {
  console.log('::warning::REPO_ABOUT_TOKEN secret is not set, so nothing was changed. See the comment at the top of scripts/sync-about.mjs for setup.');
  process.exit(0);
}

const { owner, repos } = JSON.parse(await readFile(new URL('../.github/repo-about.json', import.meta.url), 'utf8'));
const headers = {
  Authorization: `Bearer ${token}`,
  Accept: 'application/vnd.github+json',
  'Content-Type': 'application/json',
  'X-GitHub-Api-Version': '2022-11-28',
  'User-Agent': 'repo-about-sync',
};

let failed = 0;
for (const [repo, about] of Object.entries(repos)) {
  const base = `https://api.github.com/repos/${owner}/${repo}`;
  const meta = await fetch(base, { method: 'PATCH', headers, body: JSON.stringify({ description: about.description, homepage: about.homepage }) });
  const topics = await fetch(`${base}/topics`, { method: 'PUT', headers, body: JSON.stringify({ names: about.topics }) });
  const ok = meta.ok && topics.ok;
  if (!ok) failed++;
  console.log(`${ok ? '✓' : '✗'} ${repo}${ok ? '' : `  (about: ${meta.status}, topics: ${topics.status})`}`);
}
if (failed) {
  console.log(`::error::${failed} repo(s) failed. Check that the token has "Administration: read and write" on those repos.`);
  process.exit(1);
}

// SIP 自動計票（GOVERNANCE.md 第六節）
// 由 .github/workflows/sip-tally.yml 透過 actions/github-script 載入。
// 純邏輯（parse* / tally）不碰 GitHub API，供 sip-tally.test.js 單元測試。

const VOTING_HOURS = 72;
const DISCUSSION_DAYS = { T2: 7, T3: 14, E: 0 };
const TALLY_MARKER = '<!-- sip-tally -->';
const OPEN_MARKER = '<!-- sip-voting-open -->';

const LABELS = {
  proposal: { color: '5319e7', description: 'Governance proposal (SIP)' },
  'proposal:discussion': { color: 'c5def5', description: 'SIP 討論期' },
  'proposal:voting': { color: 'fbca04', description: 'SIP 投票期（72 小時）' },
  'proposal:accepted': { color: '0e8a16', description: 'SIP 通過' },
  'proposal:rejected': { color: 'b60205', description: 'SIP 未通過' },
  'governance:T1': { color: 'd4c5f9', description: 'T1 標準變更（48 小時公開期）' },
};

const HOUR = 3600 * 1000;
const DAY = 24 * HOUR;

// 擷取 issue body 中某個 `## 標題` 區段（去除 HTML 註解）
function section(body, heading) {
  const clean = (body || '').replace(/<!--[\s\S]*?-->/g, '');
  const lines = clean.split(/\r?\n/);
  const start = lines.findIndex((l) => l.trim().startsWith(`## ${heading}`));
  if (start === -1) return '';
  const out = [];
  for (const l of lines.slice(start + 1)) {
    if (/^##\s/.test(l)) break;
    out.push(l);
  }
  return out.join('\n');
}

// 等級無法判斷時往上一級（GOVERNANCE.md 第四節）→ T3
function parseTier(body) {
  const m = section(body, '等級').match(/\b(T3|T2|E)\b/);
  return m ? m[1] : 'T3';
}

function parseReviewDate(body) {
  const m = section(body, '成功指標與檢視日').match(/\d{4}-\d{2}-\d{2}/);
  return m ? m[0] : '—';
}

// 首行 `VOTE: YES|NO|ABSTAIN`
function parseVote(text) {
  const first = (text || '').trim().split(/\r?\n/)[0];
  const m = first.match(/^VOTE:\s*(YES|NO|ABSTAIN)\b/i);
  return m ? m[1].toUpperCase() : null;
}

// 首行 `VETO: <1-4>`；條號不在 1–4 視為無效否決（第五節）
function parseVeto(text) {
  const first = (text || '').trim().split(/\r?\n/)[0];
  const m = first.match(/^VETO:\s*(\S+)?/i);
  if (!m) return null;
  const clause = Number(m[1]);
  return { valid: Number.isInteger(clause) && clause >= 1 && clause <= 4, clause: m[1] || '' };
}

function isBot(user) {
  return !user || user.type === 'Bot' || /\[bot\]$/.test(user.login);
}

/**
 * 計票。
 * comments: [{ user:{login,type}, body, created_at, updated_at }]
 * voters:   { steward: 'login', maintainers: ['login'] }
 * 規則：
 *  - 僅計入投票期內建立、且截止前未再編輯的留言
 *  - 同一人以最後一次 VOTE 為準
 *  - 有效票 = YES + NO；ABSTAIN 計入投票率
 *  - 通過：投票率 ≥ 50%、YES / 有效票 ≥ 2/3、無有效否決；T3 另需 Steward 投 YES
 */
function tally({ comments, voters, tier, openedAt, deadline }) {
  const steward = voters.steward.toLowerCase();
  const eligible = new Set([steward, ...(voters.maintainers || []).map((m) => m.toLowerCase())]);
  const inWindow = (c) => {
    const created = new Date(c.created_at).getTime();
    const updated = new Date(c.updated_at || c.created_at).getTime();
    return created >= openedAt && created <= deadline && updated <= deadline;
  };

  const ballots = new Map();
  const advisory = new Map();
  let veto = null;
  const invalidVetoes = [];
  const sorted = [...comments].sort((a, b) => new Date(a.created_at) - new Date(b.created_at));

  for (const c of sorted) {
    if (isBot(c.user) || !inWindow(c)) continue;
    const login = c.user.login.toLowerCase();
    const v = parseVote(c.body);
    if (v) (eligible.has(login) ? ballots : advisory).set(login, v);
    if (login === steward) {
      const vt = parseVeto(c.body);
      if (vt && vt.valid) veto = vt;
      else if (vt) invalidVetoes.push(vt.clause || '(未填)');
    }
  }

  const count = (m, k) => [...m.values()].filter((v) => v === k).length;
  const yes = count(ballots, 'YES');
  const no = count(ballots, 'NO');
  const abstain = count(ballots, 'ABSTAIN');
  const turnout = ballots.size / eligible.size;
  const effective = yes + no;
  const ratio = effective ? yes / effective : 0;

  const reasons = [];
  if (turnout < 0.5) reasons.push(`投票率 ${(turnout * 100).toFixed(0)}% 低於 50%`);
  if (effective === 0) reasons.push('無有效票（YES + NO = 0）');
  else if (ratio < 2 / 3) reasons.push(`贊成比例 ${(ratio * 100).toFixed(1)}% 低於 2/3`);
  if (veto) reasons.push(`Steward 否決（第五節第 ${veto.clause} 款）`);
  if (tier === 'T3' && ballots.get(steward) !== 'YES') reasons.push('T3 需 Steward 明示同意（VOTE: YES）');

  return {
    accepted: reasons.length === 0,
    reasons,
    yes,
    no,
    abstain,
    eligibleCount: eligible.size,
    voted: ballots.size,
    turnout,
    ratio,
    veto,
    invalidVetoes,
    ballots: Object.fromEntries(ballots),
    advisory: { yes: count(advisory, 'YES'), no: count(advisory, 'NO'), abstain: count(advisory, 'ABSTAIN') },
  };
}

function sipId(issue) {
  const year = new Date(issue.created_at).getUTCFullYear();
  return `SIP-${year}-${String(issue.number).padStart(3, '0')}`;
}

function decisionRow(issue, tier, result, today) {
  const title = issue.title.replace(/^\[SIP\]\s*/i, '').replace(/\|/g, '\\|');
  const outcome = result.accepted ? '通過' : '未通過';
  const veto = result.veto ? `第 ${result.veto.clause} 款` : '無';
  return `| ${today} | ${sipId(issue)} | ${title} | ${tier} | ${outcome} | ${result.yes}/${result.no}/${result.abstain} | ${veto} | 待建立 | ${parseReviewDate(issue.body)} |`;
}

function resultComment(issue, tier, result, deadline) {
  const rows = Object.entries(result.ballots).map(([u, v]) => `| @${u} | ${v} |`).join('\n') || '| — | — |';
  const lines = [
    TALLY_MARKER,
    `## ${sipId(issue)} 計票結果：${result.accepted ? '通過' : '未通過'}`,
    '',
    `- 等級：${tier}`,
    `- 投票截止：${new Date(deadline).toISOString()}`,
    `- 投票率：${result.voted}/${result.eligibleCount}（${(result.turnout * 100).toFixed(0)}%）`,
    `- 票數 YES / NO / ABSTAIN：${result.yes} / ${result.no} / ${result.abstain}`,
    `- 贊成比例（YES ÷ 有效票）：${(result.ratio * 100).toFixed(1)}%`,
    `- 諮詢票（不計入門檻）YES / NO / ABSTAIN：${result.advisory.yes} / ${result.advisory.no} / ${result.advisory.abstain}`,
  ];
  if (result.veto) lines.push(`- Steward 否決：第五節第 ${result.veto.clause} 款`);
  if (result.invalidVetoes.length) lines.push(`- 無效否決（未引用第五節第 1–4 款）：${result.invalidVetoes.join(', ')}`);
  if (!result.accepted) lines.push('', '未通過原因：', ...result.reasons.map((r) => `- ${r}`));
  lines.push('', '| 投票人 | 票 |', '|---|---|', rows);
  lines.push('', result.accepted
    ? '下一步：開實作 PR 並於描述連結本 SIP；決策日誌 PR 已另開（若權限允許）。'
    : '依第五節，被否決提案可於 30 日後修改重提一次。');
  return lines.join('\n');
}

// ───────────────────────── GitHub 端 ─────────────────────────

async function ensureLabels(github, owner, repo) {
  for (const [name, spec] of Object.entries(LABELS)) {
    try {
      await github.rest.issues.getLabel({ owner, repo, name });
    } catch (e) {
      if (e.status !== 404) throw e;
      await github.rest.issues.createLabel({ owner, repo, name, ...spec });
    }
  }
}

async function loadVoters(github, owner, repo, ref) {
  const { data } = await github.rest.repos.getContent({ owner, repo, path: 'docs/governance/voters.json', ref });
  return JSON.parse(Buffer.from(data.content, 'base64').toString('utf8'));
}

// 最近一次被加上 proposal:voting 的時間
async function votingOpenedAt(github, owner, repo, number) {
  const events = await github.paginate(github.rest.issues.listEvents, { owner, repo, issue_number: number, per_page: 100 });
  const hits = events.filter((e) => e.event === 'labeled' && e.label && e.label.name === 'proposal:voting');
  return hits.length ? new Date(hits[hits.length - 1].created_at).getTime() : null;
}

async function setLabels(github, owner, repo, number, remove, add) {
  for (const name of remove) {
    try {
      await github.rest.issues.removeLabel({ owner, repo, issue_number: number, name });
    } catch (e) {
      if (e.status !== 404) throw e;
    }
  }
  if (add.length) await github.rest.issues.addLabels({ owner, repo, issue_number: number, labels: add });
}

// 投票期開始：檢查討論期是否足夠，足夠則公告截止時間，不足則退回討論期
async function onVotingLabeled({ github, context, core }) {
  const { owner, repo } = context.repo;
  const issue = context.payload.issue;
  const tier = parseTier(issue.body);
  const openedAt = Date.now();
  const minDays = DISCUSSION_DAYS[tier];
  const discussedDays = (openedAt - new Date(issue.created_at).getTime()) / DAY;

  if (discussedDays < minDays) {
    await setLabels(github, owner, repo, issue.number, ['proposal:voting'], ['proposal:discussion']);
    await github.rest.issues.createComment({
      owner, repo, issue_number: issue.number,
      body: `${OPEN_MARKER}\n投票期未開啟：${tier} 最短討論期 ${minDays} 日，目前 ${discussedDays.toFixed(1)} 日。` +
        `最早可於 ${new Date(new Date(issue.created_at).getTime() + minDays * DAY).toISOString()} 後重新加上 \`proposal:voting\`。`,
    });
    core.info(`#${issue.number} discussion period too short, reverted`);
    return;
  }

  await setLabels(github, owner, repo, issue.number, ['proposal:discussion'], []);
  const deadline = new Date(openedAt + VOTING_HOURS * HOUR).toISOString();
  await github.rest.issues.createComment({
    owner, repo, issue_number: issue.number,
    body: [
      OPEN_MARKER,
      `## ${sipId(issue)} 投票期開始（${tier}）`,
      '',
      `- 截止：${deadline}（${VOTING_HOURS} 小時）`,
      '- 有投票權者：`docs/governance/voters.json` 所列 Steward 與 Maintainers',
      '- 留言首行寫 `VOTE: YES` / `VOTE: NO` / `VOTE: ABSTAIN`，同一人以最後一次為準',
      '- 截止後才編輯的留言不計票；emoji reaction 不計票',
      '- Steward 否決：首行寫 `VETO: <1-4>`（GOVERNANCE.md 第五節條款）並附理由',
      '',
      '截止後由 SIP Tally workflow 自動計票並公告結果。',
    ].join('\n'),
  });
}

async function openDecisionLogPr(github, owner, repo, base, issue, row) {
  const path = 'docs/governance/DECISIONS.md';
  const branch = `governance/${sipId(issue).toLowerCase()}-decision`;
  const { data: ref } = await github.rest.git.getRef({ owner, repo, ref: `heads/${base}` });
  await github.rest.git.createRef({ owner, repo, ref: `refs/heads/${branch}`, sha: ref.object.sha });
  const { data: file } = await github.rest.repos.getContent({ owner, repo, path, ref: branch });
  const current = Buffer.from(file.content, 'base64').toString('utf8');
  const next = current.replace(/\n*$/, '\n') + row + '\n';
  await github.rest.repos.createOrUpdateFileContents({
    owner, repo, path, branch, sha: file.sha,
    message: `[governance] 決策日誌：${sipId(issue)}`,
    content: Buffer.from(next, 'utf8').toString('base64'),
  });
  const { data: pr } = await github.rest.pulls.create({
    owner, repo, head: branch, base,
    title: `[governance] 決策日誌：${sipId(issue)}`,
    body: `governance: T0\n\n自動計票結果寫入決策日誌。來源：#${issue.number}\n\n此 PR 由 SIP Tally workflow 產生，須由人類合併（GOVERNANCE.md 3.1）。`,
  });
  return pr.html_url;
}

// 排程：掃描所有投票中的 SIP，已過截止者計票
async function runScheduled({ github, context, core }) {
  const { owner, repo } = context.repo;
  const base = context.payload.repository?.default_branch || 'main';
  await ensureLabels(github, owner, repo);
  const voters = await loadVoters(github, owner, repo, base);

  const issues = await github.paginate(github.rest.issues.listForRepo, {
    owner, repo, state: 'open', labels: 'proposal:voting', per_page: 100,
  });

  for (const issue of issues.filter((i) => !i.pull_request)) {
    const openedAt = await votingOpenedAt(github, owner, repo, issue.number);
    if (!openedAt) continue;
    const deadline = openedAt + VOTING_HOURS * HOUR;
    if (Date.now() < deadline) {
      core.info(`#${issue.number} voting until ${new Date(deadline).toISOString()}`);
      continue;
    }

    const comments = await github.paginate(github.rest.issues.listComments, {
      owner, repo, issue_number: issue.number, per_page: 100,
    });
    // 冪等：同一輪投票已計票則略過
    if (comments.some((c) => c.body?.includes(TALLY_MARKER) && new Date(c.created_at).getTime() >= deadline)) continue;

    const tier = parseTier(issue.body);
    const result = tally({ comments, voters, tier, openedAt, deadline });
    await github.rest.issues.createComment({
      owner, repo, issue_number: issue.number, body: resultComment(issue, tier, result, deadline),
    });
    await setLabels(github, owner, repo, issue.number, ['proposal:voting'],
      [result.accepted ? 'proposal:accepted' : 'proposal:rejected']);

    const row = decisionRow(issue, tier, result, new Date().toISOString().slice(0, 10));
    try {
      const url = await openDecisionLogPr(github, owner, repo, base, issue, row);
      core.info(`#${issue.number} decision log PR: ${url}`);
    } catch (e) {
      core.warning(`decision log PR failed: ${e.message}`);
      await github.rest.issues.createComment({
        owner, repo, issue_number: issue.number,
        body: `決策日誌 PR 無法自動建立（${e.status || ''} ${e.message}）。請手動將下列一行加入 \`docs/governance/DECISIONS.md\`：\n\n\`\`\`\n${row}\n\`\`\``,
      });
    }

    if (!result.accepted) {
      await github.rest.issues.update({ owner, repo, issue_number: issue.number, state: 'closed', state_reason: 'not_planned' });
    }
  }
}

module.exports = {
  parseTier, parseVote, parseVeto, parseReviewDate, tally, sipId, decisionRow, resultComment,
  onVotingLabeled, runScheduled, VOTING_HOURS,
};

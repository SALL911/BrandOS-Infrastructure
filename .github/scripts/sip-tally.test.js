// node --test .github/scripts/sip-tally.test.js
const test = require('node:test');
const assert = require('node:assert');
const sip = require('./sip-tally.js');

const H = 3600 * 1000;
const openedAt = Date.parse('2026-11-01T00:00:00Z');
const deadline = openedAt + 72 * H;
const at = (h) => new Date(openedAt + h * H).toISOString();
const c = (login, body, h, editedH) => ({ user: { login, type: 'User' }, body, created_at: at(h), updated_at: at(editedH ?? h) });
const run = (comments, { tier = 'T2', maintainers = ['alice', 'bob'] } = {}) =>
  sip.tally({ comments, voters: { steward: 'SALL911', maintainers }, tier, openedAt, deadline });

test('parseTier 去除模板註解，未填時升級為 T3', () => {
  const tpl = '## 等級\n<!-- T2 重大 / T3 憲章 / E 緊急事後補正 -->\n\n## WHY\nx';
  assert.strictEqual(sip.parseTier(tpl), 'T3');
  assert.strictEqual(sip.parseTier(tpl.replace('-->\n', '-->\nT2 重大\n')), 'T2');
  assert.strictEqual(sip.parseTier('## 等級\nE\n'), 'E');
});

test('parseVote 只看首行', () => {
  assert.strictEqual(sip.parseVote('VOTE: yes\n理由'), 'YES');
  assert.strictEqual(sip.parseVote('我覺得\nVOTE: NO'), null);
});

test('parseVeto 須引用第 1–4 款', () => {
  assert.deepStrictEqual(sip.parseVeto('VETO: 2 超出預算'), { valid: true, clause: '2' });
  assert.strictEqual(sip.parseVeto('VETO: 7').valid, false);
  assert.strictEqual(sip.parseVeto('VETO:').valid, false);
});

test('2/3 贊成且投票率足夠 → 通過', () => {
  const r = run([c('SALL911', 'VOTE: YES', 1), c('alice', 'VOTE: YES', 2), c('bob', 'VOTE: NO', 3)]);
  assert.strictEqual(r.accepted, true);
  assert.strictEqual(r.yes, 2);
});

test('同一人以最後一票為準', () => {
  const r = run([c('SALL911', 'VOTE: YES', 1), c('alice', 'VOTE: NO', 2), c('alice', 'VOTE: YES', 5), c('bob', 'VOTE: NO', 3)]);
  assert.strictEqual(r.ballots.alice, 'YES');
  assert.strictEqual(r.accepted, true);
});

test('投票率不足 50% → 未通過', () => {
  const r = run([c('alice', 'VOTE: YES', 1)]);
  assert.strictEqual(r.accepted, false);
  assert.match(r.reasons.join(), /投票率/);
});

test('ABSTAIN 計入投票率但不計入分母', () => {
  const r = run([c('SALL911', 'VOTE: YES', 1), c('alice', 'VOTE: ABSTAIN', 1)]);
  assert.strictEqual(r.ratio, 1);
  assert.strictEqual(r.accepted, true);
});

test('投票期外與截止後編輯的留言不計', () => {
  const r = run([c('SALL911', 'VOTE: YES', -1), c('alice', 'VOTE: YES', 80), c('bob', 'VOTE: YES', 10, 73)]);
  assert.strictEqual(r.voted, 0);
  assert.strictEqual(r.accepted, false);
});

test('非投票權者與 bot 只算諮詢票', () => {
  const r = run([
    c('SALL911', 'VOTE: YES', 1), c('alice', 'VOTE: YES', 1),
    c('carol', 'VOTE: NO', 1),
    { user: { login: 'github-actions[bot]', type: 'Bot' }, body: 'VOTE: NO', created_at: at(1), updated_at: at(1) },
  ]);
  assert.strictEqual(r.advisory.no, 1);
  assert.strictEqual(r.no, 0);
  assert.strictEqual(r.accepted, true);
});

test('Steward 有效否決 → 未通過；無效否決不生效', () => {
  const base = [c('SALL911', 'VOTE: YES', 1), c('alice', 'VOTE: YES', 1), c('bob', 'VOTE: YES', 1)];
  assert.strictEqual(run([...base, c('SALL911', 'VETO: 3 客戶資料', 2)]).accepted, false);
  const r = run([...base, c('SALL911', 'VETO: 9', 2)]);
  assert.strictEqual(r.accepted, true);
  assert.deepStrictEqual(r.invalidVetoes, ['9']);
});

test('Maintainer 的 VETO 無效', () => {
  const r = run([c('SALL911', 'VOTE: YES', 1), c('alice', 'VETO: 1', 1), c('alice', 'VOTE: YES', 2)]);
  assert.strictEqual(r.veto, null);
  assert.strictEqual(r.accepted, true);
});

test('T3 需 Steward 投 YES', () => {
  const r = run([c('SALL911', 'VOTE: ABSTAIN', 1), c('alice', 'VOTE: YES', 1), c('bob', 'VOTE: YES', 1)], { tier: 'T3' });
  assert.strictEqual(r.accepted, false);
  assert.match(r.reasons.join(), /T3/);
});

test('現況：Steward 單人投票可決議', () => {
  const r = run([c('sall911', 'VOTE: YES', 1)], { tier: 'T3', maintainers: [] });
  assert.strictEqual(r.accepted, true);
  assert.strictEqual(r.turnout, 1);
});

test('decisionRow 格式與 SIP 編號', () => {
  const issue = { number: 7, title: '[SIP] 調整 | 方案', created_at: '2026-11-01T00:00:00Z', body: '## 成功指標與檢視日\n2027-03-31' };
  const r = run([c('SALL911', 'VOTE: YES', 1), c('alice', 'VOTE: YES', 1)]);
  assert.strictEqual(sip.decisionRow(issue, 'T2', r, '2026-11-04'),
    '| 2026-11-04 | SIP-2026-007 | 調整 \\| 方案 | T2 | 通過 | 2/0/0 | 無 | 待建立 | 2027-03-31 |');
});

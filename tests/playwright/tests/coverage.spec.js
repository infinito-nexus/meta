const { test, expect } = require('@playwright/test');
const { load } = require('../support/testsMatrix');

const head = rows => rows.map(([apps, variant, mode]) => ({ apps, variant: String(variant), mode }));

const SNAPSHOT = {
  rows: [{ name: 'web-app-a' }, { name: 'web-app-b' }, { name: 'web-app-c' }],
  variant_counts: { 'web-app-a': 3 },
  rounds: {
    'web-app-a#0': { active: { 'web-app-a': 0, 'web-app-b': 0 } },
    'web-app-a#2': { active: { 'web-app-a': 2 } },
    'web-app-c#0': { active: { 'web-app-c': 0 } },
  },
  sweeps: {
    0: { head: head([['web-app-a', 0, 'compose'], ['web-app-a', 2, 'swarm'], ['web-app-c', 0, 'compose']]) },
    1: { head: head([['web-app-a', 0, 'swarm'], ['web-app-a', 2, 'compose']]) },
  },
};

const BRANCH = {
  ...SNAPSHOT,
  sweeps: {
    0: { head: head([['web-app-a', 0, 'compose']]) },
    1: { head: head([['web-app-a', 0, 'swarm']]) },
  },
};

const ROWS = [
  { role: 'web-app-a', variant: 0, module: 'test-sso', test: 'sso', status: 'skipped' },
  { role: 'web-app-a', variant: 2, module: 'test-sso', test: 'sso', status: 'runs' },
  { role: 'web-app-a', variant: 0, module: 'test-baseline', test: 'baseline', status: 'runs' },
  { role: 'web-app-b', variant: null, module: 'playwright.spec', test: 'dependency', status: 'runs' },
  { role: 'web-app-c', variant: null, module: 'playwright.spec', test: 'only in one sweep', status: 'runs' },
  { role: 'web-app-z', variant: null, module: 'playwright.spec', test: 'never planned', status: 'runs' },
];

test('a snapshot credits every role a head round deploys, at the variant it deploys', async ({ page }) => {
  await load(page);
  const found = await page.evaluate(snapshot => {
    const { deployed } = window.CiCoverage.read(snapshot);
    return Object.fromEntries([...deployed].map(([key, rows]) => [key, rows]));
  }, SNAPSHOT);

  expect(found['web-app-b#0'], 'a dependency the round brings up runs its specs too')
    .toEqual([{ row: 'web-app-a#0', modes: ['compose', 'swarm'] }]);
  expect(found['web-app-a#2']).toEqual([{ row: 'web-app-a#2', modes: ['compose', 'swarm'] }]);
  expect(found['web-app-c#0'], 'a row one sweep drops does not run in every CI run').toBeUndefined();
});

test('a test that loses its only running variant is lost, a planned role without a row is a hole',
  async ({ page }) => {
    await load(page);
    const verdicts = await page.evaluate(([base, branch, rows]) => {
      const read = window.CiCoverage.read;
      const annotated = window.CiCoverage.annotate(structuredClone(rows), read(branch), read(base));
      return Object.fromEntries(annotated.map(row => [`${row.role} ${row.test} ${row.variant}`, row.coverage]));
    }, [SNAPSHOT, BRANCH, ROWS]);

    expect(verdicts['web-app-a sso 0'], 'variant 2 was the only one running it').toBe('lost');
    expect(verdicts['web-app-a sso 2']).toBe('lost');
    expect(verdicts['web-app-a baseline 0']).toBe('covered');
    expect(verdicts['web-app-b dependency null']).toBe('covered');
    expect(verdicts['web-app-c only in one sweep null']).toBe('hole');
    expect(verdicts['web-app-z never planned null'], 'discovery leaves it out on purpose').toBe('excluded');
  });

test('a snapshot without sweeps is refused and a variant count mismatch is named', async ({ page }) => {
  await load(page);
  const [refused, drift] = await page.evaluate(snapshot => {
    let message = '';
    try {
      window.CiCoverage.read({ rows: [] });
    } catch (error) {
      message = error.message;
    }
    return [message, window.CiCoverage.drift(window.CiCoverage.read(snapshot), { 'web-app-a': 2, 'web-app-b': 0 })];
  }, SNAPSHOT);

  expect(refused).toContain('variant_split');
  expect(drift).toEqual(['web-app-a']);
});

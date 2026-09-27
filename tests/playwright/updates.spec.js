const { test, expect } = require('@playwright/test');
const { boot } = require('./support/mirror');

const PULLS = [
  {
    number: 51, title: 'Bump nextcloud from 34-fpm-alpine to 35-fpm-alpine', state: 'open',
    html_url: 'https://github.com/infinito-nexus/core/pull/51', updated_at: '2026-09-20T00:00:00Z',
    base: { repo: { full_name: 'infinito-nexus/core' } },
  },
  {
    number: 52, title: 'Add a role for something else', state: 'open',
    html_url: 'https://github.com/infinito-nexus/core/pull/52', updated_at: '2026-09-19T00:00:00Z',
    base: { repo: { full_name: 'infinito-nexus/core' } },
  },
];

async function open(page, query = '?view=updates') {
  await page.route('https://api.github.com/**', route => {
    const url = new URL(route.request().url());
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      headers: { 'access-control-allow-origin': '*' },
      body: JSON.stringify(url.pathname.endsWith('/pulls') ? PULLS : []),
    });
  });
  await boot(page, [], query);
}

const rows = page => page.locator('table.update-table tbody tr');

test('the updates view states every pin and what the registry has newer', async ({ page }) => {
  await open(page);
  await expect.poll(() => rows(page).count(), { timeout: 60000 }).toBe(4);
  await expect(page.locator('#btn-items')).toHaveText('Items · Updates');
  await expect(page.locator('.table-note')).toContainText('1 of 4 pinned images has a newer tag');

  const states = await page.locator('table.update-table tbody td:first-child').allInnerTexts();
  expect(states.map(text => text.trim()), 'what fell behind is read first')
    .toEqual(['behind', 'unknown', 'unpinned', 'current']);

  const behind = rows(page).first();
  await expect(behind).toContainText('nextcloud');
  await expect(behind).toContainText('34-fpm-alpine');
  await expect(behind, 'the newest tag of the pin’s own shape').toContainText('35-fpm-alpine');
});

test('an image whose bump is already open links to that pull request', async ({ page }) => {
  await open(page);
  await expect.poll(() => rows(page).count(), { timeout: 60000 }).toBe(4);

  const behind = rows(page).first();
  await expect(behind.locator('a')).toHaveAttribute('href', 'https://github.com/infinito-nexus/core/pull/51');
  await expect(behind.locator('a')).toHaveText('#51');

  const current = rows(page).filter({ hasText: 'nginx' });
  await expect(current.locator('a'), 'a pin nobody bumped links nowhere').toHaveCount(0);
});

test('the table narrows by role and by state', async ({ page }) => {
  await open(page);
  await expect.poll(() => rows(page).count(), { timeout: 60000 }).toBe(4);

  await page.locator('select[data-filter="role"]').selectOption('web-app-nextcloud');
  await expect.poll(() => rows(page).count()).toBe(2);
  await expect(page.locator('.table-note')).toContainText('2 are left after the filters');

  await page.locator('select[data-filter="role"]').selectOption('');
  await page.locator('select[data-filter="state"]').selectOption('behind');
  await expect.poll(() => rows(page).count()).toBe(1);
  await expect(rows(page).first()).toContainText('nextcloud');

  await page.locator('select[data-filter="state"]').selectOption('');
  await page.locator('.feed-search').fill('postgres');
  await expect.poll(() => rows(page).count()).toBe(1);
  await expect(rows(page).first()).toContainText('unpinned');
});

test('a reload that fails quotes the mirror rather than its status', async ({ page }) => {
  await open(page);
  await expect.poll(() => rows(page).count(), { timeout: 60000 }).toBe(4);

  // Registered after boot, whose own stub would otherwise win: the last
  // matching route is the one playwright serves.
  await page.route('**/git/updates*', route => route.fulfill({
    status: 502, contentType: 'application/json',
    body: JSON.stringify({ error: "git ls-tree: fatal: not a valid object name: 'origin/HEAD'" }),
  }));
  await page.locator('.update-again').click();

  await expect(page.locator('.table-note'), 'the mirror names the cause, the status does not')
    .toContainText('not a valid object name');
  await expect(page.locator('.table-note')).not.toContainText('HTTP 502');
});

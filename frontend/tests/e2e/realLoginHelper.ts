import { Page } from '@playwright/test';

/**
 * Ensures the page is authenticated before each test.
 *
 * Strategy:
 * 1. Navigate to /overview with the globalSetup storageState already injected.
 * 2. Wait briefly for the authenticated sidebar (<aside>) to appear.
 *    - If it appears: auth is confirmed, return immediately (fast path).
 *    - If it doesn't appear (Firefox HTTP storageState bug, or backend down/slow
 *      causing fetchUser → logout): fall through to a real form login.
 * 3. Real form login: fill the login form and wait for the post-login redirect.
 *
 * All timeouts are sized to stay comfortably within the 60 s per-test budget
 * set in playwright.config.ts.
 */
export async function performRealLogin(page: Page) {
  // ── Fast path: storageState ──────────────────────────────────────────────
  await page.goto('/overview');

  const authenticated = await page.locator('aside')
    .waitFor({ state: 'visible', timeout: 6000 })
    .then(() => true)
    .catch(() => false);

  if (authenticated) return;

  // ── Fallback: real form login ────────────────────────────────────────────
  await page.goto('/login');
  await page.waitForSelector('input[name="username"]', { state: 'visible', timeout: 10000 });
  await page.locator('input[name="username"]').fill('admin');
  await page.locator('input[name="password"]').fill('Admin@2026!');
  await page.locator('button[type="submit"]').click();
  // 20 s is enough for a healthy local backend; stays within the 60 s test budget
  await page.waitForURL(/.*\/overview/, { timeout: 20000 });
  await page.waitForSelector('aside', { state: 'visible', timeout: 10000 });
}

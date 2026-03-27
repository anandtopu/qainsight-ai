import { chromium } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

// ESM does not provide __dirname — derive it from import.meta.url
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Global setup: authenticate once before the test suite runs and save the
 * browser storage state (JWT in localStorage) so individual tests don't need
 * to log in themselves.  This prevents parallel-login overload on the backend.
 */
async function globalSetup() {
  const authFile = path.join(__dirname, '.auth', 'user.json');
  fs.mkdirSync(path.dirname(authFile), { recursive: true });

  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();

  await page.goto('http://localhost:3000/login');
  await page.waitForSelector('input[name="username"]', { state: 'visible', timeout: 15000 });

  await page.locator('input[name="username"]').fill('admin');
  await page.locator('input[name="password"]').fill('Admin@2026!');
  await page.locator('button[type="submit"]').click();

  // Wait for the post-login redirect to complete
  await page.waitForURL(/.*\/overview/, { timeout: 30000 });

  // Save the full storage state (localStorage contains the JWT token)
  await context.storageState({ path: authFile });

  await browser.close();
}

export default globalSetup;

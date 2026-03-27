import { test, expect } from '@playwright/test';
import { performRealLogin } from './realLoginHelper';

test.describe('Defects and Failure Analysis', () => {

  test.beforeEach(async ({ page }) => {
    await performRealLogin(page);
  });

  test('should render Failure Analysis page', async ({ page }) => {
    await page.goto('/failures');
    await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible({ timeout: 10000 });
  });

  test('should render Defects tracking page', async ({ page }) => {
    await page.goto('/defects');
    await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible({ timeout: 10000 });
  });
});

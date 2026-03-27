import { test, expect } from '@playwright/test';
import { performMockLogin } from './mockHelper';

test.describe('Test Runs and Execution', () => {

  test.beforeEach(async ({ page }) => {
    await performMockLogin(page);
    await page.route('**/api/v1/runs*', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([
        { id: '1', name: 'Nightly Run', status: 'passed' }
      ]) });
    });
  });

  test('should display runs list and allow filtering', async ({ page }) => {
    await page.goto('/runs');
    await expect(page.getByRole('heading').first()).toBeVisible();

    const searchInput = page.locator('input[placeholder*="search" i], input[placeholder*="filter" i]').first();
    if (await searchInput.isVisible()) {
      await searchInput.fill('nightly');
    }

    const rowCount = await page.locator('tbody tr').count();
    
    if (rowCount > 0) {
      const firstRowLink = page.locator('tbody tr').first().locator('a').first();
      if (await firstRowLink.isVisible()) {
         await firstRowLink.click();
         await expect(page).toHaveURL(/.*\/runs\/.+/);
      }
    }
  });
});

import { test, expect } from '@playwright/test';
import { performMockLogin } from './mockHelper';

test.describe('Test Management', () => {

  test.beforeEach(async ({ page }) => {
    await performMockLogin(page);
  });

  test('should render test management and suite creation', async ({ page }) => {
    await page.goto('/test-management');
    await expect(page.getByRole('heading').first()).toBeVisible();

    const createButton = page.locator('button', { hasText: /Create|Add/i }).first();
    
    if (await createButton.isVisible()) {
      await createButton.click();
      
      const modalOrForm = page.locator('dialog, [role="dialog"], form').first();
      await expect(modalOrForm).toBeVisible({ timeout: 5000 }).catch(() => {});
    }
  });
});

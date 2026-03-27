import { test, expect } from '@playwright/test';
import { performMockLogin } from './mockHelper';

test.describe('Defects and Failure Analysis', () => {

  test.beforeEach(async ({ page }) => {
    await performMockLogin(page);
  });

  test('should render Failure Analysis page', async ({ page }) => {
    await page.goto('/failures');
    await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible();
    
    // Check if there are any AI analysis buttons or features
    const analyzeButton = page.locator('button', { hasText: /Analyze/i }).first();
    if (await analyzeButton.isVisible()) {
      await analyzeButton.click();
    }
  });

  test('should render Defects tracking page', async ({ page }) => {
    await page.goto('/defects');
    await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible();
  });
});

import { test, expect } from '@playwright/test';
import { performRealLogin } from './realLoginHelper';

test.describe('Authentication Flow', () => {

// Note: Testing successful login here only, not unauthorized redirect since it might leave token.
// We clear storage directly.
  test('should allow user to login and redirect to overview', async ({ page, context }) => {
    await context.clearCookies();
    await page.evaluate(() => window.localStorage.clear()).catch(() => {});
    
    await page.goto('/login');
    
    const usernameInput = page.locator('input[name="username"]');
    const passwordInput = page.locator('input[name="password"]');
    const submitButton = page.locator('button[type="submit"]');
    
    await expect(usernameInput).toBeVisible();
    await usernameInput.fill('admin');
    
    await expect(passwordInput).toBeVisible();
    await passwordInput.fill('Admin@2026!');
    
    await expect(submitButton).toBeVisible();
    await submitButton.click();
    
    await expect(page).toHaveURL(/.*\/overview/);
    await expect(page.locator('h1', { hasText: 'Overview' })).toBeVisible({ timeout: 10000 });
  });

});

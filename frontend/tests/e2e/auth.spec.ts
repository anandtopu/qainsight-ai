import { test, expect } from '@playwright/test';
import { mockLogin } from './mockHelper';

test.describe('Authentication Flow', () => {

  test('should redirect to login when not authenticated', async ({ page }) => {
    await page.goto('/overview');
    await expect(page).toHaveURL(/.*\/login/);
  });

  test('should allow user to login and redirect to overview', async ({ page }) => {
    await mockLogin(page);
    await page.goto('/login');
    
    const usernameInput = page.locator('input[name="username"]');
    const passwordInput = page.locator('input[name="password"]');
    const submitButton = page.locator('button[type="submit"]');
    
    await expect(usernameInput).toBeVisible();
    await usernameInput.fill('admin@qainsight.com');
    
    await expect(passwordInput).toBeVisible();
    await passwordInput.fill('password123');
    
    await expect(submitButton).toBeVisible();
    await submitButton.click();
    
    await expect(page).toHaveURL(/.*\/overview/);
    await expect(page.locator('h1', { hasText: 'Overview' })).toBeVisible({ timeout: 10000 });
  });

});

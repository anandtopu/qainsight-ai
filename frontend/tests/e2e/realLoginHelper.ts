import { Page, expect } from '@playwright/test';

export async function performRealLogin(page: Page) {
  // Check if we are already logged in by looking at localStorage or just navigating
  await page.goto('/overview');
  if (page.url().includes('/login')) {
    const emailInput = page.locator('input[name="username"]');
    const passwordInput = page.locator('input[name="password"]');
    const submitButton = page.locator('button[type="submit"]');
    
    await emailInput.fill('admin');
    await passwordInput.fill('Admin@2026!');
    await submitButton.click();
    
    await expect(page).toHaveURL(/.*\/overview/, { timeout: 15000 });
  }
}

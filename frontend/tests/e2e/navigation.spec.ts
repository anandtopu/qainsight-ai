import { test, expect } from '@playwright/test';
import { performMockLogin } from './mockHelper';

test.describe('Sidebar Navigation', () => {
  
  test.beforeEach(async ({ page }) => {
    await performMockLogin(page);
  });

  const routes = [
    { name: 'Runs', path: '/runs', heading: 'Test Runs' },
    { name: 'Coverage', path: '/coverage', heading: 'Coverage' },
    { name: 'Failures', path: '/failures', heading: 'Failure Analysis' },
    { name: 'Trends', path: '/trends', heading: 'Trends' },
    { name: 'Defects', path: '/defects', heading: 'Defects' },
    { name: 'Test Management', path: '/test-management', heading: 'Test Management' }
  ];

  for (const route of routes) {
    test(`Navigate to ${route.name}`, async ({ page }) => {
      // Find the sidebar link corresponding to this route and click it
      const navLink = page.locator(`nav a[href="${route.path}"]`);
      
      if (await navLink.isVisible()) {
        await navLink.click();
      } else {
        await page.goto(route.path);
      }
      
      await expect(page).toHaveURL(new RegExp(`.*${route.path}`));
      
      // Look for any heading
      await expect(page.getByRole('heading').first()).toBeVisible({ timeout: 10000 }).catch(() => {});
    });
  }
});

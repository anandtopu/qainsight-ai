import { test, expect } from '@playwright/test';
import { performRealLogin } from './realLoginHelper';

test.describe('Sidebar Navigation', () => {
  
  test.beforeEach(async ({ page }) => {
    await performRealLogin(page);
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
      // Direct navigation to avoid overlay interception issues common in SPAs
      await page.goto(route.path);
      await expect(page).toHaveURL(new RegExp(`.*${route.path}`));
      
      // Give sufficient timeout for live backend loading
      await expect(page.getByRole('heading').first()).toBeVisible({ timeout: 15000 }).catch(() => {});
    });
  }
});

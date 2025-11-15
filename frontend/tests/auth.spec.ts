// frontend/tests/auth.spec.ts
import { test, expect } from '@playwright/test';

test('should redirect to login page for protected route', async ({ page }) => {
  await page.goto('/terminal');
  await expect(page).toHaveURL('/login');
});

test('should allow login and access to terminal', async ({ page }) => {
  await page.goto('/login');
  await page.fill('input[type="email"]', 'test@example.com');
  await page.fill('input[type="password"]', 'password');
  await page.click('button[type="submit"]');
  await expect(page).toHaveURL('/terminal');
});

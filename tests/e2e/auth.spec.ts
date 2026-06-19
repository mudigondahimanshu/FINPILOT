import { test, expect } from "@playwright/test";

const TEST_EMAIL = process.env.E2E_EMAIL ?? "e2e@finpilot.test";
const TEST_PASSWORD = process.env.E2E_PASSWORD ?? "E2ePassword123!";

test.describe("Authentication flow", () => {
  test("register → login → dashboard", async ({ page }) => {
    // 1. Land on home → redirect to login
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/);

    // 2. Navigate to register
    await page.getByRole("link", { name: /register/i }).click();
    await expect(page).toHaveURL(/\/register/);

    // 3. Fill registration form
    await page.getByLabel(/full name/i).fill("E2E Test User");
    await page.getByLabel(/email/i).fill(TEST_EMAIL);
    await page.getByLabel(/password/i).fill(TEST_PASSWORD);
    await page.getByRole("button", { name: /create account/i }).click();

    // 4. Should land on dashboard or login (if email verification required)
    await page.waitForURL(/(dashboard|login)/, { timeout: 10_000 });

    // 5. Login with the new account
    if (page.url().includes("login")) {
      await page.getByLabel(/email/i).fill(TEST_EMAIL);
      await page.getByLabel(/password/i).fill(TEST_PASSWORD);
      await page.getByRole("button", { name: /sign in/i }).click();
    }

    await expect(page).toHaveURL(/\/dashboard/, { timeout: 10_000 });
    await expect(page.getByText(/net savings|income|expenses/i).first()).toBeVisible();
  });

  test("invalid login shows error", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/email/i).fill("nobody@example.com");
    await page.getByLabel(/password/i).fill("wrongpassword");
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page.getByText(/invalid|incorrect|not found/i)).toBeVisible({ timeout: 5_000 });
  });

  test("protected routes redirect unauthenticated users", async ({ page }) => {
    await page.goto("/transactions");
    await expect(page).toHaveURL(/\/login/);
  });
});

test.describe("Transaction management", () => {
  test.beforeEach(async ({ page }) => {
    // Quick login
    await page.goto("/login");
    await page.getByLabel(/email/i).fill(TEST_EMAIL);
    await page.getByLabel(/password/i).fill(TEST_PASSWORD);
    await page.getByRole("button", { name: /sign in/i }).click();
    await page.waitForURL(/\/dashboard/);
  });

  test("transactions page loads", async ({ page }) => {
    await page.goto("/transactions");
    await expect(page.getByText(/transactions/i).first()).toBeVisible();
  });

  test("can navigate to AI Insights", async ({ page }) => {
    await page.getByRole("link", { name: /insights/i }).click();
    await expect(page).toHaveURL(/\/insights/);
    await expect(page.getByText(/forecast|copilot|sentiment|fraud/i).first()).toBeVisible();
  });
});

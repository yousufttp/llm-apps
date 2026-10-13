import { test, expect, Page } from "@playwright/test";

async function login(page: Page, email = "alex@example.test") {
  page.on("console", msg => { if (msg.type() === "error") console.log("browser:", msg.text()); });
  page.on("request", request => {
    if (request.url().endsWith("/api/copilotkit") && request.method() === "POST") {
      const body = request.postDataJSON();
      console.log("runtime:", body.method, body.params?.agentId, body.body?.threadId || body.params?.threadId);
    }
  });
  await page.goto("/");
  await page.getByLabel("Email", {exact: true}).fill(email);
  await page.getByLabel("Password", {exact: true}).fill("CareDemo123!");
  await page.getByRole("button", {name: "Enter workspace"}).click();
}

test("customer starts a conversation, confirms a change, and reloads saved state", async ({ page }) => {
  await login(page);
  await page.getByLabel("Choose a service").selectOption("mobile-new");
  await page.getByRole("button", {name: "Start a conversation"}).click();
  const input = page.locator(".copilotKitInput textarea");
  await expect(input).toBeVisible({timeout: 30000});
  await input.fill("activate my service");
  await expect(page.getByRole("button", {name: "Send", exact: true})).toBeEnabled({timeout: 30000});
  await page.getByRole("button", {name: "Send", exact: true}).click();
  await expect(page.getByRole("button", {name: "Approve", exact: true})).toBeVisible({timeout: 45000});
  await page.getByRole("button", {name: "Approve", exact: true}).click();
  await expect(page.getByRole("status")).toContainText("completed and verified");
  await page.reload();
  await page.locator(".thread-list button").first().click();
  await page.getByText(/Saved conversation/).click();
  await expect(page.locator(".history")).toContainText("completed and verified");
});

test("customer escalates a bill and operator applies a credit", async ({ page, browser }) => {
  await login(page);
  await page.getByLabel("Choose a service").selectOption("broadband-home");
  await page.getByRole("button", {name: "Start a conversation"}).click();
  const input = page.locator(".copilotKitInput textarea");
  await expect(input).toBeVisible({timeout: 30000});
  await input.fill("My bill is incorrect; please refund the duplicate charge");
  await expect(page.getByRole("button", {name: "Send", exact: true})).toBeEnabled({timeout: 30000});
  await page.getByRole("button", {name: "Send", exact: true}).click();
  await expect(page.locator(".case-grid")).toContainText("operator review", {timeout: 45000});
  const context = await browser.newContext();
  const operator = await context.newPage();
  await login(operator, "operator@example.test");
  await operator.locator(".queue-item").filter({hasText: "billing"}).first().click();
  await operator.getByLabel("Action", {exact: true}).selectOption("credit");
  await operator.getByLabel("Credit amount").fill("10");
  await operator.getByLabel("Resolution note").fill("Duplicate charge reviewed and $10 credited.");
  await operator.getByRole("checkbox").check();
  await operator.getByRole("button", {name: "Complete resolution"}).click();
  await expect(operator.locator(".notice")).toContainText("$10 credited");
  await expect(page.locator(".case-grid")).toContainText("$10 credited", {timeout: 15000});
  await context.close();
});

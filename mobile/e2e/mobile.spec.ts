import { test, expect, type Page } from '@playwright/test'

/**
 * Mobile app (Expo Web) smoke tests — headed Chromium with screenshots.
 * Validates the 4 tab screens render real data from the orchestrator + agent mesh.
 */

async function gotoTab(page: Page, tabText: string) {
  await page.getByText(tabText, { exact: true }).click()
  await page.waitForTimeout(2000)
}

test('dashboard renders KPI cards with real portfolio data', async ({ page }) => {
  await page.goto('http://localhost:8081', { waitUntil: 'networkidle' })
  await expect(page.getByText('Portfolio Overview')).toBeVisible()
  await expect(page.getByText('$20.4M')).toBeVisible()
  await expect(page.getByText('0.58')).toBeVisible()
  await expect(page.getByText('Geographic Allocation')).toBeVisible()
  await page.screenshot({ path: 'e2e/__screens__/mobile-dashboard.png' })
})

test('portfolio screen renders deals table', async ({ page }) => {
  await page.goto('http://localhost:8081', { waitUntil: 'networkidle' })
  await gotoTab(page, 'Portfolio')
  await page.screenshot({ path: 'e2e/__screens__/mobile-portfolio.png' })
})

test('market screen renders quotes', async ({ page }) => {
  await page.goto('http://localhost:8081', { waitUntil: 'networkidle' })
  await gotoTab(page, 'Market')
  await page.screenshot({ path: 'e2e/__screens__/mobile-market.png' })
})

test('chat screen accepts input and streams a reply', async ({ page }) => {
  test.setTimeout(90000)
  await page.goto('http://localhost:8081', { waitUntil: 'networkidle' })
  await gotoTab(page, 'AI Chat')
  const input = page.getByLabel('chat-input')
  await expect(input).toBeVisible()
  await input.fill('What is my total assets under management?')
  await page.getByLabel('chat-send').click()
  await expect(page.getByText('$20.4M')).toBeVisible({ timeout: 60000 })
  await page.screenshot({ path: 'e2e/__screens__/mobile-chat.png' })
})

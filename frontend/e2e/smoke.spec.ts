import { test, expect, type Page } from '@playwright/test'

/**
 * Smoke + content tests for the LaRuche web app.
 * Validates the four screens render and surfaces the data shown in the UI
 * so it can be compared against the canonical demo data.
 */

const consoleErrors: string[] = []

test.beforeEach(async ({ page }) => {
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text())
  })
})

async function goto(page: Page, path: string) {
  await page.goto(path)
  await page.waitForLoadState('networkidle')
}

test('dashboard renders the KPI cards', async ({ page }) => {
  await goto(page, '/')
  await expect(page.getByRole('heading', { name: 'Portfolio Overview' })).toBeVisible()
  await expect(page.getByText('$20.4M')).toBeVisible()
  await expect(page.getByText('19.65%')).toBeVisible()
  await expect(page.getByText('0.58')).toBeVisible()
  await page.getByRole('button', { name: '1M' }).click()
  await expect(page.getByRole('button', { name: '1M' })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByText('Last 30 days')).toBeVisible()
  // Geographic + sector breakdowns present
  await expect(page.getByText('Geographic Allocation')).toBeVisible()
  await expect(page.getByText('Sector Mix')).toBeVisible()
  await page.screenshot({ path: 'e2e/__screens__/dashboard.png' })
})

test('portfolio deals table renders rows', async ({ page }) => {
  await goto(page, '/portfolio')
  await expect(page.getByRole('heading', { name: 'Portfolio Deals' })).toBeVisible()
  const rows = page.locator('tbody tr')
  await expect(rows).toHaveCount(8)
  await expect(page.getByText('Aurora Brands')).toBeVisible()
  await page.screenshot({ path: 'e2e/__screens__/portfolio.png' })
})

test('market page renders quotes and indicators', async ({ page }) => {
  await goto(page, '/market')
  await expect(page.getByRole('heading', { name: 'Market Data' })).toBeVisible()
  await expect(page.getByText('S&P 500')).toBeVisible()
  await expect(page.getByText('Fed Funds Rate')).toBeVisible()
  await page.screenshot({ path: 'e2e/__screens__/market.png' })
})

test('chat page renders and accepts input', async ({ page }) => {
  await goto(page, '/chat')
  await expect(page.getByRole('heading', { name: 'AI Assistant' })).toBeVisible()
  const input = page.getByPlaceholder(/Ask LaRuche anything/i)
  await expect(input).toBeVisible()
  await expect(page.getByRole('button', { name: 'Attach files' })).toBeVisible()
  const fileInput = page.locator('input[type="file"]')
  await expect(fileInput).toHaveAttribute('multiple', '')
  await expect(fileInput).toHaveAttribute('accept', /image\/\*.*audio\/\*/)
  await expect(page.getByRole('button', { name: 'Dictate message' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Start voice conversation' })).toBeVisible()
  await expect(page.getByRole('combobox', { name: 'Response mode' })).toHaveValue('instant')
  await page.getByRole('combobox', { name: 'Response mode' }).selectOption('deep')
  await expect(page.getByRole('combobox', { name: 'Response mode' })).toHaveValue('deep')
  await input.fill('What is my portfolio AUM?')
  await expect(page.getByRole('button', { name: 'Send message' })).toBeVisible()
  await page.screenshot({ path: 'e2e/__screens__/chat.png' })
})

test('voice studio exposes all three speech modes', async ({ page }) => {
  await goto(page, '/voice')
  await expect(page.getByRole('heading', { name: 'Voice Studio' })).toBeVisible()
  await expect(page.getByRole('button', { name: /Voice to voice/ })).toBeVisible()
  await expect(page.getByRole('button', { name: /Speech to text/ })).toBeVisible()
  await page.getByRole('button', { name: /Text to speech/ }).click()
  await expect(page.getByRole('heading', { name: 'Generate a briefing' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Play briefing' })).toBeVisible()
  await page.screenshot({ path: 'e2e/__screens__/voice.png' })
})

test('no console errors across navigation', async ({ page }) => {
  await goto(page, '/')
  await goto(page, '/portfolio')
  await goto(page, '/market')
  await goto(page, '/chat')
  await goto(page, '/voice')
  expect(consoleErrors, consoleErrors.join('\n')).toEqual([])
})

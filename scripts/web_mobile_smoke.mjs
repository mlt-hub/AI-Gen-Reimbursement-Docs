import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const { chromium } = require(path.join(process.cwd(), 'node_modules', 'playwright'))

const args = new Map()
for (let i = 2; i < process.argv.length; i += 1) {
  const arg = process.argv[i]
  if (!arg.startsWith('--')) {
    continue
  }
  const key = arg.slice(2)
  const next = process.argv[i + 1]
  if (!next || next.startsWith('--')) {
    args.set(key, 'true')
    continue
  }
  args.set(key, next)
  i += 1
}

const baseUrl = (args.get('base-url') || 'http://127.0.0.1:5173/static/dist/').replace(/\/+$/, '/')
const screenshotDir = args.get('screenshot-dir') || ''
const viewport = {
  width: Number(args.get('width') || 390),
  height: Number(args.get('height') || 844),
}

const routes = [
  { name: 'home', path: '', expected: ['AI 报账文档生成', '生成任务', '执行监控'] },
  { name: 'config', path: 'config', expected: ['环境诊断', '模型与凭据'] },
  { name: 'fpa-preview', path: 'preview/fpa', expected: ['FPA 预览', '输入设置', '选择功能清单'] },
  { name: 'cosmic-preview', path: 'preview/cosmic', expected: ['COSMIC 预览', '新增/修改功能过程'] },
  { name: 'fpa-debug', path: 'sessions/mobile-smoke/fpa/debug', expected: ['AI 调试信息', 'Session mobile-smoke', '结构化记录'] },
]

function joinUrl(base, routePath) {
  return new URL(routePath, base).toString()
}

async function launchBrowser() {
  try {
    return await chromium.launch({ channel: 'msedge', headless: true })
  } catch (error) {
    console.warn(`无法使用 msedge channel，改用 Playwright Chromium: ${error.message}`)
    return chromium.launch({ headless: true })
  }
}

async function collectOverflow(page) {
  return page.evaluate(() => {
    const viewportWidth = window.innerWidth
    const root = document.documentElement
    const body = document.body
    const offenders = []

    for (const element of Array.from(document.querySelectorAll('body *'))) {
      const rect = element.getBoundingClientRect()
      if (rect.width < 1 || rect.height < 1) {
        continue
      }
      if (rect.right > viewportWidth + 1 || rect.left < -1) {
        const className = typeof element.className === 'string' ? element.className : ''
        const text = (element.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 80)
        offenders.push({
          tag: element.tagName.toLowerCase(),
          className,
          left: Math.round(rect.left),
          right: Math.round(rect.right),
          width: Math.round(rect.width),
          text,
        })
      }
    }

    return {
      viewportWidth,
      documentScrollWidth: root.scrollWidth,
      bodyScrollWidth: body.scrollWidth,
      offenders: offenders.slice(0, 10),
    }
  })
}

function assertNoOverflow(route, metrics) {
  const maxScrollWidth = Math.max(metrics.documentScrollWidth, metrics.bodyScrollWidth)
  if (maxScrollWidth > metrics.viewportWidth + 1 || metrics.offenders.length > 0) {
    throw new Error(
      [
        `${route.name} 存在移动端横向溢出`,
        `viewport=${metrics.viewportWidth}, document=${metrics.documentScrollWidth}, body=${metrics.bodyScrollWidth}`,
        `offenders=${JSON.stringify(metrics.offenders, null, 2)}`,
      ].join('\n'),
    )
  }
}

async function assertMobileNav(page, route) {
  const openButton = page.getByRole('button', { name: '打开导航' })
  if (!(await openButton.isVisible())) {
    throw new Error(`${route.name} 缺少移动端打开导航按钮`)
  }
  await openButton.click()
  await page.getByRole('dialog').waitFor({ state: 'visible', timeout: 3000 })
  await page.getByRole('link', { name: '配置' }).waitFor({ state: 'visible', timeout: 3000 })
  assertNoOverflow(route, await collectOverflow(page))
  await page.getByRole('button', { name: '关闭导航' }).last().click()
}

if (screenshotDir) {
  fs.mkdirSync(screenshotDir, { recursive: true })
}

const browser = await launchBrowser()
try {
  const page = await browser.newPage({ viewport, deviceScaleFactor: 1, isMobile: true })
  page.setDefaultTimeout(10000)

  for (const route of routes) {
    const url = joinUrl(baseUrl, route.path)
    console.log(`Mobile smoke test: ${url}`)
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 })
    await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => undefined)
    await page.waitForTimeout(300)

    const bodyText = await page.locator('body').innerText()
    for (const expected of route.expected) {
      if (!bodyText.includes(expected)) {
        throw new Error(`${route.name} 缺少预期文本: ${expected}`)
      }
    }

    assertNoOverflow(route, await collectOverflow(page))
    await assertMobileNav(page, route)

    if (screenshotDir) {
      await page.screenshot({
        path: path.join(screenshotDir, `${route.name}-${viewport.width}x${viewport.height}.png`),
        fullPage: true,
      })
    }
  }
} finally {
  await browser.close()
}

console.log('Web UI mobile smoke test 通过。')

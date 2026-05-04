#!/usr/bin/env node

const baseUrl = (process.env.G2_TEST_BASE_URL || 'http://127.0.0.1:8787').replace(/\/+$/, '')
const rounds = Number(process.argv[2] || process.env.G2_TEST_ROUNDS || 1)
const tinyJpegBase64 =
  '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////2wBDAf//////////////////////////////////////////////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAGf/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABBQL/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/AV//xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/AV//xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAY/Al//xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/IV//2gAMAwEAAgADAAAAEP/EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQMBAT8QH//EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQIBAT8QH//EABQQAQAAAAAAAAAAAAAAAAAAABD/2gAIAQEAAT8QH//Z'

const tests = [
  {
    name: 'health',
    run: () => getJson('/health'),
    assert: (data) => data.ok === true,
  },
  {
    name: 'asr-status',
    run: () => getJson('/asr/status'),
    assert: (data) => data.available === true && typeof data.message === 'string',
  },
  {
    name: 'trading-overview',
    run: () => getJson('/trading/overview'),
    assert: (data) =>
      data.readOnly === true &&
      data.mode === 'live-readonly' &&
      data.live &&
      !data.live.error &&
      Number(data.live.portsTotal) > 0,
  },
  {
    name: 'openclaw-status',
    run: () => getJson('/openclaw/status'),
    assert: (data) => data.enabled === true && Boolean(data.baseUrl),
  },
  {
    name: 'ask-trading',
    run: () =>
      postJson('/ask', {
        question: '你好天禄，查看一下今天收益和交易机器人运行状态',
        locale: 'zh-CN',
      }),
    assert: (data) => Boolean(data.answer) && !/mock|stub|模拟|占位/i.test(`${data.answer} ${data.provider}`),
  },
  {
    name: 'openclaw-ask',
    run: () =>
      postJson('/openclaw/ask', {
        question: '你好天禄，只读查看交易机器人运行如何',
        locale: 'zh-CN',
      }),
    assert: (data) =>
      Boolean(data.answer) &&
      /^openclaw:/.test(data.provider || '') &&
      !/unavailable|mock|stub|模拟|占位/i.test(`${data.answer} ${data.provider}`),
  },
  {
    name: 'vision',
    run: () =>
      postJson('/vision', {
        imageBase64: tinyJpegBase64,
        mimeType: 'image/jpeg',
        prompt: '请识别这张测试图片；如果画面太小或没有内容，请明确说看不清。',
        locale: 'zh-CN',
      }),
    assert: (data) => Boolean(data.answer) && /^vision:(?!stub)/.test(data.provider),
  },
  {
    name: 'tts',
    run: () =>
      postJson('/tts', {
        text: '天禄测试播报',
        locale: 'zh-CN',
      }),
    assert: (data) => Boolean(data.provider) && !/stub|mock|模拟|占位/i.test(data.provider),
  },
]

const allResults = []
for (let round = 1; round <= rounds; round += 1) {
  console.log(`\nROUND ${round}/${rounds} ${new Date().toISOString()}`)
  for (const test of tests) {
    const started = Date.now()
    try {
      const data = await test.run()
      const passed = test.assert(data)
      const result = {
        round,
        name: test.name,
        ok: passed,
        ms: Date.now() - started,
        summary: summarize(data),
      }
      allResults.push(result)
      console.log(`${passed ? 'PASS' : 'FAIL'} ${test.name} ${result.ms}ms ${result.summary}`)
    } catch (error) {
      const result = {
        round,
        name: test.name,
        ok: false,
        ms: Date.now() - started,
        summary: error instanceof Error ? error.message : String(error),
      }
      allResults.push(result)
      console.log(`FAIL ${test.name} ${result.ms}ms ${result.summary}`)
    }
  }
}

const failed = allResults.filter((item) => !item.ok)
console.log(`\nSUMMARY pass=${allResults.length - failed.length} fail=${failed.length}`)
if (failed.length) process.exitCode = 1

async function getJson(path) {
  const response = await fetch(`${baseUrl}${path}`, {
    headers: { Accept: 'application/json' },
  })
  return readResponse(response)
}

async function postJson(path, body) {
  const response = await fetch(`${baseUrl}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'text/plain;charset=UTF-8', Accept: 'application/json' },
    body: JSON.stringify(body),
  })
  return readResponse(response)
}

async function readResponse(response) {
  const text = await response.text()
  let data
  try {
    data = text ? JSON.parse(text) : {}
  } catch {
    data = { raw: text }
  }
  if (!response.ok) {
    throw new Error(`${response.status} ${summarize(data)}`)
  }
  return data
}

function summarize(data) {
  const raw = JSON.stringify(data)
  return raw.length > 260 ? `${raw.slice(0, 257)}...` : raw
}

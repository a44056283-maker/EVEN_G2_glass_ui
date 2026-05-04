#!/usr/bin/env node
/**
 * 自动递增 package.json 和 app.json 中的版本号（patch 版本）
 * 用法：node scripts/bump-version.js
 */

import { readFileSync, writeFileSync, existsSync } from 'fs'
import { resolve } from 'path'

const rootDir = resolve('.')
const pkgPath = resolve(rootDir, 'package.json')
const appPath = resolve(rootDir, 'app.json')

const pkg = JSON.parse(readFileSync(pkgPath, 'utf-8'))
const [major, minor, patch] = pkg.version.split('.').map(Number)
const newVersion = `${major}.${minor}.${patch + 1}`

// 更新 package.json
pkg.version = newVersion
writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + '\n')

// 更新 app.json
if (existsSync(appPath)) {
  const app = JSON.parse(readFileSync(appPath, 'utf-8'))
  app.version = newVersion
  writeFileSync(appPath, JSON.stringify(app, null, 2) + '\n')
}

console.log(`Version bumped to ${newVersion}`)

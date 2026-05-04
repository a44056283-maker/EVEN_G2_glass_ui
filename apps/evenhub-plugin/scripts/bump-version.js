#!/usr/bin/env node
/**
 * 自动递增 package.json 中的版本号（patch 版本）
 * 用法：node scripts/bump-version.js
 */

import { readFileSync, writeFileSync, existsSync } from 'fs'
import { resolve } from 'path'

const args = process.argv.slice(2)
const pkgPath = existsSync(resolve('package.json')) ? resolve('package.json') : resolve('../package.json')

const pkg = JSON.parse(readFileSync(pkgPath, 'utf-8'))
const [major, minor, patch] = pkg.version.split('.').map(Number)
const newVersion = `${major}.${minor}.${patch + 1}`

pkg.version = newVersion
writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + '\n')

console.log(`Version bumped to ${newVersion}`)

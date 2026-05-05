#!/usr/bin/env node
"use strict";
const fs = require("fs");
const path = require("path");
const { Ajv2020 } = require("ajv/dist/2020");
const addFormats = require("ajv-formats");

const SCHEMA_PATH = path.resolve(__dirname, "../person.schema.json");

function buildValidator() {
  const ajv = new Ajv2020({ strict: true, allErrors: true });
  addFormats(ajv);
  return ajv.compile(JSON.parse(fs.readFileSync(SCHEMA_PATH, "utf8")));
}

function validateFile(filePath, validate) {
  let data;
  try { data = JSON.parse(fs.readFileSync(filePath, "utf8")); }
  catch (e) { return { file: filePath, valid: false, errors: [`JSON parse error: ${e.message}`] }; }
  const valid = validate(data);
  return { file: filePath, valid, errors: valid ? [] : validate.errors.map(e => `${e.instancePath || "/"} ${e.message}`) };
}

function main() {
  const args = process.argv.slice(2);
  if (args.length === 0) { console.error("Usage: node validate-person.js <file-or-dir> [...]"); process.exit(1); }
  const validate = buildValidator();
  const targets = [];
  for (const arg of args) {
    const stat = fs.statSync(arg);
    if (stat.isDirectory()) fs.readdirSync(arg).filter(f => f.endsWith(".json")).forEach(f => targets.push(path.join(arg, f)));
    else targets.push(arg);
  }
  let passed = 0, failed = 0;
  for (const t of targets) {
    const result = validateFile(t, validate);
    if (result.valid) { console.log(`PASS  ${path.basename(t)}`); passed++; }
    else { console.log(`FAIL  ${path.basename(t)}`); result.errors.forEach(e => console.log(`      ${e}`)); failed++; }
  }
  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed > 0 ? 1 : 0);
}
main();

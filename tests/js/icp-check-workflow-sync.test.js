const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { buildWorkflowSource } = require("../../workflows/lib/build-icp-check-workflow.js");

const WORKFLOW = path.join(__dirname, "..", "..", "workflows", "icp-check.workflow.js");

test("committed icp-check.workflow.js equals the generated source (run: node workflows/lib/build-icp-check-workflow.js)", () => {
  assert.equal(fs.readFileSync(WORKFLOW, "utf8"), buildWorkflowSource());
});

test("generated workflow is self-contained and calls runCheck", () => {
  const src = buildWorkflowSource();
  assert.doesNotMatch(src, /\brequire\s*\(/);
  assert.doesNotMatch(src, /^\s*import\s/m);
  assert.doesNotMatch(src, /module\.exports/);
  assert.doesNotMatch(src, /"use strict"/);
  assert.match(src, /export const meta = /);
  assert.match(src, /return await runCheck\(\{ agent, pipeline, args \}\)/);
});

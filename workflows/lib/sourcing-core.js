"use strict";
// ===== sourcing-core: deterministic logic for W3 (single source of truth) =====
// sourcing.workflow.js is GENERATED from this file by build-workflow.js and must
// stay byte-identical (guarded by tests/js/sourcing-workflow-sync.test.js). The
// workflow runtime is sandboxed: no require/import, no Date.now()/Math.random().
// Everything below is therefore pure JS with the agent runtime injected as `env`.

function interpolate(template, data) {
  return String(template == null ? "" : template).replace(/\{\{\s*([\w.]+)\s*\}\}/g, (_, k) => {
    const v = data ? data[k] : undefined;
    return v == null ? "" : String(v);
  });
}

module.exports = { interpolate };

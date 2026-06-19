"use strict";
// Generates the self-contained workflows/icp-check.workflow.js from icp-check-core.js.
// (Dedicated generator; when a 3rd workflow lands, extract a shared workflows/lib/generate.js.)
const fs = require("node:fs");
const path = require("node:path");

const META = {
  name: "icp-check",
  description: "Passe d'alignement au setup : juge un échantillon avec le prompt icpFit (Haiku) et rend les verdicts bruts pour relecture/itération par l'agent de session. Aucune écriture, aucun gate auto.",
  phases: [
    { title: "run", detail: "1 sous-agent icpFit / prospect (Haiku, parité prod) → {qualifie, raison}" },
  ],
};

function buildWorkflowSource() {
  const core = fs.readFileSync(path.join(__dirname, "icp-check-core.js"), "utf8");

  const corePhases = [...new Set([...core.matchAll(/phase:\s*"(\w+)"/g)].map((m) => m[1]))].sort();
  const metaTitles = META.phases.map((p) => p.title).sort();
  if (JSON.stringify(corePhases) !== JSON.stringify(metaTitles)) {
    throw new Error(`META.phases ${JSON.stringify(metaTitles)} out of sync with core phases ${JSON.stringify(corePhases)}`);
  }

  const body = core
    .replace(/^"use strict";\n/, "")
    .replace(/\nmodule\.exports[\s\S]*$/, "\n")
    .trimEnd();
  return [
    "// GENERATED from workflows/lib/icp-check-core.js — do not edit by hand.",
    "// Regenerate: node workflows/lib/build-icp-check-workflow.js   (guarded by tests/js/icp-check-workflow-sync.test.js)",
    `export const meta = ${JSON.stringify(META, null, 2)};`,
    "",
    body,
    "",
    "return await runCheck({ agent, pipeline, args });",
    "",
  ].join("\n");
}

module.exports = { buildWorkflowSource, META };

if (require.main === module) {
  const out = path.join(__dirname, "..", "icp-check.workflow.js");
  fs.writeFileSync(out, buildWorkflowSource());
  process.stdout.write(`wrote ${out}\n`);
}

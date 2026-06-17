const test = require("node:test");
const assert = require("node:assert/strict");
const core = require("../../workflows/lib/sourcing-core.js");

// ---------------------------------------------------------------------------
// interpolate
// ---------------------------------------------------------------------------

test("interpolate fills present tokens", () => {
  assert.equal(
    core.interpolate("Bonjour {{fullName}} de {{companyName}}", { fullName: "A B", companyName: "Acme" }),
    "Bonjour A B de Acme",
  );
});

test("interpolate blanks missing or null tokens", () => {
  assert.equal(core.interpolate("x {{ghost}} y {{nul}} z", { nul: null }), "x  y  z");
});

test("interpolate tolerates inner spaces and leaves plain text", () => {
  assert.equal(core.interpolate("{{ jobTitle }} fixe", { jobTitle: "Gérant" }), "Gérant fixe");
});

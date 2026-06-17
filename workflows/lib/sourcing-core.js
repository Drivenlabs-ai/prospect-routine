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

// ---- schemas (structured agent outputs) ----

const VERDICT_SCHEMA = {
  type: "object", additionalProperties: false,
  properties: {
    qualifie: { type: "boolean", description: "Le prospect correspond-il à l'ICP ?" },
    raison: { type: "string", description: "Justification courte ancrée sur les faits du prospect." },
  },
  required: ["qualifie", "raison"],
};

// ---- lead identity + prompt assembly ----

const PROSPECT_FIELDS = ["fullName", "jobTitle", "companyName", "location", "headline", "summary", "linkedinUrl"];

function leadId(lead) { return (lead && (lead.linkedinUrl || lead.people_db_id)) || ""; }
function leadLabel(lead) { return (lead && lead.fullName) || leadId(lead); }

function prospectBlock(lead) {
  const lines = PROSPECT_FIELDS.filter((k) => lead && lead[k]).map((k) => `- ${k}: ${lead[k]}`);
  return `## Prospect à évaluer\n${lines.join("\n")}`;
}

function buildScorePrompt(icpFitTemplate, lead) {
  return `${interpolate(icpFitTemplate, lead)}\n\n${prospectBlock(lead)}`;
}

// ---- enrich (the only tool-using agent: web research) ----

const ENRICH_SCHEMA = {
  type: "object", additionalProperties: false,
  properties: {
    summary: { type: "string", description: "Synthèse actionnable des trouvailles (1-3 phrases)." },
    signals: { type: "array", items: { type: "string" }, description: "Signaux récents pertinents (déclencheurs, actualités)." },
  },
  required: ["summary"],
};

function buildEnrichPrompt(directive, lead) {
  return [
    "Tu es un agent de recherche. Utilise la recherche web pour enrichir le prospect ci-dessous.",
    directive ? `Directive : ${directive}` : "",
    prospectBlock(lead),
    "Rends une synthèse actionnable (summary) et les signaux récents pertinents (signals). N'invente rien : si une info n'est pas vérifiable, ne la rapporte pas.",
  ].filter(Boolean).join("\n\n");
}

// ---- write (full sequence in one thread) ----

function messagesSchema(sequenceKeys) {
  const properties = {};
  for (const k of sequenceKeys) {
    properties[k] = { type: "string", description: `Message « ${k} » — vouvoiement, prêt à envoyer, sans markdown.` };
  }
  return {
    type: "object", additionalProperties: false,
    properties: { messages: { type: "object", additionalProperties: false, properties, required: [...sequenceKeys] } },
    required: ["messages"],
  };
}

const WRITE_DOCTRINE = [
  "Écris la séquence ENTIÈRE en un seul fil : chaque message prolonge l'angle ouvert par le précédent (tu les reçois tous d'un coup).",
  "Règles dures : vouvoiement, français natif, corps ≤ ~75 mots par message, une seule idée par message,",
  "n'ouvre jamais par une question ni par « je », aucun fait inventé, aucun jargon pompeux (leverage, synergies, game-changer…),",
  "pas de formule cliché (« j'espère que vous allez bien », « je me permets », « pour faire suite »), pas d'emoji, ≤ 1 point d'exclamation, pas de tiret cadratin.",
].join(" ");

function buildWritePrompt({ messagesPrompts, sequenceKeys, lead, context, feedback }) {
  const steps = sequenceKeys
    .map((k, i) => `### Message ${i + 1} — clé \`${k}\`\n${(messagesPrompts && messagesPrompts[k]) || ""}`)
    .join("\n\n");
  const ctx = context
    ? `\n\n## Contexte enrichi (à exploiter, vérifié)\n${context.summary || ""}${(context.signals && context.signals.length) ? `\nSignaux : ${context.signals.join(" · ")}` : ""}`
    : "";
  const fb = feedback
    ? `\n\n## Correction demandée (régénération)\nLa version précédente a été rejetée : ${feedback.notes || "non conforme à la rubrique"}. Corrige et respecte toute la rubrique.`
    : "";
  return `${WRITE_DOCTRINE}\n\n${prospectBlock(lead)}${ctx}\n\n## Étapes à rédiger (dans l'ordre)\n${steps}${fb}\n\nRends un objet { "messages": { ${sequenceKeys.map((k) => `"${k}"`).join(", ")} } }.`;
}

module.exports = {
  interpolate, VERDICT_SCHEMA, leadId, leadLabel, buildScorePrompt,
  ENRICH_SCHEMA, buildEnrichPrompt, messagesSchema, buildWritePrompt,
};

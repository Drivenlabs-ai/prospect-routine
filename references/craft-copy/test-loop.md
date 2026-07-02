# Boucle de test en conditions réelles (référence craft-copy, étape 2)

Chargée pour prouver qu'un changement de fiche améliore vraiment la copy, avant de l'écrire pour de bon. Le test rejoue le **vrai agent d'écriture** (mêmes réglages que la prod) sur des prospects réels, avec l'ancienne et la nouvelle fiche, et affiche les deux versions côte à côte.

## Commandes moteur

Via `uv run python scripts/routine.py <cmd>` (jamais `python3`).

## Le flux

1. **Résoudre** la campagne : `resolve --registry <racine Prospection/campaigns-registry.json> --slug <ce que dit l'utilisateur>` → `campaign_id` + `config_path`. Slug introuvable → demander lequel.
2. **Échantillon frais, sans consommer** : `source --config <config_path> --sample --target <N>` (N ≈ 3-8 selon l'ampleur du changement — quelques prospects pour un ajustement de wording, davantage pour un nouvel angle). `--sample` n'avance pas le curseur et ne contacte personne.
3. **Clés de séquence** : les vraies clés viennent de `verify --config <config_path>` (couverture prompts ↔ séquence). L'agent d'écriture écrit la séquence entière en un fil ; passer **toutes** les clés, pas seulement celle qu'on modifie.
4. **Assembler les deux jeux de fiches** : `prompts_before` = les fiches actuelles (toutes les clés) ; `prompts_after` = les mêmes, la clé éditée remplacée par la nouvelle version. Écrire la nouvelle fiche dans un fichier local **temporaire** à ce stade — la fiche définitive n'est écrite qu'après validation (étape 7).
5. **Lancer le test** : invoquer le workflow `craft-copy-test` avec
   `args = { sample: <candidats de l'étape 2>, sequence_keys: <clés de l'étape 3>, prompts_before, prompts_after, model: <config.models.writing> }`
   → `{ comparisons: [ { id, lead, before, after } ] }`.
6. **Afficher côte à côte** : pour chaque prospect, montrer la version *avant* et la version *après* du (ou des) message(s), face à face, pour comparaison. Laisser l'utilisateur juger sur l'axe qu'il visait. Ne pas parler de score ni de rubrique.
7. **Valider puis écrire** : seulement après l'aval de l'utilisateur, écrire la fiche définitive (`prompts/<clé>.md`), puis `verify --config <config_path>` → couverture toujours verte (zéro `missing_prompts`). Aval refusé → itérer (retour au dialogue, étape 1), rien n'est écrit vers la campagne.

## Gardes

- `source --sample` uniquement : jamais de `load-lead`, jamais de launch — le test ne contacte personne et ne charge aucun lead.
- La fiche définitive n'est écrite qu'après validation ; avant, tout est en fichier temporaire.
- Le test porte sur la longueur aussi : une fiche qui demande du plus long doit produire du plus long dans la version *après* — rien ne le bloque.

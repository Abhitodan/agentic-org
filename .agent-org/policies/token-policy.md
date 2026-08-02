# Token and Cost Policy

- Every workflow carries a Budget object; defaults live in budgets.yaml.
- Model routing: fast class for classification/extraction, standard for
  routine implementation, strong only for architecture/security/complex
  debugging, and only after cheaper attempts fail or impact justifies it.
- Context tiers: Tier 0 identity/policy always; Tier 1 feature brain;
  Tier 2 retrieved repository slices; Tier 3 history and Tier 4 portfolio
  only on explicit justification.
- Never send whole repositories to a model; send the deterministic repo map
  plus retrieved slices.
- Three consecutive experiments without measurable improvement stop the loop.

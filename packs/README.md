# Packs directory

Each subdirectory is a **content pack** (vertical skills + templates + defaults).

```
packs/
  tech-saas/
    pack.yaml
```

Activate with:

```bash
WORKBENCH_PACK=tech-saas   # default
# or customer override:
WORKBENCH_PACK_FILE=data/customers/acme/pack.yaml
# or:
USAGE_CUSTOMER_ID=acme     # → data/customers/acme/pack.yaml if present
```

Disable: `WORKBENCH_PACK=none`.

See `src/cn_social_agent/packs/loader.py`.

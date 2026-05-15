# Apify free-safe setup

This project is configured to start in a free-safe mode for private use.

## What you need

1. Create a free Apify account.
2. Do not add a credit card while testing.
3. Create an API token.
4. Put the token in `.env` as `APIFY_TOKEN=...`.
5. Keep the default budget guard values.

The project uses real Apify API calls. It does not use demo listings.

## Default safety settings

```env
APIFY_BUDGET_GUARD_ENABLED=true
APIFY_MONTHLY_BUDGET_USD=5.00
APIFY_BUDGET_SAFETY_BUFFER_USD=0.10
APIFY_SET_PLATFORM_HARD_LIMIT=true
APIFY_BUDGET_FAIL_CLOSED=true
```

## Default low-volume listing limits

Each source starts with:

```yaml
limit: 5
estimated_cost_usd: 0.05
run_input:
  maxItems: 5
```

With two profiles and two sources per profile, this is at most about 20 returned items per daily run before local filtering.

## What happens when the budget is reached

The agent stops running additional Apify Actors and writes a note in the report. If email sending is enabled, the email includes the warning.

Example warning:

```text
Budget guard stopped collection:
Monthly Apify budget reached. Current usage: $4.95, budget: $5.00.
```

## Recommendation

Start with one manual run:

```bash
python -m app.main --config configs/searches.yaml --profile givatayim_4_rooms_deals --send-email --include-existing
```

Then check the Apify dashboard usage. If the cost is low, enable both profiles in GitHub Actions.

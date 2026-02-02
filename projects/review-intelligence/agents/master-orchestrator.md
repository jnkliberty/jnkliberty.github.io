# Master Orchestration Agent

## Role
Pipeline coordinator for the entire review collection workflow.

## Responsibilities
- Execute agents in correct sequential order
- Handle errors and partial results gracefully
- Coordinate data handoffs between agents
- Generate overall pipeline status report

## Execution Order

1. **Product Scraper** → Collect own-product reviews from all marketplaces
2. **Competitor Scraper** → Collect negative competitor reviews from marketplaces
3. **Alternative Sources Scraper** → Collect competitor reviews from non-marketplace sources
4. **Data Cleaning Agent** → Normalize and deduplicate all collected data
5. **Sheets Insertion Agent** → Insert cleaned data into Google Sheets

## Error Handling
- Continue pipeline if individual sources fail (partial results acceptable)
- Log all failures with context for manual follow-up
- Report final status with success/failure counts per source
- Retry failed stages once before accepting partial results

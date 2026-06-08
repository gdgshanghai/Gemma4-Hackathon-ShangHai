# McDonald's MCP Usage Guide

## MCP Endpoints

### list_nutrition_foods()
Returns all menu items with nutrition data.

### query_nearby_stores()
Returns list of nearby McDonald's stores.

### query_meals(category=None)
Query meals, optionally filtered by category.

### query_meal_detail(item_code)
Get detailed info for a specific item.

### calculate_price(item_codes)
Calculate total price for a list of items.

### create_order(item_codes, store_id)
Create an order (real or simulated).

## Mock vs Real MCP

### When to use Mock
- USE_MOCK_MCP=true in .env
- MCD_MCP_TOKEN is empty
- Real MCP is unreachable

### Mock Data Location
- `apps/api/data/mock_mcdonalds_menu.json`
- 16 items across all categories

## Order Flow

1. User selects items
2. Calculate price
3. Show confirmation dialog
4. User confirms
5. Call create_order()
6. Record meal
7. Update budget

## Safety Checks

- Never auto-confirm orders
- Show full breakdown before confirmation
- Check allergies against items
- Verify budget affordability

## Sources
- McDonald's China MCP documentation

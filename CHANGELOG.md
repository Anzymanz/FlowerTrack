# Changelog

## 0.21
- Highlighted restocked items in the web view and color-coded stock pills by increase/decrease.
- Fixed scraper pagination retry handling to avoid applying partial captures when page fetches fail.
- Added optional restock notifications when items return from out of stock.
- Fixed stock change detection to consider changes in remaining counts.
- Fixed restock summary formatting that prevented notifications from sending.
- Removed duplicate "no changes detected" log entry.
- Split stock notifications into stock, out-of-stock, and restock categories with separate toggles.

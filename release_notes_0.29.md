## Highlights
- Added configurable per-threshold colouring, plus a full Theme tab to customise dark/light palettes.
- Refined tracker visuals with cleaner panel borders, labels, and consistent control outlines.
- Polished scraper and mix UI behavior with smoother window handling and reduced artifacts.
- Improved product naming quality for oils and vapes with richer, more consistent parsed titles.

## Changes
- Added an Origin column to the flower library.
- Standardised tracker panel borders and header/entry/combobox outlines for a cleaner look.
- Added per-threshold colour pickers for stock, remaining-today, days-left, and total-used metrics.
- Introduced a tabbed tracker settings layout, British spelling updates, and improved tab styling.
- Added a Theme tab with editable dark/light palettes and a reset to defaults.
- Replaced the OS colour picker with a themed in-app picker and added Copy/Paste for hex values.
- Reduced settings window dead space and improved tab/palette refresh handling.
- Added flower/oil/vape capture filters and refined scraper settings layout and borders.
- Added capture-tab reset plus Get auth token action.
- Improved auth bootstrap handling when creds/org are missing.
- Reduced window flicker on scraper and mix calculator opens.
- Remember mixed dose/stock window sizes across launches.
- Ensured scraper log window visibility re-applies after saves and window shows.
- Made the Flower Browser Removed badge clickable so users can dismiss removed highlighting per card.
- Added generalized oil naming rules from product text (Balance, Txx, TxxCyy profiles).
- Appended generated oil profile names to useful existing oil names while ignoring placeholder names like "oil".
- Updated vape parsing to prefer richer descriptive product titles over shorthand API codes.

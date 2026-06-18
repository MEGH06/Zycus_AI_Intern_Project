# Analytics Dashboard

## Overview

The Analytics Dashboard provides real-time and historical reporting across procurement spend categories.

## Known Performance Issues

Large date-range queries (more than 90 days) may experience slow load times due to unindexed aggregate scans. The engineering team has a fix scheduled for Q1 2025.

**Workaround:** Limit date ranges to 30-day windows or use the Export feature for bulk data.

## Supported Browsers

Chrome 110+, Firefox 115+, Edge 110+. Safari has known rendering issues with pivot tables.

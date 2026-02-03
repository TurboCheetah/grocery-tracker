"""Analytics and intelligence for Grocery Tracker."""

import calendar
import math
from collections import defaultdict
from datetime import date, timedelta

from .data_store import DataStore
from .models import (
    BudgetTracking,
    CategoryBudget,
    CategorySpending,
    FrequencyData,
    OutOfStockRecord,
    PriceComparison,
    SeasonalMonth,
    SeasonalPattern,
    SpendingSummary,
    Suggestion,
    WasteReason,
    WasteRecord,
)


class Analytics:
    """Provides spending analytics, frequency analysis, and smart suggestions."""

    def __init__(self, data_store: DataStore | None = None):
        self.data_store = data_store or DataStore()

    def spending_summary(
        self,
        period: str = "monthly",
        budget_limit: float | None = None,
    ) -> SpendingSummary:
        """Generate spending summary for a period.

        Args:
            period: "weekly", "monthly", or "yearly"
            budget_limit: Optional budget limit to compare against

        Returns:
            SpendingSummary with breakdown
        """
        today = date.today()

        if period == "weekly":
            start_date = today - timedelta(days=today.weekday())
        elif period == "yearly":
            start_date = today.replace(month=1, day=1)
        else:  # monthly
            start_date = today.replace(day=1)

        receipts = self.data_store.list_receipts()

        # Filter to period
        period_receipts = [r for r in receipts if start_date <= r.transaction_date <= today]

        total_spending = sum(r.total for r in period_receipts)
        total_items = sum(len(r.line_items) for r in period_receipts)

        # Category breakdown from price history and list items
        category_totals: dict[str, float] = defaultdict(float)
        category_counts: dict[str, int] = defaultdict(int)

        for receipt in period_receipts:
            for item in receipt.line_items:
                # Try to find category from list
                cat = self._guess_category(item.item_name)
                category_totals[cat] += item.total_price
                category_counts[cat] += 1

        categories = []
        for cat, total in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
            pct = (total / total_spending * 100) if total_spending > 0 else 0
            categories.append(
                CategorySpending(
                    category=cat,
                    total=round(total, 2),
                    percentage=round(pct, 1),
                    item_count=category_counts[cat],
                )
            )

        budget_remaining = None
        budget_percentage = None
        if budget_limit is not None and budget_limit > 0:
            budget_remaining = round(budget_limit - total_spending, 2)
            budget_percentage = round(total_spending / budget_limit * 100, 1)

        return SpendingSummary(
            period=period,
            start_date=start_date,
            end_date=today,
            total_spending=round(total_spending, 2),
            receipt_count=len(period_receipts),
            item_count=total_items,
            categories=categories,
            budget_limit=budget_limit,
            budget_remaining=budget_remaining,
            budget_percentage=budget_percentage,
        )

    def price_comparison(self, item_name: str) -> PriceComparison | None:
        """Compare prices for an item across stores.

        Args:
            item_name: Item to compare

        Returns:
            PriceComparison or None if no data
        """
        history = self.data_store.load_price_history()

        if item_name not in history:
            # Try case-insensitive match
            for key in history:
                if key.lower() == item_name.lower():
                    item_name = key
                    break
            else:
                return None

        stores: dict[str, float] = {}
        for store_name, ph in history[item_name].items():
            if ph.current_price is not None:
                stores[store_name] = ph.current_price

        if not stores:
            return None

        cheapest_store = min(stores, key=stores.get)  # type: ignore[arg-type]
        cheapest_price = stores[cheapest_store]
        most_expensive = max(stores.values())
        savings = round(most_expensive - cheapest_price, 2) if len(stores) > 1 else 0.0

        return PriceComparison(
            item_name=item_name,
            stores=stores,
            cheapest_store=cheapest_store,
            cheapest_price=cheapest_price,
            savings=savings,
        )

    def get_suggestions(self) -> list[Suggestion]:
        """Generate smart shopping suggestions.

        Returns:
            List of Suggestion objects
        """
        suggestions: list[Suggestion] = []

        # Restock suggestions from frequency data
        frequency = self.data_store.load_frequency_data()
        for item_name, freq in frequency.items():
            avg = freq.average_days_between_purchases
            days_since = freq.days_since_last_purchase
            if avg is not None and days_since is not None:
                if days_since >= avg:
                    overdue = days_since - avg
                    priority = "high" if overdue > avg * 0.5 else "medium"
                    suggestions.append(
                        Suggestion(
                            type="restock",
                            item_name=item_name,
                            message=(
                                f"Usually buy every {avg:.0f} days, "
                                f"last purchase {days_since} days ago"
                            ),
                            priority=priority,
                            data={
                                "average_interval": avg,
                                "days_since": days_since,
                                "last_purchased": freq.last_purchased.isoformat()
                                if freq.last_purchased
                                else None,
                            },
                        )
                    )

        # Seasonal purchase suggestions
        today = date.today()
        current_month = calendar.month_name[today.month]
        seasonal_threshold_days = 30
        for item_name, freq in frequency.items():
            pattern = self._build_seasonal_pattern(freq)
            if not pattern or pattern.year_round:
                continue
            if pattern.confidence == "low":
                continue
            if current_month not in pattern.peak_months:
                continue

            last_purchased = freq.last_purchased
            if last_purchased is None:
                continue
            days_since = (today - last_purchased).days
            if days_since < seasonal_threshold_days:
                continue

            season_label = pattern.season_range or ", ".join(pattern.peak_months) or "in season"

            suggestions.append(
                Suggestion(
                    type="seasonal",
                    item_name=item_name,
                    message=(
                        f"Typically bought {season_label}; last purchase {days_since} days ago"
                    ),
                    priority="low",
                    data={
                        "season_range": pattern.season_range,
                        "peak_months": pattern.peak_months,
                        "last_purchased": last_purchased.isoformat(),
                        "days_since": days_since,
                        "current_month": current_month,
                    },
                )
            )

        # Price alert suggestions
        history = self.data_store.load_price_history()
        for item_name, stores in history.items():
            for store_name, ph in stores.items():
                if len(ph.price_points) >= 3:
                    current = ph.current_price
                    avg = ph.average_price
                    if current is not None and avg is not None:
                        change_pct = (current - avg) / avg * 100
                        if change_pct >= 15:
                            suggestions.append(
                                Suggestion(
                                    type="price_alert",
                                    item_name=item_name,
                                    message=(
                                        f"Price at {store_name} is "
                                        f"${current:.2f} ({change_pct:+.0f}% vs avg ${avg:.2f})"
                                    ),
                                    priority="medium",
                                    data={
                                        "store": store_name,
                                        "current_price": current,
                                        "average_price": avg,
                                        "change_percent": round(change_pct, 1),
                                    },
                                )
                            )

        # Out-of-stock pattern suggestions
        oos_records = self.data_store.load_out_of_stock()
        oos_counts: dict[tuple[str, str], int] = defaultdict(int)
        for record in oos_records:
            oos_counts[(record.item_name, record.store)] += 1

        for (item_name, store), count in oos_counts.items():
            if count >= 2:
                suggestions.append(
                    Suggestion(
                        type="out_of_stock",
                        item_name=item_name,
                        message=f"Out of stock {count} times at {store}",
                        priority="low",
                        data={"store": store, "count": count},
                    )
                )

        # Sort: high priority first
        priority_order = {"high": 0, "medium": 1, "low": 2}
        suggestions.sort(key=lambda s: priority_order.get(s.priority, 1))

        return suggestions

    def record_out_of_stock(
        self,
        item_name: str,
        store: str,
        substitution: str | None = None,
        reported_by: str | None = None,
    ) -> OutOfStockRecord:
        """Record an item as out of stock.

        Args:
            item_name: Item that was out of stock
            store: Store where it was out of stock
            substitution: What was bought instead (if anything)
            reported_by: Who reported it

        Returns:
            The created OutOfStockRecord
        """
        record = OutOfStockRecord(
            item_name=item_name,
            store=store,
            substitution=substitution,
            reported_by=reported_by,
        )
        self.data_store.add_out_of_stock(record)
        return record

    def get_frequency_summary(self, item_name: str) -> FrequencyData | None:
        """Get purchase frequency data for an item.

        Args:
            item_name: Item name

        Returns:
            FrequencyData or None
        """
        return self.data_store.get_frequency(item_name)

    def get_seasonal_pattern(self, item_name: str) -> SeasonalPattern | None:
        """Get seasonal purchase patterns for an item.

        Args:
            item_name: Item name

        Returns:
            SeasonalPattern or None if insufficient data
        """
        freq = self._get_frequency_case_insensitive(item_name)
        if not freq:
            return None
        return self._build_seasonal_pattern(freq)

    def get_seasonal_patterns(self) -> list[SeasonalPattern]:
        """Get seasonal purchase patterns for all items."""
        patterns: list[SeasonalPattern] = []
        for freq in self.data_store.load_frequency_data().values():
            pattern = self._build_seasonal_pattern(freq)
            if pattern:
                patterns.append(pattern)

        return sorted(
            patterns,
            key=lambda p: (-p.total_purchases, p.item_name.lower()),
        )

    def update_frequency_from_receipt(self, receipt) -> None:
        """Update frequency data from a processed receipt.

        Args:
            receipt: A Receipt object
        """
        for item in receipt.line_items:
            cat = self._guess_category(item.item_name)
            self.data_store.update_frequency(
                item_name=item.item_name,
                purchase_date=receipt.transaction_date,
                quantity=item.quantity,
                store=receipt.store_name,
                category=cat,
            )

    def _get_frequency_case_insensitive(self, item_name: str) -> FrequencyData | None:
        """Fetch frequency data with case-insensitive fallback."""
        freq = self.data_store.get_frequency(item_name)
        if freq is not None:
            return freq

        all_frequency = self.data_store.load_frequency_data()
        for key, value in all_frequency.items():
            if key.lower() == item_name.lower():
                return value
        return None

    def _build_seasonal_pattern(self, freq: FrequencyData) -> SeasonalPattern | None:
        """Build seasonal pattern data from frequency records."""
        if not freq.purchase_history:
            return None

        month_counts: dict[int, int] = {month: 0 for month in range(1, 13)}
        for record in freq.purchase_history:
            month_counts[record.date.month] += 1

        total_purchases = sum(month_counts.values())
        if total_purchases == 0:
            return None

        months_with_purchases = sorted(
            [month for month, count in month_counts.items() if count > 0]
        )
        max_count = max(month_counts.values())
        threshold = max(1, math.ceil(max_count * 0.6))
        peak_month_numbers = sorted(
            [month for month, count in month_counts.items() if count >= threshold and count > 0]
        )

        year_round = len(months_with_purchases) >= 9
        season_range = (
            "Year-round"
            if year_round
            else self._format_season_range(peak_month_numbers, month_counts)
        )

        months = [
            SeasonalMonth(
                month=month,
                month_name=calendar.month_name[month],
                purchase_count=month_counts[month],
                percentage=round(month_counts[month] / total_purchases * 100, 1),
            )
            for month in months_with_purchases
        ]

        return SeasonalPattern(
            item_name=freq.item_name,
            total_purchases=total_purchases,
            months=months,
            peak_months=[calendar.month_name[m] for m in peak_month_numbers],
            season_range=season_range,
            year_round=year_round,
            confidence=self._confidence_from_count(total_purchases),
        )

    def _format_season_range(
        self, peak_month_numbers: list[int], month_counts: dict[int, int]
    ) -> str | None:
        """Format a season range from peak months."""
        if not peak_month_numbers:
            return None

        groups = self._group_consecutive_months(peak_month_numbers)
        if not groups:
            return None

        def group_score(group: list[int]) -> tuple[int, int, int]:
            return (
                sum(month_counts[month] for month in group),
                len(group),
                -group[0],
            )

        best_group = max(groups, key=group_score)
        start_name = calendar.month_name[best_group[0]]
        end_name = calendar.month_name[best_group[-1]]
        if start_name == end_name:
            return start_name
        return f"{start_name}-{end_name}"

    def _group_consecutive_months(self, months: list[int]) -> list[list[int]]:
        """Group consecutive months into ranges."""
        if not months:
            return []

        sorted_months = sorted(set(months))
        groups: list[list[int]] = [[sorted_months[0]]]
        for month in sorted_months[1:]:
            if month == groups[-1][-1] + 1:
                groups[-1].append(month)
            else:
                groups.append([month])
        return groups

    def _confidence_from_count(self, count: int) -> str:
        """Confidence level based on total purchase count."""
        if count >= 10:
            return "high"
        if count >= 5:
            return "medium"
        return "low"

    def _guess_category(self, item_name: str) -> str:
        """Guess category from item name. Simple heuristic."""
        name = item_name.lower()

        produce = [
            "banana",
            "apple",
            "avocado",
            "tomato",
            "lettuce",
            "onion",
            "potato",
            "carrot",
            "pepper",
            "strawberr",
            "blueberr",
            "orange",
            "lemon",
            "lime",
            "grape",
            "mango",
            "pear",
            "celery",
            "broccoli",
            "spinach",
            "kale",
            "cucumber",
            "garlic",
            "ginger",
            "mushroom",
            "corn",
            "bean",
            "pea",
        ]
        dairy = ["milk", "cheese", "yogurt", "butter", "cream", "egg"]
        meat = [
            "chicken",
            "beef",
            "pork",
            "turkey",
            "fish",
            "salmon",
            "shrimp",
            "steak",
            "bacon",
            "sausage",
            "ham",
        ]
        bakery = [
            "bread",
            "bagel",
            "muffin",
            "roll",
            "cake",
            "donut",
            "croissant",
            "tortilla",
            "bun",
        ]
        frozen = ["frozen", "ice cream", "pizza"]
        beverages = ["juice", "soda", "water", "coffee", "tea", "wine", "beer", "kombucha"]
        snacks = [
            "chips",
            "cookie",
            "cracker",
            "popcorn",
            "pretzel",
            "candy",
            "chocolate",
            "granola bar",
            "nut",
        ]
        pantry = [
            "rice",
            "pasta",
            "sauce",
            "oil",
            "vinegar",
            "sugar",
            "flour",
            "salt",
            "spice",
            "cereal",
            "oat",
            "can",
            "soup",
            "broth",
        ]

        categories = [
            (produce, "Produce"),
            (dairy, "Dairy & Eggs"),
            (meat, "Meat & Seafood"),
            (bakery, "Bakery"),
            (frozen, "Frozen Foods"),
            (beverages, "Beverages"),
            (snacks, "Snacks"),
            (pantry, "Pantry & Canned Goods"),
        ]

        for keywords, category in categories:
            for kw in keywords:
                if kw in name:
                    return category

        return "Other"

    # --- Waste Analytics ---

    def log_waste(
        self,
        item_name: str,
        quantity: float = 1.0,
        unit: str | None = None,
        reason: WasteReason = WasteReason.OTHER,
        estimated_cost: float | None = None,
        original_purchase_date: date | None = None,
        logged_by: str | None = None,
    ) -> WasteRecord:
        """Log a food waste event.

        Args:
            item_name: Item that was wasted
            quantity: Amount wasted
            unit: Unit of measurement
            reason: Why it was wasted
            estimated_cost: Estimated dollar value
            original_purchase_date: When it was bought
            logged_by: Who logged it

        Returns:
            The created WasteRecord
        """
        record = WasteRecord(
            item_name=item_name,
            quantity=quantity,
            unit=unit,
            reason=reason,
            estimated_cost=estimated_cost,
            original_purchase_date=original_purchase_date,
            logged_by=logged_by,
        )
        self.data_store.add_waste_record(record)
        return record

    def waste_summary(self, period: str = "monthly") -> dict:
        """Summarize waste for a period.

        Args:
            period: "weekly", "monthly", or "yearly"

        Returns:
            Dict with waste summary data
        """
        today = date.today()

        if period == "weekly":
            start_date = today - timedelta(days=today.weekday())
        elif period == "yearly":
            start_date = today.replace(month=1, day=1)
        else:
            start_date = today.replace(day=1)

        records = self.data_store.load_waste_log()
        period_records = [r for r in records if start_date <= r.waste_logged_date <= today]

        total_cost = sum(r.estimated_cost or 0.0 for r in period_records)
        total_items = len(period_records)

        # Breakdown by reason
        by_reason: dict[str, int] = defaultdict(int)
        for r in period_records:
            by_reason[r.reason.value] += 1

        # Most wasted items
        item_counts: dict[str, int] = defaultdict(int)
        for r in period_records:
            item_counts[r.item_name] += 1

        most_wasted = sorted(item_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "period": period,
            "start_date": start_date.isoformat(),
            "end_date": today.isoformat(),
            "total_items_wasted": total_items,
            "total_cost": round(total_cost, 2),
            "by_reason": dict(by_reason),
            "most_wasted": [{"item": item, "count": count} for item, count in most_wasted],
        }

    def waste_insights(self) -> list[str]:
        """Generate waste reduction insights.

        Returns:
            List of insight messages
        """
        insights = []
        records = self.data_store.load_waste_log()

        if not records:
            return insights

        # Find items wasted multiple times
        item_counts: dict[str, int] = defaultdict(int)
        item_costs: dict[str, float] = defaultdict(float)
        for r in records:
            item_counts[r.item_name] += 1
            item_costs[r.item_name] += r.estimated_cost or 0.0

        for item, count in item_counts.items():
            if count >= 3:
                cost = item_costs[item]
                insights.append(
                    f"You've wasted {item} {count} times"
                    + (f" (${cost:.2f} total)" if cost > 0 else "")
                    + " — consider buying less"
                )
            elif count >= 2:
                insights.append(f"{item} wasted {count} times — buy smaller quantities?")

        # Most common reason
        reason_counts: dict[str, int] = defaultdict(int)
        for r in records:
            reason_counts[r.reason.value] += 1

        if reason_counts:
            top_reason = max(reason_counts, key=reason_counts.get)  # type: ignore[arg-type]
            if top_reason == "spoiled" and reason_counts[top_reason] >= 3:
                insights.append(
                    f"{reason_counts[top_reason]} items spoiled — "
                    "check fridge temperature or buy less perishables"
                )

        return insights

    # --- Budget Tracking ---

    def get_budget_status(self, month: str | None = None) -> BudgetTracking | None:
        """Get budget tracking for a month, auto-calculating spent amounts.

        Args:
            month: YYYY-MM format. Defaults to current month.

        Returns:
            BudgetTracking with current spending, or None if no budget set
        """
        if month is None:
            month = date.today().strftime("%Y-%m")

        budget = self.data_store.load_budget(month)
        if budget is None:
            return None

        # Calculate actual spending from receipts
        summary = self.spending_summary(period="monthly")
        budget.total_spent = summary.total_spending

        # Update category spending
        cat_spending: dict[str, float] = {}
        for cat in summary.categories:
            cat_spending[cat.category] = cat.total

        for cat_budget in budget.category_budgets:
            cat_budget.spent = cat_spending.get(cat_budget.category, 0.0)

        return budget

    def set_budget(
        self,
        monthly_limit: float,
        category_limits: dict[str, float] | None = None,
        month: str | None = None,
    ) -> BudgetTracking:
        """Set budget for a month.

        Args:
            monthly_limit: Total monthly budget
            category_limits: Optional per-category limits
            month: YYYY-MM format. Defaults to current month.

        Returns:
            Created BudgetTracking
        """
        if month is None:
            month = date.today().strftime("%Y-%m")

        cat_budgets = []
        if category_limits:
            for cat, limit in category_limits.items():
                cat_budgets.append(CategoryBudget(category=cat, limit=limit))

        budget = BudgetTracking(
            month=month,
            monthly_limit=monthly_limit,
            category_budgets=cat_budgets,
        )

        self.data_store.save_budget(budget)
        return budget

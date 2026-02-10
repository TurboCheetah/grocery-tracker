"""Analytics and intelligence for Grocery Tracker."""

from collections import defaultdict
from datetime import date, timedelta

from .data_store import DataStore
from .item_normalizer import canonical_item_display_name, normalize_item_name
from .models import (
    BudgetTracking,
    CategoryBudget,
    CategoryInflation,
    CategorySpending,
    FrequencyData,
    OutOfStockRecord,
    PriceComparison,
    PricePoint,
    PurchaseRecord,
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
        period_receipts = [
            r
            for r in receipts
            if start_date <= r.transaction_date <= today
        ]

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

        category_inflation = self._calculate_category_inflation(
            period_receipts=period_receipts,
            start_date=start_date,
            end_date=today,
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
            category_inflation=category_inflation,
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
        canonical_target = normalize_item_name(item_name)
        matched_keys = [
            key for key in history if normalize_item_name(key) == canonical_target
        ]

        if not matched_keys:
            return None

        display_name = self._choose_display_name(item_name, matched_keys)

        latest_by_store: dict[str, PricePoint] = {}
        all_price_points: list[PricePoint] = []
        for key in matched_keys:
            for store_name, ph in history[key].items():
                all_price_points.extend(ph.price_points)
                latest = self._latest_price_point(ph.price_points)
                if latest is None:
                    continue
                if (
                    store_name not in latest_by_store
                    or latest.date > latest_by_store[store_name].date
                ):
                    latest_by_store[store_name] = latest

        stores = {store: pp.price for store, pp in latest_by_store.items()}
        if not stores:
            return None

        cheapest_store = min(stores, key=stores.get)  # type: ignore[arg-type]
        cheapest_price = stores[cheapest_store]
        most_expensive = max(stores.values())
        savings = round(most_expensive - cheapest_price, 2) if len(stores) > 1 else 0.0

        average_30d = self._average_for_window(all_price_points, 30)
        average_90d = self._average_for_window(all_price_points, 90)

        delta_30d = None
        if average_30d and average_30d > 0:
            delta_30d = round((cheapest_price - average_30d) / average_30d * 100, 1)

        delta_90d = None
        if average_90d and average_90d > 0:
            delta_90d = round((cheapest_price - average_90d) / average_90d * 100, 1)

        return PriceComparison(
            item_name=display_name,
            stores=stores,
            cheapest_store=cheapest_store,
            cheapest_price=cheapest_price,
            savings=savings,
            average_price_30d=average_30d,
            average_price_90d=average_90d,
            delta_vs_30d_pct=delta_30d,
            delta_vs_90d_pct=delta_90d,
        )

    def get_suggestions(self) -> list[Suggestion]:
        """Generate smart shopping suggestions.

        Returns:
            List of Suggestion objects
        """
        suggestions: list[Suggestion] = []

        # Restock suggestions from frequency data
        frequency = self.data_store.load_frequency_data()
        grouped_frequency = self._group_frequency_data(frequency)
        for canonical_name, grouped in grouped_frequency.items():
            avg = self._average_days_between(grouped["purchase_history"])
            last_purchase = self._last_purchase_date(grouped["purchase_history"])
            if avg is None or last_purchase is None:
                continue

            days_since = (date.today() - last_purchase).days
            if days_since < avg:
                continue

            overdue = days_since - avg
            priority = "high" if overdue > avg * 0.5 else "medium"
            suggestions.append(
                Suggestion(
                    type="restock",
                    item_name=(
                        grouped["display_name"]
                        or canonical_item_display_name(canonical_name)
                    ),
                    message=(
                        f"Usually buy every {avg:.0f} days, "
                        f"last purchase {days_since} days ago"
                    ),
                    priority=priority,
                    data={
                        "average_interval": avg,
                        "days_since": days_since,
                        "last_purchased": last_purchase.isoformat(),
                    },
                )
            )

        # Price alert suggestions
        history = self.data_store.load_price_history()
        grouped_history = self._group_price_history(history)
        for _, item_data in grouped_history.items():
            display_name = item_data["display_name"]
            for store_name, price_points in item_data["stores"].items():
                if len(price_points) < 3:
                    continue

                latest = self._latest_price_point(price_points)
                if latest is None:
                    continue

                avg_price = sum(pp.price for pp in price_points) / len(price_points)
                if avg_price <= 0:
                    continue

                change_pct = (latest.price - avg_price) / avg_price * 100
                if change_pct >= 15:
                    suggestions.append(
                        Suggestion(
                            type="price_alert",
                            item_name=display_name,
                            message=(
                                f"Price at {store_name} is "
                                f"${latest.price:.2f} ({change_pct:+.0f}% vs avg ${avg_price:.2f})"
                            ),
                            priority="medium",
                            data={
                                "store": store_name,
                                "current_price": latest.price,
                                "average_price": round(avg_price, 2),
                                "change_percent": round(change_pct, 1),
                            },
                        )
                    )

        # Out-of-stock pattern suggestions
        oos_records = self.data_store.load_out_of_stock()
        oos_counts: dict[tuple[str, str], int] = defaultdict(int)
        oos_display_names: dict[str, str] = {}
        for record in oos_records:
            canonical_item = normalize_item_name(record.item_name)
            if canonical_item not in oos_display_names:
                oos_display_names[canonical_item] = record.item_name
            oos_counts[(canonical_item, record.store)] += 1

        for (canonical_item, store), count in oos_counts.items():
            if count >= 2:
                suggestions.append(
                    Suggestion(
                        type="out_of_stock",
                        item_name=oos_display_names.get(
                            canonical_item,
                            canonical_item_display_name(canonical_item),
                        ),
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
        frequency = self.data_store.load_frequency_data()
        canonical_target = normalize_item_name(item_name)
        matching = [
            freq
            for key, freq in frequency.items()
            if normalize_item_name(key) == canonical_target
        ]

        if not matching:
            return None

        combined_history: list[PurchaseRecord] = []
        category = "Other"
        display_name = matching[0].item_name
        for freq in matching:
            combined_history.extend(freq.purchase_history)
            if category == "Other" and freq.category != "Other":
                category = freq.category

        return FrequencyData(
            item_name=display_name,
            category=category,
            purchase_history=sorted(combined_history, key=lambda p: p.date),
        )

    def update_frequency_from_receipt(self, receipt) -> None:
        """Update frequency data from a processed receipt.

        Args:
            receipt: A Receipt object
        """
        for item in receipt.line_items:
            canonical_name = canonical_item_display_name(item.item_name)
            cat = self._guess_category(item.item_name)
            self.data_store.update_frequency(
                item_name=canonical_name,
                purchase_date=receipt.transaction_date,
                quantity=item.quantity,
                store=receipt.store_name,
                category=cat,
            )

    def _calculate_category_inflation(
        self,
        period_receipts: list,
        start_date: date,
        end_date: date,
    ) -> list[CategoryInflation]:
        """Calculate category-level price inflation within a period."""
        total_days = (end_date - start_date).days
        if total_days < 1 or not period_receipts:
            return []

        midpoint = start_date + timedelta(days=total_days // 2)
        baseline_start = start_date
        baseline_end = midpoint
        current_start = min(end_date, midpoint + timedelta(days=1))
        current_end = end_date

        category_prices: dict[str, dict[str, list[float]]] = defaultdict(
            lambda: {"baseline": [], "current": []}
        )

        for receipt in period_receipts:
            period_key = "baseline" if receipt.transaction_date <= midpoint else "current"
            for item in receipt.line_items:
                if item.unit_price <= 0:
                    continue
                category = self._guess_category(item.item_name)
                category_prices[category][period_key].append(item.unit_price)

        inflation: list[CategoryInflation] = []
        for category, windows in category_prices.items():
            baseline_prices = windows["baseline"]
            current_prices = windows["current"]
            if not baseline_prices or not current_prices:
                continue

            baseline_avg = round(sum(baseline_prices) / len(baseline_prices), 2)
            current_avg = round(sum(current_prices) / len(current_prices), 2)
            delta_pct = None
            if baseline_avg > 0:
                delta_pct = round((current_avg - baseline_avg) / baseline_avg * 100, 1)

            inflation.append(
                CategoryInflation(
                    category=category,
                    baseline_start=baseline_start,
                    baseline_end=baseline_end,
                    current_start=current_start,
                    current_end=current_end,
                    baseline_avg_price=baseline_avg,
                    current_avg_price=current_avg,
                    delta_pct=delta_pct,
                    baseline_samples=len(baseline_prices),
                    current_samples=len(current_prices),
                )
            )

        return sorted(
            inflation,
            key=lambda entry: abs(entry.delta_pct) if entry.delta_pct is not None else -1,
            reverse=True,
        )

    def _group_frequency_data(self, frequency_data: dict[str, FrequencyData]) -> dict[str, dict]:
        grouped: dict[str, dict] = {}
        for item_name, freq in frequency_data.items():
            canonical = normalize_item_name(item_name)
            if canonical not in grouped:
                grouped[canonical] = {
                    "display_name": item_name,
                    "purchase_history": [],
                }
            grouped[canonical]["purchase_history"].extend(freq.purchase_history)
        return grouped

    def _group_price_history(self, history_data: dict) -> dict[str, dict]:
        grouped: dict[str, dict] = {}
        for item_name, stores in history_data.items():
            canonical = normalize_item_name(item_name)
            if canonical not in grouped:
                grouped[canonical] = {"display_name": item_name, "stores": defaultdict(list)}

            for store_name, price_history in stores.items():
                grouped[canonical]["stores"][store_name].extend(price_history.price_points)

        return grouped

    def _choose_display_name(self, queried_name: str, matched_keys: list[str]) -> str:
        for key in matched_keys:
            if key.lower() == queried_name.lower():
                return key
        return matched_keys[0]

    def _latest_price_point(self, points: list[PricePoint]) -> PricePoint | None:
        if not points:
            return None
        return max(points, key=lambda point: point.date)

    def _average_for_window(self, points: list[PricePoint], days: int) -> float | None:
        if not points:
            return None
        cutoff = date.today() - timedelta(days=days - 1)
        window_prices = [pp.price for pp in points if pp.date >= cutoff]
        if not window_prices:
            return None
        return round(sum(window_prices) / len(window_prices), 2)

    def _average_days_between(self, purchases: list[PurchaseRecord]) -> float | None:
        if len(purchases) < 2:
            return None
        dates = sorted(p.date for p in purchases)
        intervals = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
        return sum(intervals) / len(intervals)

    def _last_purchase_date(self, purchases: list[PurchaseRecord]) -> date | None:
        if not purchases:
            return None
        return max(p.date for p in purchases)

    def _guess_category(self, item_name: str) -> str:
        """Guess category from item name. Simple heuristic."""
        name = item_name.lower()

        produce = ["banana", "apple", "avocado", "tomato", "lettuce", "onion",
                    "potato", "carrot", "pepper", "strawberr", "blueberr",
                    "orange", "lemon", "lime", "grape", "mango", "pear",
                    "celery", "broccoli", "spinach", "kale", "cucumber",
                    "garlic", "ginger", "mushroom", "corn", "bean", "pea"]
        dairy = ["milk", "cheese", "yogurt", "butter", "cream", "egg"]
        meat = ["chicken", "beef", "pork", "turkey", "fish", "salmon",
                "shrimp", "steak", "bacon", "sausage", "ham"]
        bakery = ["bread", "bagel", "muffin", "roll", "cake", "donut",
                  "croissant", "tortilla", "bun"]
        frozen = ["frozen", "ice cream", "pizza"]
        beverages = ["juice", "soda", "water", "coffee", "tea", "wine",
                     "beer", "kombucha"]
        snacks = ["chips", "cookie", "cracker", "popcorn", "pretzel",
                  "candy", "chocolate", "granola bar", "nut"]
        pantry = ["rice", "pasta", "sauce", "oil", "vinegar", "sugar",
                  "flour", "salt", "spice", "cereal", "oat", "can",
                  "soup", "broth"]

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
        period_records = [
            r for r in records
            if start_date <= r.waste_logged_date <= today
        ]

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
                insights.append(
                    f"{item} wasted {count} times — buy smaller quantities?"
                )

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

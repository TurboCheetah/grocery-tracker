"""Analytics and intelligence for Grocery Tracker."""

from collections import defaultdict
from datetime import date, timedelta

from .data_store import DataStore
from .models import (
    BudgetTracking,
    CategoryBudget,
    CategorySpending,
    Deal,
    DealType,
    FrequencyData,
    OutOfStockRecord,
    PriceComparison,
    SavingsRecord,
    SavingsSummary,
    SavingsType,
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

    # --- Deals & Savings Tracking ---

    def add_deal(
        self,
        item_name: str,
        store: str,
        deal_type: DealType = DealType.SALE,
        regular_price: float | None = None,
        deal_price: float | None = None,
        discount_amount: float | None = None,
        discount_percent: float | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        coupon_code: str | None = None,
        source: str | None = None,
        notes: str | None = None,
    ) -> Deal:
        """Create and store a coupon/sale deal."""
        deal = Deal(
            item_name=item_name,
            store=store,
            deal_type=deal_type,
            regular_price=regular_price,
            deal_price=deal_price,
            discount_amount=discount_amount,
            discount_percent=discount_percent,
            start_date=start_date,
            end_date=end_date,
            coupon_code=coupon_code,
            source=source,
            notes=notes,
        )
        self.data_store.add_deal(deal)
        return deal

    def redeem_deal(
        self,
        deal_id: str,
        quantity: float = 1.0,
        redeemed_date: date | None = None,
        savings_override: float | None = None,
        regular_price: float | None = None,
        paid_price: float | None = None,
        notes: str | None = None,
    ) -> tuple[Deal, SavingsRecord]:
        """Redeem a deal and record savings."""
        deal = self.data_store.get_deal(deal_id)
        if deal is None:
            raise ValueError(f"Deal not found: {deal_id}")
        if deal.redeemed:
            raise ValueError(f"Deal already redeemed: {deal_id}")

        redeem_date = redeemed_date or date.today()

        if savings_override is not None:
            total_savings = savings_override
        else:
            effective_regular = regular_price if regular_price is not None else deal.regular_price
            effective_paid = paid_price if paid_price is not None else deal.deal_price

            savings_per_unit = None
            if effective_regular is not None and effective_paid is not None:
                savings_per_unit = effective_regular - effective_paid
            else:
                savings_per_unit = deal.savings_per_unit

            if savings_per_unit is None:
                raise ValueError(
                    "Unable to determine savings; provide --savings or both regular and paid prices."
                )

            total_savings = savings_per_unit * quantity
            regular_price = effective_regular
            paid_price = effective_paid

        total_savings = round(max(total_savings, 0.0), 2)

        savings_record = SavingsRecord(
            item_name=deal.item_name,
            store=deal.store,
            savings_amount=total_savings,
            regular_price=regular_price,
            paid_price=paid_price,
            quantity=quantity,
            savings_type=SavingsType(deal.deal_type.value),
            date=redeem_date,
            deal_id=deal.id,
            notes=notes,
        )

        deal.redeemed = True
        deal.redeemed_date = redeem_date
        self.data_store.update_deal(deal)
        self.data_store.add_savings(savings_record)

        return deal, savings_record

    def log_savings(
        self,
        item_name: str,
        store: str | None,
        savings_amount: float | None = None,
        regular_price: float | None = None,
        paid_price: float | None = None,
        quantity: float = 1.0,
        savings_type: SavingsType = SavingsType.MANUAL,
        record_date: date | None = None,
        notes: str | None = None,
    ) -> SavingsRecord:
        """Log a savings record manually."""
        if savings_amount is None:
            if regular_price is None or paid_price is None:
                raise ValueError("Provide savings amount or both regular and paid prices.")
            savings_amount = (regular_price - paid_price) * quantity

        savings_amount = round(max(savings_amount, 0.0), 2)

        record = SavingsRecord(
            item_name=item_name,
            store=store,
            savings_amount=savings_amount,
            regular_price=regular_price,
            paid_price=paid_price,
            quantity=quantity,
            savings_type=savings_type,
            date=record_date or date.today(),
            notes=notes,
        )
        self.data_store.add_savings(record)
        return record

    def savings_summary(self, period: str = "monthly") -> SavingsSummary:
        """Summarize savings over a time period."""
        today = date.today()

        if period == "weekly":
            start_date = today - timedelta(days=today.weekday())
        elif period == "yearly":
            start_date = today.replace(month=1, day=1)
        else:
            start_date = today.replace(day=1)

        records = self.data_store.load_savings()
        period_records = [r for r in records if start_date <= r.date <= today]

        total_savings = sum(r.savings_amount for r in period_records)
        savings_count = len(period_records)
        average_savings = round(total_savings / savings_count, 2) if savings_count else 0.0

        by_type: dict[str, float] = defaultdict(float)
        by_store: dict[str, float] = defaultdict(float)
        item_totals: dict[str, float] = defaultdict(float)

        for record in period_records:
            by_type[record.savings_type.value] += record.savings_amount
            if record.store:
                by_store[record.store] += record.savings_amount
            item_totals[record.item_name] += record.savings_amount

        top_items = [
            {"item": item, "total": round(total, 2)}
            for item, total in sorted(item_totals.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

        return SavingsSummary(
            period=period,
            start_date=start_date,
            end_date=today,
            total_savings=round(total_savings, 2),
            savings_count=savings_count,
            average_savings=average_savings,
            by_type={k: round(v, 2) for k, v in by_type.items()},
            by_store={k: round(v, 2) for k, v in by_store.items()},
            top_items=top_items,
        )

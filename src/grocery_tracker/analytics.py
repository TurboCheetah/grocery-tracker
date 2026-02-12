"""Analytics and intelligence for Grocery Tracker."""

from collections import defaultdict
from datetime import date, timedelta

from .data_store import DataStore
from .item_normalizer import canonical_item_display_name, normalize_item_name
from .models import (
    BudgetTracking,
    BulkBuyingAnalysis,
    BulkPackOption,
    CategoryBudget,
    CategoryInflation,
    CategorySpending,
    FrequencyData,
    ItemRecommendation,
    ItemStatus,
    OutOfStockRecord,
    PriceComparison,
    PricePoint,
    Priority,
    PurchaseRecord,
    RecipeHookItem,
    RecipeHookPayload,
    RouteItemAssignment,
    RouteStoreStop,
    SavingsContributor,
    SavingsRecord,
    SavingsSummary,
    SeasonalMonthStat,
    SeasonalPurchasePattern,
    ShoppingRoute,
    SpendingSummary,
    StorePreferenceScore,
    SubstitutionRecommendation,
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
        start_date, today = self._period_window(period)

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

    def savings_summary(self, period: str = "monthly") -> SavingsSummary:
        """Generate savings summary from persisted savings records."""
        start_date, end_date = self._period_window(period)
        records = [
            record
            for record in self.data_store.load_savings_records()
            if start_date <= record.transaction_date <= end_date
        ]

        total_savings = round(sum(record.savings_amount for record in records), 2)
        receipt_count = len({record.receipt_id for record in records})

        return SavingsSummary(
            period=period,
            start_date=start_date,
            end_date=end_date,
            total_savings=total_savings,
            receipt_count=receipt_count,
            record_count=len(records),
            top_items=self._savings_contributors(records, key="item_name"),
            top_stores=self._savings_contributors(records, key="store"),
            top_categories=self._savings_contributors(records, key="category"),
            by_source=self._savings_contributors(records, key="source"),
            assumptions=[
                "Line-item savings use explicit discount/coupon amounts when provided.",
                "Receipt-level discounts are prorated across line items by line total.",
            ],
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
        matched_keys = [key for key in history if normalize_item_name(key) == canonical_target]

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

    def seasonal_purchase_pattern(self, item_name: str) -> SeasonalPurchasePattern | None:
        """Build month-by-month seasonal purchase pattern for an item."""
        history = self.data_store.load_price_history()
        canonical_target = normalize_item_name(item_name)
        matched_keys = [key for key in history if normalize_item_name(key) == canonical_target]
        if not matched_keys:
            return None

        display_name = self._choose_display_name(item_name, matched_keys)
        all_points = []
        for key in matched_keys:
            for price_history in history[key].values():
                all_points.extend(price_history.price_points)

        return self._build_seasonal_purchase_pattern(display_name, all_points)

    def bulk_buying_analysis(
        self,
        item_name: str,
        standard_quantity: float,
        standard_price: float,
        standard_unit: str,
        bulk_quantity: float,
        bulk_price: float,
        bulk_unit: str,
        monthly_usage: float | None = None,
    ) -> BulkBuyingAnalysis:
        """Compare standard and bulk pack options with unit normalization."""
        assumptions = [
            "Unit-price comparison assumes both pack options are for the same product quality.",
            "Projected monthly savings are directional and based on recent usage estimates.",
        ]

        standard = BulkPackOption(
            name="standard",
            quantity=standard_quantity,
            unit=standard_unit,
            pack_price=standard_price,
        )
        bulk = BulkPackOption(
            name="bulk",
            quantity=bulk_quantity,
            unit=bulk_unit,
            pack_price=bulk_price,
        )

        standard_norm = self._normalize_unit(standard_unit)
        bulk_norm = self._normalize_unit(bulk_unit)

        if standard_norm is None or bulk_norm is None:
            assumptions.append("Unknown unit detected; comparison skipped for safety.")
            return BulkBuyingAnalysis(
                item_name=item_name,
                comparable=False,
                comparison_status="unknown_unit",
                standard_option=standard,
                bulk_option=bulk,
                break_even_recommendation=(
                    "Unable to compare pack options because one or more units are unknown."
                ),
                assumptions=assumptions,
            )

        standard_group, standard_factor, normalized_unit = standard_norm
        bulk_group, bulk_factor, _ = bulk_norm

        if standard_group != bulk_group:
            assumptions.append("Unit families differ (for example weight vs volume).")
            return BulkBuyingAnalysis(
                item_name=item_name,
                comparable=False,
                comparison_status="unit_mismatch",
                standard_option=standard,
                bulk_option=bulk,
                break_even_recommendation=(
                    "Unable to compare pack options because units are not compatible."
                ),
                assumptions=assumptions,
            )

        standard_normalized_qty = round(standard_quantity * standard_factor, 4)
        bulk_normalized_qty = round(bulk_quantity * bulk_factor, 4)
        standard.normalized_quantity = standard_normalized_qty
        standard.normalized_unit = normalized_unit
        bulk.normalized_quantity = bulk_normalized_qty
        bulk.normalized_unit = normalized_unit

        if standard_normalized_qty <= 0 or bulk_normalized_qty <= 0:
            assumptions.append("Pack quantity must be greater than zero for safe comparison.")
            return BulkBuyingAnalysis(
                item_name=item_name,
                comparable=False,
                comparison_status="invalid_quantity",
                standard_option=standard,
                bulk_option=bulk,
                break_even_recommendation="Unable to compare pack options due to invalid quantity.",
                assumptions=assumptions,
            )

        standard.unit_price = round(standard_price / standard_normalized_qty, 4)
        bulk.unit_price = round(bulk_price / bulk_normalized_qty, 4)

        savings_per_unit = round((standard.unit_price - bulk.unit_price), 4)
        recommended_option = "bulk" if savings_per_unit > 0 else "standard"

        break_even_units = None
        break_even_standard_packs = None
        break_even_recommendation = "Standard pack is equal or cheaper per unit."

        if savings_per_unit > 0:
            if bulk_price <= standard_price:
                break_even_recommendation = "Bulk is immediately cheaper per unit and per pack."
                break_even_units = 0.0
                break_even_standard_packs = 0.0
            else:
                upfront_delta = bulk_price - standard_price
                break_even_units = round(upfront_delta / savings_per_unit, 2)
                break_even_standard_packs = round(
                    break_even_units / standard_normalized_qty,
                    2,
                )
                break_even_recommendation = (
                    f"Bulk breaks even after ~{break_even_units:g} {normalized_unit} "
                    f"(~{break_even_standard_packs:g} standard pack(s))."
                )

        monthly_usage_units = None
        if monthly_usage is not None:
            monthly_usage_units = round(monthly_usage * standard_factor, 2)
            assumptions.append(
                f"Monthly usage provided directly: {monthly_usage:g} {standard_unit}."
            )
        else:
            estimated_packs = self._estimate_monthly_pack_usage(item_name)
            if estimated_packs is not None:
                monthly_usage_units = round(estimated_packs * standard_normalized_qty, 2)
                assumptions.append(
                    "Monthly usage estimated from purchase frequency history "
                    "(pack counts projected to 30 days)."
                )
            else:
                assumptions.append(
                    "Monthly usage unavailable from history; monthly savings not projected."
                )

        projected_monthly_savings = None
        if monthly_usage_units is not None:
            projected_monthly_savings = round(savings_per_unit * monthly_usage_units, 2)

        return BulkBuyingAnalysis(
            item_name=item_name,
            comparable=True,
            comparison_status="ok",
            standard_option=standard,
            bulk_option=bulk,
            recommended_option=recommended_option,
            break_even_units=break_even_units,
            break_even_standard_packs=break_even_standard_packs,
            monthly_usage_units=monthly_usage_units,
            projected_monthly_savings=projected_monthly_savings,
            break_even_recommendation=break_even_recommendation,
            assumptions=assumptions,
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
                        grouped["display_name"] or canonical_item_display_name(canonical_name)
                    ),
                    message=(
                        f"Usually buy every {avg:.0f} days, last purchase {days_since} days ago"
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

        # Seasonal price context suggestions
        for _, item_data in grouped_history.items():
            display_name = item_data["display_name"]
            all_points = [
                pp for points in item_data["stores"].values() for pp in points if pp.price > 0
            ]
            pattern = self._build_seasonal_purchase_pattern(display_name, all_points)
            if pattern is None or pattern.confidence == "low" or len(pattern.monthly_stats) < 2:
                continue

            latest = self._latest_price_point(all_points)
            if latest is None:
                continue

            month_price_map = {
                stat.month: stat.average_price
                for stat in pattern.monthly_stats
                if stat.average_price is not None and stat.average_price > 0
            }
            if len(month_price_map) < 2:
                continue

            baseline_price = min(month_price_map.values())
            if baseline_price <= 0:
                continue

            baseline_months = sorted(
                month for month, avg_price in month_price_map.items() if avg_price == baseline_price
            )
            current_month = latest.date.month
            ratio = latest.price / baseline_price
            if ratio < 1.25:
                continue

            priority = "high" if ratio >= 1.75 else "medium"
            baseline_month_names = ", ".join(self._month_name(m) for m in baseline_months)
            recommendation_reason = (
                f"{self._month_name(current_month)} pricing is {ratio:.1f}x the seasonal baseline."
            )

            suggestions.append(
                Suggestion(
                    type="seasonal_optimization",
                    item_name=display_name,
                    message=(
                        f"Current price ${latest.price:.2f} is {ratio:.1f}x seasonal baseline "
                        f"${baseline_price:.2f}; best value in {baseline_month_names}"
                    ),
                    priority=priority,
                    data={
                        "baseline": {
                            "average_price": round(baseline_price, 2),
                            "months": baseline_months,
                            "in_season_months": pattern.peak_purchase_months,
                            "confidence": pattern.confidence,
                        },
                        "current_context": {
                            "month": current_month,
                            "month_average_price": month_price_map.get(current_month),
                            "latest_observed_price": latest.price,
                            "latest_observed_date": latest.date.isoformat(),
                        },
                        "recommendation_reason": recommendation_reason,
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
                substitutions = self._substitution_recommendations(
                    canonical_item,
                    records=oos_records,
                )
                message = f"Out of stock {count} times at {store}"
                if substitutions:
                    message += f"; try {substitutions[0].item_name}"
                suggestions.append(
                    Suggestion(
                        type="out_of_stock",
                        item_name=oos_display_names.get(
                            canonical_item,
                            canonical_item_display_name(canonical_item),
                        ),
                        message=message,
                        priority="low",
                        data={
                            "store": store,
                            "count": count,
                            "substitutions": [s.model_dump() for s in substitutions],
                        },
                    )
                )

        # Sort: high priority first
        priority_order = {"high": 0, "medium": 1, "low": 2}
        suggestions.sort(key=lambda s: priority_order.get(s.priority, 1))

        return suggestions

    def recommend_item(
        self,
        item_name: str,
        min_confidence: float = 0.45,
    ) -> ItemRecommendation | None:
        """Recommend the best store for an item based on history quality.

        Args:
            item_name: Item to recommend a store for
            min_confidence: Minimum confidence score required to return a recommendation

        Returns:
            ItemRecommendation when confidence threshold is met, otherwise None.
        """
        history = self.data_store.load_price_history()
        canonical_target = normalize_item_name(item_name)
        matched_keys = [key for key in history if normalize_item_name(key) == canonical_target]
        if not matched_keys:
            return None

        store_points: dict[str, list[PricePoint]] = defaultdict(list)
        for key in matched_keys:
            for store_name, price_history in history[key].items():
                store_points[store_name].extend(price_history.price_points)

        if not store_points:
            return None

        oos_records = self.data_store.load_out_of_stock()
        oos_count_by_store: dict[str, int] = defaultdict(int)
        for record in oos_records:
            if normalize_item_name(record.item_name) == canonical_target:
                oos_count_by_store[record.store] += 1

        stats: list[dict] = []
        for store_name, points in store_points.items():
            if not points:
                continue

            latest = self._latest_price_point(points)
            if latest is None:
                continue

            avg_price = round(sum(pp.price for pp in points) / len(points), 2)
            stats.append(
                {
                    "store": store_name,
                    "current_price": latest.price,
                    "average_price": avg_price,
                    "samples": len(points),
                    "recency_days": max((date.today() - latest.date).days, 0),
                    "out_of_stock_count": oos_count_by_store.get(store_name, 0),
                }
            )

        if not stats:
            return None

        current_prices = [s["current_price"] for s in stats]
        min_price = min(current_prices)
        max_price = max(current_prices)

        for store_stats in stats:
            if max_price == min_price:
                price_score = 0.7
            else:
                price_score = (max_price - store_stats["current_price"]) / (max_price - min_price)
            recency_score = max(0.0, 1.0 - store_stats["recency_days"] / 90.0)
            sample_score = min(store_stats["samples"] / 6.0, 1.0)
            availability_score = max(
                0.0,
                1.0 - min(store_stats["out_of_stock_count"], 5) / 5.0,
            )

            store_stats["score"] = round(
                (0.5 * price_score)
                + (0.2 * recency_score)
                + (0.15 * sample_score)
                + (0.15 * availability_score),
                4,
            )

        stats.sort(
            key=lambda s: (
                -s["score"],
                s["current_price"],
                s["out_of_stock_count"],
                s["store"].lower(),
            )
        )

        store_coverage_score = min(len(stats) / 3.0, 1.0)
        sample_depth_score = min(sum(s["samples"] for s in stats) / 12.0, 1.0)
        freshness_score = sum(max(0.0, 1.0 - s["recency_days"] / 90.0) for s in stats) / len(stats)
        availability_score = sum(
            max(0.0, 1.0 - min(s["out_of_stock_count"], 5) / 5.0) for s in stats
        ) / len(stats)
        confidence_score = round(
            (0.3 * store_coverage_score)
            + (0.35 * sample_depth_score)
            + (0.2 * freshness_score)
            + (0.15 * availability_score),
            2,
        )

        if confidence_score < min_confidence:
            return None

        confidence = "high" if confidence_score >= 0.75 else "medium"
        ranked_stores: list[StorePreferenceScore] = []
        for rank, row in enumerate(stats, start=1):
            rationale = []
            if row["current_price"] == min_price:
                rationale.append("Lowest current price.")
            if row["out_of_stock_count"] == 0:
                rationale.append("No out-of-stock reports.")
            elif row["out_of_stock_count"] > 0:
                rationale.append(f"{row['out_of_stock_count']} out-of-stock reports.")
            if row["recency_days"] <= 14:
                rationale.append("Recent price data.")
            elif row["recency_days"] > 60:
                rationale.append("Price data is stale.")

            ranked_stores.append(
                StorePreferenceScore(
                    store=row["store"],
                    rank=rank,
                    score=row["score"],
                    current_price=row["current_price"],
                    average_price=row["average_price"],
                    out_of_stock_count=row["out_of_stock_count"],
                    samples=row["samples"],
                    recency_days=row["recency_days"],
                    rationale=rationale,
                )
            )

        substitutions = self._substitution_recommendations(
            item_name=item_name,
            records=oos_records,
        )

        recommendation_rationale = [
            "Ranking uses price, recency, sample depth, and out-of-stock history.",
        ]
        if len(stats) > 1 and max_price > min_price:
            recommendation_rationale.append(
                f"Current price spread across stores: ${max_price - min_price:.2f}."
            )
        if substitutions:
            recommendation_rationale.append(f"Common substitute: {substitutions[0].item_name}.")

        return ItemRecommendation(
            item_name=canonical_item_display_name(canonical_target),
            confidence=confidence,
            confidence_score=confidence_score,
            recommended_store=ranked_stores[0].store if ranked_stores else None,
            ranked_stores=ranked_stores,
            substitutions=substitutions,
            rationale=recommendation_rationale,
        )

    def plan_shopping_route(self) -> ShoppingRoute:
        """Build a deterministic store route for pending grocery list items."""
        grocery_list = self.data_store.load_list()
        pending_items = [item for item in grocery_list.items if item.status != ItemStatus.BOUGHT]

        if not pending_items:
            return ShoppingRoute(
                rationale=["No pending grocery list items to route."],
            )

        grouped_history = self._group_price_history(self.data_store.load_price_history())

        store_assignments: dict[str, list[RouteItemAssignment]] = defaultdict(list)
        unassigned_items: list[RouteItemAssignment] = []

        for item in pending_items:
            rationale: list[str] = []
            assigned_store: str | None = None
            assignment_source = "unassigned"
            estimated_price = item.estimated_price

            if item.store:
                assigned_store = item.store
                assignment_source = "list_preference"
                rationale.append("Uses the store set on the grocery list item.")
                if estimated_price is None:
                    estimated_price = self._latest_price_for_store(
                        item_name=item.name,
                        store=item.store,
                        grouped_history=grouped_history,
                    )
            else:
                recommendation = self.recommend_item(item.name, min_confidence=0.0)
                if recommendation and recommendation.recommended_store:
                    assigned_store = recommendation.recommended_store
                    assignment_source = "recommendation"
                    rationale.append("Assigned from historical price and availability scoring.")
                    if estimated_price is None:
                        for ranked_store in recommendation.ranked_stores:
                            if ranked_store.store == assigned_store:
                                estimated_price = ranked_store.current_price
                                break

                if assigned_store is None:
                    fallback_store, fallback_price = self._fallback_store_from_history(
                        item_name=item.name,
                        grouped_history=grouped_history,
                    )
                    if fallback_store:
                        assigned_store = fallback_store
                        assignment_source = "price_history"
                        rationale.append("Assigned to the lowest recent-price store.")
                        if estimated_price is None:
                            estimated_price = fallback_price

            assignment = RouteItemAssignment(
                item_name=item.name,
                quantity=item.quantity,
                category=item.category,
                priority=item.priority,
                assigned_store=assigned_store,
                estimated_price=round(estimated_price, 2) if estimated_price is not None else None,
                assignment_source=assignment_source,
                rationale=rationale,
            )

            if assigned_store is None:
                unassigned_items.append(assignment)
            else:
                store_assignments[assigned_store].append(assignment)

        sorted_stores = sorted(
            store_assignments.keys(),
            key=lambda store: self._store_stop_sort_key(store, store_assignments[store]),
        )

        stops: list[RouteStoreStop] = []
        for stop_number, store in enumerate(sorted_stores, start=1):
            ordered_items = sorted(
                store_assignments[store],
                key=self._assignment_sort_key,
            )
            estimated_total = round(
                sum(item.estimated_price or 0.0 for item in ordered_items),
                2,
            )

            stop_rationale = []
            if any(item.assignment_source == "list_preference" for item in ordered_items):
                stop_rationale.append("Contains explicit store preferences from the list.")
            if any(item.assignment_source == "recommendation" for item in ordered_items):
                stop_rationale.append("Contains history-based store recommendations.")

            stops.append(
                RouteStoreStop(
                    stop_number=stop_number,
                    store=store,
                    items=ordered_items,
                    item_count=len(ordered_items),
                    estimated_total=estimated_total,
                    rationale=stop_rationale,
                )
            )

        route_rationale = [
            "Store order is deterministic: item priority, item count, then store name.",
        ]
        if unassigned_items:
            route_rationale.append(
                f"{len(unassigned_items)} item(s) are unassigned due to missing store and history."
            )

        return ShoppingRoute(
            total_items=len(pending_items),
            total_estimated_cost=round(sum(stop.estimated_total for stop in stops), 2),
            stops=stops,
            unassigned_items=sorted(unassigned_items, key=self._assignment_sort_key),
            rationale=route_rationale,
        )

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
            freq for key, freq in frequency.items() if normalize_item_name(key) == canonical_target
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

    @staticmethod
    def _period_window(period: str) -> tuple[date, date]:
        """Return start/end date for supported summary periods."""
        today = date.today()
        if period == "weekly":
            return today - timedelta(days=today.weekday()), today
        if period == "yearly":
            return today.replace(month=1, day=1), today
        return today.replace(day=1), today

    @staticmethod
    def _savings_contributors(
        records: list[SavingsRecord],
        key: str,
        limit: int = 5,
    ) -> list[SavingsContributor]:
        """Aggregate savings contributors deterministically."""
        totals: dict[str, float] = defaultdict(float)
        counts: dict[str, int] = defaultdict(int)

        for record in records:
            bucket = getattr(record, key, None)
            if not bucket:
                continue
            totals[bucket] += record.savings_amount
            counts[bucket] += 1

        ranked = sorted(
            totals.items(),
            key=lambda row: (
                -round(row[1], 2),
                -counts[row[0]],
                row[0].lower(),
            ),
        )[:limit]

        return [
            SavingsContributor(
                name=name,
                total_savings=round(total, 2),
                record_count=counts[name],
            )
            for name, total in ranked
        ]

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

    def _normalize_unit(self, unit: str | None) -> tuple[str, float, str] | None:
        """Normalize units to a comparable family and base unit."""
        if not unit:
            return None

        normalized = unit.strip().lower().replace(".", "")
        normalized = " ".join(normalized.split())

        aliases = {
            "count": {"count", "ct", "ea", "each", "item", "items", "piece", "pieces", "unit"},
            "g": {"g", "gram", "grams"},
            "kg": {"kg", "kilogram", "kilograms"},
            "oz": {"oz", "ounce", "ounces"},
            "lb": {"lb", "lbs", "pound", "pounds"},
            "ml": {"ml", "milliliter", "milliliters"},
            "l": {"l", "liter", "liters"},
            "fl_oz": {"fl oz", "floz", "fluid ounce", "fluid ounces"},
        }

        canonical = None
        for key, values in aliases.items():
            if normalized in values:
                canonical = key
                break
        if canonical is None:
            return None

        if canonical in {"count"}:
            return "count", 1.0, "count"
        if canonical in {"g"}:
            return "weight", 1.0, "g"
        if canonical in {"kg"}:
            return "weight", 1000.0, "g"
        if canonical in {"oz"}:
            return "weight", 28.3495, "g"
        if canonical in {"lb"}:
            return "weight", 453.592, "g"
        if canonical in {"ml"}:
            return "volume", 1.0, "ml"
        if canonical in {"l"}:
            return "volume", 1000.0, "ml"
        return "volume", 29.5735, "ml"

    def _estimate_monthly_pack_usage(self, item_name: str) -> float | None:
        """Estimate monthly pack usage from frequency history."""
        frequency = self.data_store.load_frequency_data()
        canonical_target = normalize_item_name(item_name)
        matching = [
            freq for key, freq in frequency.items() if normalize_item_name(key) == canonical_target
        ]
        if not matching:
            return None

        purchases: list[PurchaseRecord] = []
        for freq in matching:
            purchases.extend(freq.purchase_history)

        if len(purchases) < 2:
            return None

        ordered = sorted(purchases, key=lambda p: p.date)
        day_span = max((ordered[-1].date - ordered[0].date).days, 1)
        total_quantity = sum(max(p.quantity, 0) for p in ordered)
        if total_quantity <= 0:
            return None
        return round(total_quantity / day_span * 30, 2)

    def _recipe_constraints(self, user: str | None = None) -> dict:
        """Build recipe constraints from one user or aggregated preferences."""
        if user:
            prefs = self.data_store.get_user_preferences(user)
            if prefs is None:
                return {
                    "dietary_restrictions": [],
                    "allergens": [],
                    "favorite_items": [],
                    "brand_preferences": {},
                }
            return {
                "dietary_restrictions": sorted(set(prefs.dietary_restrictions)),
                "allergens": sorted(set(prefs.allergens)),
                "favorite_items": sorted(set(prefs.favorite_items)),
                "brand_preferences": {
                    item_name: [brand]
                    for item_name, brand in sorted(
                        prefs.brand_preferences.items(),
                        key=lambda row: row[0],
                    )
                },
            }

        preferences = self.data_store.load_preferences()
        dietary: set[str] = set()
        allergens: set[str] = set()
        favorites: set[str] = set()
        brand_candidates: dict[str, set[str]] = defaultdict(set)

        for pref in preferences.values():
            dietary.update(pref.dietary_restrictions)
            allergens.update(pref.allergens)
            favorites.update(pref.favorite_items)
            for item_name, brand in pref.brand_preferences.items():
                brand_candidates[item_name].add(brand)

        brand_preferences = {
            item_name: sorted(brands)
            for item_name, brands in sorted(brand_candidates.items(), key=lambda row: row[0])
        }
        return {
            "dietary_restrictions": sorted(dietary),
            "allergens": sorted(allergens),
            "favorite_items": sorted(favorites),
            "brand_preferences": brand_preferences,
        }

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

    def _substitution_recommendations(
        self,
        item_name: str,
        limit: int = 3,
        records: list[OutOfStockRecord] | None = None,
    ) -> list[SubstitutionRecommendation]:
        """Build substitution suggestions from out-of-stock history."""
        oos_records = records if records is not None else self.data_store.load_out_of_stock()
        canonical_target = normalize_item_name(item_name)

        substitution_counts: dict[str, int] = defaultdict(int)
        substitution_display_names: dict[str, str] = {}
        substitution_stores: dict[str, set[str]] = defaultdict(set)

        for record in oos_records:
            if normalize_item_name(record.item_name) != canonical_target:
                continue
            if not record.substitution:
                continue

            canonical_sub = normalize_item_name(record.substitution)
            if not canonical_sub:
                continue

            substitution_counts[canonical_sub] += 1
            substitution_stores[canonical_sub].add(record.store)
            if canonical_sub not in substitution_display_names:
                substitution_display_names[canonical_sub] = canonical_item_display_name(
                    record.substitution
                )

        ranked = sorted(
            substitution_counts.items(),
            key=lambda row: (
                -row[1],
                substitution_display_names.get(row[0], row[0]).lower(),
            ),
        )[:limit]

        return [
            SubstitutionRecommendation(
                item_name=substitution_display_names.get(
                    canonical_sub, canonical_item_display_name(canonical_sub)
                ),
                count=count,
                stores=sorted(substitution_stores.get(canonical_sub, set())),
            )
            for canonical_sub, count in ranked
        ]

    def _group_price_history(self, history_data: dict) -> dict[str, dict]:
        grouped: dict[str, dict] = {}
        for item_name, stores in history_data.items():
            canonical = normalize_item_name(item_name)
            if canonical not in grouped:
                grouped[canonical] = {"display_name": item_name, "stores": defaultdict(list)}

            for store_name, price_history in stores.items():
                grouped[canonical]["stores"][store_name].extend(price_history.price_points)

        return grouped

    def _build_seasonal_purchase_pattern(
        self,
        item_name: str,
        price_points: list[PricePoint],
    ) -> SeasonalPurchasePattern | None:
        if not price_points:
            return None

        month_prices: dict[int, list[float]] = defaultdict(list)
        for point in price_points:
            if point.price <= 0:
                continue
            month_prices[point.date.month].append(point.price)

        if not month_prices:
            return None

        monthly_stats = [
            SeasonalMonthStat(
                month=month,
                purchase_count=len(prices),
                average_price=round(sum(prices) / len(prices), 2),
            )
            for month, prices in sorted(month_prices.items())
        ]

        sample_size = sum(stat.purchase_count for stat in monthly_stats)
        observed_months = len(monthly_stats)
        confidence = self._seasonal_confidence(sample_size, observed_months)

        peak_purchase_months: list[int] = []
        low_purchase_months: list[int] = []
        if confidence != "low" and observed_months >= 3:
            max_count = max(stat.purchase_count for stat in monthly_stats)
            min_count = min(stat.purchase_count for stat in monthly_stats)
            if max_count > min_count:
                peak_purchase_months = [
                    stat.month for stat in monthly_stats if stat.purchase_count == max_count
                ]
                low_purchase_months = [
                    stat.month for stat in monthly_stats if stat.purchase_count == min_count
                ]

        return SeasonalPurchasePattern(
            item_name=item_name,
            sample_size=sample_size,
            observed_months=observed_months,
            peak_purchase_months=peak_purchase_months,
            low_purchase_months=low_purchase_months,
            monthly_stats=monthly_stats,
            confidence=confidence,
        )

    @staticmethod
    def _seasonal_confidence(sample_size: int, observed_months: int) -> str:
        if sample_size >= 24 and observed_months >= 6:
            return "high"
        if sample_size >= 12 and observed_months >= 4:
            return "medium"
        return "low"

    @staticmethod
    def _month_name(month: int) -> str:
        return date(2000, month, 1).strftime("%B")

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

    @staticmethod
    def _priority_weight(priority: Priority) -> int:
        weights = {
            Priority.HIGH: 3,
            Priority.MEDIUM: 2,
            Priority.LOW: 1,
        }
        return weights.get(priority, 1)

    def _assignment_sort_key(self, assignment: RouteItemAssignment) -> tuple:
        return (
            -self._priority_weight(assignment.priority),
            assignment.item_name.lower(),
        )

    def _store_stop_sort_key(
        self,
        store: str,
        assignments: list[RouteItemAssignment],
    ) -> tuple:
        priority_score = sum(self._priority_weight(item.priority) for item in assignments)
        return (
            -priority_score,
            -len(assignments),
            store.lower(),
        )

    def _latest_price_for_store(
        self,
        item_name: str,
        store: str,
        grouped_history: dict[str, dict],
    ) -> float | None:
        canonical_item = normalize_item_name(item_name)
        item_history = grouped_history.get(canonical_item)
        if not item_history:
            return None

        for store_name, price_points in item_history["stores"].items():
            if store_name.lower() != store.lower():
                continue
            latest = self._latest_price_point(price_points)
            if latest is not None:
                return latest.price
        return None

    def _fallback_store_from_history(
        self,
        item_name: str,
        grouped_history: dict[str, dict],
    ) -> tuple[str | None, float | None]:
        canonical_item = normalize_item_name(item_name)
        item_history = grouped_history.get(canonical_item)
        if not item_history:
            return None, None

        candidates: list[tuple[str, float, int, int]] = []
        for store_name, price_points in item_history["stores"].items():
            latest = self._latest_price_point(price_points)
            if latest is None:
                continue
            recency_days = max((date.today() - latest.date).days, 0)
            candidates.append((store_name, latest.price, recency_days, len(price_points)))

        if not candidates:
            return None, None

        candidates.sort(key=lambda row: (row[1], row[2], -row[3], row[0].lower()))
        best_store, best_price, _, _ = candidates[0]
        return best_store, best_price

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

    # --- Skill Hook Payloads ---

    def recipe_use_it_up_payload(
        self,
        days: int = 3,
        user: str | None = None,
    ) -> RecipeHookPayload:
        """Build structured payload for external recipe/use-it-up generation."""
        today = date.today()
        inventory = self.data_store.load_inventory()
        expiring = []
        for item in inventory:
            if item.expiration_date is None:
                continue
            days_until = (item.expiration_date - today).days
            if days_until <= days:
                expiring.append((item, days_until))

        expiring.sort(
            key=lambda row: (
                row[1],
                row[0].item_name.lower(),
            )
        )

        payload_items: list[RecipeHookItem] = []
        for rank, (item, days_until) in enumerate(expiring, start=1):
            payload_items.append(
                RecipeHookItem(
                    item_name=item.item_name,
                    quantity=item.quantity,
                    unit=item.unit,
                    category=item.category,
                    location=item.location,
                    expiration_date=item.expiration_date,
                    days_until_expiration=days_until,
                    priority_rank=rank,
                )
            )

        constraints = self._recipe_constraints(user=user)
        assumptions = [
            "Payload is intended for external recipe generation skills only.",
            "Priority ordering is by nearest expiration date, then item name.",
        ]
        if user:
            assumptions.append(f"Constraints are scoped to user '{user}'.")
        else:
            assumptions.append("Constraints aggregate all known household preferences.")

        return RecipeHookPayload(
            horizon_days=days,
            user=user,
            expiring_items=payload_items,
            priority_order=[item.item_name for item in payload_items],
            constraints=constraints,
            assumptions=assumptions,
        )

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

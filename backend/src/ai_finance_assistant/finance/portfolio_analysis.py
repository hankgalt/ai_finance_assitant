"""Pure deterministic valuation and portfolio analysis."""

from collections import defaultdict
from decimal import Decimal, localcontext
from typing import TypeVar

from ai_finance_assistant.finance.models import (
    CalculationWarning,
    ClassificationConcentration,
    CurrencyTotal,
    DiversificationHeuristic,
    ExpenseMetric,
    HoldingValuation,
    ImportedHolding,
    PortfolioAnalysisRequest,
    PortfolioSnapshot,
    SecurityReference,
)
from ai_finance_assistant.finance.precision import count_value, money, percent, ratio

_T = TypeVar("_T")
_DIVERSIFICATION_LIMITATION = (
    "HHI and effective holding count describe only observed holding-value concentration within "
    "one currency. They do not measure correlation, volatility, liquidity, suitability, or risk."
)


def _unique_by(items: tuple[_T, ...], attribute: str, label: str) -> dict[str, _T]:
    result: dict[str, _T] = {}
    for item in items:
        key = str(getattr(item, attribute))
        if key in result:
            raise ValueError(f"duplicate {label} for {key}")
        result[key] = item
    return result


def _selected_field(
    imported: str | Decimal | None,
    provider: str | Decimal | None,
) -> tuple[str | Decimal | None, str | None, bool]:
    if provider is None:
        return imported, "user_import" if imported is not None else None, False
    conflict = imported is not None and str(imported).casefold() != str(provider).casefold()
    return provider, "provider", conflict


class PortfolioAnalysis:
    """Deep calculation module with a single request/result interface."""

    def analyze(self, request: PortfolioAnalysisRequest) -> PortfolioSnapshot:
        holdings = tuple(
            holding for account in request.portfolio.accounts for holding in account.holdings
        )
        holding_ids = {holding.holding_id for holding in holdings}
        references = _unique_by(request.security_references, "holding_id", "security reference")
        quotes = _unique_by(request.quote_set.quotes, "holding_id", "quote")
        unknown_references = set(references).difference(holding_ids)
        unknown_quotes = set(quotes).difference(holding_ids)
        if unknown_references:
            raise ValueError(
                f"security references do not belong to the portfolio: {sorted(unknown_references)}"
            )
        if unknown_quotes:
            raise ValueError(f"quotes do not belong to the portfolio: {sorted(unknown_quotes)}")

        warnings: list[CalculationWarning] = []
        valuations: list[HoldingValuation] = []
        for holding in sorted(holdings, key=lambda item: item.holding_id):
            reference = references.get(holding.holding_id)
            valuation = self._value_holding(
                holding,
                reference,
                quotes.get(holding.holding_id),
                warnings,
            )
            valuations.append(valuation)

        totals = self._currency_totals(holdings, valuations)
        totals_by_currency = {total.currency: total.priced_value for total in totals}
        valuations = [
            valuation.model_copy(
                update={
                    "allocation_percent": (
                        percent(
                            valuation.market_value,
                            totals_by_currency[valuation.currency],
                        )
                        if valuation.market_value is not None
                        and totals_by_currency[valuation.currency] > 0
                        else None
                    )
                }
            )
            for valuation in valuations
        ]

        holding_currencies = {holding.currency for holding in holdings}
        if holding_currencies == {request.portfolio.base_currency}:
            base_total = totals_by_currency.get(
                request.portfolio.base_currency, money(Decimal("0"))
            )
        else:
            base_total = None
            warnings.append(
                CalculationWarning(
                    code="MIXED_CURRENCY_NO_FX",
                    message=(
                        "Values remain partitioned by currency because no approved FX conversion "
                        "set was supplied."
                    ),
                )
            )

        concentrations = self._concentrations(valuations, totals_by_currency)
        expense_metrics = self._expense_metrics(valuations, totals_by_currency)
        diversification = self._diversification(valuations, totals_by_currency)
        unpriced = tuple(
            valuation.holding_id for valuation in valuations if valuation.market_value is None
        )
        return PortfolioSnapshot(
            snapshot_id=request.snapshot_id,
            portfolio_id=request.portfolio.portfolio_id,
            calculated_at=request.calculated_at,
            quote_set_id=request.quote_set.quote_set_id,
            security_reference_ids=tuple(
                sorted(reference.reference_id for reference in request.security_references)
            ),
            base_currency=request.portfolio.base_currency,
            base_currency_total=base_total,
            totals_by_currency=tuple(totals),
            holding_valuations=tuple(valuations),
            concentrations=tuple(concentrations),
            expense_metrics=tuple(expense_metrics),
            diversification=tuple(diversification),
            unpriced_holding_ids=unpriced,
            warnings=tuple(warnings),
        )

    @staticmethod
    def _value_holding(
        holding: ImportedHolding,
        reference: SecurityReference | None,
        quote: object | None,
        warnings: list[CalculationWarning],
    ) -> HoldingValuation:
        from ai_finance_assistant.finance.models import HoldingQuote

        if quote is not None and not isinstance(quote, HoldingQuote):
            raise TypeError("quote lookup returned an invalid object")

        provider_asset = None if reference is None else reference.asset_class
        provider_sector = None if reference is None else reference.sector
        provider_expense = None if reference is None else reference.expense_ratio
        asset_class, asset_source, asset_conflict = _selected_field(
            holding.asset_class, provider_asset
        )
        sector, sector_source, sector_conflict = _selected_field(holding.sector, provider_sector)
        expense, expense_source, expense_conflict = _selected_field(
            holding.expense_ratio, provider_expense
        )
        for field_name, has_conflict in (
            ("asset_class", asset_conflict),
            ("sector", sector_conflict),
            ("expense_ratio", expense_conflict),
        ):
            if has_conflict:
                warnings.append(
                    CalculationWarning(
                        code="ENRICHMENT_CONFLICT",
                        message=(
                            f"Provider {field_name} differs from imported evidence; the provider "
                            "value was used for this snapshot and both records remain unchanged."
                        ),
                        holding_id=holding.holding_id,
                    )
                )
        if reference is not None:
            for reported_conflict in reference.conflicts:
                warnings.append(
                    CalculationWarning(
                        code="PROVIDER_REPORTED_CONFLICT",
                        message=(
                            "The enrichment record reports a "
                            f"{reported_conflict.field_name} conflict."
                        ),
                        holding_id=holding.holding_id,
                    )
                )

        price: Decimal | None = None
        price_source: str | None = None
        if quote is not None:
            if quote.currency != holding.currency:
                warnings.append(
                    CalculationWarning(
                        code="QUOTE_CURRENCY_MISMATCH",
                        message=(
                            "The quote currency differs from the imported Holding currency and was "
                            "not converted."
                        ),
                        holding_id=holding.holding_id,
                    )
                )
            else:
                price = quote.price
                price_source = "quote_set"
                if quote.provenance.is_stale:
                    warnings.append(
                        CalculationWarning(
                            code="STALE_QUOTE",
                            message=(
                                "A stale-labeled quote was used and remains identified as such."
                            ),
                            holding_id=holding.holding_id,
                        )
                    )
        elif holding.user_price is not None:
            price = holding.user_price
            price_source = "user_import"
            warnings.append(
                CalculationWarning(
                    code="USER_PRICE_USED",
                    message="The valuation used the preserved user-supplied price.",
                    holding_id=holding.holding_id,
                )
            )
        if price is None:
            warnings.append(
                CalculationWarning(
                    code="MISSING_PRICE",
                    message="No usable price was available; the Holding is excluded from totals.",
                    holding_id=holding.holding_id,
                )
            )

        value = None if price is None else money(holding.quantity * price)
        return HoldingValuation(
            holding_id=holding.holding_id,
            account_id=holding.account_id,
            currency=holding.currency,
            quantity=holding.quantity,
            price=price,
            price_source=price_source,
            market_value=value,
            asset_class=asset_class,
            asset_class_source=asset_source,
            sector=sector,
            sector_source=sector_source,
            expense_ratio=expense,
            expense_ratio_source=expense_source,
        )

    @staticmethod
    def _currency_totals(
        holdings: tuple[ImportedHolding, ...], valuations: list[HoldingValuation]
    ) -> list[CurrencyTotal]:
        total_counts: defaultdict[str, int] = defaultdict(int)
        for holding in holdings:
            total_counts[holding.currency] += 1
        priced_values: defaultdict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        priced_counts: defaultdict[str, int] = defaultdict(int)
        for valuation in valuations:
            if valuation.market_value is not None:
                priced_values[valuation.currency] += valuation.market_value
                priced_counts[valuation.currency] += 1
        return [
            CurrencyTotal(
                currency=currency,
                priced_value=money(priced_values[currency]),
                priced_holding_count=priced_counts[currency],
                total_holding_count=total_counts[currency],
                holding_count_coverage_percent=percent(
                    Decimal(priced_counts[currency]), Decimal(total_counts[currency])
                ),
            )
            for currency in sorted(total_counts)
        ]

    @staticmethod
    def _concentrations(
        valuations: list[HoldingValuation], totals: dict[str, Decimal]
    ) -> list[ClassificationConcentration]:
        output: list[ClassificationConcentration] = []
        for classification in ("asset_class", "sector"):
            grouped: defaultdict[tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0"))
            classified_totals: defaultdict[str, Decimal] = defaultdict(lambda: Decimal("0"))
            for valuation in valuations:
                category = getattr(valuation, classification)
                if valuation.market_value is None or category is None:
                    continue
                grouped[(valuation.currency, category)] += valuation.market_value
                classified_totals[valuation.currency] += valuation.market_value
            for (currency, category), value in sorted(grouped.items()):
                output.append(
                    ClassificationConcentration(
                        classification=classification,
                        currency=currency,
                        category=category,
                        market_value=money(value),
                        percent_of_classified_value=percent(value, classified_totals[currency]),
                        classified_value_coverage_percent=percent(
                            classified_totals[currency], totals[currency]
                        ),
                    )
                )
        return output

    @staticmethod
    def _expense_metrics(
        valuations: list[HoldingValuation], totals: dict[str, Decimal]
    ) -> list[ExpenseMetric]:
        metrics: list[ExpenseMetric] = []
        for currency in sorted(totals):
            covered = Decimal("0")
            weighted = Decimal("0")
            for valuation in valuations:
                if (
                    valuation.currency != currency
                    or valuation.market_value is None
                    or valuation.expense_ratio is None
                ):
                    continue
                covered += valuation.market_value
                weighted += valuation.market_value * valuation.expense_ratio
            weighted_ratio = None
            if covered > 0:
                with localcontext() as context:
                    context.prec = 34
                    weighted_ratio = ratio(weighted / covered)
            metrics.append(
                ExpenseMetric(
                    currency=currency,
                    weighted_expense_ratio=weighted_ratio,
                    covered_value=money(covered),
                    known_value_coverage_percent=percent(covered, totals[currency]),
                )
            )
        return metrics

    @staticmethod
    def _diversification(
        valuations: list[HoldingValuation], totals: dict[str, Decimal]
    ) -> list[DiversificationHeuristic]:
        output: list[DiversificationHeuristic] = []
        for currency in sorted(totals):
            values = [
                valuation.market_value
                for valuation in valuations
                if valuation.currency == currency and valuation.market_value is not None
            ]
            total = totals[currency]
            if total <= 0 or not values:
                output.append(
                    DiversificationHeuristic(
                        currency=currency,
                        priced_holding_count=len(values),
                        limitation=_DIVERSIFICATION_LIMITATION,
                    )
                )
                continue
            with localcontext() as context:
                context.prec = 34
                weights = [value / total for value in values]
                hhi_unrounded = sum((weight * weight for weight in weights), Decimal("0"))
                effective = Decimal("1") / hhi_unrounded
            output.append(
                DiversificationHeuristic(
                    currency=currency,
                    holding_hhi=ratio(hhi_unrounded),
                    effective_holding_count=count_value(effective),
                    top_holding_percent=percent(max(values), total),
                    priced_holding_count=len(values),
                    limitation=_DIVERSIFICATION_LIMITATION,
                )
            )
        return output

export function formatCurrency(
  value: string | number | null,
  currency = "USD",
): string {
  if (value === null || !Number.isFinite(Number(value))) return "Not available";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(Number(value));
}

export function formatPercent(
  value: string | number | null,
  fraction = false,
): string {
  if (value === null || !Number.isFinite(Number(value))) return "Not available";
  const numeric = Number(value) * (fraction ? 100 : 1);
  return `${numeric.toFixed(2)}%`;
}

export function formatDateTime(value: string | null): string {
  if (!value) return "Not available";
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

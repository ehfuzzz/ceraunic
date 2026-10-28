// Shared by csv-source.ts, square/source.ts and any later shopify adapter.
// The panel is the contract: everything downstream reads SalesPanel only.

/** Calendar date "YYYY-MM-DD" in the LOCATION's own IANA time zone. Never a UTC date. */
export type LocalDate = string & { readonly __brand: "LocalDate" };

export type SalesSourceKind = "csv" | "square" | "shopify";
export type SalesSourceMode = "upload" | "fixture" | "sandbox" | "production";

export interface SalesLocation {
  /** Source-qualified and stable: "square:L88917AVBK2S5", "csv:scoops-midtown". */
  id: string;
  name: string;
  /** IANA zone, required. Square: Location.timezone. CSV: chosen in the upload form. */
  timezone: string;
  /** Prototype is USD-only; any other currency is rejected, never converted. */
  currency: "USD";
  /** Square: Location.coordinates. CSV: geocoded postal code or entered. Used for the station join. */
  lat?: number;
  lon?: number;
  postalCode?: string;
}

export interface DailySalesRow {
  locationId: string; // SalesLocation.id
  date: LocalDate;
  /** Integer US cents, >= 0. */
  grossSalesCents: number;
  /** Integer >= 0. Completed sale orders. */
  orderCount: number;
  /** Optional. Category name -> integer cents; values sum EXACTLY to grossSalesCents
   *  ("Uncategorized" absorbs custom amounts and unknown/deleted catalog ids). */
  categories?: Record<string, number>;
}

export interface SalesPanel {
  source: SalesSourceKind;
  mode: SalesSourceMode;
  locations: SalesLocation[];
  /** Sorted by (locationId, date); unique per (locationId, date). Every date in [start, end]
   *  has a row for every location (explicit 0/0 for closed days). */
  rows: DailySalesRow[];
  start: LocalDate; // inclusive
  end: LocalDate; // inclusive
  /** Rows on/after this date may still change (Square: offline POS orders can arrive up to 72 h late). */
  provisionalFrom?: LocalDate;
  /** UTC ISO-8601 with Z. */
  pulledAt: string;
  /** Provenance for the run manifest: api host or "fixture", Square-Version, pages, orders seen,
   *  duplicates, skipped counts by reason. */
  provenance: Record<string, string | number>;
}

export interface FetchDailyRequest {
  locationIds: string[]; // SalesLocation.id values; empty = every valid location
  start: LocalDate;
  end: LocalDate; // inclusive
  includeCategories?: boolean;
  signal?: AbortSignal;
}

export interface SalesSource {
  readonly kind: SalesSourceKind;
  readonly mode: SalesSourceMode;
  listLocations(): Promise<SalesLocation[]>;
  fetchDaily(req: FetchDailyRequest): Promise<SalesPanel>;
}

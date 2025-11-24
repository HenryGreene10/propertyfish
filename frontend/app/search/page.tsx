'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import type { ReadonlyURLSearchParams } from 'next/navigation';

import type {
  ChatResponse,
  PropertySummary,
  SearchFilters,
  SearchResultRow,
} from '@/lib/types';

type SearchItem = SearchResultRow & {
  zipcode?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  year_built?: number | null;
  floors?: number | null;
  units_total?: number | null;
  stories?: number | null;
  lot_sqft?: number | null;
  building_dimensions?: string | null;
  lot_dimensions?: string | null;
  zoning?: string | null;
  permit_count_12mo?: number | null;
  latest_permit_date?: string | null;
  latest_permit_description?: string | null;
  last_permit?: string | null;
  last_sale_date?: string | null;
  last_sale_price?: number | null;
  tax_year?: number | null;
  market_value?: number | null;
  tax_amount?: number | null;
};

type SearchResponse = {
  total: number;
  items: SearchItem[];
};

type ChatTurn = {
  id: string;
  role?: 'user' | 'assistant' | 'combined';
  user: string;
  assistant: string;
  total: number;
  filters?: ChatResponse['filters'];
  rows: PropertySummary[];
};

const CHAT_HISTORY_KEY = 'pf_chat_history_v1';
const LAST_RESULTS_KEY = 'pf_last_results_v1';

type CachedFilters = {
  q: string | null;
  borough: string | null;
  year_min: number | null;
};

type CachedResultsPayload = {
  filters: CachedFilters;
  total: number;
  rows: PropertySummary[];
};

function generateChatTurnId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `chat-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function sanitizeChatFilters(filters: unknown): ChatResponse['filters'] | undefined {
  if (!filters || typeof filters !== 'object') {
    return undefined;
  }
  const candidate = filters as ChatResponse['filters'];
  const q =
    typeof candidate.q === 'string' && candidate.q.trim() !== '' ? candidate.q : null;
  const borough =
    typeof candidate.borough === 'string' && candidate.borough.trim() !== ''
      ? candidate.borough
      : null;
  const year_min =
    typeof candidate.year_min === 'number' && Number.isFinite(candidate.year_min)
      ? candidate.year_min
      : null;
  const sort =
    typeof candidate.sort === 'string' && candidate.sort.trim() !== ''
      ? candidate.sort
      : null;

  if (q !== null || borough !== null || year_min !== null || sort !== null) {
    return { q, borough, year_min, sort };
  }
  return undefined;
}

function toPreviewRows(rows: unknown, limit = 3): PropertySummary[] {
  if (!Array.isArray(rows) || limit <= 0) return [];
  return rows
    .slice(0, limit)
    .map((row) => {
      if (!row || typeof row !== 'object') return null;
      const summary = row as PropertySummary;
      if (
        typeof summary.bbl !== 'string' ||
        typeof summary.address !== 'string'
      ) {
        return null;
      }
      return { ...summary };
    })
    .filter((row): row is PropertySummary => Boolean(row));
}

function loadStoredChatHistory(): ChatTurn[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.sessionStorage.getItem(CHAT_HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map((entry: any) => {
        if (!entry || typeof entry !== 'object') return null;
        const user = typeof entry.user === 'string' ? entry.user : '';
        const assistant =
          typeof entry.assistant === 'string'
            ? entry.assistant
            : typeof entry.reply === 'string'
              ? entry.reply
              : '';
        if (!user && !assistant) return null;
          const total =
            typeof entry.total === 'number' && Number.isFinite(entry.total)
              ? entry.total
              : typeof entry.matches === 'number' && Number.isFinite(entry.matches)
                ? entry.matches
                : 0;
        const filters = sanitizeChatFilters(entry.filters);
        const previewRows = toPreviewRows(entry.rows ?? entry.previewRows ?? entry.cards);
        const role =
          entry.role === 'user' || entry.role === 'assistant' || entry.role === 'combined'
            ? entry.role
            : assistant
              ? (user ? 'combined' : 'assistant')
              : 'user';
        const id =
          typeof entry.id === 'string' && entry.id.trim() !== ''
            ? entry.id
            : generateChatTurnId();
        return {
          id,
          role,
          user,
          assistant,
          total,
          filters,
          rows: previewRows,
        } as ChatTurn;
      })
      .filter((turn): turn is ChatTurn => Boolean(turn));
  } catch {
    return [];
  }
}

function normalizeQueryValue(value: string | null | undefined) {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed === '' ? null : trimmed;
}

function normalizeBoroughValue(value: string | null | undefined) {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim().toUpperCase();
  return trimmed === '' ? null : trimmed;
}

function normalizeYearValue(value: number | null | undefined) {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  return null;
}

function toCacheFilters(
  filters?: Partial<SearchFilters> | ChatResponse['filters'] | null,
): CachedFilters {
  if (!filters) {
    return { q: null, borough: null, year_min: null };
  }
  return {
    q: normalizeQueryValue(filters.q),
    borough: normalizeBoroughValue(filters.borough),
    year_min: normalizeYearValue(filters.year_min ?? null),
  };
}

function cacheFiltersMatch(
  cached: CachedFilters,
  filters: Partial<SearchFilters>,
): boolean {
  const target = toCacheFilters(filters);
  return (
    (cached.q ?? null) === (target.q ?? null) &&
    (cached.borough ?? null) === (target.borough ?? null) &&
    (cached.year_min ?? null) === (target.year_min ?? null)
  );
}

function loadResultsCache(): CachedResultsPayload | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.sessionStorage.getItem(LAST_RESULTS_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (
      !parsed ||
      typeof parsed !== 'object' ||
      typeof parsed.total !== 'number' ||
      !Array.isArray(parsed.rows) ||
      !parsed.filters ||
      typeof parsed.filters !== 'object'
    ) {
      return null;
    }
    const filters = parsed.filters as Partial<CachedFilters>;
    return {
      filters: {
        q: normalizeQueryValue(filters.q ?? null),
        borough: normalizeBoroughValue(filters.borough ?? null),
        year_min: normalizeYearValue(filters.year_min ?? null),
      },
      total: parsed.total,
      rows: parsed.rows as PropertySummary[],
    };
  } catch {
    return null;
  }
}

function saveResultsCache(
  rows: PropertySummary[],
  total: number,
  filters?: Partial<SearchFilters> | ChatResponse['filters'],
) {
  if (typeof window === 'undefined') return;
  try {
    const payload: CachedResultsPayload = {
      filters: toCacheFilters(filters ?? null),
      total,
      rows,
    };
    window.sessionStorage.setItem(LAST_RESULTS_KEY, JSON.stringify(payload));
  } catch {
    // ignore cache write errors
  }
}

function extractUrlFilters(searchParams: URLSearchParams | ReadonlyURLSearchParams | null) {
  const urlQ = (searchParams?.get('q') ?? '').trim();
  const urlBorough = searchParams?.get('borough') ?? '';
  const rawYear = searchParams?.get('year_min') ?? searchParams?.get('year') ?? '';
  const parsedYear = rawYear !== '' ? Number(rawYear) : undefined;
  const yearValue =
    typeof parsedYear === 'number' && Number.isFinite(parsedYear) ? parsedYear : undefined;
  return { urlQ, urlBorough, yearValue };
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8000';
const PAGE_SIZE = 24;

const SORT_WHITELIST: ReadonlySet<NonNullable<SearchFilters['sort']>> = new Set([
  'last_permit_date',
  'year_built',
  'permit_count_12m',
  'relevance',
]);
const ORDER_WHITELIST: ReadonlySet<'asc' | 'desc'> = new Set(['asc', 'desc']);

function clampLimit(value: number | undefined) {
  if (typeof value !== 'number' || Number.isNaN(value)) return undefined;
  return Math.min(Math.max(Math.trunc(value), 1), 50);
}

function normalizeOffset(value: number | undefined) {
  if (typeof value !== 'number' || Number.isNaN(value)) return undefined;
  return Math.max(0, Math.trunc(value));
}

function asNumber(value: number | undefined) {
  if (typeof value !== 'number' || Number.isNaN(value)) return undefined;
  return value;
}

function buildSearchParams(filters: Partial<SearchFilters> = {}) {
  const params = new URLSearchParams();

  const text = typeof filters.q === 'string' ? filters.q.trim() : '';
  if (text) {
    params.set('q', text);
  }
  if (filters.borough) {
    params.set('borough', filters.borough);
  }

  const numericEntries: Array<[keyof SearchFilters, number | undefined]> = [
    ['limit', clampLimit(filters.limit)],
    ['offset', normalizeOffset(filters.offset)],
    ['year_min', asNumber(filters.year_min)],
  ];
  numericEntries.forEach(([key, value]) => {
    if (typeof value === 'number' && Number.isFinite(value)) {
      params.set(key, String(value));
    }
  });

  if (filters.sort && SORT_WHITELIST.has(filters.sort)) {
    params.set('sort', filters.sort);
  }
  if (filters.order && ORDER_WHITELIST.has(filters.order)) {
    params.set('order', filters.order);
  }

  return params;
}

function toSearchResponse(payload: unknown): SearchResponse {
  const raw = (payload ?? {}) as {
    total?: number;
    items?: SearchItem[];
    rows?: SearchItem[];
  };

  const items = Array.isArray(raw.items)
    ? raw.items
    : Array.isArray(raw.rows)
      ? raw.rows
      : [];
  const total =
    typeof raw.total === 'number' && Number.isFinite(raw.total)
      ? raw.total
      : items.length;

  return { total, items };
}

function preferNumber(...values: Array<number | null | undefined>) {
  for (const value of values) {
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value;
    }
  }
  return null;
}

function preferString(...values: Array<string | null | undefined>) {
  for (const value of values) {
    if (typeof value === 'string' && value.trim() !== '') {
      return value;
    }
  }
  return null;
}

function mapToCard(item: SearchItem): PropertySummary {
  return {
    bbl: item.bbl,
    address: item.address,
    borough: item.borough,
    borough_full: item.borough_full,
    zipcode: item.zipcode,
    latitude: item.latitude,
    longitude: item.longitude,
    yearbuilt: preferNumber(item.yearbuilt, item.year_built),
    year_built: item.year_built,
    numfloors: preferNumber(item.numfloors, item.floors),
    floors: item.floors,
    stories: item.stories ?? item.numfloors ?? null,
    unitsres: item.unitsres,
    unitstotal: preferNumber(item.unitstotal, item.units_total),
    units_total: item.units_total,
    lot_sqft: (item.lot_sqft ?? item.lotarea) ?? null,
    building_dimensions: item.building_dimensions ?? null,
    lot_dimensions: item.lot_dimensions ?? null,
    zoning:
      item.zoning && item.zoning.trim() !== ''
        ? item.zoning
        : item.zonedist1 || null,
    zonedist1: item.zonedist1,
    landuse: item.landuse,
    bldgarea: item.bldgarea,
    lotarea: item.lotarea,
    permit_count_12mo: preferNumber(item.permit_count_12mo, item.permit_count_12m),
    permit_count_12m: item.permit_count_12m,
    latest_permit_date: preferString(item.latest_permit_date, item.last_permit_date),
    last_permit_date: item.last_permit_date,
    latest_permit_description: preferString(
      item.latest_permit_description,
      item.last_permit,
    ),
    last_permit: item.last_permit,
    last_sale_date: item.last_sale_date ?? null,
    last_sale_price: item.last_sale_price ?? null,
    tax_year: item.tax_year ?? null,
    market_value: item.market_value ?? null,
    tax_amount: item.tax_amount ?? null,
  };
}

export default function SearchPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [results, setResults] = useState<PropertySummary[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [limit, setLimit] = useState(PAGE_SIZE);
  const [page, setPage] = useState(0);
  const [isEnd, setIsEnd] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [query, setQuery] = useState('');
  const [boroughFilter, setBoroughFilter] = useState('');
  const [yearMin, setYearMin] = useState<number | ''>('');
  const [activeFilters, setActiveFilters] = useState<Partial<SearchFilters>>({
    limit: PAGE_SIZE,
    offset: 0,
  });
  const [chatQuestion, setChatQuestion] = useState<string>('');
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [chatRows, setChatRows] = useState<PropertySummary[]>([]);
  const [chatHistory, setChatHistory] = useState<ChatTurn[]>(loadStoredChatHistory);
  const [chatContextFilters, setChatContextFilters] = useState<
    ChatResponse['filters'] | undefined
  >(() => {
    const history = loadStoredChatHistory();
    return history.length > 0 ? history[history.length - 1].filters : undefined;
  });
  const [hasMounted, setHasMounted] = useState(false);
  const transcriptRef = useRef<HTMLDivElement | null>(null);
  const cacheAttemptedRef = useRef(false);
  const cacheAppliedRef = useRef(false);

  const handleApply = async (
    nextFilters: Partial<SearchFilters>,
    options?: { updateUrl?: boolean; preserveResults?: boolean },
  ) => {
    const shouldUpdateUrl = options?.updateUrl ?? true;
    const shouldPreserveResults = options?.preserveResults ?? false;
    const rawYear = nextFilters.year_min;
    const parsedYear =
      typeof rawYear === 'string'
        ? Number.parseInt(rawYear, 10)
        : typeof rawYear === 'number' && Number.isFinite(rawYear)
          ? rawYear
          : undefined;
    const yearValue = Number.isFinite(parsedYear) ? parsedYear : undefined;
    const appliedLimit = clampLimit(nextFilters.limit ?? limit) ?? PAGE_SIZE;
    const baseFilters: Partial<SearchFilters> = {
      ...nextFilters,
      limit: appliedLimit,
      offset: 0,
      year_min: yearValue,
    };

    const params = buildSearchParams(baseFilters);
    const qs = params.toString();
    const currentQs = searchParams?.toString() ?? '';
    if (shouldUpdateUrl && qs !== currentQs) {
      router.push(`/search${qs ? `?${qs}` : ''}`, { scroll: false });
    }

    setIsLoading(true);
    setError(null);
    setPage(0);
    setIsEnd(false);
    if (!shouldPreserveResults) {
      setResults([]);
      setTotal(null);
    }
    setLimit(appliedLimit);
    setActiveFilters(baseFilters);

    const url = `${API_BASE}/api/search${qs ? `?${qs}` : ''}`;
    console.debug('PF-FE-SEARCH', url);

    try {
      // Paging: reset to page 0 and fetch PAGE_SIZE rows; subsequent clicks use offset to append.
      const res = await fetch(url, { cache: 'no-store' });
      if (!res.ok) {
        throw new Error(`Request failed with status ${res.status}`);
      }
      const data = toSearchResponse(await res.json());
      const mapped = data.items.map(mapToCard);
      setResults(mapped);
      setTotal(data.total);
      setPage(0);
      setIsEnd(mapped.length >= data.total);
      setHasSearched(true);
      saveResultsCache(mapped, data.total, baseFilters);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Unable to fetch search results';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    handleApply({
      q: query.trim() === '' ? undefined : query.trim(),
      borough: boroughFilter === '' ? undefined : (boroughFilter as SearchFilters['borough']),
      limit,
      offset: 0,
      year_min:
        yearMin === ''
          ? undefined
          : Number.isFinite(Number.parseInt(String(yearMin), 10))
            ? Number.parseInt(String(yearMin), 10)
            : undefined,
    });
  };

  const handleChatSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const text = chatQuestion.trim();
    if (!text) return;

    setChatLoading(true);
    setChatError(null);
    const userTurn: ChatTurn = {
      id: generateChatTurnId(),
      role: 'user',
      user: text,
      assistant: '',
      total: 0,
      filters: undefined,
      rows: [],
    };
    setChatHistory((prev) => [...prev, userTurn]);
    setChatLoading(true);
    const body = {
      message: text,
      borough: activeFilters.borough || null,
      year_min: activeFilters.year_min ?? null,
      previous_filters: chatContextFilters ?? null,
    };

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        throw new Error(`Chat request failed with status ${res.status}`);
      }
      const data: ChatResponse = await res.json();
      const assistantMessage = typeof data.message === 'string' ? data.message : '';
      const mappedRows: PropertySummary[] = Array.isArray(data.rows)
        ? data.rows.map((row: any) => ({ ...row }))
        : [];
      const nextTotal =
        typeof data.total === 'number' && Number.isFinite(data.total)
          ? data.total
          : mappedRows.length;
      const sanitizedFilters = sanitizeChatFilters(data.filters);
      const filtersFromChat = data.filters || {};
      const previewRows = toPreviewRows(mappedRows);
      const nextFilters: Partial<SearchFilters> = {
        q: filtersFromChat.q ?? text,
        borough:
          typeof filtersFromChat.borough === 'string' && filtersFromChat.borough.trim() !== ''
            ? (filtersFromChat.borough as SearchFilters['borough'])
            : undefined,
        year_min: filtersFromChat.year_min ?? undefined,
        limit: PAGE_SIZE,
        offset: 0,
      };

      setResults(mappedRows);
      setTotal(nextTotal);
      setPage(0);
      setLimit(PAGE_SIZE);
      setIsEnd(mappedRows.length >= nextTotal);
      setHasSearched(true);
      setError(null);
      setActiveFilters(nextFilters);
      setChatRows(mappedRows);
      setChatContextFilters(sanitizedFilters);
      setChatQuestion('');
      setChatHistory((prev) => {
        const newTurn: ChatTurn = {
          id: generateChatTurnId(),
          role: 'assistant',
          user: text,
          assistant: assistantMessage,
          total: nextTotal,
          filters: sanitizedFilters,
          rows: previewRows,
        };
        return [...prev, newTurn];
      });
      saveResultsCache(mappedRows, nextTotal, nextFilters);

      const params = buildSearchParams(nextFilters);
      const qs = params.toString();
      router.push(`/search${qs ? `?${qs}` : ''}`, { scroll: false });
    } catch (err) {
      console.error('PF-FE-SEARCH chat error', err);
      setChatError('Something went wrong with chat. Try again.');
    } finally {
      setChatLoading(false);
    }
  };

  useEffect(() => {
    if (!hasMounted) return;
    if (cacheAttemptedRef.current) return;
    cacheAttemptedRef.current = true;
    const { urlQ, urlBorough, yearValue } = extractUrlFilters(searchParams ?? null);
    const targetFilters: Partial<SearchFilters> = {
      q: urlQ || undefined,
      borough: (urlBorough || undefined) as SearchFilters['borough'] | undefined,
      year_min: yearValue,
    };
    const cached = loadResultsCache();
    if (cached && cacheFiltersMatch(cached.filters, targetFilters)) {
      cacheAppliedRef.current = true;
      setResults(cached.rows);
      setTotal(cached.total);
      setHasSearched(true);
      setIsEnd(cached.rows.length >= cached.total);
      setError(null);
      setActiveFilters((prev) => ({
        ...prev,
        q: cached.filters.q ?? undefined,
        borough: (cached.filters.borough as SearchFilters['borough']) ?? undefined,
        year_min: cached.filters.year_min ?? undefined,
        limit: PAGE_SIZE,
        offset: 0,
      }));
    }
  }, [hasMounted, searchParams]);

  useEffect(() => {
    if (!hasMounted || !searchParams) return;

    const { urlQ, urlBorough, yearValue } = extractUrlFilters(searchParams);

    const hasParams = urlQ !== '' || urlBorough !== '' || typeof yearValue === 'number';
    if (!hasParams) return;

    setQuery(urlQ);
    setBoroughFilter(urlBorough);
    setYearMin(typeof yearValue === 'number' ? yearValue : '');

    const matchesActive =
      (activeFilters.q ?? '') === urlQ &&
      (activeFilters.borough ?? '') === urlBorough &&
      String(activeFilters.year_min ?? '') === String(yearValue ?? '');
    if (hasSearched && matchesActive) {
      return;
    }

    const preserveResults = cacheAppliedRef.current;
    if (preserveResults) {
      cacheAppliedRef.current = false;
    }
    handleApply(
      {
        q: urlQ || undefined,
        borough: (urlBorough || undefined) as SearchFilters['borough'] | undefined,
        year_min: yearValue,
        limit: PAGE_SIZE,
        offset: 0,
      },
      { updateUrl: false, preserveResults },
    );
  }, [
    hasMounted,
    searchParams,
    activeFilters.borough,
    activeFilters.q,
    activeFilters.year_min,
    hasSearched,
  ]);

  useEffect(() => {
    setHasMounted(true);
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      window.sessionStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(chatHistory));
    } catch {
      // ignore write errors
    }
  }, [chatHistory]);

  useEffect(() => {
    if (chatHistory.length === 0) {
      setChatContextFilters(undefined);
      return;
    }
    setChatContextFilters(chatHistory[chatHistory.length - 1].filters);
  }, [chatHistory]);

  useEffect(() => {
    if (!hasMounted) return;
    const container = transcriptRef.current;
    if (!container) return;
    container.scrollTop = container.scrollHeight;
  }, [chatHistory, chatLoading, hasMounted]);

  const fieldClasses =
    'w-full rounded-lg border border-charcoal_brown-600 bg-carbon_black-300 px-3 py-2 text-sm text-floral_white placeholder:text-dust_grey-500 focus:border-spicy_paprika-500 focus:ring-2 focus:ring-spicy_paprika-500 focus:outline-none transition';

  const boroughLabels: Record<NonNullable<SearchFilters['borough']>, string> = {
    MN: 'Manhattan',
    BX: 'Bronx',
    BK: 'Brooklyn',
    QN: 'Queens',
    SI: 'Staten Island',
  };

  const formatChatFilters = (filters?: ChatResponse['filters']) => {
    if (!filters) return '';
    const parts: string[] = [];
    const queryText = typeof filters.q === 'string' ? filters.q.trim() : '';
    if (queryText) {
      parts.push(`q="${queryText}"`);
    }
    const boroughCode = filters.borough;
    if (boroughCode && typeof boroughCode === 'string') {
      const label =
        boroughLabels[boroughCode as NonNullable<SearchFilters['borough']>] ?? boroughCode;
      parts.push(`borough=${label}`);
    }
    if (typeof filters.year_min === 'number' && Number.isFinite(filters.year_min)) {
      parts.push(`year ≥ ${filters.year_min}`);
    }

    return parts.length > 0 ? `Filters → ${parts.join(', ')}` : '';
  };

  const activeQuery = typeof activeFilters.q === 'string' ? activeFilters.q.trim() : '';
  const activeBorough = activeFilters.borough;
  const boroughLabel = activeBorough ? boroughLabels[activeBorough] ?? activeBorough : '';
  const shouldShowSummary = hasSearched && total !== null && !error;

  const summaryText = (() => {
    if (!shouldShowSummary || total === null) return '';
    if (activeQuery) {
      return `Showing ${results.length} of ${total} matches for "${activeQuery}"${
        boroughLabel ? ` in ${boroughLabel}` : ''
      }`;
    }
    if (boroughLabel) {
      return `Showing ${results.length} of ${total} properties in ${boroughLabel}`;
    }
    return `Showing ${results.length} of ${total} properties matching your filters`;
  })();

  const latestChatTurn =
    chatHistory.length > 0 ? chatHistory[chatHistory.length - 1] : null;
  const previewChatRows = chatRows.slice(0, 5);
  const previewCount = previewChatRows.length;

  const handleLoadMore = async () => {
    if (isLoading || isLoadingMore || isEnd || total === null) return;
    const nextPage = page + 1;
    const nextOffset = nextPage * limit;
    const params = buildSearchParams({
      ...activeFilters,
      limit,
      offset: nextOffset,
    });
    const qs = params.toString();
    const url = `${API_BASE}/api/search${qs ? `?${qs}` : ''}`;
    console.debug('PF-FE-SEARCH load more', url);

    setIsLoadingMore(true);
    setError(null);

    try {
      const res = await fetch(url, { cache: 'no-store' });
      if (!res.ok) {
        throw new Error(`Request failed with status ${res.status}`);
      }
      const data = toSearchResponse(await res.json());
      const mapped = data.items.map(mapToCard);
      const combinedRows = [...results, ...mapped];
      const nextTotal = data.total ?? total ?? combinedRows.length;
      setTotal(nextTotal);
      setResults(combinedRows);
      setPage(nextPage);
      setIsEnd(combinedRows.length >= nextTotal);
      saveResultsCache(combinedRows, nextTotal, activeFilters);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Unable to fetch search results';
      setError(message);
    } finally {
      setIsLoadingMore(false);
    }
  };

  return (
    <div className="min-h-screen bg-carbon_black text-floral_white-500">
      <div className="mx-auto max-w-5xl p-6">
        <h1 className="mb-4 text-2xl font-bold text-floral_white-500">Search</h1>
        <form
          onSubmit={handleSubmit}
          className="mb-6 rounded-xl border border-charcoal_brown-600 bg-charcoal_brown-400 p-4 shadow-sm"
        >
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3 lg:grid-cols-4 lg:items-end">
            <div className="flex flex-col gap-2 lg:col-span-2">
              <label className="text-xs uppercase tracking-wide text-dust_grey-500">
                Search
              </label>
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Address or BBL"
                className={fieldClasses}
              />
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-xs uppercase tracking-wide text-dust_grey-500">
                Borough
              </label>
              <select
                value={boroughFilter}
                onChange={(e) => setBoroughFilter(e.target.value)}
                className={fieldClasses}
              >
                <option value="">Any</option>
                <option value="MN">Manhattan</option>
                <option value="BX">Bronx</option>
                <option value="BK">Brooklyn</option>
                <option value="QN">Queens</option>
                <option value="SI">Staten Island</option>
              </select>
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-xs uppercase tracking-wide text-dust_grey-500">
                Year ≥
              </label>
              <input
                type="number"
                inputMode="numeric"
                value={yearMin}
                onChange={(e) =>
                  setYearMin(e.target.value === '' ? '' : Number(e.target.value))
                }
                placeholder="e.g. 1920"
                className={fieldClasses}
              />
            </div>
            <div className="flex items-end">
              <button
                type="submit"
                disabled={isLoading}
                className="w-full rounded-lg px-6 py-2 font-medium text-floral_white-500 shadow-sm transition-colors duration-150 sm:w-auto bg-spicy_paprika-500 hover:bg-spicy_paprika-400 disabled:cursor-not-allowed disabled:bg-spicy_paprika-300"
              >
                {isLoading ? 'Searching…' : 'Apply'}
              </button>
            </div>
          </div>
        </form>
        {!hasSearched && !isLoading && (
          <div className="py-6 text-center text-sm text-dust_grey-500">
            Enter filters and click Apply to see results.
          </div>
        )}
        {isLoading && (
          <div className="text-sm text-dust_grey-400">Loading…</div>
        )}
        {error && !isLoading && (
          <div className="text-sm text-spicy_paprika-500">Error: {error}</div>
        )}
        <div className="mb-6 rounded-lg border border-neutral-800 bg-neutral-900 p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-300">
            Ask PropertyFish <span className="ml-1 text-[10px] font-normal text-neutral-500">beta</span>
          </h2>
          <form onSubmit={handleChatSubmit} className="mt-3 flex gap-2">
            <input
              type="text"
              value={chatQuestion}
              onChange={(e) => setChatQuestion(e.target.value)}
              placeholder="Ask about buildings or areas you care about"
              className="flex-1 rounded-md border border-neutral-700 bg-neutral-950 px-3 py-2 text-sm text-neutral-100 placeholder:text-neutral-500 focus:outline-none focus:ring-1 focus:ring-neutral-400"
            />
            <button
              type="submit"
              disabled={chatLoading}
              className="rounded-md bg-neutral-100 px-4 py-2 text-sm font-medium text-black disabled:opacity-60"
            >
              {chatLoading ? 'Thinking…' : 'Ask'}
            </button>
          </form>
          {chatError && <p className="mt-2 text-xs text-red-400">{chatError}</p>}
          <div className="mt-4">
            <div
              ref={transcriptRef}
              className="max-h-[420px] space-y-4 overflow-y-auto pr-1 text-sm text-neutral-200"
            >
              {hasMounted ? (
                <>
                  {chatHistory.length > 0 ? (
                    chatHistory.map((turn) => {
                      const role =
                        turn.role ??
                        (turn.user && turn.assistant ? 'combined' : turn.assistant ? 'assistant' : 'user');
                      const filterSummary = formatChatFilters(turn.filters);
                      const matchesLabel = `${turn.total} ${turn.total === 1 ? 'match' : 'matches'}`;
                      const friendlyLine = `I found ${turn.total} ${
                        turn.total === 1 ? 'property' : 'properties'
                      } that match your request.`;
                      const assistantContext = turn.assistant?.trim()
                        ? turn.assistant.trim()
                        : filterSummary;
                      return (
                        <div key={turn.id} className="space-y-3">
                          {(role === 'user' || role === 'combined') && turn.user && (
                            <div className="flex justify-end">
                              <div className="max-w-[80%] text-right">
                                <p className="mb-1 text-[11px] uppercase tracking-wide text-neutral-500">
                                  You
                                </p>
                                <div className="inline-block rounded-2xl border border-neutral-700 bg-neutral-900/70 px-4 py-2 text-sm text-neutral-100">
                                  {turn.user}
                                </div>
                              </div>
                            </div>
                          )}
                          {(role === 'assistant' || role === 'combined') && turn.assistant && (
                            <div className="flex justify-start">
                              <div className="max-w-[85%]">
                                <p className="mb-1 text-[11px] uppercase tracking-wide text-neutral-500">
                                  PropertyFish
                                </p>
                                <div className="rounded-2xl border border-neutral-800 bg-neutral-950 px-4 py-3 text-neutral-100">
                                  <p className="text-sm text-neutral-100">{friendlyLine}</p>
                                  {assistantContext && (
                                    <p className="mt-1 text-xs text-neutral-400">
                                      {assistantContext}
                                    </p>
                                  )}
                                  {turn.rows.length > 0 && (
                                    <ul className="mt-3 space-y-2 text-xs text-neutral-300">
                                      {turn.rows.map((row) => {
                                        const boroughCode =
                                          typeof row.borough === 'string'
                                            ? (row.borough as NonNullable<SearchFilters['borough']>)
                                            : undefined;
                                        const boroughName =
                                          row.borough_full ??
                                          (boroughCode ? boroughLabels[boroughCode] : undefined) ??
                                          row.borough;
                                        const yearBuilt = row.yearbuilt ?? row.year_built;
                                        return (
                                          <li
                                            key={`${turn.id}-${row.bbl}`}
                                            className="rounded-md border border-neutral-800 bg-neutral-900/70 p-2"
                                          >
                                            <div className="text-sm text-neutral-100">
                                              {row.address ?? 'Unknown address'}
                                            </div>
                                            <div className="text-[11px] text-neutral-500">
                                              {boroughName ?? '—'}
                                              {yearBuilt ? ` · Built ${yearBuilt}` : ''}
                                            </div>
                                          </li>
                                        );
                                      })}
                                    </ul>
                                  )}
                                  <p className="mt-2 text-[11px] text-neutral-600">
                                    {matchesLabel}
                                    {filterSummary && <> · {filterSummary}</>}
                                  </p>
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })
                  ) : (
                    !chatLoading && (
                      <p className="text-center text-xs text-neutral-500">
                        Start a conversation to have PropertyFish search for you.
                      </p>
                    )
                  )}
                  {chatLoading && (
                    <div className="space-y-3">
                      <div className="flex justify-start">
                        <div className="max-w-[85%]">
                          <p className="mb-1 text-[11px] uppercase tracking-wide text-neutral-500">
                            PropertyFish
                          </p>
                          <div className="rounded-2xl border border-neutral-800 bg-neutral-950 px-4 py-3 text-neutral-100">
                            <p className="text-sm text-neutral-100">PropertyFish is searching…</p>
                            <div className="mt-2 flex items-center gap-1">
                              {[0, 1, 2].map((dot) => (
                                <span
                                  key={dot}
                                  className="h-2 w-2 rounded-full bg-neutral-400 animate-bounce"
                                  style={{
                                    animationDelay: `${dot * 0.15}s`,
                                    animationDuration: '1s',
                                  }}
                                />
                              ))}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="py-6 text-center text-xs text-neutral-600">
                  Loading conversation…
                </div>
              )}
            </div>
          </div>
          {chatRows.length > 0 && (
            <div className="mt-3 text-xs text-neutral-400">
              <p className="mb-1 text-[11px] uppercase tracking-wide text-neutral-500">
                Showing up to {previewCount} of {latestChatTurn?.total ?? chatRows.length} matches
              </p>
              <ul className="space-y-1">
                {previewChatRows.map((row) => (
                  <li key={row.bbl}>
                    <span className="text-neutral-200">{row.address ?? 'Unknown address'}</span>
                    {row.borough_full && <> · {row.borough_full}</>}
                    {row.yearbuilt && <> · Built {row.yearbuilt}</>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        {shouldShowSummary && (
          <div className="mb-4 text-sm text-dust_grey-400">{summaryText}</div>
        )}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {results.map((item) => (
            <Link
              key={item.bbl}
              href={`/property/${encodeURIComponent(item.bbl)}`}
              className="block h-full"
            >
              <div className="h-full cursor-pointer rounded-lg border border-charcoal_brown-600 bg-charcoal_brown-400 p-4 shadow-sm transition hover:border-spicy_paprika-500 hover:shadow-md">
                <div className="mb-3 flex h-28 w-full items-center justify-center rounded-md bg-neutral-800/80 text-[10px] uppercase tracking-wide text-neutral-500">
                  Photo coming soon
                </div>
                <div className="text-sm font-semibold uppercase tracking-wide text-floral_white-500">
                  {item.address ?? 'Unknown address'}
                </div>
                <div className="mt-1 text-xs text-dust_grey-400">
                  {(item.borough_full ?? '—') + ' · ' + (item.zonedist1 ?? 'Zoning —')}
                </div>
                <div className="mt-2 text-xs text-dust_grey-300">
                  Year built: {item.yearbuilt ?? '—'} · Units: {item.unitsres ?? 0}/
                  {item.unitstotal ?? 0}
                </div>
                <div className="mt-2 text-xs text-dust_grey-300">
                  Permits (12m): {item.permit_count_12m ?? 0} · Last: {item.last_permit_date ?? '—'}
                </div>
                <div className="mt-2 text-xs text-dust_grey-300">
                  Zoning: {item.zonedist1 ?? '—'} · Land use: {item.landuse ?? '—'}
                </div>
                {(typeof item.bldgarea === 'number' && Number.isFinite(item.bldgarea)) ||
                (typeof item.lotarea === 'number' && Number.isFinite(item.lotarea)) ? (
                  <div className="mt-2 text-xs text-dust_grey-300">
                    Area: {typeof item.bldgarea === 'number' && Number.isFinite(item.bldgarea)
                      ? `${item.bldgarea.toLocaleString()} sf`
                      : '—'}{' '}
                    · Lot:{' '}
                    {typeof item.lotarea === 'number' && Number.isFinite(item.lotarea)
                      ? `${item.lotarea.toLocaleString()} sf`
                      : '—'}
                  </div>
                ) : null}
              </div>
            </Link>
          ))}
        </div>
        {!isLoading && hasSearched && !error && results.length === 0 && (
          <p className="mt-8 text-sm text-dust_grey-500">
            No properties found. Try broadening your search (for example, just "82nd street" or
            removing the year filter).
          </p>
        )}
        {results.length > 0 && !isEnd && total !== null && results.length < total && !isLoading && (
          <div className="mt-6 flex justify-center">
            <button
              type="button"
              onClick={handleLoadMore}
              disabled={isLoading || isLoadingMore}
              className="rounded-lg bg-charcoal_brown-500 px-6 py-2 text-sm font-medium text-floral_white-500 transition hover:bg-charcoal_brown-400 disabled:cursor-not-allowed disabled:bg-charcoal_brown-700"
            >
              {isLoadingMore ? 'Loading…' : 'Load more'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

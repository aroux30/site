# Admin page data-layer migration

Every admin page loaded its own data with `useEffect` + `useState(loading)` +
`useState(error)` + a hand-written `try/catch`. Fifty-seven copies of that
block meant fifty-seven places to get error handling wrong, and some of them
failed silently — the products page showed fabricated rows because its `catch`
did nothing. This replaces that pattern with one shared path.

## The hook

`lib/api/admin-query.ts` exports three things:

- `useAdminQuery({ queryKey, queryFn, fallbackError, enabled?, options?, toastOnError? })`
  returns `{ data, loading, error, reload }` — the same shape the old local
  state had, so call sites barely change.
- `useAdminMutation()` runs a write, invalidates the given cache keys and
  returns `{ ok: true, data } | { ok: false, error }`.
- `useAdminInvalidate()` invalidates keys directly, for the rarer cases.

## Migration shape

Before:

```tsx
const [items, setItems] = useState<Thing[]>([]);
const [loading, setLoading] = useState(true);
const [error, setError] = useState<string | null>(null);

const load = useCallback(async () => {
  setLoading(true);
  setError(null);
  try {
    const res = await thingsApi.list();
    setItems(res.items);
  } catch (reason) {
    setError(errorText(reason, "دریافت فهرست ناموفق بود"));
  } finally {
    setLoading(false);
  }
}, []);
useEffect(() => { void load(); }, [load]);
```

After:

```tsx
const { data, loading, error, reload: load } = useAdminQuery({
  queryKey: [THING_QUERY_KEY],
  queryFn: () => thingsApi.list(),
  fallbackError: "دریافت فهرست ناموفق بود",
});
const items: Thing[] = data?.items ?? [];
```

Writes:

```tsx
const runMutation = useAdminMutation();
const result = await runMutation(
  () => thingsApi.update(id, payload),
  { fallbackError: "ذخیره ناموفق بود", invalidateKeys: [[THING_QUERY_KEY]] },
);
if (!result.ok) setFormError(result.error);
```

## Rules

1. **Do not change behaviour.** The migration is mechanical. Same requests,
   same messages, same field names. If the old code did something odd, keep
   the oddity and note it — a migration is not the place for a redesign.
2. **Delete the local `errorText` / `errorDetail` / `operationError` helper.**
   `apiErrorMessage` in `lib/api/error-message.ts` already does this job and
   the hook applies it. Six local copies exist; they must not survive.
3. **`data ?? []`, not a default object in state.** The old pages initialised
   to `[]` and rendered it before the first response; `undefined ?? []` gives
   the same first paint without a fake value living in state.
4. **Keep `reload` named `load` at the call site** where the page already has a
   refresh button calling `load()`. Rename only if the page has no such button.
5. **Query keys are stable arrays.** `["admin-orders", page, status]`, never an
   inline object. A key that changes identity every render refetches forever.
6. **`toastOnError: true`** only where the page currently reports load failure
   with a toast. Otherwise leave it off and render `error`.
7. **Local `saving` state stays.** The hook does not manage write-in-progress;
   buttons rely on it to prevent double-submits.
8. **Test after every page:** `npx tsc --noEmit` must stay at zero errors, and
   `npx vitest run` at 40 passing.
9. **Prune dead imports by hand.** `noUnusedLocals` is off, so `tsc` will not
   catch the `useCallback`/`useEffect` you removed — grep each migrated page
   for `useEffect(`, `useCallback(` and for each leftover `useState` of
   items/loading/error, and remove what no longer has a call site. A deleted
   fetch with a kept import is still dead code.

## What must not regress

These were real bugs found in this codebase and the migration must not bring
them back:

- A failing request must never render as an empty-but-successful list. That is
  why `error` is separate from `data` and why the toast path deduplicates.
- A stuck spinner: `loading` is `isPending || isFetching`, so it clears on
  both the first load and a background refetch.
- Double-submit on save: `saving` is set before the await and cleared after.
- Two independent fetches on one page (e.g. warehouses + stock) must share ONE
  query so they cannot disagree — combine them in `queryFn` with `Promise.all`
  and return both under one key.

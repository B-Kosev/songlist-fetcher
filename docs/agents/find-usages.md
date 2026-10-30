# Finding all usages of a symbol

When a conclusion rests on "every caller / usage / call site of X", resolve it with the TypeScript compiler, not grep. Grep misses renamed imports, aliases and functions passed through wrappers, and it can't tell a call from a comment or a type. Use grep only to cross-check.

## Tool

`apps/iriskmanager-forge-app/scripts/find-callers.mjs` walks the TypeScript call hierarchy (the same thing as "Show Call Hierarchy" in an editor). It only reads files, so read-only subagents can run it.

```bash
cd apps/iriskmanager-forge-app
node scripts/find-callers.mjs tsconfig.json src/lib/jira-key-search.ts searchJqlByKeys --depth 2
```

- Output: `file:line  callerName`, one per call. Callers of callers are indented, down to `--depth` levels (default 1). Each caller is expanded once, so a caller reached by a second path is listed but not expanded again under it. The list is complete; the indentation is not a full call tree.
- A whole call sweep takes a few seconds.
- `tsconfig.json` covers `src/` except `src/ui-kit` and stories. For those, run it again with `tsconfig.ui-kit.json` or `tsconfig.stories.json`.

## Procedure

1. **Run the script on the symbol.** For an external API (for example `requestJira` from `@forge/api`), start from our wrappers around it. Run it on each wrapper, with enough `--depth` to get past our own wrapper layers.
2. **Cross-check with grep** over the same files, for the symbol name and any obvious aliases.
3. **Explain every difference, in both directions.** A grep-only hit is usually a comment, a type, a mock or a re-export. A script-only hit is usually an alias or a renamed import. Don't seal the inventory until each difference has a reason.

## Blind spots

The call hierarchy follows declarations. It does not see:

- **Calls through a function-typed parameter, or a function returned by another function.** For example, a `JiraRequestFn` injected into a service, or the result of `jiraRequestFor(...)`. Find the references to the type, or to the factory, as well.
- **Values typed `any`, and dynamic property access** (`obj[name](...)`).
- **Code outside the tsconfig you pass,** such as root `scripts/` and `e2e/` (which has its own `e2e/tsconfig.json`). Cover those with a separate run or with grep.

## Briefing a subagent

Name this file in the brief ("use `docs/agents/find-usages.md`"). Ask for the script output, the grep cross-check and the explained differences, not a summary from grep alone.

import { useCallback, useEffect, useState } from "react";
import { storage } from "@/lib/utils";

const KEY = "inccorpai.checklists.v1";
type Store = Record<string, Record<string, number>>; // checklistKey -> itemId -> filedAt (ms)

let memory: Store = storage.get<Store>(KEY, {});
const listeners = new Set<() => void>();

function commit(next: Store) {
  memory = next;
  storage.set(KEY, memory);
  listeners.forEach((l) => l());
}

/**
 * Shared, persisted tick state for a checklist. The same checklist shown inline in the
 * conversation and in the dossier panel stays in sync because both read this store.
 */
export function useChecklist(checklistKey: string) {
  const [, force] = useState(0);
  useEffect(() => {
    const l = () => force((n) => n + 1);
    listeners.add(l);
    return () => void listeners.delete(l);
  }, []);

  const filed = memory[checklistKey] ?? {};

  const toggle = useCallback(
    (itemId: string) => {
      const cur = { ...(memory[checklistKey] ?? {}) };
      if (cur[itemId]) delete cur[itemId];
      else cur[itemId] = Date.now();
      commit({ ...memory, [checklistKey]: cur });
    },
    [checklistKey],
  );

  const reset = useCallback(() => {
    const next = { ...memory };
    delete next[checklistKey];
    commit(next);
  }, [checklistKey]);

  return { filed, toggle, reset };
}

"use client";

import * as React from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { type TransactionFilters } from "@/lib/api";
import { Search, X } from "lucide-react";

interface Props {
  filters: TransactionFilters;
  onChange: (f: TransactionFilters) => void;
}

export function TransactionFiltersBar({ filters, onChange }: Props) {
  const clear = () =>
    onChange({ page: 1, page_size: 50 });

  const hasActive = !!(
    filters.search || filters.date_from || filters.date_to ||
    filters.category_id || filters.amount_min || filters.amount_max
  );

  return (
    <div className="flex flex-wrap items-end gap-3">
      {/* Search */}
      <div className="relative flex-1 min-w-[180px]">
        <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input
          className="pl-9"
          placeholder="Search description…"
          value={filters.search ?? ""}
          onChange={(e) => onChange({ ...filters, page: 1, search: e.target.value || undefined })}
        />
      </div>

      {/* Date range */}
      <div className="space-y-1">
        <Label>From</Label>
        <Input
          type="date"
          className="w-36"
          value={filters.date_from ?? ""}
          onChange={(e) => onChange({ ...filters, page: 1, date_from: e.target.value || undefined })}
        />
      </div>
      <div className="space-y-1">
        <Label>To</Label>
        <Input
          type="date"
          className="w-36"
          value={filters.date_to ?? ""}
          onChange={(e) => onChange({ ...filters, page: 1, date_to: e.target.value || undefined })}
        />
      </div>

      {/* Amount range */}
      <div className="space-y-1">
        <Label>Min ₹</Label>
        <Input
          type="number"
          className="w-28"
          placeholder="–"
          value={filters.amount_min ?? ""}
          onChange={(e) =>
            onChange({ ...filters, page: 1, amount_min: e.target.value ? Number(e.target.value) : undefined })
          }
        />
      </div>
      <div className="space-y-1">
        <Label>Max ₹</Label>
        <Input
          type="number"
          className="w-28"
          placeholder="–"
          value={filters.amount_max ?? ""}
          onChange={(e) =>
            onChange({ ...filters, page: 1, amount_max: e.target.value ? Number(e.target.value) : undefined })
          }
        />
      </div>

      {hasActive && (
        <Button variant="ghost" size="sm" onClick={clear} className="gap-1.5">
          <X className="h-3.5 w-3.5" />
          Clear
        </Button>
      )}
    </div>
  );
}

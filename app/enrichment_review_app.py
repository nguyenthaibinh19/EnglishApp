"""Enrichment Review dialog (Phase 15B).

Reusable Tk component. Production Word Detail only opens this when an
enrichment provider is explicitly configured — no fake data for real users.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

import config
import ui_common
from vocabulary_enrichment import (
    EnrichmentApplySelection,
    EnrichmentDraft,
    EnrichmentReviewState,
    VocabularyEnrichmentService,
    apply_enrichment,
    build_review_state,
)


class EnrichmentReviewDialog:
    """Show current vs suggested enrichment; apply only selected fields."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        entry: dict,
        draft: EnrichmentDraft,
        on_apply: Optional[Callable[[EnrichmentApplySelection], None]] = None,
        form_labels: Optional[dict] = None,
    ):
        self.entry = entry
        self.draft = draft
        self.on_apply = on_apply
        self._vars: dict[str, tk.BooleanVar] = {}
        self._suggested_vars: dict[str, tk.StringVar] = {}

        labels = form_labels or {
            "plural": config.ui("Số nhiều", "Plural"),
            "past": config.ui("Quá khứ", "Past"),
            "past_participle": config.ui("Quá khứ phân từ", "Past participle"),
            "comparative": config.ui("So sánh hơn", "Comparative"),
            "superlative": config.ui("So sánh nhất", "Superlative"),
        }
        self.state = build_review_state(entry, draft, form_labels=labels)

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(config.ui("Xem xét làm giàu từ", "Review enrichment"))
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self._build()

    def _build(self):
        frame = ttk.Frame(self.dialog, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame,
            text=config.ui(
                "Chọn các gợi ý muốn áp dụng. Dữ liệu hiện tại không bị ghi đè nếu bạn không chọn.",
                "Select suggestions to apply. Current data is not overwritten unless selected.",
            ),
            style="Muted.TLabel",
            wraplength=480,
        ).pack(anchor="w")

        source = self.state.source
        ttk.Label(
            frame,
            text=config.ui(f"Nguồn: {source}", f"Source: {source}"),
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(4, 10))

        items = self.state.visible_items()
        if not items:
            ttk.Label(
                frame,
                text=config.ui("Không có gợi ý.", "No suggestions."),
                style="Muted.TLabel",
            ).pack(anchor="w")
        else:
            for item in items:
                block = ttk.Frame(frame, padding=(0, 0, 0, 10))
                block.pack(fill=tk.X, anchor="w")
                selected = tk.BooleanVar(value=item.selected)
                self._vars[item.key] = selected
                ttk.Checkbutton(
                    block,
                    text=item.label,
                    variable=selected,
                ).pack(anchor="w")
                ttk.Label(
                    block,
                    text=config.ui(
                        f"Hiện tại: {item.current}",
                        f"Current: {item.current}",
                    ),
                    style="Muted.TLabel",
                    wraplength=460,
                ).pack(anchor="w", padx=(22, 0))
                suggested_var = tk.StringVar(value=item.suggested)
                self._suggested_vars[item.key] = suggested_var
                row = ttk.Frame(block)
                row.pack(fill=tk.X, padx=(22, 0), pady=(2, 0))
                ttk.Label(
                    row,
                    text=config.ui("Gợi ý:", "Suggested:"),
                    style="Muted.TLabel",
                ).pack(side=tk.LEFT)
                ttk.Entry(row, textvariable=suggested_var, width=42).pack(
                    side=tk.LEFT, padx=(6, 0)
                )

        buttons = ttk.Frame(frame)
        buttons.pack(fill=tk.X, pady=(12, 0))
        ttk.Button(
            buttons,
            text=config.ui("Áp dụng đã chọn", "Apply selected"),
            style="Primary.TButton",
            command=self._apply,
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(
            buttons,
            text=config.ui("Hủy", "Cancel"),
            command=self.dialog.destroy,
        ).pack(side=tk.LEFT)

    def _current_state(self) -> EnrichmentReviewState:
        state = self.state
        for key, var in self._vars.items():
            state = state.with_selection(key, bool(var.get()))
        for key, var in self._suggested_vars.items():
            state = state.with_suggested(key, var.get())
        return state

    def _apply(self):
        selection = self._current_state().to_selection()
        if callable(self.on_apply):
            self.on_apply(selection)
        self.dialog.destroy()


def open_enrichment_review(
    parent: tk.Misc,
    *,
    entry: dict,
    draft: EnrichmentDraft,
    on_apply: Optional[Callable[[EnrichmentApplySelection], None]] = None,
) -> EnrichmentReviewDialog:
    return EnrichmentReviewDialog(
        parent, entry=entry, draft=draft, on_apply=on_apply
    )


def apply_selected_via_service(
    service: VocabularyEnrichmentService,
    store,
    index: int,
    draft: EnrichmentDraft,
    selection: EnrichmentApplySelection,
) -> bool:
    """Helper for callers that already have a service instance."""
    return service.apply_to_store(store, index, draft, selection)


# Re-export for tests that want a pure apply without UI.
__all__ = [
    "EnrichmentReviewDialog",
    "open_enrichment_review",
    "apply_selected_via_service",
    "apply_enrichment",
]

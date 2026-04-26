/* ===================================================================
   Dashboard Record Table Primitives
   =================================================================== */

"use strict";

function createRecordTablePrimitives(context) {
    const {
        dedupeRowsById,
        normalizeTextValue,
        safeInt,
        state,
        toTitleCaseFromSnake,
    } = context;

    function renderBadge(container, text, cls) {
        if (!container) return;
        container.innerHTML = "";
        const badge = document.createElement("span");
        badge.className = "badge";
        if (cls) {
            badge.classList.add(cls);
        }
        badge.textContent = text;
        container.appendChild(badge);
    }

    function updateCollectionCount(collectionKey, count, ...elements) {
        const safeCount = Number.isFinite(Number(count)) ? Number(count) : 0;
        state.collectionCounts[collectionKey] = safeCount;
        elements
            .filter(Boolean)
            .forEach((element) => {
                element.textContent = safeInt(safeCount);
            });
    }

    function setCellText(fragment, selector, value) {
        const cell = fragment.querySelector(selector);
        if (!cell) return;
        cell.textContent = value == null ? "" : String(value);
    }

    function applySessionStatusBadge(fragment, selector, statusValue, fallbackStatus) {
        const normalizedStatus = normalizeTextValue(statusValue || fallbackStatus).toLowerCase() || fallbackStatus;
        const badgeClass = normalizedStatus === "closed" ? "closed" : "open";
        renderBadge(
            fragment.querySelector(selector),
            toTitleCaseFromSnake(normalizedStatus),
            badgeClass,
        );
    }

    function configureModerationButton(fragment, entityId, entitySummary) {
        const button = fragment.querySelector(".moderation-delete");
        if (!button) return null;

        if (entityId == null || entityId === "") {
            button.hidden = true;
            button.dataset.entityId = "";
            button.dataset.entitySummary = "";
            return button;
        }

        button.hidden = false;
        button.dataset.entityId = String(entityId);
        button.dataset.entitySummary = normalizeTextValue(entitySummary) || "";
        return button;
    }

    function renderRecordTableRows(config) {
        const {
            rows,
            tableBody,
            templateElement,
            emptyText,
            collectionKey,
            countElements = [],
            onRowsPrepared,
            buildRow,
        } = config;

        const normalizedRows = dedupeRowsById(rows);
        if (collectionKey) {
            updateCollectionCount(collectionKey, normalizedRows.length, ...countElements);
        }
        if (typeof onRowsPrepared === "function") {
            onRowsPrepared(normalizedRows);
        }
        if (!tableBody || !templateElement || typeof buildRow !== "function") {
            return;
        }

        renderTableBodyRows(
            tableBody,
            normalizedRows,
            { emptyText },
            (rowData) => buildTemplateRow(templateElement, rowData, buildRow),
        );
    }

    return {
        applySessionStatusBadge,
        configureModerationButton,
        renderBadge,
        renderRecordTableRows,
        setCellText,
    };
}

function resolveTableRenderConfig(tableBody, options = {}) {
    const table = tableBody && typeof tableBody.closest === "function"
        ? tableBody.closest("table")
        : null;
    const tableHeaderCount = table ? table.querySelectorAll("thead th").length : 0;
    const emptyCell = tableBody ? tableBody.querySelector("td.table-empty") : null;

    const optionColspan = Number.parseInt(options.emptyColspan, 10);
    const markupColspan = emptyCell
        ? Number.parseInt(emptyCell.getAttribute("colspan") || "", 10)
        : 0;
    const emptyColspan = Number.isFinite(optionColspan) && optionColspan > 0
        ? optionColspan
        : (Number.isFinite(markupColspan) && markupColspan > 0
            ? markupColspan
            : (tableHeaderCount > 0 ? tableHeaderCount : 1));

    const optionText = String(options.emptyText || "").trim();
    const markupText = emptyCell ? String(emptyCell.textContent || "").trim() : "";
    const emptyText = optionText || markupText || "No rows available";

    return {
        emptyColspan,
        emptyText,
    };
}

function renderTableBodyRows(tableBody, rows, options, createRowFragment) {
    if (!tableBody) return;

    const { emptyColspan, emptyText } = resolveTableRenderConfig(tableBody, options || {});
    tableBody.innerHTML = "";
    if (!Array.isArray(rows) || rows.length === 0) {
        const emptyRow = document.createElement("tr");
        const emptyCell = document.createElement("td");
        emptyCell.colSpan = emptyColspan;
        emptyCell.className = "table-empty";
        emptyCell.textContent = emptyText;
        emptyRow.appendChild(emptyCell);
        tableBody.appendChild(emptyRow);
        return;
    }

    rows.forEach((row) => {
        const fragment = typeof createRowFragment === "function"
            ? createRowFragment(row)
            : null;
        if (fragment) {
            tableBody.appendChild(fragment);
        }
    });
}

function buildTemplateRow(templateElement, rowData, buildRow) {
    if (!templateElement || !templateElement.content || typeof buildRow !== "function") {
        return null;
    }
    const fragment = templateElement.content.cloneNode(true);
    buildRow(fragment, rowData);
    return fragment;
}

export {
    createRecordTablePrimitives,
};

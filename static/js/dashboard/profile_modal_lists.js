/* ===================================================================
   Dashboard Profile Modal Lists
   =================================================================== */

"use strict";

function renderProfileListItems(listElement, items, emptyText) {
    if (!listElement) return;
    listElement.innerHTML = "";
    if (!Array.isArray(items) || items.length === 0) {
        const emptyItem = document.createElement("li");
        emptyItem.className = "profile-modal-empty";
        emptyItem.textContent = emptyText;
        listElement.appendChild(emptyItem);
        return;
    }

    items.forEach((item) => {
        const listItem = document.createElement("li");
        listItem.className = "profile-modal-list__item";

        const head = document.createElement("div");
        head.className = "profile-modal-list__item-head";

        const title = document.createElement("div");
        title.className = "profile-modal-list__title";
        title.textContent = item.title || "Record";
        head.appendChild(title);

        if (item.badgeText) {
            const badge = document.createElement("span");
            badge.className = "badge";
            if (item.badgeClass) {
                badge.classList.add(item.badgeClass);
            }
            badge.textContent = item.badgeText;
            head.appendChild(badge);
        }

        listItem.appendChild(head);

        if (item.meta) {
            const meta = document.createElement("div");
            meta.className = "profile-modal-list__meta";
            meta.textContent = item.meta;
            listItem.appendChild(meta);
        }

        if (item.note) {
            const note = document.createElement("div");
            note.className = "profile-modal-list__note";
            note.textContent = item.note;
            listItem.appendChild(note);
        }

        listElement.appendChild(listItem);
    });
}

export {
    renderProfileListItems,
};

(() => {
    const VIDU_PROMPT_SOFT_LIMIT = 2000;

    function updatePromptCharBadge(textarea) {
        if (!textarea || !textarea.matches("[data-live-char-count]")) return;
        const sel = textarea.getAttribute("data-live-char-count");
        const badge = sel ? document.querySelector(sel) : null;
        if (!badge) return;
        const n = (textarea.value || "").length;
        badge.textContent = `${n} chars`;
        badge.classList.toggle("badge-warn", n > VIDU_PROMPT_SOFT_LIMIT);
        badge.classList.toggle("badge-info", n <= VIDU_PROMPT_SOFT_LIMIT);
        badge.title =
            n > VIDU_PROMPT_SOFT_LIMIT
                ? `Over ${VIDU_PROMPT_SOFT_LIMIT} chars — full prompt is still sent as written`
                : `${n} characters`;
    }

    function autosizeConceptField(el) {
        if (!el || !el.matches || !el.matches("textarea.concept-inline")) return;
        el.style.height = "auto";
        el.style.height = `${Math.max(el.scrollHeight, 28)}px`;
    }

    function autosizeAllConceptFields(root) {
        (root || document).querySelectorAll("textarea.concept-inline").forEach(autosizeConceptField);
    }

    document.addEventListener("input", (event) => {
        const el = event.target;
        if (el && el.matches && el.matches("textarea[data-live-char-count]")) {
            updatePromptCharBadge(el);
            const status = document.getElementById("script-save-status");
            if (status) status.textContent = "";
        }
        if (el && el.matches && el.matches("textarea.concept-inline")) {
            autosizeConceptField(el);
        }
    });

    document.body.addEventListener("htmx:afterSwap", () => {
        autosizeAllConceptFields(document);
    });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => autosizeAllConceptFields(document));
    } else {
        autosizeAllConceptFields(document);
    }

    let pendingDeleteUrl = null;

    function openDeleteConfirm(url, title) {
        const dialog = document.getElementById("app-confirm-dialog");
        const message = document.getElementById("app-confirm-message");
        if (!dialog || !message) return;
        pendingDeleteUrl = url;
        const label = (title || "this video").trim() || "this video";
        message.textContent = `Delete “${label}” from the queue? This cannot be undone.`;
        if (typeof dialog.showModal === "function") {
            dialog.showModal();
        } else {
            dialog.setAttribute("open", "open");
        }
    }

    function closeDeleteConfirm() {
        const dialog = document.getElementById("app-confirm-dialog");
        if (!dialog) return;
        if (typeof dialog.close === "function") {
            dialog.close("cancel");
        } else {
            dialog.removeAttribute("open");
        }
    }

    function finishEpisodeRename(input, { submit }) {
        if (!input || input.readOnly) return;
        const form = input.closest("[data-ep-rename-form]");
        const original = input.getAttribute("data-original") || "";
        const next = (input.value || "").trim();
        input.classList.remove("is-editing");
        input.readOnly = true;
        if (!next) {
            input.value = original;
            return;
        }
        if (submit && next !== original && form) {
            form.submit();
            return;
        }
        if (next !== original) {
            input.value = next;
        } else {
            input.value = original;
        }
    }

    document.addEventListener("click", (event) => {
        const renameBtn = event.target.closest("[data-ep-rename]");
        if (renameBtn) {
            event.preventDefault();
            event.stopPropagation();
            const form = renameBtn.closest("[data-ep-rename-form]");
            const input = form && form.querySelector(".ep-title-input");
            if (!input) return;
            input.readOnly = false;
            input.classList.add("is-editing");
            input.focus();
            input.select();
            return;
        }

        const deleteBtn = event.target.closest("[data-confirm-delete]");
        if (deleteBtn) {
            event.preventDefault();
            event.stopPropagation();
            openDeleteConfirm(
                deleteBtn.getAttribute("data-delete-url") || "",
                deleteBtn.getAttribute("data-delete-title") || ""
            );
            return;
        }

        const seekBtn = event.target.closest("[data-seek]");
        if (!seekBtn) return;
        const player = document.getElementById("main-video-player");
        if (!player || !player.src) return;
        const seconds = Number(seekBtn.getAttribute("data-seek") || 0);
        player.currentTime = seconds;
        player.play().catch(() => {});
        document.querySelectorAll(".timeline-scene-chip").forEach((chip) => {
            chip.classList.toggle("active", chip === seekBtn);
        });
    });

    const confirmDialog = document.getElementById("app-confirm-dialog");
    if (confirmDialog) {
        confirmDialog.addEventListener("close", () => {
            const url = pendingDeleteUrl;
            const confirmed = confirmDialog.returnValue === "confirm";
            pendingDeleteUrl = null;
            if (!confirmed || !url || typeof htmx === "undefined") return;
            htmx.ajax("POST", url, {
                target: "#workspace",
                swap: "outerHTML",
                indicator: "#busy",
            });
        });

        confirmDialog.addEventListener("click", (event) => {
            if (event.target === confirmDialog) {
                closeDeleteConfirm();
            }
        });
    }

    document.addEventListener("keydown", (event) => {
        const input = event.target;
        if (!input || !input.matches || !input.matches(".ep-title-input.is-editing")) return;
        if (event.key === "Enter") {
            event.preventDefault();
            finishEpisodeRename(input, { submit: true });
        } else if (event.key === "Escape") {
            event.preventDefault();
            input.value = input.getAttribute("data-original") || "";
            finishEpisodeRename(input, { submit: false });
        }
    });

    document.addEventListener(
        "blur",
        (event) => {
            const input = event.target;
            if (!input || !input.matches || !input.matches(".ep-title-input.is-editing")) return;
            finishEpisodeRename(input, { submit: true });
        },
        true
    );

    document.body.addEventListener("htmx:afterSwap", () => {
        document.querySelectorAll("textarea[data-live-char-count]").forEach(updatePromptCharBadge);
        const toast = document.getElementById("toast");
        if (toast && toast.classList.contains("show") && !toast.hidden) {
            window.clearTimeout(window.__toastTimer);
            window.__toastTimer = window.setTimeout(() => {
                toast.classList.remove("show");
                toast.hidden = true;
            }, 3200);
        }

        const player = document.getElementById("main-video-player");
        if (player && !player._hasTimelineListener) {
            player._hasTimelineListener = true;
            player.addEventListener("timeupdate", () => {
                const chips = Array.from(document.querySelectorAll(".timeline-scene-chip"));
                const bounds = chips.map((chip) => Number(chip.getAttribute("data-seek") || 0));
                bounds.push(Number.POSITIVE_INFINITY);
                const cur = player.currentTime;
                chips.forEach((chip, idx) => {
                    const start = bounds[idx];
                    const end = bounds[idx + 1];
                    chip.classList.toggle("active", cur >= start && cur < end);
                });
            });
        }
    });

    document.body.addEventListener("htmx:responseError", () => {
        const toast = document.getElementById("toast");
        if (!toast) return;
        toast.hidden = false;
        toast.className = "toast toast-error show";
        toast.textContent = "Request failed. Try again.";
    });

    document.body.addEventListener("htmx:sendError", () => {
        const toast = document.getElementById("toast");
        if (!toast) return;
        toast.hidden = false;
        toast.className = "toast toast-error show";
        toast.textContent = "Network error. Could not reach the server.";
    });
})();

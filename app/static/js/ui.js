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

    function autosizePromptField(el) {
        if (!el || !el.matches || !el.matches("textarea.script-prompt-editor, #scene-prompt-textarea")) return;
        const card = document.getElementById("vidu-prompt-card");
        if (card && card.classList.contains("is-fullscreen")) {
            el.style.height = "";
            return;
        }
        el.style.height = "auto";
        el.style.height = `${Math.max(el.scrollHeight, 120)}px`;
    }

    function autosizeAllPromptFields(root) {
        (root || document).querySelectorAll("textarea.script-prompt-editor, #scene-prompt-textarea").forEach(autosizePromptField);
    }

    window.autoResizePrompt = autosizePromptField;

    window.togglePromptFullscreen = function() {
        const card = document.getElementById("vidu-prompt-card");
        const btnText = document.getElementById("prompt-fullscreen-text");
        const btnIcon = document.getElementById("prompt-fullscreen-icon");
        const textarea = document.getElementById("scene-prompt-textarea");
        if (!card) return;
        
        const isFull = card.classList.toggle("is-fullscreen");
        if (isFull) {
            document.body.style.overflow = "hidden";
            if (btnText) btnText.textContent = "Exit Fullscreen";
            if (btnIcon) btnIcon.textContent = "✕";
            if (textarea) {
                textarea.style.height = "";
                textarea.style.overflowY = "auto";
                textarea.focus();
            }
        } else {
            document.body.style.overflow = "";
            if (btnText) btnText.textContent = "Fullscreen";
            if (btnIcon) btnIcon.textContent = "⛶";
            if (textarea) {
                textarea.style.overflowY = "hidden";
                autosizePromptField(textarea);
            }
        }
    };

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            const card = document.getElementById("vidu-prompt-card");
            if (card && card.classList.contains("is-fullscreen")) {
                window.togglePromptFullscreen();
            }
        }
    });

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
        if (el && el.matches && el.matches("textarea.script-prompt-editor, #scene-prompt-textarea")) {
            autosizePromptField(el);
        }
    });

    document.body.addEventListener("htmx:afterSwap", () => {
        autosizeAllConceptFields(document);
        autosizeAllPromptFields(document);
    });

    window.addEventListener("resize", () => {
        autosizeAllPromptFields(document);
    });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => {
            autosizeAllConceptFields(document);
            autosizeAllPromptFields(document);
        });
    } else {
        autosizeAllConceptFields(document);
        autosizeAllPromptFields(document);
    }

    let pendingDeleteUrl = null;

    window.closeDeleteConfirm = function() {
        closeDeleteConfirm();
    };

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
            if (form.hasAttribute("hx-post") && typeof htmx !== "undefined") {
                htmx.trigger(form, "submit");
            } else {
                form.submit();
            }
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

    // Mobile / Narrow Sidebar Toggle (Hamburger menu)
    function setupSidebarToggle() {
        const toggleBtn = document.getElementById("sidebar-toggle");
        const sidebar = document.getElementById("site-sidebar");
        const backdrop = document.getElementById("sidebar-backdrop");

        if (!toggleBtn || !sidebar) return;

        function closeSidebar() {
            sidebar.classList.remove("sidebar-open");
            if (backdrop) backdrop.classList.remove("show");
            toggleBtn.setAttribute("aria-expanded", "false");
        }

        function openSidebar() {
            sidebar.classList.add("sidebar-open");
            if (backdrop) backdrop.classList.add("show");
            toggleBtn.setAttribute("aria-expanded", "true");
        }

        toggleBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            if (sidebar.classList.contains("sidebar-open")) {
                closeSidebar();
            } else {
                openSidebar();
            }
        });

        if (backdrop) {
            backdrop.addEventListener("click", closeSidebar);
        }

        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape" && sidebar.classList.contains("sidebar-open")) {
                closeSidebar();
            }
        });

        // Close menu when clicking nav links on narrow screens
        sidebar.querySelectorAll(".nav-link").forEach((link) => {
            link.addEventListener("click", () => {
                if (window.innerWidth <= 980) {
                    closeSidebar();
                }
            });
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", setupSidebarToggle);
    } else {
        setupSidebarToggle();
    }

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

    // Global helper to trigger in-app toast alerts
    window.showInAppToast = function(message, kind = "info", duration = 4000) {
        const toast = document.getElementById("toast");
        if (!toast) return;
        window.clearTimeout(window.__toastTimer);
        toast.hidden = false;
        toast.className = `toast toast-${kind} show`;
        toast.textContent = message;
        if (duration > 0) {
            window.__toastTimer = window.setTimeout(() => {
                toast.classList.remove("show");
                toast.hidden = true;
            }, duration);
        }
    };

    // Opening a signal remounts #research-root — keep window + list scroll put.
    window.__researchScrollLock = null;
    function captureResearchScroll() {
        const list = document.querySelector("#research-root .research-signal-list");
        window.__researchScrollLock = {
            windowY: window.scrollY || window.pageYOffset || 0,
            listTop: list ? list.scrollTop : 0,
        };
    }
    function restoreResearchScroll(clear) {
        const lock = window.__researchScrollLock;
        if (!lock) return;
        const list = document.querySelector("#research-root .research-signal-list");
        if (list) list.scrollTop = lock.listTop;
        window.scrollTo(0, lock.windowY);
        if (clear) window.__researchScrollLock = null;
    }
    document.body.addEventListener("htmx:beforeRequest", (evt) => {
        const elt = evt.detail && evt.detail.elt;
        if (!elt || !elt.matches || !elt.matches(".research-signal-main")) return;
        if (document.activeElement && document.activeElement.blur) {
            document.activeElement.blur();
        }
        captureResearchScroll();
    });
    document.body.addEventListener("htmx:afterSwap", (evt) => {
        const target = evt.detail && evt.detail.target;
        if (!target) return;
        const isResearch =
            (target.id === "research-root") ||
            (target.querySelector && target.querySelector("#research-root"));
        if (!isResearch || !window.__researchScrollLock) return;
        // Restore after layout settles (detail card height can change).
        requestAnimationFrame(() => {
            restoreResearchScroll(false);
            requestAnimationFrame(() => restoreResearchScroll(true));
        });
    });

    // Trend Research: sync Select buttons in place (same as old checkbox flow).
    // Server toggles selection; HX-Trigger updates buttons without remounting the list.
    window.__lastResearchSelection = null;
    window.syncResearchSelection = function(detail, { toast = true } = {}) {
        const root = document.getElementById("research-root");
        if (!root || !detail) return;
        window.__lastResearchSelection = detail;
        const selected = new Set((detail.selected || []).map(String));

        root.querySelectorAll(".research-signal").forEach((row) => {
            const id = String(row.getAttribute("data-signal-id") || "");
            if (!id) return;
            row.classList.toggle("is-selected", selected.has(id));
        });

        const selectedId = selected.size ? String([...selected][0]) : "";
        const pitchMode = String(detail.pitch_btn_mode || (selectedId ? "create" : "disabled"));
        window.syncResearchPitchButton(pitchMode, selectedId);

        if (toast && detail.toast && window.showInAppToast) {
            window.showInAppToast(detail.toast, detail.toast_kind || "info", 2500);
        }
    };

    const RESEARCH_VIEW_PITCH_HTML =
        '<svg class="research-view-pitch-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
        '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"></path>' +
        '<circle cx="12" cy="12" r="3"></circle>' +
        "</svg><span class=\"research-view-pitch-label\">View Pitch</span>";

    window.__lastResearchPitchReady = null;

    window.syncResearchPitchButton = function(mode, signalId) {
        const createBtn = document.getElementById("research-create-pitches-btn");
        if (!createBtn) return;
        const pitchMode = String(mode || "disabled");
        const sid = String(signalId || "");
        createBtn.dataset.pitchBtnMode = pitchMode;
        createBtn.dataset.selectedSignalId = sid;
        createBtn.dataset.loading = "";
        createBtn.removeAttribute("hx-post");
        createBtn.removeAttribute("hx-swap");
        createBtn.removeAttribute("hx-indicator");
        createBtn.removeAttribute("hx-disabled-elt");
        createBtn.removeAttribute("disabled");
        createBtn.onclick = null;

        if (pitchMode === "view") {
            createBtn.disabled = false;
            createBtn.removeAttribute("aria-disabled");
            createBtn.removeAttribute("title");
            createBtn.innerHTML = RESEARCH_VIEW_PITCH_HTML;
            createBtn.setAttribute("aria-label", "View Pitch");
            createBtn.onclick = (evt) => {
                if (evt) evt.preventDefault();
                window.openResearchPitchModal && window.openResearchPitchModal(sid);
            };
        } else if (pitchMode === "create") {
            createBtn.disabled = false;
            createBtn.removeAttribute("aria-disabled");
            createBtn.removeAttribute("title");
            createBtn.textContent = "Create Pitch";
            createBtn.setAttribute("aria-label", "Create Pitch");
            createBtn.setAttribute("hx-post", "/ui/agent0/create-pitch");
            createBtn.setAttribute("hx-swap", "none");
            createBtn.setAttribute("hx-indicator", "#busy");
            // Do not use hx-disabled-elt — it restores pre-request HTML and can wipe View Pitch.
            createBtn.onclick = function() {
                this.dataset.loading = "1";
                this.textContent = "Creating…";
                this.disabled = true;
            };
            if (window.htmx) window.htmx.process(createBtn);
        } else {
            createBtn.disabled = true;
            createBtn.title = "Select one topic from All signals first";
            createBtn.textContent = "Create Pitch";
            createBtn.setAttribute("aria-label", "Create Pitch");
        }
    };

    function getResearchPitchModalHost() {
        let host = document.getElementById("research-pitch-modal-host");
        if (!host) {
            host = document.createElement("div");
            host.id = "research-pitch-modal-host";
            host.className = "research-pitch-modal-root";
            document.body.appendChild(host);
        }
        return host;
    }

    async function mountPitchModalHtml(url) {
        const host = getResearchPitchModalHost();
        const res = await fetch(url, {
            credentials: "same-origin",
            headers: { Accept: "text/html" },
        });
        if (!res.ok) throw new Error(`pitch modal ${res.status}`);
        host.innerHTML = await res.text();
        host.hidden = false;
        document.body.classList.add("pitch-modal-open");
        if (window.htmx) window.htmx.process(host);
    }

    window.openResearchPitchModal = async function(signalId) {
        const sid = encodeURIComponent(String(signalId || ""));
        try {
            await mountPitchModalHtml(`/ui/agent0/pitch-modal?signal_id=${sid}`);
        } catch (err) {
            if (window.showInAppToast) {
                window.showInAppToast("Could not open pitch details", "error", 3000);
            }
        }
    };

    window.openEpisodePitchModal = async function(episodeId) {
        const eid = encodeURIComponent(String(episodeId || ""));
        try {
            await mountPitchModalHtml(`/ui/episodes/${eid}/pitch-modal`);
        } catch (err) {
            if (window.showInAppToast) {
                window.showInAppToast("Could not open episode pitch", "error", 3000);
            }
        }
    };

    window.closeResearchPitchModal = function() {
        const host = document.getElementById("research-pitch-modal-host");
        if (host) {
            host.hidden = true;
            host.innerHTML = "";
        }
        document.body.classList.remove("pitch-modal-open");
    };

    document.addEventListener("keydown", (evt) => {
        if (evt.key === "Escape" && document.body.classList.contains("pitch-modal-open")) {
            window.closeResearchPitchModal && window.closeResearchPitchModal();
        }
    });

    document.body.addEventListener("htmx:beforeRequest", (evt) => {
        const elt = evt.detail && evt.detail.elt;
        const path = String(
            evt.detail?.pathInfo?.requestPath ||
            evt.detail?.requestConfig?.path ||
            (elt && elt.getAttribute && elt.getAttribute("hx-post")) ||
            ""
        );
        if (!path.includes("/ui/agent0/approve-pitch")) return;
        // Close Episode Pitch immediately, then show generating alert while script builds.
        window.closeResearchPitchModal && window.closeResearchPitchModal();
        if (window.showInAppToast) {
            window.showInAppToast("Generating Script…", "info", 0);
        }
    });

    document.body.addEventListener("htmx:afterRequest", (evt) => {
        const path = String(evt.detail?.pathInfo?.requestPath || evt.detail?.xhr?.responseURL || "");
        if (!path.includes("/ui/agent0/approve-pitch")) return;
        window.closeResearchPitchModal && window.closeResearchPitchModal();
        if (!evt.detail?.successful && window.showInAppToast) {
            window.showInAppToast("Script generation failed", "error", 4000);
        }
    });

    document.body.addEventListener("researchPitchReady", (evt) => {
        const detail = evt.detail || {};
        window.__lastResearchPitchReady = detail;
        const sid = detail.signal_id || "";
        window.syncResearchPitchButton(detail.pitch_btn_mode || "view", sid);
        // HTMX may restore the button after this event — re-apply on next frames.
        requestAnimationFrame(() => {
            window.syncResearchPitchButton("view", sid);
            requestAnimationFrame(() => window.syncResearchPitchButton("view", sid));
        });
        if (sid && window.openResearchPitchModal) {
            window.openResearchPitchModal(sid);
        }
        if (window.showInAppToast && detail.toast) {
            window.showInAppToast(detail.toast, detail.toast_kind || "success", 3000);
        }
    });

    document.body.addEventListener("htmx:afterSettle", (evt) => {
        const path = String(evt.detail?.pathInfo?.requestPath || evt.detail?.xhr?.responseURL || "");
        const ready = window.__lastResearchPitchReady;
        if (path.includes("/ui/agent0/create-pitch") && ready && ready.signal_id) {
            window.syncResearchPitchButton(ready.pitch_btn_mode || "view", ready.signal_id);
            return;
        }
        // After open remounts #research-root, re-bind View Pitch from server-rendered data attrs.
        const btn = document.getElementById("research-create-pitches-btn");
        if (!btn) return;
        const mode = btn.dataset.pitchBtnMode || "";
        const sid = btn.dataset.selectedSignalId || "";
        if (mode === "view" && sid) {
            window.syncResearchPitchButton("view", sid);
        }
    });

    document.body.addEventListener("researchPitchError", (evt) => {
        const detail = evt.detail || {};
        const createBtn = document.getElementById("research-create-pitches-btn");
        if (createBtn && createBtn.dataset.loading === "1") {
            window.syncResearchPitchButton("create", createBtn.dataset.selectedSignalId || "");
        }
        if (window.showInAppToast) {
            window.showInAppToast(detail.message || "Pitch creation failed", "error", 4000);
        }
    });

    document.body.addEventListener("researchSelectionUpdated", (evt) => {
        window.syncResearchSelection(evt.detail || {}, { toast: true });
    });

    // Re-apply after HTMX clears hx-disabled-elt on the clicked Select button.
    document.body.addEventListener("htmx:afterRequest", (evt) => {
        const path = String(evt.detail?.pathInfo?.requestPath || evt.detail?.xhr?.responseURL || "");
        if (!path.includes("/ui/agent0/signals/") || !path.includes("/toggle")) return;
        if (window.__lastResearchSelection) {
            window.syncResearchSelection(window.__lastResearchSelection, { toast: false });
        }
    });

    // —— Mockup background search (survives page switches) ——
    window.__mockupPollTimer = window.__mockupPollTimer || null;
    window.__mockupFinishing = false;

    function setMockupButtonSearching(searching) {
        const btn = document.getElementById("research-mockup-btn");
        if (!btn) return;
        btn.classList.toggle("is-searching", !!searching);
        btn.textContent = searching ? "Searching..." : "Mockup";
        if (searching) btn.setAttribute("disabled", "disabled");
        else btn.removeAttribute("disabled");
    }

    async function fetchMockupStatus(ack = false) {
        const url = ack ? "/ui/queue/mockup/status?ack=1" : "/ui/queue/mockup/status";
        const res = await fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } });
        if (!res.ok) throw new Error(`mockup status ${res.status}`);
        return res.json();
    }

    async function finishMockupSearch(job) {
        if (window.__mockupFinishing) return;
        window.__mockupFinishing = true;
        try {
            if (window.__mockupPollTimer) {
                window.clearInterval(window.__mockupPollTimer);
                window.__mockupPollTimer = null;
            }
            const status = String(job?.status || "");
            const epId = String(job?.episode_id || "");
            if (status === "error") {
                if (window.showInAppToast) {
                    window.showInAppToast(job?.error || "Mockup search failed", "error", 6000);
                }
                setMockupButtonSearching(false);
                await fetchMockupStatus(true);
                return;
            }
            if (window.showInAppToast) {
                window.showInAppToast(job?.message || "Trends refreshed", "ok", 5000);
            }
            await fetchMockupStatus(true);
            const push = epId
                ? `/studio?stage=0&research=today&episode=${encodeURIComponent(epId)}`
                : "/studio?stage=0&research=today";
            try { history.pushState({}, "", push); } catch (_) {}
            if (window.htmx) {
                window.htmx.ajax("GET", "/ui/stage/0?research=today", {
                    target: "#workspace",
                    swap: "outerHTML",
                });
            } else {
                window.location.href = push;
            }
        } finally {
            window.__mockupFinishing = false;
        }
    }

    window.startMockupSearchPolling = function(detail) {
        if (detail && window.showInAppToast) {
            window.showInAppToast(
                detail.message || "Searching for Trending Topics...",
                "info",
                0
            );
        }
        setMockupButtonSearching(true);
        if (window.__mockupPollTimer) {
            window.clearInterval(window.__mockupPollTimer);
        }
        window.__mockupPollTimer = window.setInterval(async () => {
            try {
                const job = await fetchMockupStatus(false);
                if (job.running) {
                    setMockupButtonSearching(true);
                    return;
                }
                if (job.status === "done" || job.status === "error") {
                    await finishMockupSearch(job);
                }
            } catch (_) {
                // Keep polling; transient network blips shouldn't stop the job.
            }
        }, 1500);
    };

    document.body.addEventListener("mockupSearchStarted", (evt) => {
        window.startMockupSearchPolling(evt.detail || {});
    });

    // Resume Searching state + polling after any full/partial page load.
    async function resumeMockupSearchIfNeeded() {
        try {
            const job = await fetchMockupStatus(false);
            if (job.running) {
                window.startMockupSearchPolling({
                    message: job.message || "Searching for Trending Topics...",
                });
            } else if (job.status === "done" || job.status === "error") {
                await finishMockupSearch(job);
            } else {
                setMockupButtonSearching(false);
            }
        } catch (_) {}
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", resumeMockupSearchIfNeeded);
    } else {
        resumeMockupSearchIfNeeded();
    }
    document.body.addEventListener("htmx:afterSwap", (evt) => {
        const target = evt.detail && evt.detail.target;
        if (!target) return;
        if (target.id === "workspace" || (target.querySelector && target.querySelector("#research-mockup-btn"))) {
            resumeMockupSearchIfNeeded();
        }
    });
})();

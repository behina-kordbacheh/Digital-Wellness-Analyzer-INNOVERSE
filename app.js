
document.addEventListener("DOMContentLoaded", () => {
    const root = document.documentElement;

    // ---------------------------------------------------------
    // Theme
    // ---------------------------------------------------------
    const applyTheme = (theme) => {
        const safeTheme = theme === "dark" ? "dark" : "light";
        root.dataset.theme = safeTheme;

        try {
            localStorage.setItem("dw-theme", safeTheme);
        } catch (_) {}

        const metaTheme = document.querySelector('meta[name="theme-color"]');
        if (metaTheme) {
            metaTheme.setAttribute(
                "content",
                safeTheme === "dark" ? "#07111f" : "#f4f7fb"
            );
        }
    };

    let savedTheme = "light";
    try {
        savedTheme = localStorage.getItem("dw-theme") || "light";
    } catch (_) {}

    applyTheme(savedTheme);

    const themeToggle = document.querySelector(".theme-toggle");
    if (themeToggle) {
        themeToggle.addEventListener("click", () => {
            const current = root.dataset.theme || "light";
            applyTheme(current === "dark" ? "light" : "dark");
        });
    }

    // ---------------------------------------------------------
    // Motion: ON by default for the competition demo.
    // ---------------------------------------------------------
    const motionToggle = document.querySelector(".motion-toggle");
    root.dataset.motion = "full";

    const setMotionButton = () => {
        if (!motionToggle) return;
        const on = root.dataset.motion === "full";
        const label = motionToggle.querySelector("b");
        if (label) label.textContent = on ? "Motion on" : "Motion paused";
        motionToggle.setAttribute("aria-pressed", String(on));
    };

    setMotionButton();

    if (motionToggle) {
        motionToggle.addEventListener("click", () => {
            root.dataset.motion =
                root.dataset.motion === "full" ? "paused" : "full";

            document.querySelectorAll(".reveal-item").forEach((element) => {
                if (root.dataset.motion === "paused") {
                    element.classList.add("is-visible");
                }
            });

            setMotionButton();
        });
    }

    // ---------------------------------------------------------
    // Make every radio/checkbox card visibly track native state.
    // This is an enhancement; :checked CSS still works without JS.
    // ---------------------------------------------------------
    const optionInputs = Array.from(
        document.querySelectorAll(
            '.interactive-options input[type="radio"], ' +
            '.interactive-options input[type="checkbox"]'
        )
    );

    const labelFor = (input) => {
        if (!input.id) return null;
        return document.querySelector(`label[for="${CSS.escape(input.id)}"]`);
    };

    const syncOptionGroup = (input) => {
        if (input.type === "radio") {
            document
                .querySelectorAll(`input[type="radio"][name="${CSS.escape(input.name)}"]`)
                .forEach((radio) => {
                    const label = labelFor(radio);
                    if (label) {
                        label.classList.toggle("option-selected", radio.checked);
                    }
                });
        } else {
            const label = labelFor(input);
            if (label) {
                label.classList.toggle("option-selected", input.checked);
            }
        }
    };

    optionInputs.forEach((input) => {
        syncOptionGroup(input);

        input.addEventListener("change", () => {
            syncOptionGroup(input);

            const label = labelFor(input);
            if (label) {
                label.classList.remove("option-bump");
                void label.offsetWidth;
                label.classList.add("option-bump");
            }

            refreshActivityDetails();
        });
    });

    // Extra pointer fallback for environments where custom CSS/layout
    // interferes with label-to-input activation.
    document.querySelectorAll(".interactive-options label[for]").forEach((label) => {
        label.addEventListener("pointerup", () => {
            const id = label.getAttribute("for");
            const input = id ? document.getElementById(id) : null;
            if (!input) return;

            // The browser normally toggles the input automatically.
            // We wait one frame and then synchronize the visual state.
            requestAnimationFrame(() => syncOptionGroup(input));
        });
    });

    // ---------------------------------------------------------
    // Weekly activity detail visibility.
    // ---------------------------------------------------------
    function refreshActivityDetails() {
        document.querySelectorAll("[data-activity-detail]").forEach((field) => {
            const activity = field.dataset.activityDetail;
            const checkbox = Array.from(
                document.querySelectorAll(
                    'input[name="selected_activities"][type="checkbox"]'
                )
            ).find((item) => item.value === activity);

            field.hidden = checkbox ? !checkbox.checked : false;
        });
    }

    refreshActivityDetails();

    // ---------------------------------------------------------
    // Keep range sliders and exact number inputs synchronized.
    // ---------------------------------------------------------
    document.querySelectorAll("[data-range]").forEach((range) => {
        const key = range.dataset.range;
        const number = document.querySelector(`[data-number="${key}"]`);
        if (!number) return;

        range.addEventListener("input", () => {
            number.value = range.value;
        });

        number.addEventListener("input", () => {
            const value = Number(number.value);
            const min = Number(range.min);
            const max = Number(range.max);

            if (Number.isNaN(value)) return;
            range.value = Math.min(Math.max(value, min), max);
        });
    });

    // ---------------------------------------------------------
    // Scroll reveal animations with a safe fallback.
    // ---------------------------------------------------------
    const revealElements = document.querySelectorAll(
        ".how-grid article, .form-group, .panel, .metric-card, " +
        ".balance-card, .coach-card, .challenge, .submit-card"
    );

    revealElements.forEach((element) => element.classList.add("reveal-item"));

    if ("IntersectionObserver" in window && root.dataset.motion === "full") {
        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add("is-visible");
                        observer.unobserve(entry.target);
                    }
                });
            },
            {
                threshold: 0.08,
                rootMargin: "0px 0px -5% 0px",
            }
        );

        revealElements.forEach((element) => observer.observe(element));

        // Never leave the first viewport invisible.
        setTimeout(() => {
            revealElements.forEach((element) => {
                const rect = element.getBoundingClientRect();
                if (rect.top < window.innerHeight * 1.1) {
                    element.classList.add("is-visible");
                }
            });
        }, 180);
    } else {
        revealElements.forEach((element) => element.classList.add("is-visible"));
    }

    // ---------------------------------------------------------
    // Challenge completion.
    // ---------------------------------------------------------
    const challengeButton = document.querySelector(".challenge-button");
    if (challengeButton) {
        challengeButton.addEventListener("click", async () => {
            const analysisId = challengeButton.dataset.analysisId;

            try {
                const response = await fetch(
                    `/api/challenge/${analysisId}/complete`,
                    { method: "POST" }
                );

                if (response.ok) {
                    challengeButton.textContent = "✓ Accepted";
                    challengeButton.disabled = true;
                }
            } catch (error) {
                console.error("Could not save challenge completion.", error);
            }
        });
    }

    // ---------------------------------------------------------
    // Daily mood/focus reflection.
    // ---------------------------------------------------------
    document.querySelectorAll("[data-mood]").forEach((slider) => {
        const key = slider.dataset.mood;
        const output = document.querySelector(`[data-mood-value="${key}"]`);

        slider.addEventListener("input", () => {
            if (output) output.textContent = slider.value;
        });
    });


    // ---------------------------------------------------------
    // Local progress charts. No external chart library is used.
    // ---------------------------------------------------------
    const progressCanvases = [
        {id: "riskProgressChart", key: "risk", fixedMax: 100, suffix: ""},
        {id: "screenProgressChart", key: "screen", fixedMax: null, suffix: " h"},
    ];

    const parseProgressPoints = (canvas) => {
        if (!canvas) return [];
        try {
            const value = JSON.parse(canvas.dataset.points || "[]");
            return Array.isArray(value) ? value.slice(-90) : [];
        } catch (error) {
            console.error("Could not parse local progress data.", error);
            return [];
        }
    };

    const drawProgressChart = ({id, key, fixedMax, suffix}) => {
        const canvas = document.getElementById(id);
        if (!canvas) return;

        const points = parseProgressPoints(canvas);
        const cssWidth = Math.max(280, Math.min(canvas.clientWidth || 640, 1200));
        const cssHeight = 190;
        const pixelRatio = Math.max(1, Math.min(window.devicePixelRatio || 1, 2));

        canvas.width = Math.round(cssWidth * pixelRatio);
        canvas.height = Math.round(cssHeight * pixelRatio);
        canvas.style.height = `${cssHeight}px`;

        const context = canvas.getContext("2d");
        if (!context) return;
        context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
        context.clearRect(0, 0, cssWidth, cssHeight);

        const palette = document.documentElement.dataset.theme === "dark"
            ? {grid: "rgba(255,255,255,.09)", text: "#aebbd0", line: "#ff6fb1", dot: "#ffffff"}
            : {grid: "rgba(22,43,72,.10)", text: "#75869a", line: "#e7428a", dot: "#162b48"};

        if (!points.length) {
            context.fillStyle = palette.text;
            context.font = "600 12px system-ui, sans-serif";
            context.textAlign = "center";
            context.fillText("Run a daily analysis to start this trend.", cssWidth / 2, cssHeight / 2);
            return;
        }

        const values = points
            .map((point) => point[key])
            .filter((value) => value !== null && value !== undefined && value !== "")
            .map(Number)
            .filter(Number.isFinite);
        if (!values.length) {
            context.fillStyle = palette.text;
            context.font = "600 12px system-ui, sans-serif";
            context.textAlign = "center";
            context.fillText("No recorded check-ins in this window yet.", cssWidth / 2, cssHeight / 2);
            return;
        }

        const pad = {left: 38, right: 16, top: 18, bottom: 30};
        const chartWidth = cssWidth - pad.left - pad.right;
        const chartHeight = cssHeight - pad.top - pad.bottom;
        const minValue = 0;
        const maxValue = fixedMax || Math.max(1, Math.ceil(Math.max(...values) * 1.15));

        context.strokeStyle = palette.grid;
        context.fillStyle = palette.text;
        context.lineWidth = 1;
        context.font = "600 10px system-ui, sans-serif";
        context.textAlign = "right";

        for (let index = 0; index <= 4; index += 1) {
            const y = pad.top + chartHeight * index / 4;
            const labelValue = maxValue - (maxValue - minValue) * index / 4;
            context.beginPath();
            context.moveTo(pad.left, y);
            context.lineTo(cssWidth - pad.right, y);
            context.stroke();
            context.fillText(`${labelValue.toFixed(key === "risk" ? 0 : 1)}${suffix}`, pad.left - 6, y + 3);
        }

        const pointX = (index) => {
            if (points.length === 1) return pad.left + chartWidth / 2;
            return pad.left + chartWidth * index / (points.length - 1);
        };
        const pointY = (value) => {
            const ratio = (Number(value) - minValue) / Math.max(maxValue - minValue, 1e-9);
            return pad.top + chartHeight * (1 - Math.max(0, Math.min(ratio, 1)));
        };

        const numericValue = (point) => {
            const raw = point[key];
            if (raw === null || raw === undefined || raw === "") return null;
            const value = Number(raw);
            return Number.isFinite(value) ? value : null;
        };

        // Missing days intentionally break the line. They are not plotted at zero.
        context.strokeStyle = palette.line;
        context.lineWidth = 2.5;
        context.lineJoin = "round";
        context.lineCap = "round";
        context.beginPath();
        let segmentOpen = false;
        points.forEach((point, index) => {
            const value = numericValue(point);
            if (value === null) {
                segmentOpen = false;
                return;
            }
            const x = pointX(index);
            const y = pointY(value);
            if (!segmentOpen) {
                context.moveTo(x, y);
                segmentOpen = true;
            } else {
                context.lineTo(x, y);
            }
        });
        context.stroke();

        context.fillStyle = palette.dot;
        points.forEach((point, index) => {
            const value = numericValue(point);
            if (value === null) return;
            if (points.length > 24 && index % Math.ceil(points.length / 18) !== 0 && index !== points.length - 1) return;
            context.beginPath();
            context.arc(pointX(index), pointY(value), 2.7, 0, Math.PI * 2);
            context.fill();
        });

        context.fillStyle = palette.text;
        context.font = "600 10px system-ui, sans-serif";
        context.textAlign = "left";
        context.fillText(points[0].date, pad.left, cssHeight - 8);
        context.textAlign = "right";
        context.fillText(points[points.length - 1].date, cssWidth - pad.right, cssHeight - 8);
    };

    const drawAllProgressCharts = () => {
        progressCanvases.forEach(drawProgressChart);
    };

    drawAllProgressCharts();
    let progressResizeTimer = null;
    window.addEventListener("resize", () => {
        window.clearTimeout(progressResizeTimer);
        progressResizeTimer = window.setTimeout(drawAllProgressCharts, 120);
    });

    const progressThemeButton = document.querySelector(".theme-toggle");
    if (progressThemeButton) {
        progressThemeButton.addEventListener("click", () => {
            window.requestAnimationFrame(drawAllProgressCharts);
        });
    }

    const moodSaveButton = document.querySelector(".mood-save-button");

    if (moodSaveButton) {
        moodSaveButton.addEventListener("click", async () => {
            const status = document.querySelector(".mood-save-status");

            const value = (key) => {
                const input = document.querySelector(`[data-mood="${key}"]`);
                return input ? Number(input.value) : 5;
            };

            const payload = {
                anxiety: value("anxiety"),
                stress: value("stress"),
                sadness: value("sadness"),
                happiness: value("happiness"),
                focus: value("focus"),
                exercise_minutes: Number(
                    document.querySelector("#moodExerciseMinutes")?.value || 0
                ),
                note: document.querySelector("#moodNote")?.value || "",
            };

            try {
                moodSaveButton.disabled = true;
                if (status) status.textContent = "Saving locally…";

                const response = await fetch("/api/mood-checkin", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify(payload),
                });

                if (!response.ok) {
                    throw new Error("Could not save the check-in.");
                }

                if (status) {
                    status.textContent =
                        "Saved locally ✓ Refresh later to see the updated trend.";
                }
            } catch (error) {
                console.error(error);
                if (status) {
                    status.textContent = "Could not save this check-in.";
                }
            } finally {
                moodSaveButton.disabled = false;
            }
        });
    }
});


// ---------------------------------------------------------
// Galaxy visual enhancements: subtle parallax + click ripple.
// These do not alter form behavior or ML logic.
// ---------------------------------------------------------
(() => {
    const parallaxTargets = document.querySelectorAll(
        ".hero-dashboard, .how-grid article, .metric-card, .balance-card"
    );

    parallaxTargets.forEach((card) => {
        card.classList.add("parallax-card");

        card.addEventListener("pointermove", (event) => {
            if (document.documentElement.dataset.motion !== "full") return;
            if (window.innerWidth < 900) return;

            const rect = card.getBoundingClientRect();
            const x = (event.clientX - rect.left) / rect.width - 0.5;
            const y = (event.clientY - rect.top) / rect.height - 0.5;

            const rotateY = x * 4.2;
            const rotateX = y * -3.2;

            card.style.transform =
                `perspective(900px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-3px)`;
        });

        card.addEventListener("pointerleave", () => {
            card.style.transform = "";
        });
    });

    document.addEventListener("pointerdown", (event) => {
        if (document.documentElement.dataset.motion !== "full") return;
        if (event.pointerType === "touch") return;

        const ripple = document.createElement("span");
        ripple.className = "cosmic-ripple";
        ripple.style.left = `${event.clientX}px`;
        ripple.style.top = `${event.clientY}px`;
        document.body.appendChild(ripple);

        setTimeout(() => ripple.remove(), 800);
    });
})();


// ---------------------------------------------------------
// Premium pink galaxy feedback.
// Adds visual delight without changing input values or form logic.
// ---------------------------------------------------------
document.addEventListener("pointerup", (event) => {
    if (document.documentElement.dataset.motion !== "full") return;

    const interactive = event.target.closest(
        ".interactive-options label, .primary-btn, .analyze-button, .secondary-btn"
    );
    if (!interactive) return;

    const rect = interactive.getBoundingClientRect();
    const spark = document.createElement("span");
    spark.style.position = "fixed";
    spark.style.left = `${Math.min(rect.right - 12, event.clientX || rect.right - 16)}px`;
    spark.style.top = `${Math.max(rect.top + 12, event.clientY || rect.top + 16)}px`;
    spark.style.width = "7px";
    spark.style.height = "7px";
    spark.style.borderRadius = "50%";
    spark.style.background = "#ff5fa2";
    spark.style.pointerEvents = "none";
    spark.style.zIndex = "10000";
    spark.style.boxShadow = "0 0 16px rgba(255,95,162,.75)";
    spark.style.transition = "transform .55s ease, opacity .55s ease";
    document.body.appendChild(spark);

    requestAnimationFrame(() => {
        spark.style.transform = "translateY(-18px) scale(2)";
        spark.style.opacity = "0";
    });

    setTimeout(() => spark.remove(), 620);
});


document.addEventListener("DOMContentLoaded", () => {
    const panel = document.querySelector("#focusSoundPanel");
    const openButton = document.querySelector("#focusSoundOpen");
    const floatingButton = document.querySelector("#focusSoundFloating");
    const heroFocusButton = document.querySelector("#heroFocusSoundCTA");
    const closeButtons = document.querySelectorAll("[data-sound-close]");
    const cards = Array.from(document.querySelectorAll(".sound-card"));

    const masterToggle = document.querySelector("#soundMasterToggle");
    const volumeSlider = document.querySelector("#soundVolume");
    const volumeValue = document.querySelector("#soundVolumeValue");
    const timerSelect = document.querySelector("#soundTimer");
    const nowName = document.querySelector("#nowPlayingName");
    const nowNote = document.querySelector("#nowPlayingNote");
    const visualizer = document.querySelector("#soundVisualizer");
    const recommendation = document.querySelector("#soundRecommendation");
    const sessionTip = document.querySelector("#soundSessionTip");
    const audioStatus = document.querySelector("#audioStatus");
    const speakerTestButton = document.querySelector("#speakerTestButton");

    const mixModeToggle = document.querySelector("#mixModeToggle");
    const activeMixPanel = document.querySelector("#activeMixPanel");
    const activeMixLayers = document.querySelector("#activeMixLayers");
    const activeMixCount = document.querySelector("#activeMixCount");
    const clearMixButton = document.querySelector("#clearMixButton");

    const miniPlayer = document.querySelector("#focusMiniPlayer");
    const miniSoundName = document.querySelector("#miniSoundName");
    const miniSoundToggle = document.querySelector("#miniSoundToggle");
    const miniSoundOpen = document.querySelector("#miniSoundOpen");
    const miniSoundStop = document.querySelector("#miniSoundStop");
    const miniSoundWave = document.querySelector("#miniSoundWave");

    if (!panel || (!openButton && !floatingButton && !heroFocusButton)) return;

    const defs = {
        white:{label:"White Focus Noise",note:"Broad-spectrum masking noise."},
        pink:{label:"Pink Focus Noise",note:"Softer high frequencies than white noise."},
        brown:{label:"Deep Brown Noise",note:"Lower-frequency preference option."},
        rain:{label:"Soft Rain",note:"Gentle rain texture."},
        waterfall:{label:"Waterfall Flow",note:"Continuous water-like sound."},
        forest:{label:"Forest Birds",note:"Soft wind with synthesized chirps."},
        ocean:{label:"Ocean Breathing",note:"Slow wave-like sound."},
        ambient:{label:"Soft Instrumental Pad",note:"Original lyric-free ambient tones."},
        drizzle:{label:"Gentle Drizzle",note:"Fine, quiet raindrops."},
        rain_ground:{label:"Rain on the Ground",note:"Soft rounded rain splashes."},
        rain_leaves:{label:"Rain on Leaves",note:"Light drops tapping leaves."},
        gentle_stream:{label:"Gentle Stream",note:"Continuous flowing water."},
        birds_only:{label:"Birds Only",note:"Sparse bird-like chirps with very little continuous noise."},
        gentle_waterfall:{label:"Gentle Waterfall",note:"A smoother, softer waterfall layer."},
    };

    let mixMode = false;
    const tracks = new Map();
    let isPausedGlobally = false;
    let timerId = null;

    const setStatus = (html, kind="") => {
        if (!audioStatus) return;
        audioStatus.classList.remove("is-ok","is-error");
        if (kind) audioStatus.classList.add(kind);
        audioStatus.innerHTML = html;
    };

    const openPanel = () => {
        panel.classList.add("is-open");
        panel.setAttribute("aria-hidden","false");
    };
    const closePanel = () => {
        panel.classList.remove("is-open");
        panel.setAttribute("aria-hidden","true");
    };

    openButton?.addEventListener("click", openPanel);
    floatingButton?.addEventListener("click", openPanel);
    heroFocusButton?.addEventListener("click", openPanel);
    miniSoundOpen?.addEventListener("click", openPanel);
    closeButtons.forEach(btn => btn.addEventListener("click", closePanel));

    document.addEventListener("keydown", e => {
        if (e.key === "Escape" && panel.classList.contains("is-open")) closePanel();
    });

    // ---------------------------------------------------------
    // Optional recommendation context
    // ---------------------------------------------------------
    const prefs = {adhd:null,goal:null};

    const recommended = () => {
        const set = new Set();
        if (prefs.adhd === "yes"){set.add("white");set.add("pink")}
        if (prefs.goal === "focus" || prefs.goal === "study"){
            ["pink","white","rain","drizzle","gentle_stream"].forEach(x=>set.add(x));
        }
        if (prefs.goal === "busy-mind"){
            ["pink","drizzle","rain_leaves","ocean","gentle_stream"].forEach(x=>set.add(x));
        }
        if (prefs.goal === "relax"){
            ["drizzle","rain_ground","rain_leaves","gentle_stream","birds_only","gentle_waterfall","ocean","ambient"].forEach(x=>set.add(x));
        }
        return set;
    };

    const updateRecommendations = () => {
        const set = recommended();
        cards.forEach(card => card.classList.toggle("is-recommended", set.has(card.dataset.sound)));

        if (!prefs.adhd && !prefs.goal){
            recommendation.textContent = "Choose an option above and I’ll highlight a few sounds worth trying.";
        } else if (prefs.adhd === "yes"){
            recommendation.innerHTML =
                "<b>Evidence-aware suggestion:</b> compare White or Pink Focus Noise with silence. " +
                "If you prefer something more natural, you can also test a gentle nature layer such as Drizzle.";
        } else if (prefs.goal === "busy-mind"){
            recommendation.innerHTML =
                "<b>Low-complexity set:</b> try Pink Focus Noise, Gentle Drizzle, Rain on Leaves, Ocean Breathing, or Gentle Stream. " +
                "The goal is not to stop thoughts; it is to test whether a steadier background feels less distracting.";
        } else if (prefs.goal === "relax"){
            recommendation.innerHTML =
                "<b>Nature set:</b> Drizzle, Rain on the Ground, Rain on Leaves, Gentle Stream, Birds Only, and Gentle Waterfall are highlighted. " +
                "You can use one alone or layer a quiet mix.";
        } else {
            recommendation.innerHTML =
                "<b>Focus set:</b> compare a colored noise with a calm nature sound. If any sound makes your task harder, choose silence.";
        }
    };

    document.querySelectorAll("[data-sound-question]").forEach(group => {
        const key = group.dataset.soundQuestion;
        group.querySelectorAll("button[data-value]").forEach(button => {
            button.addEventListener("click", () => {
                prefs[key] = button.dataset.value;
                group.querySelectorAll("button[data-value]").forEach(x => x.classList.toggle("is-selected", x === button));
                updateRecommendations();
            });
        });
    });

    // ---------------------------------------------------------
    // Track helpers
    // ---------------------------------------------------------
    const globalVolume = () => Number(volumeSlider.value) / 100;

    const createTrack = (key, url, localVolume = 1.0) => {
        const audio = new Audio(url);
        audio.loop = true;
        audio.preload = "auto";
        audio.volume = Math.min(1, globalVolume() * localVolume);

        const track = {
            key,
            url,
            audio,
            localVolume,
            playing:false,
        };

        audio.addEventListener("playing", () => {
            track.playing = true;
            updateUI();
        });
        audio.addEventListener("pause", () => {
            track.playing = false;
            updateUI();
        });
        audio.addEventListener("error", () => {
            track.playing = false;
            setStatus(
                "<b>An audio file could not load.</b> Run the site with <code>python app.py</code> and do not open index.html directly.",
                "is-error"
            );
            updateUI();
        });

        tracks.set(key, track);
        return track;
    };

    const playTrack = async (key, url) => {
        let track = tracks.get(key);
        if (!track) track = createTrack(key, url, 1.0);

        try{
            track.audio.volume = Math.min(1, globalVolume() * track.localVolume);
            await track.audio.play();
            track.playing = true;
            isPausedGlobally = false;
            setStatus(
                mixMode
                    ? "Mix is playing ✓ Add or remove layers anytime."
                    : "Audio is playing ✓ You can close this panel and keep listening.",
                "is-ok"
            );
            scheduleTimer();
            updateUI();
        }catch(error){
            console.error("Audio playback failed:", error);
            setStatus(
                "<b>Playback was blocked or failed.</b> Click Test speaker and check the browser tab is not muted.",
                "is-error"
            );
        }
    };

    const pauseTrack = (key) => {
        const track = tracks.get(key);
        if (!track) return;
        track.audio.pause();
        track.playing = false;
        updateUI();
    };

    const removeTrack = (key) => {
        const track = tracks.get(key);
        if (!track) return;
        track.audio.pause();
        try{track.audio.currentTime = 0}catch(_){}
        tracks.delete(key);
        updateUI();
    };

    const stopAll = () => {
        tracks.forEach(track => {
            track.audio.pause();
            try{track.audio.currentTime = 0}catch(_){}
        });
        tracks.clear();
        isPausedGlobally = false;
        clearTimer();
        setStatus("Stopped. Pick one sound, or turn Mix Mode on and layer several.");
        updateUI();
    };

    const pauseAll = () => {
        tracks.forEach(track => track.audio.pause());
        isPausedGlobally = true;
        clearTimer();
        updateUI();
    };

    const resumeAll = async () => {
        if (!tracks.size) return;
        isPausedGlobally = false;

        for (const track of tracks.values()){
            try{
                track.audio.volume = Math.min(1, globalVolume() * track.localVolume);
                await track.audio.play();
            }catch(error){
                console.error("Could not resume track:", track.key, error);
            }
        }

        scheduleTimer();
        updateUI();
    };

    const anyPlaying = () => Array.from(tracks.values()).some(t => !t.audio.paused);

    // ---------------------------------------------------------
    // Timer: Always means no automatic stop.
    // ---------------------------------------------------------
    const clearTimer = () => {
        if (timerId){clearTimeout(timerId);timerId=null}
    };

    const scheduleTimer = () => {
        clearTimer();
        const value = timerSelect.value;

        if (value === "always"){
            sessionTip.textContent =
                "Always mode is on: audio will continue until you press Pause or Stop, or leave the page.";
            return;
        }

        const minutes = Number(value);
        if (!minutes || !anyPlaying()) return;

        timerId = setTimeout(() => {
            pauseAll();
            sessionTip.textContent =
                `Your ${minutes}-minute sound session finished. Notice whether the sound actually helped.`;
        }, minutes * 60 * 1000);
    };

    // ---------------------------------------------------------
    // Mix panel renderer
    // ---------------------------------------------------------
    const renderMixLayers = () => {
        if (!activeMixLayers || !activeMixPanel) return;

        activeMixLayers.innerHTML = "";
        activeMixPanel.hidden = tracks.size === 0;
        activeMixCount.textContent = `${tracks.size} ${tracks.size === 1 ? "layer" : "layers"}`;

        tracks.forEach(track => {
            const row = document.createElement("div");
            row.className = "mix-layer-row";

            const name = document.createElement("span");
            name.className = "mix-layer-name";
            name.textContent = defs[track.key]?.label || track.key;

            const slider = document.createElement("input");
            slider.type = "range";
            slider.min = "0";
            slider.max = "100";
            slider.value = String(Math.round(track.localVolume * 100));
            slider.setAttribute("aria-label", `${name.textContent} volume`);

            const percent = document.createElement("span");
            percent.className = "mix-layer-percent";
            percent.textContent = `${slider.value}%`;

            const remove = document.createElement("button");
            remove.type = "button";
            remove.className = "mix-layer-remove";
            remove.textContent = "Remove";

            slider.addEventListener("input", () => {
                track.localVolume = Number(slider.value) / 100;
                track.audio.volume = Math.min(1, globalVolume() * track.localVolume);
                percent.textContent = `${slider.value}%`;
            });

            remove.addEventListener("click", () => removeTrack(track.key));

            row.append(name, slider, percent, remove);
            activeMixLayers.appendChild(row);
        });
    };

    // ---------------------------------------------------------
    // UI renderer
    // ---------------------------------------------------------
    const updateUI = () => {
        const keys = Array.from(tracks.keys());
        const playing = anyPlaying();

        if (!keys.length){
            nowName.textContent = "Nothing yet";
            nowNote.textContent = "Pick a sound card below.";
            masterToggle.disabled = true;
            masterToggle.textContent = "Play";
            visualizer.classList.remove("is-playing");
            miniPlayer?.classList.remove("is-visible");
        } else {
            const labels = keys.map(k => defs[k]?.label || k);
            nowName.textContent = keys.length === 1 ? labels[0] : `${keys.length}-layer mix`;
            nowNote.textContent = keys.length === 1
                ? defs[keys[0]]?.note || ""
                : labels.join(" + ");

            masterToggle.disabled = false;
            masterToggle.textContent = playing ? "Pause all" : "Play all";
            visualizer.classList.toggle("is-playing", playing);

            miniSoundName.textContent = keys.length === 1 ? labels[0] : `${keys.length}-layer sound mix`;
            miniSoundToggle.textContent = playing ? "Pause" : "Play";
            miniSoundWave?.classList.toggle("is-paused", !playing);
            miniPlayer?.classList.add("is-visible");
            miniPlayer?.setAttribute("aria-hidden", "false");
        }

        cards.forEach(card => {
            const key = card.dataset.sound;
            const active = tracks.has(key);
            const track = tracks.get(key);
            card.classList.toggle("is-active", active && track && !track.audio.paused);

            const button = card.querySelector(".sound-play-card");
            if (!button) return;

            if (mixMode){
                button.textContent = active ? "Remove from mix" : "Add to mix";
            } else {
                button.textContent = active && track && !track.audio.paused ? "Pause" : "Play";
            }
        });

        renderMixLayers();
    };

    // ---------------------------------------------------------
    // Card clicks
    // ---------------------------------------------------------
    cards.forEach(card => {
        const button = card.querySelector(".sound-play-card");
        const key = card.dataset.sound;
        const url = card.dataset.audioUrl;
        if (!button || !key || !url) return;

        button.addEventListener("click", async () => {
            if (mixMode){
                if (tracks.has(key)){
                    removeTrack(key);
                } else {
                    await playTrack(key, url);
                }
                return;
            }

            // Single mode: selecting a new sound stops every other track.
            if (tracks.has(key)){
                const track = tracks.get(key);
                if (!track.audio.paused){
                    pauseTrack(key);
                } else {
                    await playTrack(key, url);
                }
                return;
            }

            stopAll();
            await playTrack(key, url);
        });
    });

    mixModeToggle?.addEventListener("click", () => {
        mixMode = !mixMode;
        mixModeToggle.classList.toggle("is-on", mixMode);
        mixModeToggle.setAttribute("aria-pressed", String(mixMode));
        mixModeToggle.textContent = `Mix Mode: ${mixMode ? "On" : "Off"}`;

        if (mixMode){
            sessionTip.textContent =
                "Mix Mode is on. Add several sounds, then adjust each layer volume in Active Mix.";
        } else if (tracks.size > 1){
            // Keep the first active track when returning to single mode.
            const firstKey = tracks.keys().next().value;
            for (const key of Array.from(tracks.keys())){
                if (key !== firstKey) removeTrack(key);
            }
            sessionTip.textContent =
                "Mix Mode is off. The first active sound was kept as your single track.";
        }

        updateUI();
    });

    clearMixButton?.addEventListener("click", stopAll);

    masterToggle.addEventListener("click", async () => {
        if (anyPlaying()) pauseAll();
        else await resumeAll();
    });

    miniSoundToggle?.addEventListener("click", async () => {
        if (anyPlaying()) pauseAll();
        else await resumeAll();
    });

    miniSoundStop?.addEventListener("click", stopAll);

    volumeSlider.addEventListener("input", () => {
        const value = Number(volumeSlider.value);
        volumeValue.textContent = `${value}%`;
        tracks.forEach(track => {
            track.audio.volume = Math.min(1, (value/100) * track.localVolume);
        });
    });

    timerSelect.addEventListener("change", scheduleTimer);

    // Obvious speaker test.
    speakerTestButton?.addEventListener("click", async () => {
        const url = speakerTestButton.dataset.testUrl;
        if (!url) return;

        const test = new Audio(url);
        test.volume = Math.max(0.35, globalVolume());

        try{
            await test.play();
            setStatus("Speaker test started ✓ You should hear two short tones.", "is-ok");
        }catch(error){
            console.error("Speaker test failed:", error);
            setStatus(
                "<b>Speaker test could not play.</b> Check the browser tab mute state and Windows sound output.",
                "is-error"
            );
        }
    });



    // ---------------------------------------------------------
    // V2 category navigation.
    // Nature Sounds is the default view so the new feature is visible immediately.
    // ---------------------------------------------------------
    const viewTabs = Array.from(document.querySelectorAll("[data-sound-view]"));
    const viewSections = Array.from(document.querySelectorAll("[data-view-section]"));
    const quickMixButton = document.querySelector("#quickMixButton");

    const showSoundView = (view) => {
        viewTabs.forEach(tab => {
            const active = tab.dataset.soundView === view;
            tab.classList.toggle("is-active", active);
            tab.setAttribute("aria-selected", String(active));
        });

        viewSections.forEach(section => {
            section.classList.toggle(
                "is-view-visible",
                section.dataset.viewSection === view
            );
        });

        if (view === "mix" && mixModeToggle && !mixMode){
            mixMode = true;
            mixModeToggle.classList.add("is-on");
            mixModeToggle.setAttribute("aria-pressed", "true");
            mixModeToggle.textContent = "Mix Mode: On";
        }

        if (view === "nature"){
            sessionTip.textContent =
                "Nature Sounds are open. Play one sound, or open Mix Studio to layer several together.";
        }

        if (view === "mix"){
            sessionTip.textContent =
                "Mix Studio is open. Add multiple sounds, then adjust each layer volume separately.";
        }

        updateUI();
    };

    viewTabs.forEach(tab => {
        tab.addEventListener("click", () => showSoundView(tab.dataset.soundView));
    });

    quickMixButton?.addEventListener("click", () => showSoundView("mix"));

    // Default to Nature Sounds every time the Focus Sound Space opens.
    const openNatureView = () => showSoundView("nature");
    openButton?.addEventListener("click", openNatureView);
    floatingButton?.addEventListener("click", openNatureView);
    heroFocusButton?.addEventListener("click", openNatureView);

    showSoundView("nature");


    updateRecommendations();
    updateUI();
});

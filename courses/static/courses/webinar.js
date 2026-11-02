(() => {
    const status = document.getElementById("webinar-status");

    const showError = () => {
        if (status) {
            status.textContent =
                "Видео не загрузилось. Попробуйте открыть его на видеоплощадке.";
        }
    };

    const rutubeFrame = document.getElementById("webinar-rutube");

    if (rutubeFrame) {
        let configured = false;

        window.addEventListener("message", (event) => {
            if (
                event.origin !== "https://rutube.ru" ||
                event.source !== rutubeFrame.contentWindow
            ) {
                return;
            }

            let message;

            try {
                message = typeof event.data === "string"
                    ? JSON.parse(event.data)
                    : event.data;
            } catch {
                return;
            }

            if (message?.type === "player:ready" && !configured) {
                configured = true;

                for (const type of ["player:mute", "player:pause"]) {
                    rutubeFrame.contentWindow.postMessage(
                        JSON.stringify({type, data: {}}),
                        "https://rutube.ru"
                    );
                }
            }

            if (message?.type === "player:error") {
                showError();
            }
        });

        rutubeFrame.src = rutubeFrame.dataset.src;
    }

    const youtubeElement = document.getElementById("webinar-youtube");

    if (youtubeElement) {
        const videoId = youtubeElement.dataset.videoId;

        const createPlayer = () => {
            new window.YT.Player(youtubeElement.id, {
                width: "100%",
                height: "100%",

                playerVars: {
                    autoplay: 0,
                    playsinline: 1,
                    origin: window.location.origin,
                },

                events: {
                    onReady(event) {
                        event.target.mute();
                        event.target.cueVideoById(videoId);
                        event.target.getIframe().title = "Вебинар к уроку";
                    },

                    onError: showError,
                },
            });
        };

        if (window.YT && window.YT.Player) {
            createPlayer();
        } else {
            window.onYouTubeIframeAPIReady = createPlayer;

            const script = document.createElement("script");
            script.src = "https://www.youtube.com/iframe_api";
            script.async = true;
            script.onerror = showError;

            document.head.appendChild(script);
        }
    }
})();
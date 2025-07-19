(() => {
        try {
        // Check if the navigator is initialized
        if (typeof window.NavigatorOn === 'undefined') {
            window.NavigatorOn = true;
        } else if (window.NavigatorOn === true) {
            window.NavigatorOn = false;
            document.getElementById('video-nav-overlay')?.remove();
            document.getElementById('video-nav-style')?.remove();
            delete window.videoNavController;
            return;
        } else {
            window.NavigatorOn = true;
        }

        let VIDEOS = [];
        let ADDED_VIDEO_IDS = new Set();


        // Locate the video container
        function getVideoList() {
            const videoContainer = document
                .querySelector('div#items.style-scope.ytd-watch-next-secondary-results-renderer')
                ?.querySelector('ytd-item-section-renderer')
                ?.querySelector('#contents');

            if (!videoContainer) {
                console.warn('[video-nav] videoContainer not found!');
                VIDEOS = [];
                return;
            }

            // Collect video elements
            const selector = `
            ytd-compact-video-renderer,
            ytd-video-renderer,
            ytd-rich-item-renderer,
            yt-lockup-view-model,
            yt-lockup-view-model-wiz
            `.trim();

            const foundVideos = Array.from(videoContainer.querySelectorAll(selector));
            VIDEOS = foundVideos;
        }
        getVideoList();

        function waitForVideoListChange(container) {
            return new Promise((resolve) => {
                const originalHeight = container.offsetHeight;
            
                const observer = new ResizeObserver(() => {
                    if (container.offsetHeight !== originalHeight) {
                        observer.disconnect();
                        resolve();
                    }
                });
            
                observer.observe(container);
            });
        }

        // Extend the video list by scrolling to the last video and loading more
        function delay(ms) {
            return new Promise(resolve => setTimeout(resolve, ms));
        }

        async function extendOriginalVideoList() {
            try {
                let scrollY = window.scrollY;
                const container = document
                    .querySelector('div#items.style-scope.ytd-watch-next-secondary-results-renderer')
                    ?.querySelector('ytd-item-section-renderer')
                    ?.querySelector('#contents');
            
                if (!container) {
                    console.warn('[video-nav] videoContainer not found for observing!');
                    return [];
                }
            
                VIDEOS[VIDEOS.length - 1].scrollIntoView();
            
                await delay(50);
                window.scrollTo(0, scrollY);
            
                await waitForVideoListChange(container);
            
                getVideoList(); // Updates VIDEOS
                return Array.from(VIDEOS);
            } catch (e) {
                console.error('[video-nav] Error extending video list:', e);
                return [];
            }
        }


        // Create overlay and grid (same as before)...
        const overlay = Object.assign(document.createElement('div'), {
            id: 'video-nav-overlay',
            style: `
            position:fixed; inset:0; z-index:1000000;
            background:rgba(0,0,0,.90); overflow-y:auto;
            display:flex; flex-direction:column;
            font-family:Roboto,Arial,sans-serif;`
        });

        const grid = Object.assign(document.createElement('div'), {
            id: 'video-nav-grid',
            style: `
            display:grid;
            grid-template-columns:repeat(2, 1fr);
            gap:12px;
            padding:24px;
            max-width: calc(100vw - 30px);
            margin:0 auto;
            width:max-content;
            box-sizing:border-box;
            position:relative;
            padding-bottom: 93px; /* Space for the load more button */`
        });

        const loadMoreBtn = Object.assign(document.createElement('button'), {
            textContent: 'Load more videos',
            className: 'video-nav-loadmore video-nav-item',
        });
        overlay.appendChild(grid);
        document.body.appendChild(overlay);

        if (!document.getElementById('video-nav-style')) {
            const style = document.createElement('style');
            style.id = 'video-nav-style';
            style.textContent = `
            .video-nav-item {
                padding: 10px;
                border-radius: 10px;
                transition:
                    scale 0.2s ease-in-out,
                    background-color 0.2s ease-in-out,
                    transform 0.2s ease-in-out;
                margin: 0 !important;
                zoom: 1.75;
            }

            .video-nav-item__selected {
                background-color: rgba(255, 255, 255, 0.3);
                scale: 1.05;
            }

            .video-nav-loadmore {
                position: absolute;
                bottom: 24px;
                left: 50%;
                transform: translateX(-50%) scale(1);
                transform-origin: center;
                border: 0;
                background-color: rgba(255, 255, 255, 0.2);
                color: white;
                zoom: 1;
                font-size: 32px;
                line-height: 1;
                width: 25%;
            }

            .video-nav-loadmore.video-nav-item__selected {
                background-color: rgba(255, 255, 255, 0.5) !important;
                transform: translateX(-50%) scale(1.1);
                scale: 1;
            }
            `;
            document.head.appendChild(style);
        }

        // Add videos to grid
        function addVideosToGrid(newVideos) {
            const grid = document.getElementById('video-nav-grid');
            document.querySelector('.video-nav-loadmore')?.remove();

            const videoItems = newVideos.filter(v => {
                const link = v.querySelector('a[href*="/watch?v="]');
                const match = link?.href.match(/[?&]v=([\w-]+)/);
                const videoId = match?.[1];

                if (videoId && !ADDED_VIDEO_IDS.has(videoId)) {
                    ADDED_VIDEO_IDS.add(videoId);
                    return true;
                }
                return false;
            });

            videoItems.forEach(original => {
                const v = original.cloneNode(true);
                const link = v.querySelector('a[href*="/watch?v="]');
                const img = v.querySelector('img');

                v.classList.add('video-nav-item');
                original.querySelectorAll('.yt-lockup-metadata-view-model-wiz__menu-button, yt-touch-feedback-shape').forEach(el => el.remove());

                if (link && img) {
                    const match = link.href.match(/[?&]v=([\w-]+)/);
                    if (match) {
                        const videoId = match[1];
                        const thumbnailUrl = 'https://i.ytimg.com/vi/' + videoId + '/hqdefault.jpg';
                        img.src = thumbnailUrl;
                        img.loading = 'eager';
                        img.classList.add('yt-core-image--loaded');
                    }
                }


                grid.appendChild(v);
            });
            grid.appendChild(loadMoreBtn);
        }

        // Initially add videos
        addVideosToGrid(VIDEOS);

        // Navigation controller code...
        window.videoNavController = (() => {
            let selectedIndex = 0;
            let items = Array.from(document.querySelectorAll('.video-nav-item'));
            items[0]?.classList.add('video-nav-item__selected');

            function updateSelection(newIndex) {
                if (newIndex < 0) return;
                if (newIndex > items.length - 1) newIndex = items.length - 1;

                items[selectedIndex]?.classList.remove('video-nav-item__selected');
                selectedIndex = newIndex;
                items[selectedIndex]?.classList.add('video-nav-item__selected');

                // Scroll to the selected video, at the center of the screen
                const overlay = document.getElementById('video-nav-overlay');
                const overlayRect = overlay.getBoundingClientRect();
                const selectedRect = items[selectedIndex].getBoundingClientRect();
                const offset = selectedRect.top - overlayRect.top - (overlay.clientHeight / 2) + (items[selectedIndex].clientHeight / 2);
                overlay.scrollBy({ top: offset, behavior: 'smooth' });
            }

            return {
                up() { updateSelection(selectedIndex - 2); },
                down() { updateSelection(selectedIndex + 2); },
                left() {  if (selectedIndex % 2 === 1) updateSelection(selectedIndex - 1); },
                right() {  if (selectedIndex % 2 === 0) updateSelection(selectedIndex + 1); },
                select() {
                    items = Array.from(document.querySelectorAll('.video-nav-item'));
                    const selected = items[selectedIndex];

                    if (selected.classList.contains('video-nav-loadmore')) {
                        extendOriginalVideoList().then((newVideos) => {
                            addVideosToGrid(newVideos);
                            items = Array.from(document.querySelectorAll('.video-nav-item'));
                        
                            // If the previously selected index is beyond new videos length (excluding the button),
                            // clamp it to last video index (excluding the button)
                            const lastVideoIndex = items.length - 2; // -1 for button, -1 for zero-based index
                        
                            selectedIndex = Math.min(selectedIndex, lastVideoIndex);
                            updateSelection(selectedIndex);
                        });
                        return;
                    }
                    
                    let link;
                    try { link = selected.querySelector('a[href*="/watch?v="]'); }
                    catch (e) { console.warn('[video-nav] Error: ' + e); }
                    
                    if (link) { window.location.href = link.href; }
                    else { console.warn('[video-nav] No link found in selected item'); }
                }
            };
        })();
    } catch (e) {
        console.log('error: ' + e)
    }
})();
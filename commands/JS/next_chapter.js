(() => {
    const video = document.querySelector('video');
    if (!video) return;
    const timeDivs = Array.from(document.querySelectorAll('#contents #endpoint #details div#time.style-scope.ytd-macro-markers-list-item-renderer'));
    if (timeDivs.length === 0) return;
    function parseTime(t) {
        return t.split(':').reduce((acc, v) => acc * 60 + parseFloat(v), 0);
    }
    const times = timeDivs.map(div => parseTime(div.textContent.trim()));
    times.push(video.duration);
    const now = video.currentTime;
    for (let i = 0; i < times.length - 1; i++) {
        if (now < times[i] - 1) {
            video.currentTime = times[i];
            return;
        }
    }
    video.currentTime = video.duration;
})()
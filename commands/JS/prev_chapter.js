(() => {
    const video = document.querySelector('video');
    if (!video) return;
    const timeDivs = Array.from(document.querySelectorAll('#contents #endpoint #details div#time.style-scope.ytd-macro-markers-list-item-renderer'));
    if (timeDivs.length === 0) return;
    function parseTime(t) {
        return t.split(':').reduce((acc, v) => acc * 60 + parseFloat(v), 0);
    }
    const times = timeDivs.map(div => parseTime(div.textContent.trim()));
    times.unshift(0);
    const now = video.currentTime;
    let prev = 0;
    for (let i = 1; i < times.length; i++) {
        if (now < times[i] - 1) {
            video.currentTime = times[i - 2] || 0;
            return;
        }
    }
    video.currentTime = times[times.length - 2];
})()
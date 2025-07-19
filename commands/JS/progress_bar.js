// (() => {
//     const player = document.getElementById('movie_player');
//     if (!player) return;
//     // Toggle progress bar visibility by toggling autohide classes
//     if (player.classList.contains('ytp-autohide') || player.classList.contains('ytp-autohide-active')) {
//         player.classList.remove('ytp-autohide', 'ytp-autohide-active');
//     } else {
//         player.classList.add('ytp-autohide', 'ytp-autohide-active');
//     }
//     // Try to trigger the UI update by dispatching mouseenter and mousemove events
//     const video = document.querySelector('video');
//     if (video) {
//         const rect = video.getBoundingClientRect();
//         const eventOpts = { bubbles: true, cancelable: true, view: window };
//         // Mouseenter
//         video.dispatchEvent(new MouseEvent('mouseenter', {
//             ...eventOpts,
//             clientX: rect.left + rect.width / 2,
//             clientY: rect.top + rect.height / 2
//         }));
//         // Mousemove
//         video.dispatchEvent(new MouseEvent('mousemove', {
//             ...eventOpts,
//             clientX: rect.left + rect.width / 2,
//             clientY: rect.top + rect.height / 2
//         }));
//     }
// })()
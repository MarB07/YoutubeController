(() => {
    const menuBtn = document.querySelector('.ytp-settings-button');
    if (!menuBtn) return;
    menuBtn.click();
    setTimeout(() => {
        const items = Array.from(document.querySelectorAll('.ytp-menuitem'));
        const qualityItem = items.find(i =>
            i.textContent.includes('Quality') || i.textContent.includes('Kwaliteit')
        );
        if (!qualityItem) { menuBtn.click(); return; }
        qualityItem.click();
        setTimeout(() => {
            const options = Array.from(document.querySelectorAll('.ytp-quality-menu .ytp-menuitem'));
            const selected = options.findIndex(o => o.getAttribute('aria-checked') === 'true');
            if (selected > 0) options[selected - 1].click();
            menuBtn.click();
        }, 100);
    }, 100);
})()
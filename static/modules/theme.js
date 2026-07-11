/* ── OJ Coach - 明暗主题切换 ────────────────────────── */

(function () {
    const KEY = 'ojCoachTheme';

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem(KEY, theme);
        const btn = document.getElementById('themeToggle');
        if (btn) btn.textContent = theme === 'light' ? '☀' : '☽';
    }

    function toggle() {
        const current = document.documentElement.getAttribute('data-theme') || 'dark';
        applyTheme(current === 'dark' ? 'light' : 'dark');
    }

    // 初始化
    const saved = localStorage.getItem(KEY) || 'dark';
    applyTheme(saved);

    // 绑定按钮
    document.addEventListener('DOMContentLoaded', () => {
        const btn = document.getElementById('themeToggle');
        if (btn) btn.addEventListener('click', toggle);
    });
})();

/* OJ Coach Agent - WebUI 入口（纯原生 JS，无框架依赖） */
/* 分模块加载：静态模块 session → chat → ui → theme */

document.addEventListener('DOMContentLoaded', () => {
    state.cmdHistory = loadHistory();
    initSession();
    initResizers();
    initEvents();

    // 自动调整 textarea 高度
    const cmdInput = document.getElementById('commandInput');
    cmdInput.addEventListener('input', () => {
        cmdInput.style.height = 'auto';
        cmdInput.style.height = Math.min(cmdInput.scrollHeight, 120) + 'px';
    });

    // 定时刷新状态 + 连接检测
    setInterval(refreshStatus, 5000);
    setInterval(checkLlmStatus, 30000);
    setInterval(pingConnection, 10000);

    console.log('OJ Coach Agent WebUI 已就绪');
});

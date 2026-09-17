(function () {
    'use strict';

    function findLogComponent(vm) {
        if (!vm) return null;
        if (vm.$el && vm.$el.id === 'log-realtime') return vm;
        var children = vm.$children || [];
        for (var index = 0; index < children.length; index += 1) {
            var result = findLogComponent(children[index]);
            if (result) return result;
        }
        return null;
    }

    function getLogComponent(page) {
        if (page.__vue__) return page.__vue__;
        var app = document.getElementById('app');
        return app && app.__vue__ ? findLogComponent(app.__vue__) : null;
    }

    function clearDisplayedLogs(page, button) {
        var component = getLogComponent(page);
        if (!component || !Array.isArray(component.lists)) return;

        button.disabled = true;
        var clear = function () {
            component.lists.splice(0, component.lists.length);
            component.$nextTick(function () {
                if (component.$refs.logs) component.$refs.logs.scrollTop = 0;
                button.disabled = false;
            });
        };

        if (!component.loading_lists) {
            clear();
            return;
        }

        var attempts = 0;
        var timer = window.setInterval(function () {
            attempts += 1;
            if (!component.loading_lists || attempts >= 100) {
                window.clearInterval(timer);
                clear();
            }
        }, 50);
    }

    function installButton() {
        var page = document.getElementById('log-realtime');
        if (!page) return;
        var controls = page.querySelector('.refresh-switch');
        if (!controls || controls.querySelector('.log-clear-button')) return;

        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'log-clear-button';
        button.title = '清空当前显示的日志';
        button.innerHTML = '<i class="fa fa-eraser" aria-hidden="true"></i><span>清空显示</span>';
        controls.insertBefore(button, controls.firstChild);
    }

    document.addEventListener('click', function (event) {
        var button = event.target.closest && event.target.closest('.log-clear-button');
        if (!button) return;
        var page = document.getElementById('log-realtime');
        if (page) clearDisplayedLogs(page, button);
    });

    var observer = new MutationObserver(installButton);
    observer.observe(document.documentElement, {childList: true, subtree: true});
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', installButton);
    } else {
        installButton();
    }
}());

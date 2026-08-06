/**
 * 浮窗模式嵌入脚本
 * 第三方网站引入此脚本后，会自动在右下角添加一个机器人图标
 * 点击图标可展开对话窗口，支持最小化、全屏、关闭等操作
 * 
 * 使用方式：
 * <script async defer src="https://your-domain/chat-embed.js?token=YOUR_TOKEN&host=your-domain"></script>
 * 
 * 可选参数：
 * - loginPaths: 自定义登录页路径，多个用逗号分隔，如 /login,/sign-in,/auth
 * - autoHideOnLogin: 是否在登录页自动隐藏，默认 true
 */
(function() {
  'use strict';
  
  // 检测是否在iframe中运行（防止循环嵌套）
  try {
    if (window.self !== window.top) {
      console.log('[Chat Assistant] 在iframe内运行，跳过加载以防止循环嵌套');
      return;
    }
  } catch (e) {
    console.log('[Chat Assistant] 跨域iframe环境，跳过加载');
    return;
  }
  
  // 防止重复加载
  if (window.__CHAT_ASSISTANT_LOADED__) {
    console.warn('[Chat Assistant] 脚本已加载');
    return;
  }
  window.__CHAT_ASSISTANT_LOADED__ = true;
  
  // 默认登录页路径列表
  var DEFAULT_LOGIN_PATHS = ['/login', '/sign-in', '/signin', '/auth', '/app-login'];
  
  // 从脚本标签获取参数
  function getScriptParams() {
    var scripts = document.querySelectorAll('script[src*="chat-embed.js"]');
    if (scripts.length === 0) {
      scripts = document.querySelectorAll('script[src*="embed"]');
    }
    if (scripts.length === 0) {
      return { token: '', protocol: window.location.protocol.replace(':', ''), host: window.location.host, loginPaths: DEFAULT_LOGIN_PATHS, autoHideOnLogin: true };
    }
    
    var src = scripts[scripts.length - 1].getAttribute('src');
    var url = new URL(src, window.location.origin);
    
    var customLoginPaths = url.searchParams.get('loginPaths');
    var loginPaths = DEFAULT_LOGIN_PATHS;
    if (customLoginPaths) {
      loginPaths = customLoginPaths.split(',').map(function(p) { return p.trim(); }).filter(Boolean);
    }
    
    var autoHideOnLogin = url.searchParams.get('autoHideOnLogin');
    var autoHide = autoHideOnLogin !== 'false';
    
    return {
      token: url.searchParams.get('token') || '',
      protocol: url.searchParams.get('protocol') || window.location.protocol.replace(':', ''),
      host: url.searchParams.get('host') || window.location.host,
      loginPaths: loginPaths,
      autoHideOnLogin: autoHide
    };
  }
  
  var params = getScriptParams();
  
  if (!params.token) {
    console.error('[Chat Assistant] 缺少 token 参数');
    return;
  }
  
  /**
   * 检测当前页面是否为登录页（仅通过URL路径判断，不依赖sessionStorage状态）
   * @returns {boolean}
   */
  function isLoginPage() {
    if (!params.autoHideOnLogin) {
      return false;
    }
    
    var currentPath = window.location.pathname.toLowerCase();
    
    // 检查路径是否匹配登录页
    for (var i = 0; i < params.loginPaths.length; i++) {
      var loginPath = params.loginPaths[i].toLowerCase();
      if (currentPath === loginPath || currentPath.startsWith(loginPath + '/')) {
        return true;
      }
    }
    
    // 检查查询参数
    var searchParams = new URLSearchParams(window.location.search);
    if (searchParams.get('login') === 'true' || searchParams.get('auth') === 'required') {
      return true;
    }
    
    return false;
  }
  
  // 等待 DOM 就绪
  function ready(fn) {
    if (document.readyState !== 'loading') {
      fn();
    } else {
      document.addEventListener('DOMContentLoaded', fn);
    }
  }
  
  ready(function() {
    var baseUrl = params.protocol + '://' + params.host;
    var initiallyHidden = isLoginPage();
    
    // ========== 创建容器 ==========
    var container = document.createElement('div');
    container.id = 'chat-assistant-container';
    container.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:2147483647;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;';
    if (initiallyHidden) {
      container.style.display = 'none';
    }
    
    // ========== 创建浮动按钮（机器人图标） ==========
    var floatBtn = document.createElement('div');
    floatBtn.id = 'chat-assistant-btn';
    floatBtn.style.cssText = 'position:relative;width:56px;height:56px;border-radius:50%;background:linear-gradient(135deg,#3b82f6 0%,#2563eb 100%);cursor:pointer;box-shadow:0 4px 20px rgba(59,130,246,0.4);transition:all 0.3s ease;display:flex;align-items:center;justify-content:center;';
    
    floatBtn.innerHTML = '<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg" style="width:36px;height:36px;"><rect x="14" y="18" width="20" height="16" rx="3" fill="white"/><circle cx="20" cy="26" r="2.5" fill="#3b82f6"/><circle cx="28" cy="26" r="2.5" fill="#3b82f6"/><path d="M18 32 Q24 36 30 32" stroke="#3b82f6" stroke-width="2" fill="none" stroke-linecap="round"/></svg>';
    
    // 创建欢迎提示
    var tooltip = document.createElement('div');
    tooltip.style.cssText = 'position:absolute;top:-48px;right:0;background:#1f2937;color:white;padding:8px 16px;border-radius:8px;font-size:13px;white-space:nowrap;box-shadow:0 4px 12px rgba(0,0,0,0.15);display:none;';
    tooltip.textContent = '智能助手为您服务';
    tooltip.innerHTML += '<div style="position:absolute;bottom:-6px;right:20px;width:12px;height:12px;background:#1f2937;transform:rotate(45deg);"></div>';
    
    floatBtn.appendChild(tooltip);
    
    // 非登录页时显示欢迎提示
    if (!initiallyHidden) {
      setTimeout(function() {
        tooltip.style.display = 'block';
        setTimeout(function() {
          tooltip.style.display = 'none';
        }, 5000);
      }, 1000);
    }
    
    // ========== 创建聊天窗口 ==========
    var chatWindow = document.createElement('div');
    chatWindow.id = 'chat-assistant-window';
    chatWindow.style.cssText = 'display:none;position:fixed;bottom:0;right:0;width:528px;height:680px;background:white;border-radius:16px 0 0 0;border-left:1px solid #e2e8f0;border-right:1px solid #e2e8f0;overflow:hidden;flex-direction:column;animation:chatSlideUp 0.3s ease;transition:all 0.3s ease;z-index:2147483647;';
    
    var style = document.createElement('style');
    style.textContent = '@keyframes chatSlideUp {from{transform:translateY(20px);opacity:0;}to{transform:translateY(0);opacity:1;}}';
    document.head.appendChild(style);
    
    var iframe = document.createElement('iframe');
    iframe.style.cssText = 'width:100%;height:100%;border:none;';
    iframe.src = baseUrl + '/chat/' + params.token + '?mode=float';
    iframe.title = '智能助手';
    iframe.allow = 'microphone';
    iframe.setAttribute('scrolling', 'no');
    
    chatWindow.appendChild(iframe);
    
    var isExpanded = false;
    var originalSize = { width: '528px', height: '680px', bottom: '0', right: '0', borderRadius: '16px 0 0 0' };

    function getExpandedSize() {
      var width = window.innerWidth * 0.6;
      width = Math.max(width, 576);
      width = Math.min(width, 864);
      return {
        width: width + 'px',
        height: '100vh',
        right: '0',
        bottom: '0'
      };
    }
    
    function toggleExpanded() {
      if (!isExpanded) {
        var expandedSize = getExpandedSize();
        chatWindow.style.position = 'fixed';
        chatWindow.style.bottom = expandedSize.bottom;
        chatWindow.style.left = 'auto';
        chatWindow.style.right = expandedSize.right;
        chatWindow.style.top = 'auto';
        chatWindow.style.width = expandedSize.width;
        chatWindow.style.height = expandedSize.height;
        chatWindow.style.borderRadius = '0';
        chatWindow.style.overflow = 'hidden';
        chatWindow.style.borderLeft = '1px solid #e2e8f0';
        chatWindow.style.borderRight = '1px solid #e2e8f0';
        isExpanded = true;
        try {
          iframe.contentWindow.postMessage({ type: 'chat-expanded-enter' }, '*');
        } catch(e) {}
      } else {
        chatWindow.style.position = 'fixed';
        chatWindow.style.bottom = originalSize.bottom;
        chatWindow.style.right = originalSize.right;
        chatWindow.style.left = '';
        chatWindow.style.top = '';
        chatWindow.style.width = originalSize.width;
        chatWindow.style.height = originalSize.height;
        chatWindow.style.borderRadius = originalSize.borderRadius;
        chatWindow.style.overflow = 'hidden';
        chatWindow.style.borderLeft = '1px solid #e2e8f0';
        chatWindow.style.borderRight = '1px solid #e2e8f0';
        isExpanded = false;
        try {
          iframe.contentWindow.postMessage({ type: 'chat-expanded-exit' }, '*');
        } catch(e) {}
      }
    }
    
    // ========== 浮动按钮点击事件 ==========
    floatBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      if (chatWindow.style.display === 'none' || chatWindow.style.display === '') {
        chatWindow.style.display = 'flex';
        chatWindow.style.animation = 'none';
        chatWindow.offsetHeight;
        chatWindow.style.animation = 'chatSlideUp 0.3s ease';
        tooltip.style.display = 'none';
        floatBtn.style.display = 'none';
      }
    });
    
    chatWindow.addEventListener('click', function(e) {
      e.stopPropagation();
    });
    
    // ========== 监听来自iframe的消息 ==========
    window.addEventListener('message', function(e) {
      if (!e.data || typeof e.data !== 'object') return;
      
      switch (e.data.type) {
        case 'chat-toggle-expanded':
          toggleExpanded();
          break;
        case 'chat-minimize':
          if (isExpanded) {
            toggleExpanded();
          }
          chatWindow.style.display = 'none';
          floatBtn.style.display = 'flex';
          break;
        case 'chat-close':
          if (isExpanded) {
            toggleExpanded();
          }
          chatWindow.style.display = 'none';
          floatBtn.style.display = 'flex';
          setTimeout(function() {
            tooltip.style.display = 'block';
            setTimeout(function() {
              tooltip.style.display = 'none';
            }, 3000);
          }, 500);
          break;
      }
    });
    
    // 窗口大小改变时重新计算展开尺寸
    window.addEventListener('resize', function() {
      if (isExpanded) {
        var expandedSize = getExpandedSize();
        chatWindow.style.right = expandedSize.right;
        chatWindow.style.bottom = expandedSize.bottom;
        chatWindow.style.width = expandedSize.width;
        chatWindow.style.height = expandedSize.height;
      }
    });
    
    // ========== 组装并挂载 ==========
    container.appendChild(chatWindow);
    container.appendChild(floatBtn);
    document.body.appendChild(container);
    
    // ========== 切换浮窗显示/隐藏的核心函数 ==========
    function showAssistant() {
      container.style.display = 'block';
      floatBtn.style.display = 'flex';
      try {
        sessionStorage.setItem('__CHAT_USER_LOGGED_IN__', 'true');
      } catch (e) {}
      console.log('[Chat Assistant] 浮窗助手已显示');
    }
    
    function hideAssistant() {
      container.style.display = 'none';
      chatWindow.style.display = 'none';
      try {
        sessionStorage.setItem('__CHAT_USER_LOGGED_IN__', 'false');
      } catch (e) {}
      console.log('[Chat Assistant] 浮窗助手已隐藏');
    }
    
    // ========== 暴露全局接口 ==========
    window.__CHAT_ASSISTANT_SHOW__ = showAssistant;
    window.__CHAT_ASSISTANT_HIDE__ = hideAssistant;
    window.__CHAT_ASSISTANT_STATUS__ = function() {
      return {
        isVisible: container.style.display !== 'none',
        isWindowOpen: chatWindow.style.display !== 'none',
        isExpanded: isExpanded,
        isLoginPage: isLoginPage()
      };
    };
    
    // ========== 监听 SPA 路由变化，动态切换显示状态 ==========
    (function setupRouterListener() {
      var originalPushState = history.pushState;
      var originalReplaceState = history.replaceState;
      
      history.pushState = function() {
        var result = originalPushState.apply(this, arguments);
        window.dispatchEvent(new Event('locationchange'));
        return result;
      };
      
      history.replaceState = function() {
        var result = originalReplaceState.apply(this, arguments);
        window.dispatchEvent(new Event('locationchange'));
        return result;
      };
      
      window.addEventListener('popstate', function() {
        window.dispatchEvent(new Event('locationchange'));
      });
      
      // 路由变化时，动态切换浮窗显示/隐藏（不刷新页面）
      window.addEventListener('locationchange', function() {
        if (isLoginPage()) {
          // 当前页变为登录页，隐藏浮窗
          if (container.style.display !== 'none') {
            hideAssistant();
          }
        } else {
          // 当前页变为非登录页，显示浮窗
          if (container.style.display === 'none') {
            showAssistant();
          }
        }
      });
    })();
    
    // 如果初始为登录页，设置定时检查（以防路由同步变化）
    if (initiallyHidden) {
      var checkInterval = setInterval(function() {
        if (!isLoginPage() && container.style.display === 'none') {
          showAssistant();
          clearInterval(checkInterval);
        }
      }, 500);
      // 最多检查30秒
      setTimeout(function() {
        clearInterval(checkInterval);
      }, 30000);
    }
    
    console.log('[Chat Assistant] 浮窗模式已初始化', { token: params.token, initiallyHidden: initiallyHidden });
  });
})();

/**
 * 浮窗模式嵌入脚本
 * 第三方网站引入此脚本后，会自动在右下角添加一个机器人图标
 * 点击图标可展开对话窗口，支持最小化、全屏、关闭等操作
 * 
 * 使用方式：
 * <script async defer src="https://your-domain/chat-embed.js?token=YOUR_TOKEN&host=your-domain"></script>
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
    // 跨域时也跳过，防止循环
    console.log('[Chat Assistant] 跨域iframe环境，跳过加载');
    return;
  }
  
  // 防止重复加载
  if (window.__CHAT_ASSISTANT_LOADED__) {
    console.warn('[Chat Assistant] 脚本已加载');
    return;
  }
  window.__CHAT_ASSISTANT_LOADED__ = true;
  
  // 从脚本标签获取参数
  function getScriptParams() {
    var scripts = document.querySelectorAll('script[src*="chat-embed.js"]');
    if (scripts.length === 0) {
      scripts = document.querySelectorAll('script[src*="embed"]');
    }
    if (scripts.length === 0) {
      return { token: '', protocol: window.location.protocol.replace(':', ''), host: window.location.host };
    }
    
    var src = scripts[scripts.length - 1].getAttribute('src');
    var url = new URL(src, window.location.origin);
    
    return {
      token: url.searchParams.get('token') || '',
      protocol: url.searchParams.get('protocol') || window.location.protocol.replace(':', ''),
      host: url.searchParams.get('host') || window.location.host
    };
  }
  
  var params = getScriptParams();
  
  if (!params.token) {
    console.error('[Chat Assistant] 缺少 token 参数');
    return;
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
    
    // ========== 创建容器 ==========
    var container = document.createElement('div');
    container.id = 'chat-assistant-container';
    container.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:2147483647;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;';
    
    // ========== 创建浮动按钮（机器人图标） ==========
    var floatBtn = document.createElement('div');
    floatBtn.id = 'chat-assistant-btn';
    floatBtn.style.cssText = 'position:relative;width:56px;height:56px;border-radius:50%;background:linear-gradient(135deg,#8b5cf6 0%,#7c3aed 100%);cursor:pointer;box-shadow:0 4px 20px rgba(139,92,246,0.4);transition:all 0.3s ease;display:flex;align-items:center;justify-content:center;';
    
    floatBtn.innerHTML = '<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg" style="width:36px;height:36px;"><circle cx="24" cy="24" r="20" fill="#8b5cf6"/><rect x="14" y="18" width="20" height="16" rx="3" fill="white"/><circle cx="20" cy="26" r="2.5" fill="#8b5cf6"/><circle cx="28" cy="26" r="2.5" fill="#8b5cf6"/><path d="M18 32 Q24 36 30 32" stroke="#8b5cf6" stroke-width="2" fill="none" stroke-linecap="round"/><circle cx="36" cy="14" r="3" fill="#10b981"/><circle cx="36" cy="14" r="6" fill="#10b981" opacity="0.3"/></svg>';
    
    // 创建欢迎提示
    var tooltip = document.createElement('div');
    tooltip.style.cssText = 'position:absolute;top:-48px;right:0;background:#1f2937;color:white;padding:8px 16px;border-radius:8px;font-size:13px;white-space:nowrap;box-shadow:0 4px 12px rgba(0,0,0,0.15);display:none;';
    tooltip.textContent = '智能助手为您服务';
    tooltip.innerHTML += '<div style="position:absolute;bottom:-6px;right:20px;width:12px;height:12px;background:#1f2937;transform:rotate(45deg);"></div>';
    
    floatBtn.appendChild(tooltip);
    
    // 显示欢迎提示
    setTimeout(function() {
      tooltip.style.display = 'block';
      setTimeout(function() {
        tooltip.style.display = 'none';
      }, 5000);
    }, 1000);
    
    // ========== 创建聊天窗口 ==========
    // 初始小窗口：调大点，右边与网页右边对齐，下边框与网页下边框对齐
    var chatWindow = document.createElement('div');
    chatWindow.id = 'chat-assistant-window';
    chatWindow.style.cssText = 'display:none;position:fixed;bottom:0;right:0;width:528px;height:680px;background:white;border-radius:16px 0 0 0;box-shadow:-4px -4px 24px rgba(0,0,0,0.15);overflow:hidden;flex-direction:column;animation:chatSlideUp 0.3s ease;transition:all 0.3s ease;z-index:2147483647;';
    
    // 添加动画样式
    var style = document.createElement('style');
    style.textContent = '@keyframes chatSlideUp {from{transform:translateY(20px);opacity:0;}to{transform:translateY(0);opacity:1;}}';
    document.head.appendChild(style);
    
    // 创建iframe加载聊天页面（带mode=float参数）
    var iframe = document.createElement('iframe');
    iframe.style.cssText = 'width:100%;height:100%;border:none;';
    iframe.src = baseUrl + '/chat/' + params.token + '?mode=float';
    iframe.title = '智能助手';
    iframe.allow = 'microphone';
    iframe.setAttribute('scrolling', 'no');
    
    chatWindow.appendChild(iframe);
    
    // 展开状态（右侧全屏高度）
    var isExpanded = false;

    // 保存小窗口尺寸（调大后：右边、底部对齐）
    var originalSize = { width: '528px', height: '680px', bottom: '0', right: '0', borderRadius: '16px 0 0 0' };

    // 计算展开尺寸（继续变大：右侧对齐，底部对齐，宽度约60%视口）
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
    
    // 切换展开/缩小模式
    function toggleExpanded() {
      if (!isExpanded) {
        // 展开为右侧全高度（右边对齐，底部对齐）
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
        chatWindow.style.boxShadow = '-4px 0 24px rgba(0,0,0,0.15)';
        isExpanded = true;
        // 通知iframe进入展开模式（不自动显示侧边栏）
        try {
          iframe.contentWindow.postMessage({ type: 'chat-expanded-enter' }, '*');
        } catch(e) {
          console.warn('无法发送消息到iframe', e);
        }
      } else {
        // 缩小回小窗口（右边、底部对齐）
        chatWindow.style.position = 'fixed';
        chatWindow.style.bottom = originalSize.bottom;
        chatWindow.style.right = originalSize.right;
        chatWindow.style.left = '';
        chatWindow.style.top = '';
        chatWindow.style.width = originalSize.width;
        chatWindow.style.height = originalSize.height;
        chatWindow.style.borderRadius = originalSize.borderRadius;
        chatWindow.style.overflow = 'hidden';
        chatWindow.style.boxShadow = '-4px -4px 24px rgba(0,0,0,0.15)';
        isExpanded = false;
        // 通知iframe退出展开模式
        try {
          iframe.contentWindow.postMessage({ type: 'chat-expanded-exit' }, '*');
        } catch(e) {
          console.warn('无法发送消息到iframe', e);
        }
      }
    }
    
    // ========== 浮动按钮点击事件 ==========
    floatBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      if (chatWindow.style.display === 'none' || chatWindow.style.display === '') {
        // 点击浮窗图标，显示调大的小窗口（不进入展开模式）
        chatWindow.style.display = 'flex';
        // 重置动画
        chatWindow.style.animation = 'none';
        chatWindow.offsetHeight;
        chatWindow.style.animation = 'chatSlideUp 0.3s ease';
        tooltip.style.display = 'none';
        // 隐藏浮窗小图标
        floatBtn.style.display = 'none';
      }
    });
    
    // ========== 点击外部不关闭聊天窗口（仅通过X按钮关闭） ==========
    // 防止聊天窗口内点击冒泡
    chatWindow.addEventListener('click', function(e) {
      e.stopPropagation();
    });
    
    // ========== 监听来自iframe的消息（ChatEmbedView通信） ==========
    window.addEventListener('message', function(e) {
      if (!e.data || typeof e.data !== 'object') return;
      
      switch (e.data.type) {
        case 'chat-toggle-expanded':
          // 切换展开/缩小模式
          toggleExpanded();
          break;
        case 'chat-minimize':
          // 最小化：隐藏窗口
          if (isExpanded) {
            toggleExpanded();
          }
          chatWindow.style.display = 'none';
          break;
        case 'chat-close':
          // 关闭：隐藏窗口，恢复浮窗图标显示
          if (isExpanded) {
            toggleExpanded();
          }
          chatWindow.style.display = 'none';
          // 恢复显示浮窗小图标
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
    
    console.log('[Chat Assistant] 浮窗模式已初始化', { token: params.token });
  });
})();

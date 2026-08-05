/**
 * 剪贴板工具函数
 * 兼容安全上下文（HTTPS/localhost）和非安全上下文（HTTP/IP）
 */

/**
 * 复制文本到剪贴板
 * 优先使用 navigator.clipboard API，不可用时回退到 execCommand
 * @param text 待复制的文本
 * @returns 是否复制成功
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  // 优先使用现代 Clipboard API（需安全上下文：HTTPS 或 localhost）
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch {
      // 权限被拒绝或写入失败，回退到传统方案
    }
  }

  // 回退方案：使用 textarea + execCommand
  try {
    const textarea = document.createElement('textarea')
    textarea.value = text
    // 防止页面滚动
    textarea.style.position = 'fixed'
    textarea.style.left = '-9999px'
    textarea.style.top = '0'
    textarea.setAttribute('readonly', '')
    document.body.appendChild(textarea)

    // iOS 需要先创建 Range 选区
    const isIOS = /ipad|iphone|ipod/i.test(navigator.userAgent)
    if (isIOS) {
      const range = document.createRange()
      range.selectNodeContents(textarea)
      const selection = window.getSelection()
      selection?.removeAllRanges()
      selection?.addRange(range)
      textarea.setSelectionRange(0, text.length)
    } else {
      textarea.select()
    }

    const success = document.execCommand('copy')
    document.body.removeChild(textarea)
    return success
  } catch {
    return false
  }
}

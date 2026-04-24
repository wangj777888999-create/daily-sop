import { computed } from 'vue'

// 设计令牌 hook - 提供设计系统中定义的所有颜色、字体、间距等令牌
export function useDesignTokens() {
  const colors = {
    pageBg: '#F7F3EC',
    sidebarBg: '#EDE7D9',
    aiPanelBg: '#EAE4D6',
    topbarBg: '#FEFCF8',
    cardBg: '#FEFCF8',
    border: '#C4BAA8',
    textHeading: '#3D3530',
    textBody: '#6B5F52',
    textLight: '#9C8E82',
    accent: '#5B8F7A',
    accentLight: '#D6EDE7',
    amber: '#C17F3A',
    blue: '#3A7FC1',
    purple: '#7B6BAA',
    placeholder: '#DDD6C8',
    placeholderDk: '#C8BFB0',
    chip: '#E5DDD0'
  }

  const spacing = {
    xs: '4px',
    sm: '8px',
    md: '12px',
    lg: '14px',
    xl: '20px'
  }

  const borderRadius = {
    sm: '6px',
    md: '8px',
    lg: '10px',
    xl: '12px'
  }

  const typography = {
    titleLg: { fontSize: '20px', fontWeight: '700' },
    titleMd: { fontSize: '16px', fontWeight: '700' },
    titleSm: { fontSize: '14px', fontWeight: '700' },
    body: { fontSize: '13px', fontWeight: '400' },
    helper: { fontSize: '12px', fontWeight: '400' },
    label: { fontSize: '11px', fontWeight: '400' },
    micro: { fontSize: '10px', fontWeight: '700', letterSpacing: '1px' }
  }

  const shadows = {
    cardHover: '0 4px 16px rgba(61, 53, 48, 0.10)',
    inputFocus: '0 0 0 2px rgba(91, 143, 122, 0.25)'
  }

  const layout = {
    sidebarWidth: '220px',
    aiPanelWidth: '280px',
    topbarHeight: '52px'
  }

  // 获取带透明度的颜色（用于图标背景等）
  const getColorWithAlpha = (color: string, alpha: number) => {
    const hex = color.replace('#', '')
    const r = parseInt(hex.substring(0, 2), 16)
    const g = parseInt(hex.substring(2, 4), 16)
    const b = parseInt(hex.substring(4, 6), 16)
    return `rgba(${r}, ${g}, ${b}, ${alpha})`
  }

  return {
    colors,
    spacing,
    borderRadius,
    typography,
    shadows,
    layout,
    getColorWithAlpha,
    // 便捷方法
    getIconBg: (color: string) => getColorWithAlpha(color, 0.13) // 13% 透明度
  }
}

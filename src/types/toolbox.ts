/** 单个工具的注册信息 */
export interface Tool {
  /** 唯一标识 */
  id: string
  /** 工具名称，显示在卡片上 */
  name: string
  /** 一句话描述 */
  description: string
  /** 卡片图标（emoji 或字符） */
  icon: string
  /** 主题色（hex） */
  color: string
  /** 分类标签 */
  tags: string[]
  /** iframe 加载的 URL 路径（相对于 public/） */
  src: string
  /** 展开后面板的默认高度（px），默认 800 */
  iframeHeight?: number
  /** 是否启用，默认 true */
  enabled?: boolean
}

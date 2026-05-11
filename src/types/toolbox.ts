/** 工具类型 */
export type ToolKind = 'iframe' | 'vue'

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
  /** 工具类型：iframe 加载 HTML 或 vue 原生页面 */
  type: ToolKind
  /** iframe 加载的 URL 路径（相对于 public/），type=iframe 时必填 */
  src?: string
  /** Vue 路由路径，type=vue 时必填 */
  route?: string
  /** 展开后面板的默认高度（px），默认 800，仅 iframe 工具有效 */
  iframeHeight?: number
  /** 是否启用，默认 true */
  enabled?: boolean
}

// 全局类型定义

// 用户信息
export interface User {
  id: string
  name: string
  role: string
  avatar?: string
}

// 面包屑
export interface Breadcrumb {
  label: string
  path?: string
}

// AI 消息
export interface AIMessage {
  id: string
  role: 'ai' | 'user'
  content: string
  timestamp: number
}

// 导航项
export interface NavItem {
  icon: string
  label: string
  key: string
  path: string
}

// 步骤状态
export type StepStatus = 'pending' | 'active' | 'completed'

// SOP 模板
export interface SOPTemplate {
  id: string
  name: string
  description: string
  tags: string[]
  estimatedTime: string
}

// 文件类型
export type FileType = 'PDF' | 'DOCX' | 'XLSX' | 'TXT'

// 文件项
export interface FileItem {
  id: string
  name: string
  type: FileType
  size: string
  date: string
  tags?: string[]
}

// 指标卡片数据
export interface MetricData {
  label: string
  value: string | number
  delta?: number
}

// 查询结果
export interface QueryResult {
  columns: string[]
  rows: any[][]
  rowCount: number
  executionTime: number
}

// 表格列定义
export interface TableColumn {
  key: string
  label: string
  width?: string
}

// 组件 Props 类型
export interface CardProps {
  hoverable?: boolean
}

export interface ButtonProps {
  variant: 'primary' | 'secondary'
  size: 'normal' | 'small'
  icon?: string
}

export interface ChipProps {
  active?: boolean
}

export interface StepBadgeProps {
  step: number
  label: string
  status: StepStatus
}

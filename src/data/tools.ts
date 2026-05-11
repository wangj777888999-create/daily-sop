import type { Tool } from '@/types/toolbox'

export const tools: Tool[] = [
  {
    id: 'fee-calculator',
    name: '课时费计算器',
    description: '上传 Excel 数据，按教练×课程规则计算课时费，支持多种计费方式和补贴配置',
    icon: '◈',
    color: '#5B8F7A',
    tags: ['财务', 'Excel'],
    type: 'iframe',
    src: '/tools/课时费计算器.html',
    iframeHeight: 800,
  },
  {
    id: 'monthly-analysis',
    name: '校内月度分析',
    description: '月度校内数据分析，产出课时费计算所需的月度分析表',
    icon: '◈',
    color: '#6366f1',
    tags: ['分析', '月度'],
    type: 'vue',
    route: '/tools/monthly-analysis',
  },
]

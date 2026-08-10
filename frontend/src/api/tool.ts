import request from './index'

// 工具列表
export const getTools = async (toolType?: string) => {
  try {
    const url = toolType ? `/tools?tool_type=${toolType}` : '/tools'
    const response = await request.get(url)
    return response
  } catch (error: any) {
    console.error('获取工具列表失败:', error)
    throw error
  }
}

// 创建 MCP
export const createMCP = async (data: {
  name: string
  description?: string
  mcp_config: Record<string, any>
}) => {
  try {
    const response = await request.post('/tools/mcp', data)
    return response
  } catch (error: any) {
    console.error('创建MCP失败:', error)
    throw error
  }
}

// 更新 MCP
export const updateMCP = async (id: number, data: {
  name?: string
  description?: string
  mcp_config?: Record<string, any>
}) => {
  try {
    const response = await request.put(`/tools/mcp/${id}`, data)
    return response
  } catch (error: any) {
    console.error('更新MCP失败:', error)
    throw error
  }
}

// 测试 MCP 连接
export const testMCPConnection = async (mcpConfig: Record<string, any>) => {
  try {
    const response = await request.post('/tools/mcp/test', { mcp_config: mcpConfig })
    return response
  } catch (error: any) {
    console.error('MCP连接测试失败:', error)
    throw error
  }
}

// 创建 Skill (带文件上传)
export const createSkill = async (formData: FormData) => {
  try {
    const response = await request.post('/tools/skill', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response
  } catch (error: any) {
    console.error('创建Skill失败:', error)
    throw error
  }
}

// 更新 Skill (带可选文件上传)
export const updateSkill = async (id: number, formData: FormData) => {
  try {
    const response = await request.put(`/tools/skill/${id}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response
  } catch (error: any) {
    console.error('更新Skill失败:', error)
    throw error
  }
}

// 删除工具
export const deleteTool = async (id: number) => {
  try {
    const response = await request.delete(`/tools/${id}`)
    return response
  } catch (error: any) {
    console.error('删除工具失败:', error)
    throw error
  }
}

// 更新工具状态
export const updateToolStatus = async (id: number, status: string) => {
  try {
    const response = await request.put(`/tools/${id}/status`, null, {
      params: { status }
    })
    return response
  } catch (error: any) {
    console.error('更新工具状态失败:', error)
    throw error
  }
}

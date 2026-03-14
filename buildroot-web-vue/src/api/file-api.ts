// HTTP API for file operations
// 用于小文件的简单 HTTP 上传和下载

const API_BASE = '/api'

/**
 * 上传文件（HTTP，适用于小文件 <10MB）
 */
export async function uploadFile(
  deviceId: string,
  file: File,
  path: string
): Promise<{ success: boolean; message?: string }> {
  const formData = new FormData()
  formData.append('file', file)

  const url = `${API_BASE}/devices/${deviceId}/files/upload?path=${encodeURIComponent(path)}&filename=${encodeURIComponent(file.name)}`

  try {
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Upload failed')
    }

    return await response.json()
  } catch (error: any) {
    console.error('Upload error:', error)
    throw error
  }
}

/**
 * 下载文件（HTTP，适用于小文件 <10MB）
 */
export async function downloadFile(
  deviceId: string,
  path: string,
  filename?: string
): Promise<void> {
  const url = `${API_BASE}/devices/${deviceId}/files/download?path=${encodeURIComponent(path)}`

  try {
    const response = await fetch(url)

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Download failed')
    }

    const blob = await response.blob()
    const downloadUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = filename || path.split('/').pop() || 'file'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(downloadUrl)
  } catch (error: any) {
    console.error('Download error:', error)
    throw error
  }
}

/**
 * 删除文件/目录（HTTP）
 */
export async function deleteFile(
  deviceId: string,
  path: string
): Promise<{ success: boolean; message?: string }> {
  const url = `${API_BASE}/devices/${deviceId}/files`

  try {
    const response = await fetch(url, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ path }),
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Delete failed')
    }

    return await response.json()
  } catch (error: any) {
    console.error('Delete error:', error)
    throw error
  }
}

/**
 * 创建目录（HTTP）
 */
export async function createDirectory(
  deviceId: string,
  path: string
): Promise<{ success: boolean; message?: string }> {
  const url = `${API_BASE}/devices/${deviceId}/files/mkdir`

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ path }),
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Create directory failed')
    }

    return await response.json()
  } catch (error: any) {
    console.error('Create directory error:', error)
    throw error
  }
}

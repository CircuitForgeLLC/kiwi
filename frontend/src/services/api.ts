/**
 * API Service for Kiwi Backend
 *
 * VITE_API_BASE is baked in at build time:
 *   dev:   '' (empty — proxy in vite.config.ts handles /api/)
 *   cloud: '/kiwi' (Caddy strips /kiwi and forwards to nginx, which proxies /api/ → api container)
 */

import axios, { type AxiosInstance } from 'axios'

// API Configuration
const API_BASE_URL = (import.meta.env.VITE_API_BASE ?? '') + '/api/v1'

// Create axios instance
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 seconds
})

// Request interceptor for logging
api.interceptors.request.use(
  (config) => {
    console.log(`[API] ${config.method?.toUpperCase()} ${config.baseURL}${config.url}`, {
      params: config.params,
      data: config.data instanceof FormData ? '<FormData>' : config.data,
    })
    return config
  },
  (error) => {
    console.error('[API Request Error]', error)
    return Promise.reject(error)
  }
)

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    console.log(`[API] ✓ ${response.status} ${response.config.method?.toUpperCase()} ${response.config.url}`)
    return response
  },
  (error) => {
    console.error('[API Error]', {
      message: error.message,
      url: error.config?.url,
      method: error.config?.method?.toUpperCase(),
      status: error.response?.status,
      statusText: error.response?.statusText,
      data: error.response?.data,
      baseURL: error.config?.baseURL,
    })
    return Promise.reject(error)
  }
)

// ========== Types ==========

export interface Product {
  id: string
  barcode: string | null
  name: string
  brand: string | null
  category: string | null
  description: string | null
  image_url: string | null
  nutrition_data: Record<string, any>
  source: string
  tags: Tag[]
}

export interface Tag {
  id: string
  name: string
  slug: string
  description: string | null
  color: string | null
  category: string | null
}

export interface InventoryItem {
  id: string
  product_id: string
  product: Product
  quantity: number
  unit: string
  location: string
  sublocation: string | null
  purchase_date: string | null
  expiration_date: string | null
  status: string
  source: string
  notes: string | null
  created_at: string
  updated_at: string
}

export interface InventoryItemUpdate {
  quantity?: number
  unit?: string
  location?: string
  sublocation?: string | null
  purchase_date?: string | null
  expiration_date?: string | null
  status?: string
  notes?: string | null
}

export interface InventoryStats {
  total_items: number
  total_products: number
  expiring_soon: number
  expired: number
  items_by_location: Record<string, number>
  items_by_status: Record<string, number>
}

export interface Receipt {
  id: string
  filename: string
  status: string
  metadata: Record<string, any>
  quality_score: number | null
}

export interface ReceiptOCRData {
  id: string
  receipt_id: string
  merchant: {
    name: string | null
    address: string | null
    phone: string | null
  }
  transaction: {
    date: string | null
    time: string | null
    receipt_number: string | null
    register: string | null
    cashier: string | null
  }
  items: Array<{
    name: string
    quantity: number
    unit_price: number | null
    total_price: number
    category: string | null
  }>
  totals: {
    subtotal: number | null
    tax: number | null
    total: number | null
    payment_method: string | null
  }
  confidence: Record<string, number>
  warnings: string[]
  processing_time: number | null
  created_at: string
}

// ========== Inventory API ==========

export const inventoryAPI = {
  /**
   * List all inventory items
   */
  async listItems(params?: {
    location?: string
    status?: string
    limit?: number
    offset?: number
  }): Promise<InventoryItem[]> {
    const response = await api.get('/inventory/items', { params })
    return response.data
  },

  /**
   * Get a single inventory item
   */
  async getItem(itemId: string): Promise<InventoryItem> {
    const response = await api.get(`/inventory/items/${itemId}`)
    return response.data
  },

  /**
   * Update an inventory item
   */
  async updateItem(itemId: string, update: InventoryItemUpdate): Promise<InventoryItem> {
    const response = await api.patch(`/inventory/items/${itemId}`, update)
    return response.data
  },

  /**
   * Delete an inventory item
   */
  async deleteItem(itemId: string): Promise<void> {
    await api.delete(`/inventory/items/${itemId}`)
  },

  /**
   * Get inventory statistics
   */
  async getStats(): Promise<InventoryStats> {
    const response = await api.get('/inventory/stats')
    return response.data
  },

  /**
   * Get items expiring soon
   */
  async getExpiring(days: number = 7): Promise<any[]> {
    const response = await api.get(`/inventory/expiring?days=${days}`)
    return response.data
  },

  /**
   * Scan barcode from text
   */
  async scanBarcodeText(
    barcode: string,
    location: string = 'pantry',
    quantity: number = 1.0,
    autoAdd: boolean = true
  ): Promise<any> {
    const response = await api.post('/inventory/scan/text', {
      barcode,
      location,
      quantity,
      auto_add_to_inventory: autoAdd,
    })
    return response.data
  },

  /**
   * Mark item as consumed
   */
  async consumeItem(itemId: string): Promise<void> {
    await api.post(`/inventory/items/${itemId}/consume`)
  },

  /**
   * Create a new product
   */
  async createProduct(data: {
    name: string
    brand?: string
    source?: string
  }): Promise<Product> {
    const response = await api.post('/inventory/products', data)
    return response.data
  },

  /**
   * Create a new inventory item
   */
  async createItem(data: {
    product_id: string
    quantity: number
    unit?: string
    location: string
    expiration_date?: string
    source?: string
  }): Promise<InventoryItem> {
    const response = await api.post('/inventory/items', data)
    return response.data
  },

  /**
   * Scan barcode from image
   */
  async scanBarcodeImage(
    file: File,
    location: string = 'pantry',
    quantity: number = 1.0,
    autoAdd: boolean = true
  ): Promise<any> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('location', location)
    formData.append('quantity', quantity.toString())
    formData.append('auto_add_to_inventory', autoAdd.toString())

    const response = await api.post('/inventory/scan', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },
}

// ========== Receipts API ==========

export const receiptsAPI = {
  /**
   * List all receipts
   */
  async listReceipts(): Promise<Receipt[]> {
    const response = await api.get('/receipts/')
    return response.data
  },

  /**
   * Get a single receipt
   */
  async getReceipt(receiptId: string): Promise<Receipt> {
    const response = await api.get(`/receipts/${receiptId}`)
    return response.data
  },

  /**
   * Upload a receipt
   */
  async upload(file: File): Promise<Receipt> {
    const formData = new FormData()
    formData.append('file', file)

    const response = await api.post('/receipts/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  /**
   * Get receipt statistics
   */
  async getStats(): Promise<any> {
    const response = await api.get('/export/stats')
    return response.data
  },

  /**
   * Get OCR data for a receipt
   */
  async getOCRData(receiptId: string): Promise<ReceiptOCRData> {
    const response = await api.get(`/receipts/${receiptId}/ocr/data`)
    return response.data
  },

  /**
   * Get OCR status for a receipt
   */
  async getOCRStatus(receiptId: string): Promise<any> {
    const response = await api.get(`/receipts/${receiptId}/ocr/status`)
    return response.data
  },

  /**
   * Trigger OCR processing
   */
  async triggerOCR(receiptId: string, forceReprocess: boolean = false): Promise<any> {
    const response = await api.post(`/receipts/${receiptId}/ocr/trigger`, {
      force_reprocess: forceReprocess,
    })
    return response.data
  },
}

// ========== Export API ==========

export const exportAPI = {
  /**
   * Get export statistics
   */
  async getStats(): Promise<any> {
    const response = await api.get('/export/stats')
    return response.data
  },

  /**
   * Download inventory CSV
   */
  getInventoryCSVUrl(location?: string, status: string = 'available'): string {
    const params = new URLSearchParams()
    if (location) params.append('location', location)
    params.append('status', status)
    return `${API_BASE_URL}/export/inventory/csv?${params.toString()}`
  },

  /**
   * Download inventory Excel
   */
  getInventoryExcelUrl(location?: string, status: string = 'available'): string {
    const params = new URLSearchParams()
    if (location) params.append('location', location)
    params.append('status', status)
    return `${API_BASE_URL}/export/inventory/excel?${params.toString()}`
  },

  /**
   * Download receipts CSV
   */
  getReceiptsCSVUrl(): string {
    return `${API_BASE_URL}/export/csv`
  },

  /**
   * Download receipts Excel
   */
  getReceiptsExcelUrl(): string {
    return `${API_BASE_URL}/export/excel`
  },
}

export default api

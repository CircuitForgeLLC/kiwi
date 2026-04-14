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
  id: number
  product_id: number
  product_name: string | null
  barcode: string | null
  category: string | null
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
  available_items: number
  expiring_soon: number
  expired_items: number
  locations: Record<string, number>
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
  async updateItem(itemId: number, update: InventoryItemUpdate): Promise<InventoryItem> {
    const response = await api.patch(`/inventory/items/${itemId}`, update)
    return response.data
  },

  /**
   * Delete an inventory item
   */
  async deleteItem(itemId: number): Promise<void> {
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
  async consumeItem(itemId: number): Promise<void> {
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
   * Bulk-add items by ingredient name (no barcode required).
   * Idempotent: re-adding an existing product just creates a new inventory entry.
   */
  async bulkAddByName(items: Array<{
    name: string
    quantity?: number
    unit?: string
    location?: string
  }>): Promise<{ added: number; failed: number; results: Array<{ name: string; ok: boolean; item_id?: number; error?: string }> }> {
    const response = await api.post('/inventory/items/bulk-add-by-name', { items })
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

// ========== Recipes & Settings Types ==========

export interface SwapCandidate {
  original_name: string
  substitute_name: string
  constraint_label: string
  explanation: string
  compensation_hints: Record<string, string>[]
}

export interface NutritionPanel {
  calories: number | null
  fat_g: number | null
  protein_g: number | null
  carbs_g: number | null
  fiber_g: number | null
  sugar_g: number | null
  sodium_mg: number | null
  servings: number | null
  estimated: boolean
}

export interface RecipeSuggestion {
  id: number
  title: string
  match_count: number
  element_coverage: Record<string, number>
  swap_candidates: SwapCandidate[]
  matched_ingredients: string[]
  missing_ingredients: string[]
  directions: string[]
  prep_notes: string[]
  notes: string
  level: number
  is_wildcard: boolean
  nutrition: NutritionPanel | null
  source_url: string | null
}

export interface NutritionFilters {
  max_calories: number | null
  max_sugar_g: number | null
  max_carbs_g: number | null
  max_sodium_mg: number | null
}

export interface GroceryLink {
  ingredient: string
  retailer: string
  url: string
}

export interface RecipeResult {
  suggestions: RecipeSuggestion[]
  element_gaps: string[]
  grocery_list: string[]
  grocery_links: GroceryLink[]
  rate_limited: boolean
  rate_limit_count: number
}

export interface RecipeRequest {
  pantry_items: string[]
  level: number
  constraints: string[]
  allergies: string[]
  expiry_first: boolean
  hard_day_mode: boolean
  max_missing: number | null
  style_id: string | null
  category: string | null
  wildcard_confirmed: boolean
  nutrition_filters: NutritionFilters
  excluded_ids: number[]
  shopping_mode: boolean
}

export interface Staple {
  slug: string
  name: string
  category: string
  dietary_tags: string[]
}

// ── Build Your Own types ──────────────────────────────────────────────────

export interface AssemblyRoleOut {
  display: string
  required: boolean
  keywords: string[]
  hint: string
}

export interface AssemblyTemplateOut {
  id: string
  title: string
  icon: string
  descriptor: string
  role_sequence: AssemblyRoleOut[]
}

export interface RoleCandidateItem {
  name: string
  in_pantry: boolean
  tags: string[]
}

export interface RoleCandidatesResponse {
  compatible: RoleCandidateItem[]
  other: RoleCandidateItem[]
  available_tags: string[]
}

export interface BuildRequest {
  template_id: string
  role_overrides: Record<string, string>
}

// ========== Recipes API ==========

export const recipesAPI = {
  async suggest(req: RecipeRequest): Promise<RecipeResult> {
    const response = await api.post('/recipes/suggest', req)
    return response.data
  },
  async getRecipe(id: number): Promise<RecipeSuggestion> {
    const response = await api.get(`/recipes/${id}`)
    return response.data
  },
  async listStaples(dietary?: string): Promise<Staple[]> {
    const response = await api.get('/staples/', { params: dietary ? { dietary } : undefined })
    return response.data
  },
  async getTemplates(): Promise<AssemblyTemplateOut[]> {
    const response = await api.get('/recipes/templates')
    return response.data
  },
  async getRoleCandidates(
    templateId: string,
    role: string,
    priorPicks: string[] = [],
  ): Promise<RoleCandidatesResponse> {
    const response = await api.get('/recipes/template-candidates', {
      params: {
        template_id: templateId,
        role,
        prior_picks: priorPicks.join(','),
      },
    })
    return response.data
  },
  async buildRecipe(req: BuildRequest): Promise<RecipeSuggestion> {
    const response = await api.post('/recipes/build', req)
    return response.data
  },
}

// ========== Settings API ==========

export const settingsAPI = {
  async getSetting(key: string): Promise<string | null> {
    try {
      const response = await api.get(`/settings/${key}`)
      return response.data.value
    } catch {
      return null
    }
  },
  async setSetting(key: string, value: string): Promise<void> {
    await api.put(`/settings/${key}`, { value })
  },
}

// ========== Household Types ==========

export interface HouseholdMember {
  user_id: string
  joined_at: string
  is_owner: boolean
}

export interface HouseholdStatus {
  in_household: boolean
  household_id: string | null
  is_owner: boolean
  members: HouseholdMember[]
  max_seats: number
}

export interface HouseholdInvite {
  invite_url: string
  token: string
  expires_at: string
}

// ========== Household API ==========

export const householdAPI = {
  async create(): Promise<{ household_id: string; message: string }> {
    const response = await api.post('/household/create')
    return response.data
  },
  async status(): Promise<HouseholdStatus> {
    const response = await api.get('/household/status')
    return response.data
  },
  async invite(): Promise<HouseholdInvite> {
    const response = await api.post('/household/invite')
    return response.data
  },
  async accept(householdId: string, token: string): Promise<{ message: string; household_id: string }> {
    const response = await api.post('/household/accept', { household_id: householdId, token })
    return response.data
  },
  async leave(): Promise<{ message: string }> {
    const response = await api.post('/household/leave')
    return response.data
  },
  async removeMember(userId: string): Promise<{ message: string }> {
    const response = await api.post('/household/remove-member', { user_id: userId })
    return response.data
  },
}

// ========== Saved Recipes Types ==========

export interface SavedRecipe {
  id: number
  recipe_id: number
  title: string
  saved_at: string
  notes: string | null
  rating: number | null
  style_tags: string[]
  collection_ids: number[]
}

export interface RecipeCollection {
  id: number
  name: string
  description: string | null
  member_count: number
  created_at: string
}

// ========== Saved Recipes API ==========

export const savedRecipesAPI = {
  async save(recipe_id: number, notes?: string, rating?: number): Promise<SavedRecipe> {
    const response = await api.post('/recipes/saved', { recipe_id, notes, rating })
    return response.data
  },
  async unsave(recipe_id: number): Promise<void> {
    await api.delete(`/recipes/saved/${recipe_id}`)
  },
  async update(recipe_id: number, data: { notes?: string | null; rating?: number | null; style_tags?: string[] }): Promise<SavedRecipe> {
    const response = await api.patch(`/recipes/saved/${recipe_id}`, data)
    return response.data
  },
  async list(params?: { sort_by?: string; collection_id?: number }): Promise<SavedRecipe[]> {
    const response = await api.get('/recipes/saved', { params })
    return response.data
  },
  async listCollections(): Promise<RecipeCollection[]> {
    const response = await api.get('/recipes/saved/collections')
    return response.data
  },
  async createCollection(name: string, description?: string): Promise<RecipeCollection> {
    const response = await api.post('/recipes/saved/collections', { name, description })
    return response.data
  },
  async deleteCollection(id: number): Promise<void> {
    await api.delete(`/recipes/saved/collections/${id}`)
  },
  async addToCollection(collection_id: number, saved_recipe_id: number): Promise<void> {
    await api.post(`/recipes/saved/collections/${collection_id}/members`, { saved_recipe_id })
  },
  async removeFromCollection(collection_id: number, saved_recipe_id: number): Promise<void> {
    await api.delete(`/recipes/saved/collections/${collection_id}/members/${saved_recipe_id}`)
  },
}

// ========== Browser Types ==========

export interface BrowserDomain {
  id: string
  label: string
}

export interface BrowserCategory {
  category: string
  recipe_count: number
}

export interface BrowserRecipe {
  id: number
  title: string
  category: string | null
  match_pct: number | null
}

export interface BrowserResult {
  recipes: BrowserRecipe[]
  total: number
  page: number
}

// ========== Browser API ==========

export const browserAPI = {
  async listDomains(): Promise<BrowserDomain[]> {
    const response = await api.get('/recipes/browse/domains')
    return response.data
  },
  async listCategories(domain: string): Promise<BrowserCategory[]> {
    const response = await api.get(`/recipes/browse/${domain}`)
    return response.data
  },
  async browse(domain: string, category: string, params?: {
    page?: number
    page_size?: number
    pantry_items?: string
  }): Promise<BrowserResult> {
    const response = await api.get(`/recipes/browse/${domain}/${encodeURIComponent(category)}`, { params })
    return response.data
  },
}

export default api

export interface Property {
  id: number
  address: string
  owner_name: string
  tenant_url_slug: string | null
  access_notes: string | null
}

export interface Job {
  id: number
  property_id: number
  description: string
  cost: number
  status: 'pending' | 'scheduled' | 'completed'
  work_order_id: number | null
  created_at: string
  completed_at: string | null
}

export interface Payment {
  id: number
  amount: number
  date: string
  note: string
  created_at: string
}

export interface WorkOrder {
  id: number
  property_id: number
  description: string
  urgency: 'low' | 'medium' | 'high'
  photo_path: string | null
  status: 'submitted' | 'approved' | 'denied'
  submitted_at: string
  resolved_at: string | null
}

export interface DashboardData {
  completed: string[][]
  scheduled: string[][]
  pending: string[][]
  payments: string[][]
}

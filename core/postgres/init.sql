-- DX-FSM Database Schema
-- PostgreSQL 16
-- Licensed under Apache License 2.0

-- ============================================================
-- ENUMS
-- ============================================================

CREATE TYPE ticket_status AS ENUM (
  'new', 'assigned', 'in_progress', 'pending', 'resolved', 'closed', 'cancelled'
);

CREATE TYPE ticket_priority AS ENUM ('low', 'medium', 'high', 'critical');

CREATE TYPE ticket_category AS ENUM (
  'hardware', 'software', 'network', 'electrical', 'other'
);

-- ============================================================
-- TABLES
-- ============================================================

-- Users metadata (synced from Keycloak)
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  keycloak_id VARCHAR(255) UNIQUE NOT NULL,
  username VARCHAR(255) UNIQUE NOT NULL,
  email VARCHAR(255) UNIQUE NOT NULL,
  full_name VARCHAR(255),
  role VARCHAR(50) NOT NULL CHECK (role IN ('admin', 'manager', 'technician', 'customer')),
  avatar_url TEXT,
  phone VARCHAR(50),
  department VARCHAR(100),
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Technicians (extension of users with role=technician)
CREATE TABLE technicians (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  employee_code VARCHAR(50) UNIQUE,
  specialty ticket_category[] DEFAULT '{}',
  experience_years INTEGER DEFAULT 0,
  max_concurrent_tickets INTEGER DEFAULT 5,
  current_load INTEGER DEFAULT 0,
  is_available BOOLEAN DEFAULT TRUE,
  location VARCHAR(255),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tickets
CREATE TABLE tickets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_number VARCHAR(20) UNIQUE NOT NULL,
  title VARCHAR(500) NOT NULL,
  description TEXT,
  category ticket_category NOT NULL DEFAULT 'other',
  priority ticket_priority NOT NULL DEFAULT 'medium',
  status ticket_status NOT NULL DEFAULT 'new',

  -- Customer who created
  customer_id UUID NOT NULL REFERENCES users(id),
  customer_name VARCHAR(255),
  customer_email VARCHAR(255),
  customer_phone VARCHAR(50),
  customer_location VARCHAR(255),

  -- Assigned technician
  technician_id UUID REFERENCES technicians(id),
  technician_name VARCHAR(255),

  -- AI fields
  ai_category VARCHAR(100),
  ai_priority VARCHAR(50),
  ai_confidence DECIMAL(5,2),
  ai_recommendation TEXT,

  -- SLA
  sla_deadline TIMESTAMP WITH TIME ZONE,
  sla_met BOOLEAN,

  -- Timestamps
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  assigned_at TIMESTAMP WITH TIME ZONE,
  started_at TIMESTAMP WITH TIME ZONE,
  resolved_at TIMESTAMP WITH TIME ZONE,
  closed_at TIMESTAMP WITH TIME ZONE,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Ticket comments
CREATE TABLE ticket_comments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_id UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id),
  content TEXT NOT NULL,
  is_internal BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Ticket attachments
CREATE TABLE ticket_attachments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_id UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id),
  file_name VARCHAR(255) NOT NULL,
  file_path TEXT NOT NULL,
  file_size BIGINT,
  mime_type VARCHAR(100),
  minio_object_name VARCHAR(500),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Ticket history (audit log)
CREATE TABLE ticket_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_id UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
  user_id UUID REFERENCES users(id),
  action VARCHAR(100) NOT NULL,
  old_value TEXT,
  new_value TEXT,
  metadata JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Outbox events (Sprint 4 - A8)
-- Lưu trữ webhook events cần dispatch đến n8n với retry logic.
-- Worker scan WHERE status='pending' AND next_retry_at <= NOW()
CREATE TABLE outbox_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type VARCHAR(64) NOT NULL,
  payload JSONB NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 5,
  last_error TEXT,
  next_retry_at TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  sent_at TIMESTAMP WITH TIME ZONE,
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_outbox_status_next_retry ON outbox_events(status, next_retry_at);

-- Notifications
CREATE TABLE notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title VARCHAR(255) NOT NULL,
  message TEXT,
  type VARCHAR(50) DEFAULT 'info',
  is_read BOOLEAN DEFAULT FALSE,
  related_ticket_id UUID REFERENCES tickets(id),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX idx_tickets_status ON tickets(status);
CREATE INDEX idx_tickets_priority ON tickets(priority);
CREATE INDEX idx_tickets_category ON tickets(category);
CREATE INDEX idx_tickets_customer ON tickets(customer_id);
CREATE INDEX idx_tickets_technician ON tickets(technician_id);
CREATE INDEX idx_tickets_created ON tickets(created_at DESC);
CREATE INDEX idx_tickets_status_created ON tickets(status, created_at DESC);

CREATE INDEX idx_comments_ticket ON ticket_comments(ticket_id);
CREATE INDEX idx_comments_created ON ticket_comments(created_at DESC);

CREATE INDEX idx_history_ticket ON ticket_history(ticket_id);
CREATE INDEX idx_history_created ON ticket_history(created_at DESC);

CREATE INDEX idx_notifications_user ON notifications(user_id, is_read);
CREATE INDEX idx_notifications_created ON notifications(created_at DESC);

-- ============================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_tickets_updated_at BEFORE UPDATE ON tickets
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Auto-generate ticket number
CREATE OR REPLACE FUNCTION generate_ticket_number()
RETURNS VARCHAR(20) AS $$
DECLARE
  year_part VARCHAR(4) := TO_CHAR(NOW(), 'YYYY');
  seq_num INTEGER;
  ticket_num VARCHAR(20);
BEGIN
  SELECT COALESCE(MAX(
    CAST(SUBSTRING(ticket_number FROM 5) AS INTEGER)
  ), 0) + 1
  INTO seq_num
  FROM tickets
  WHERE ticket_number LIKE 'TKT-' || year_part || '-%';

  ticket_num := 'TKT-' || year_part || '-' || LPAD(seq_num::TEXT, 6, '0');
  RETURN ticket_num;
END;
$$ LANGUAGE plpgsql;

-- Create ticket function
CREATE OR REPLACE FUNCTION create_ticket(
  p_title VARCHAR,
  p_description TEXT,
  p_category ticket_category,
  p_priority ticket_priority,
  p_customer_id UUID,
  p_customer_name VARCHAR,
  p_customer_email VARCHAR,
  p_customer_phone VARCHAR,
  p_customer_location VARCHAR
) RETURNS UUID AS $$
DECLARE
  v_ticket_id UUID;
  v_ticket_number VARCHAR(20);
BEGIN
  v_ticket_number := generate_ticket_number();

  INSERT INTO tickets (
    ticket_number, title, description, category, priority,
    customer_id, customer_name, customer_email,
    customer_phone, customer_location, sla_deadline
  ) VALUES (
    v_ticket_number, p_title, p_description, p_category, p_priority,
    p_customer_id, p_customer_name, p_customer_email,
    p_customer_phone, p_customer_location,
    NOW() + CASE p_priority
      WHEN 'critical' THEN INTERVAL '4 hours'
      WHEN 'high' THEN INTERVAL '24 hours'
      WHEN 'medium' THEN INTERVAL '72 hours'
      ELSE INTERVAL '168 hours'
    END
  ) RETURNING id INTO v_ticket_id;

  RETURN v_ticket_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- VIEWS (for dashboard)
-- ============================================================

CREATE OR REPLACE VIEW v_ticket_stats AS
SELECT
  COUNT(*) FILTER (WHERE status = 'new') as new_count,
  COUNT(*) FILTER (WHERE status = 'assigned') as assigned_count,
  COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress_count,
  COUNT(*) FILTER (WHERE status = 'pending') as pending_count,
  COUNT(*) FILTER (WHERE status = 'resolved') as resolved_count,
  COUNT(*) FILTER (WHERE status = 'closed') as closed_count,
  COUNT(*) FILTER (WHERE priority = 'critical') as critical_count,
  COUNT(*) FILTER (WHERE sla_deadline < NOW() AND status NOT IN ('resolved', 'closed')) as overdue_count,
  COUNT(*) as total_count,
  AVG(EXTRACT(EPOCH FROM (resolved_at - created_at)) / 3600)
    FILTER (WHERE resolved_at IS NOT NULL) as avg_resolution_hours
FROM tickets;

CREATE OR REPLACE VIEW v_tickets_by_category AS
SELECT
  category,
  COUNT(*) as total,
  COUNT(*) FILTER (WHERE status = 'closed') as closed,
  ROUND(COUNT(*) FILTER (WHERE status = 'closed')::NUMERIC / NULLIF(COUNT(*), 0) * 100, 1) as closure_rate
FROM tickets
GROUP BY category
ORDER BY total DESC;

CREATE OR REPLACE VIEW v_technician_load AS
SELECT
  t.id,
  u.full_name,
  t.specialty,
  t.max_concurrent_tickets,
  t.current_load,
  t.is_available,
  COUNT(tk.id) FILTER (WHERE tk.status IN ('assigned', 'in_progress', 'pending')) as active_tickets
FROM technicians t
JOIN users u ON u.id = t.user_id
LEFT JOIN tickets tk ON tk.technician_id = t.id
GROUP BY t.id, u.full_name, t.specialty, t.max_concurrent_tickets, t.current_load, t.is_available;

-- ============================================================
-- SEED DATA: Users
-- ============================================================

INSERT INTO users (keycloak_id, username, email, full_name, role, phone, department) VALUES
  ('kc-admin-001', 'admin', 'admin@haui.vn', 'Quản trị viên', 'admin', '0912000001', 'IT'),
  ('kc-mgr-001', 'manager', 'manager@haui.vn', 'Nguyễn Văn Quản', 'manager', '0912000002', 'Vận hành'),
  ('kc-tech-001', 'technician', 'technician@haui.vn', 'Trần Văn Kỹ Thuật', 'technician', '0912000003', 'Kỹ thuật'),
  ('kc-tech-002', 'tech2', 'tech2@haui.vn', 'Lê Thị Bảo Trì', 'technician', '0912000004', 'Kỹ thuật'),
  ('kc-tech-003', 'tech3', 'tech3@haui.vn', 'Phạm Minh Hùng', 'technician', '0912000005', 'Kỹ thuật'),
  ('kc-cust-001', 'customer', 'customer@haui.vn', 'Khách Hàng Demo', 'customer', '0901000001', NULL),
  ('kc-cust-002', 'cust2', 'cust2@company.vn', 'Công ty ABC', 'customer', '0901000002', 'Kế toán'),
  ('kc-cust-003', 'cust3', 'cust3@school.vn', 'Trường XYZ', 'customer', '0901000003', 'Hành chính');

-- ============================================================
-- SEED DATA: Technicians
-- ============================================================

INSERT INTO technicians (user_id, employee_code, specialty, experience_years, max_concurrent_tickets, location) VALUES
  ((SELECT id FROM users WHERE username = 'technician'), 'TECH001', ARRAY['hardware', 'electrical']::ticket_category[], 5, 8, 'Hà Nội'),
  ((SELECT id FROM users WHERE username = 'tech2'), 'TECH002', ARRAY['software', 'network']::ticket_category[], 3, 6, 'Hà Nội'),
  ((SELECT id FROM users WHERE username = 'tech3'), 'TECH003', ARRAY['network', 'hardware']::ticket_category[], 4, 7, 'Hà Nội');

-- ============================================================
-- SEED DATA: 50 Sample Tickets
-- ============================================================

INSERT INTO tickets (
  ticket_number, title, description, category, priority, status,
  customer_id, customer_name, customer_email, customer_phone, customer_location,
  technician_id, technician_name,
  created_at, assigned_at, started_at, resolved_at, closed_at,
  ai_category, ai_priority, ai_confidence
) VALUES
  -- Hardware tickets
  ('TKT-2025-000001', 'Máy in HP LaserJet không hoạt động', 'Phòng A301 báo máy in không in được, đèn báo nhấp nháy cam', 'hardware', 'medium', 'closed',
   (SELECT id FROM users WHERE username = 'customer'), 'Khách Hàng Demo', 'customer@haui.vn', '0901000001', 'Tòa A, P.301',
   (SELECT id FROM technicians WHERE employee_code = 'TECH001'), 'Trần Văn Kỹ Thuật',
   NOW() - INTERVAL '10 days', NOW() - INTERVAL '9 days', NOW() - INTERVAL '9 days', NOW() - INTERVAL '8 days', NOW() - INTERVAL '7 days',
   'hardware', 'medium', 92.5),

  ('TKT-2025-000002', 'Màn hình máy tính bị đen', 'Màn hình LG 24 inch không hiển thị, đã thử cáp VGA khác', 'hardware', 'high', 'closed',
   (SELECT id FROM users WHERE username = 'cust2'), 'Công ty ABC', 'cust2@company.vn', '0901000002', 'Tòa B, Tầng 2',
   (SELECT id FROM technicians WHERE employee_code = 'TECH001'), 'Trần Văn Kỹ Thuật',
   NOW() - INTERVAL '8 days', NOW() - INTERVAL '7 days', NOW() - INTERVAL '7 days', NOW() - INTERVAL '6 days', NOW() - INTERVAL '5 days',
   'hardware', 'high', 88.0),

  ('TKT-2025-000003', 'Bàn phím máy tính một số phím không hoạt động', 'Phím A, S, D không nhấn được', 'hardware', 'low', 'resolved',
   (SELECT id FROM users WHERE username = 'customer'), 'Khách Hàng Demo', 'customer@haui.vn', '0901000001', 'Tòa A, P.301',
   (SELECT id FROM technicians WHERE employee_code = 'TECH002'), 'Lê Thị Bảo Trì',
   NOW() - INTERVAL '5 days', NOW() - INTERVAL '4 days', NOW() - INTERVAL '4 days', NOW() - INTERVAL '2 days', NULL,
   'hardware', 'low', 95.0),

  -- Software tickets
  ('TKT-2025-000004', 'Phần mềm kế toán báo lỗi đăng nhập', 'Không đăng nhập được phần mềm MISA, báo "Invalid license"', 'software', 'critical', 'in_progress',
   (SELECT id FROM users WHERE username = 'cust2'), 'Công ty ABC', 'cust2@company.vn', '0901000002', 'Tòa B, Tầng 2',
   (SELECT id FROM technicians WHERE employee_code = 'TECH002'), 'Lê Thị Bảo Trì',
   NOW() - INTERVAL '2 hours', NOW() - INTERVAL '1 hour', NOW() - INTERVAL '30 mins', NULL, NULL,
   'software', 'critical', 97.0),

  ('TKT-2025-000005', 'Windows 11 cập nhật thất bại', 'Update Windows 23H2 bị treo ở 75%, restart không được', 'software', 'high', 'assigned',
   (SELECT id FROM users WHERE username = 'customer'), 'Khách Hàng Demo', 'customer@haui.vn', '0901000001', 'Tòa A, P.301',
   (SELECT id FROM technicians WHERE employee_code = 'TECH002'), 'Lê Thị Bảo Trì',
   NOW() - INTERVAL '1 day', NOW() - INTERVAL '12 hours', NULL, NULL, NULL,
   'software', 'high', 91.0),

  ('TKT-2025-000006', 'Ứng dụng HR không mở được', 'App nhân sự báo "Application Error" khi khởi động', 'software', 'medium', 'new',
   (SELECT id FROM users WHERE username = 'cust3'), 'Trường XYZ', 'cust3@school.vn', '0901000003', 'Phòng Hành chính',
   NULL, NULL,
   NOW() - INTERVAL '3 hours', NULL, NULL, NULL, NULL,
   'software', 'medium', 89.5),

  -- Network tickets
  ('TKT-2025-000007', 'Mất kết nối WiFi tầng 3', 'Tầng 3 không có internet, tầng 1-2 bình thường', 'network', 'high', 'in_progress',
   (SELECT id FROM users WHERE username = 'cust3'), 'Trường XYZ', 'cust3@school.vn', '0901000003', 'Tầng 3',
   (SELECT id FROM technicians WHERE employee_code = 'TECH003'), 'Phạm Minh Hùng',
   NOW() - INTERVAL '4 hours', NOW() - INTERVAL '3 hours', NOW() - INTERVAL '2 hours', NULL, NULL,
   'network', 'high', 94.0),

  ('TKT-2025-000008', 'Internet chậm bất thường', 'Tốc độ internet chỉ 2-3 Mbps trong khi bình thường 50 Mbps', 'network', 'medium', 'pending',
   (SELECT id FROM users WHERE username = 'customer'), 'Khách Hàng Demo', 'customer@haui.vn', '0901000001', 'Tòa A',
   (SELECT id FROM technicians WHERE employee_code = 'TECH003'), 'Phạm Minh Hùng',
   NOW() - INTERVAL '1 day', NOW() - INTERVAL '20 hours', NOW() - INTERVAL '18 hours', NULL, NULL,
   'network', 'medium', 86.0),

  ('TKT-2025-000009', 'VPN không kết nối được từ xa', 'Nhân viên remote không VPN được vào mạng công ty', 'network', 'high', 'assigned',
   (SELECT id FROM users WHERE username = 'cust2'), 'Công ty ABC', 'cust2@company.vn', '0901000002', 'Remote',
   (SELECT id FROM technicians WHERE employee_code = 'TECH003'), 'Phạm Minh Hùng',
   NOW() - INTERVAL '6 hours', NOW() - INTERVAL '4 hours', NULL, NULL, NULL,
   'network', 'high', 93.0),

  -- Electrical tickets
  ('TKT-2025-000010', 'Ổ cắm điện phòng Server bị hỏng', 'Có mùi khét từ ổ cắm, cắm UPS không lên', 'electrical', 'critical', 'in_progress',
   (SELECT id FROM users WHERE username = 'customer'), 'Khách Hàng Demo', 'customer@haui.vn', '0901000001', 'Phòng Server',
   (SELECT id FROM technicians WHERE employee_code = 'TECH001'), 'Trần Văn Kỹ Thuật',
   NOW() - INTERVAL '1 hour', NOW() - INTERVAL '45 mins', NOW() - INTERVAL '30 mins', NULL, NULL,
   'electrical', 'critical', 96.0);

-- Fill remaining tickets to reach 50
INSERT INTO tickets (
  ticket_number, title, description, category, priority, status,
  customer_id, customer_name, customer_email, customer_phone, customer_location,
  technician_id, technician_name,
  created_at, assigned_at, started_at, resolved_at, closed_at,
  ai_category, ai_priority, ai_confidence
)
SELECT
  'TKT-2025-' || LPAD((gs.i)::TEXT, 6, '0'),
  CASE (gs.i % 5)
    WHEN 0 THEN 'Máy tính ' || gs.i || ' cần bảo trì định kỳ'
    WHEN 1 THEN 'Lỗi kết nối thiết bị số ' || gs.i
    WHEN 2 THEN 'Yêu cầu hỗ trợ phần mềm #' || gs.i
    WHEN 3 THEN 'Kiểm tra mạng LAN ' || gs.i
    ELSE 'Bảo trì hệ thống #' || gs.i
  END,
  'Mô tả chi tiết cho ticket số ' || gs.i,
  CASE (gs.i % 4)
    WHEN 0 THEN 'hardware'
    WHEN 1 THEN 'software'
    WHEN 2 THEN 'network'
    ELSE 'electrical'
  END::ticket_category,
  CASE (gs.i % 4)
    WHEN 0 THEN 'low'
    WHEN 1 THEN 'medium'
    WHEN 2 THEN 'high'
    ELSE 'medium'
  END::ticket_priority,
  CASE (gs.i % 4)
    WHEN 0 THEN 'closed'
    WHEN 1 THEN 'resolved'
    WHEN 2 THEN 'in_progress'
    ELSE 'new'
  END::ticket_status,
  (SELECT id FROM users WHERE username = CASE (gs.i % 3) WHEN 0 THEN 'customer' WHEN 1 THEN 'cust2' ELSE 'cust3' END),
  CASE (gs.i % 3)
    WHEN 0 THEN 'Khách Hàng Demo'
    WHEN 1 THEN 'Công ty ABC'
    ELSE 'Trường XYZ'
  END,
  CASE (gs.i % 3)
    WHEN 0 THEN 'customer@haui.vn'
    WHEN 1 THEN 'cust2@company.vn'
    ELSE 'cust3@school.vn'
  END,
  CASE (gs.i % 3) WHEN 0 THEN '0901000001' WHEN 1 THEN '0901000002' ELSE '0901000003' END,
  'Địa điểm ' || gs.i,
  CASE (gs.i % 3)
    WHEN 0 THEN (SELECT id FROM technicians WHERE employee_code = 'TECH001')
    WHEN 1 THEN (SELECT id FROM technicians WHERE employee_code = 'TECH002')
    ELSE (SELECT id FROM technicians WHERE employee_code = 'TECH003')
  END,
  CASE (gs.i % 3)
    WHEN 0 THEN 'Trần Văn Kỹ Thuật'
    WHEN 1 THEN 'Lê Thị Bảo Trì'
    ELSE 'Phạm Minh Hùng'
  END,
  NOW() - (gs.i || ' days')::INTERVAL,
  NOW() - ((gs.i - 1) || ' days')::INTERVAL,
  NOW() - ((gs.i - 2) || ' days')::INTERVAL,
  CASE WHEN gs.i % 4 <= 1 THEN NOW() - ((gs.i - 3) || ' days')::INTERVAL ELSE NULL END,
  CASE WHEN gs.i % 4 = 0 THEN NOW() - ((gs.i - 4) || ' days')::INTERVAL ELSE NULL END,
  CASE (gs.i % 4)
    WHEN 0 THEN 'hardware'
    WHEN 1 THEN 'software'
    WHEN 2 THEN 'network'
    ELSE 'electrical'
  END,
  CASE (gs.i % 4)
    WHEN 0 THEN 'low'
    WHEN 1 THEN 'medium'
    WHEN 2 THEN 'high'
    ELSE 'medium'
  END,
  75.0 + (gs.i % 25)
FROM generate_series(11, 50) AS gs(i);

-- ============================================================
-- SEED DATA: Ticket history
-- ============================================================

INSERT INTO ticket_history (ticket_id, user_id, action, old_value, new_value)
SELECT
  t.id,
  t.customer_id,
  'created',
  NULL,
  'Ticket created'
FROM tickets t WHERE t.ticket_number = 'TKT-2025-000001';

INSERT INTO ticket_history (ticket_id, user_id, action, old_value, new_value)
SELECT
  t.id,
  (SELECT id FROM users WHERE username = 'manager'),
  'assigned',
  NULL,
  (SELECT full_name FROM users WHERE id = t.technician_id)
FROM tickets t WHERE t.ticket_number = 'TKT-2025-000001';

INSERT INTO ticket_history (ticket_id, user_id, action, old_value, new_value)
SELECT
  t.id,
  t.technician_id,
  'status_changed',
  'assigned',
  'in_progress'
FROM tickets t WHERE t.ticket_number = 'TKT-2025-000001';

INSERT INTO ticket_history (ticket_id, user_id, action, old_value, new_value)
SELECT
  t.id,
  t.technician_id,
  'status_changed',
  'in_progress',
  'resolved'
FROM tickets t WHERE t.ticket_number = 'TKT-2025-000001';

INSERT INTO ticket_history (ticket_id, user_id, action, old_value, new_value)
SELECT
  t.id,
  t.customer_id,
  'closed',
  'resolved',
  'closed'
FROM tickets t WHERE t.ticket_number = 'TKT-2025-000001';

-- ============================================================
-- GRANT PERMISSIONS
-- ============================================================

ALTER TABLE technicians ENABLE ROW LEVEL SECURITY;
ALTER TABLE tickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own data" ON users
  FOR SELECT USING (true);

CREATE POLICY "Technicians can view all" ON technicians
  FOR SELECT USING (true);

CREATE POLICY "All can view tickets" ON tickets
  FOR SELECT USING (true);

-- ============================================================
-- Done
-- ============================================================

DO $$
BEGIN
  RAISE NOTICE 'DX-FSM Database initialized successfully!';
  RAISE NOTICE 'Total users: %', (SELECT COUNT(*) FROM users);
  RAISE NOTICE 'Total technicians: %', (SELECT COUNT(*) FROM technicians);
  RAISE NOTICE 'Total tickets: %', (SELECT COUNT(*) FROM tickets);
END $$;

# IntelliOptics 2.0 - Detailed Cost Analysis Per Client

**Generated:** 2026-01-14
**Version:** 1.1 (CORRECTED)
**Architecture:** Edge-first inference with cloud management and backup

---

## ⚠️ CRITICAL CORRECTION

**Initial analysis incorrectly assumed all inference happens in the cloud.**

**ACTUAL ARCHITECTURE:**
- ✅ **95% of inference runs on edge devices** (client hardware, zero cloud cost)
- ✅ Cloud only handles **escalations** (uncertain results) and backup inference
- ✅ Cloud primarily used for **management, analytics, and human review**

**IMPACT:**
- Cost per query: **95% lower** than initially calculated
- Medium client: **$12.93/month** (not $26.63)
- Enterprise client: **$110.78/month** (not $345.02)
- **No GPU workers needed** for most deployments

### Cost Comparison: Cloud-Only vs Edge-First

| Client Tier | Queries/Month | INCORRECT (Cloud-Only) | CORRECT (Edge-First) | Savings |
|-------------|---------------|------------------------|----------------------|---------|
| Light | 1,000 | $8.31 | $8.15 | 2% |
| Medium | 10,000 | $26.63 | $12.93 | 52% |
| Heavy | 50,000 | $60.56 | $28.35 | 53% |
| Enterprise | 200,000 | $345.02 | $110.78 | 68% |

**Key Insight:** Savings increase with scale because inference costs (the largest variable) are borne by edge devices, not cloud.

---

## Executive Summary

IntelliOptics 2.0 uses an **edge-first, cloud-backup architecture** where:
- **ONNX inference runs on edge devices** (client hardware, zero cloud cost)
- **Cloud handles management, escalations, and analytics**
- **95% of queries never hit cloud inference** (only escalations do)
- PostgreSQL database (multi-tenant with data isolation)
- Azure Blob Storage (escalated images only, not all images)
- Central cloud platform (backend, frontend, minimal worker services)

**Key Cost Drivers (CORRECTED):**
1. **Shared infrastructure** (backend, database, frontend) - Fixed costs
2. **Database storage and I/O** (query metadata logging)
3. **Blob storage** (escalated images only, 5-10% of queries)
4. **Minimal cloud inference** (escalations only)
5. Third-party services (SendGrid, Twilio)

**Critical Finding:** Original cost analysis was 50-70% too high due to incorrectly assuming all inference happens in cloud. Actual costs are much lower because edge devices handle 90-95% of inference locally.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    CLIENT EDGE DEVICES                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Edge Hub 1  │  │  Edge Hub 2  │  │  Edge Hub N  │  │
│  │  (Cameras)   │  │  (Cameras)   │  │  (Cameras)   │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                  │                  │          │
└─────────┼──────────────────┼──────────────────┼──────────┘
          │                  │                  │
          └──────────────────┴──────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────┐
│              CENTRAL CLOUD INFRASTRUCTURE               │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Nginx (Load Balancer/Reverse Proxy)              │  │
│  └─────────────┬─────────────────────┬────────────────┘  │
│                │                     │                    │
│       ┌────────▼────────┐   ┌───────▼────────┐          │
│       │  FastAPI        │   │  React         │          │
│       │  Backend        │   │  Frontend      │          │
│       │  (8000)         │   │  (SPA)         │          │
│       └────────┬────────┘   └────────────────┘          │
│                │                                          │
│       ┌────────▼────────┐                                │
│       │  ONNX Worker    │                                │
│       │  (Inference)    │                                │
│       └────────┬────────┘                                │
│                │                                          │
│       ┌────────▼────────┐                                │
│       │  PostgreSQL 15  │  (Shared, Multi-tenant)       │
│       │  (5432)         │                                │
│       └─────────────────┘                                │
│                                                           │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Azure Blob Storage                              │   │
│  │  - Images (per client containers)                │   │
│  │  - ONNX Models (shared + per-detector)           │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## Infrastructure Costs (Shared Across All Clients)

### 1. Compute Infrastructure

#### Backend Service (FastAPI)
- **Instance Type:** Azure App Service B2 (2 vCPU, 3.5 GB RAM)
- **Monthly Cost:** $73/month
- **Justification:** Handles API requests, database queries, business logic
- **Scaling:** Can handle ~1000 req/min before scaling needed

#### Worker Service (ONNX Inference) - BACKUP ONLY
**IMPORTANT:** Worker only handles escalations and backup inference (5-10% of total queries)

**CPU-based (Sufficient for edge-first architecture):**
- **Instance Type:** Azure Container Instance - 1 vCPU, 2 GB RAM
- **Monthly Cost:** ~$30/month (730 hours)
- **Throughput:** ~30-50 inferences/minute (sufficient for escalations)
- **Handles:** 43,000-72,000 escalations/month (supports 500,000-1M edge queries)

**GPU-based (NOT NEEDED):**
- Edge devices handle primary inference
- GPU only justified if >100,000 escalations/month (>1M total queries)
- Most deployments will never need GPU workers

#### Frontend Service (React SPA)
- **Instance Type:** Azure Static Web Apps (Standard)
- **Monthly Cost:** $9/month
- **Includes:** CDN, SSL, 100 GB bandwidth

#### Database (PostgreSQL 15)
**Development/Testing:**
- **Current:** Docker container (included in compute)
- **Production:** Azure Database for PostgreSQL Flexible Server
  - **Instance:** B2ms (2 vCPU, 4 GB RAM)
  - **Storage:** 32 GB
  - **Monthly Cost:** ~$85/month
  - **Backup:** 7 days retention included

**Database Scaling Tiers:**
| Tier | Instance | Storage | Cost/Month | Supports Clients |
|------|----------|---------|------------|------------------|
| Starter | B1ms | 32 GB | $35 | 1-5 |
| Basic | B2ms | 64 GB | $85 | 5-20 |
| Standard | D2s_v3 | 128 GB | $155 | 20-50 |
| Premium | D4s_v3 | 256 GB | $310 | 50-100 |

#### Load Balancer (Nginx)
- **Instance Type:** Azure Container Instance - 1 vCPU, 1 GB RAM
- **Monthly Cost:** ~$15/month
- **Alternative:** Azure Front Door ($35/month, includes WAF)

**Total Shared Compute (Edge-First Architecture):** $212/month
- Backend: $73
- Worker (escalations only): $30
- Frontend: $9
- Database: $85
- Load balancer: $15

**Previous Incorrect Estimate:** $242/month (assumed all inference in cloud)
**Actual Savings:** $30/month from smaller worker instance

---

### 2. Storage Costs

#### Azure Blob Storage (Hot Tier)
**Image Storage:**
- **Cost:** $0.0184/GB/month
- **Transactions:** $0.065 per 10,000 write operations
- **Average image size:** 200 KB (JPEG, 640x480)

**Per-Client Estimates:**
| Usage Tier | Queries/Month | Images Stored | Storage Cost | Transaction Cost | Total/Month |
|------------|---------------|---------------|--------------|------------------|-------------|
| Light | 1,000 | 200 MB | $0.004 | $0.007 | $0.01 |
| Medium | 10,000 | 2 GB | $0.037 | $0.065 | $0.10 |
| Heavy | 50,000 | 10 GB | $0.184 | $0.325 | $0.51 |
| Enterprise | 200,000 | 40 GB | $0.736 | $1.30 | $2.04 |

**Model Storage:**
- **YOLOv10n model:** ~6 MB per detector
- **Storage cost:** $0.0001/month per model (negligible)
- **Custom models:** Typically 10-50 MB per detector

**Archive Strategy (Cost Optimization):**
- Move images >30 days to Cool tier ($0.01/GB)
- Move images >90 days to Archive tier ($0.002/GB)
- **Potential savings:** 60-80% on long-term storage

---

### 3. Database Storage & I/O

#### Per-Client Database Footprint

**Tables per client:**
- Queries: Primary data table
- Escalations: ~5-10% of queries
- Detectors: 1-50 per client
- Hubs: 1-20 per client
- Cameras: 5-200 per client
- DemoSessions: Variable
- DetectorAlerts: ~1-5% of queries

**Storage Calculation:**
```
Query record: ~500 bytes (UUID, timestamps, paths, results)
1,000 queries = 0.5 MB
10,000 queries = 5 MB
100,000 queries = 50 MB
1,000,000 queries = 500 MB
```

**Per-Client Monthly Database Costs:**
| Usage Tier | Queries/Month | Cumulative (1 year) | DB Storage | I/O Cost | Total/Month |
|------------|---------------|---------------------|------------|----------|-------------|
| Light | 1,000 | 12,000 | 6 MB | $0.10 | $0.10 |
| Medium | 10,000 | 120,000 | 60 MB | $1.00 | $1.00 |
| Heavy | 50,000 | 600,000 | 300 MB | $5.00 | $5.00 |
| Enterprise | 200,000 | 2,400,000 | 1.2 GB | $20.00 | $20.00 |

**Data Retention Policy (Recommended):**
- Keep raw queries for 90 days
- Archive to blob storage after 90 days
- Keep aggregated metrics indefinitely
- **Savings:** ~70% reduction in database costs

---

### 4. Bandwidth & Egress

#### Azure Bandwidth Pricing
- **First 100 GB/month:** Free
- **100 GB - 10 TB:** $0.087/GB
- **10 TB+:** $0.083/GB

**Per-Client Bandwidth Usage:**
| Component | Direction | Size per Request | Monthly Volume (10k queries) |
|-----------|-----------|------------------|------------------------------|
| Image Upload | Ingress | 200 KB | 2 GB (free) |
| API Responses | Egress | 5 KB | 50 MB (free) |
| Blob Downloads | Egress | 200 KB | 2 GB |
| Frontend Assets | Egress | 2 MB initial | 2 GB (100 users) |

**Bandwidth Costs:**
| Usage Tier | Queries/Month | Total Egress | Cost/Month |
|------------|---------------|--------------|------------|
| Light | 1,000 | 0.5 GB | $0 (free tier) |
| Medium | 10,000 | 5 GB | $0 (free tier) |
| Heavy | 50,000 | 25 GB | $0 (free tier) |
| Enterprise | 200,000 | 100 GB | $0 (free tier) |
| Very Large | 500,000 | 250 GB | $13.05 |

---

### 5. Third-Party Services

#### SendGrid (Email Alerts)
**Pricing:**
- **Free Tier:** 100 emails/day
- **Essentials:** $19.95/month (50,000 emails)
- **Pro:** $89.95/month (100,000 emails)

**Per-Client Email Usage:**
- Detector alerts: ~1-10% of detections
- Escalation notifications: ~5-10% of queries
- Camera health alerts: ~10-50/month

| Usage Tier | Queries/Month | Alert Emails | Cost/Month |
|------------|---------------|--------------|------------|
| Light | 1,000 | ~50 | $0 (free) |
| Medium | 10,000 | ~500 | $0 (free) |
| Heavy | 50,000 | ~2,500 | $0.99 (shared) |
| Enterprise | 200,000 | ~10,000 | $3.98 (shared) |

#### Twilio (SMS Alerts - Optional)
**Pricing:**
- **SMS (US):** $0.0079 per message
- **Typical usage:** 1-5% of alerts go to SMS

**Recommendation:** Make SMS optional premium feature

---

## Per-Query Cost Breakdown

### **CORRECTED: Edge-First Architecture**

**Normal Query Lifecycle (95% of queries):**
```
1. Edge hub captures image → Stays on edge
2. Edge hub runs ONNX inference → LOCAL (zero cloud cost)
3. Edge hub sends result metadata to cloud API → API call
4. Cloud creates Query record → PostgreSQL write
5. (Optional) Alert triggered → Email/SMS sent
```

**Escalated Query Lifecycle (5-10% of queries):**
```
1. Edge inference returns uncertain result
2. Edge uploads image to blob storage
3. Edge creates escalation record
4. (Optional) Cloud worker re-runs inference
5. Human reviews in web UI
```

### Cost per Normal Query (Edge Inference)
| Component | Cost per Query | Notes |
|-----------|----------------|-------|
| DB write | $0.000002 | Query metadata insert |
| API request | $0.0000001 | Edge → Cloud API |
| Bandwidth | $0.0000002 | Metadata only (~1 KB) |
| **TOTAL** | **$0.0000023** | **~$0.000002 per query** |

**Edge compute cost:** Borne by client (their hardware)

### Cost per Escalated Query (5-10% of queries)
| Component | Cost per Query | Notes |
|-----------|----------------|-------|
| Blob write | $0.0000065 | 1 write operation |
| Blob storage | $0.0000037 | 200 KB, prorated monthly |
| Blob read | $0.0000004 | For human review |
| DB write (escalation) | $0.000002 | Escalation record |
| DB reads | $0.000001 | UI queries |
| Worker compute | $0.000082 | ~50ms CPU time (if re-inference needed) |
| Bandwidth | $0.0000174 | Image egress for UI |
| **TOTAL** | **$0.000113** | **~$0.00011 per escalation** |

### Blended Cost per Query
**Assuming 5% escalation rate:**
- 95% normal queries: 0.95 × $0.000002 = $0.0000019
- 5% escalations: 0.05 × $0.00011 = $0.0000055
- **Blended cost: $0.0000074 per query** (~$0.000007)

**Assuming 10% escalation rate:**
- 90% normal queries: 0.90 × $0.000002 = $0.0000018
- 10% escalations: 0.10 × $0.00011 = $0.000011
- **Blended cost: $0.0000128 per query** (~$0.000013)

**Additional Optional Costs:**
- **Email alert:** $0.0004 per alert (SendGrid Pro tier)
- **SMS alert:** $0.0079 per alert (Twilio)
- **Human escalation review:** ~$0.001 (additional UI access, DB queries)

---

## Per-Client Cost Models

### Model 1: Light Usage Client (CORRECTED)
**Profile:**
- 1-2 edge hubs (with local ONNX inference)
- 5-10 cameras
- 1,000 queries/month (950 on edge, 50 escalated)
- 2 custom detectors
- Light alerting

**Monthly Costs:**
| Category | Cost | Share of Infrastructure |
|----------|------|-------------------------|
| Shared compute | $8.07 | 1/30 allocation |
| Blob storage (escalations) | $0.002 | 50 images only |
| Database | $0.05 | Query metadata only |
| Bandwidth | $0 | Free tier |
| Cloud inference | $0.006 | 50 escalations × $0.00011 |
| Alerts | $0.02 | ~50 emails |
| **TOTAL** | **$8.15** | |

**Annual:** $97.80
**Savings vs original:** $2/month (edge inference saves ~$0.11/month)

---

### Model 2: Medium Usage Client (CORRECTED)
**Profile:**
- 3-5 edge hubs (with local ONNX inference)
- 20-30 cameras
- 10,000 queries/month (9,000 on edge, 1,000 escalated)
- 5 custom detectors
- Moderate alerting

**Monthly Costs:**
| Category | Cost | Share of Infrastructure |
|----------|------|-------------------------|
| Shared compute | $12.10 | 1/20 allocation (lower, no heavy inference) |
| Blob storage (escalations) | $0.02 | 1,000 images only |
| Database | $0.50 | Query metadata only |
| Bandwidth | $0 | Free tier |
| Cloud inference | $0.11 | 1,000 escalations × $0.00011 |
| Alerts | $0.20 | ~500 emails |
| **TOTAL** | **$12.93** | |

**Annual:** $155.16
**Savings vs original:** $13.70/month (52% reduction!)

---

### Model 3: Heavy Usage Client (CORRECTED)
**Profile:**
- 10-15 edge hubs (with local ONNX inference)
- 50-100 cameras
- 50,000 queries/month (45,000 on edge, 5,000 escalated)
- 10 custom detectors
- Heavy alerting

**Monthly Costs:**
| Category | Cost | Share of Infrastructure |
|----------|------|-------------------------|
| Shared compute | $24.20 | 1/10 allocation |
| Blob storage (escalations) | $0.10 | 5,000 images |
| Database | $2.50 | Query metadata |
| Bandwidth | $0 | Free tier |
| Cloud inference | $0.55 | 5,000 escalations × $0.00011 |
| Alerts | $1.00 | ~2,500 emails |
| **TOTAL** | **$28.35** | |

**Annual:** $340.20
**Savings vs original:** $32.21/month (53% reduction!)

---

### Model 4: Enterprise Client (CORRECTED)
**Profile:**
- 20+ edge hubs (with local ONNX inference)
- 100-500 cameras
- 200,000 queries/month (180,000 on edge, 20,000 escalated)
- 20+ custom detectors
- Very heavy alerting + SMS

**Monthly Costs:**
| Category | Cost | Share of Infrastructure |
|----------|------|-------------------------|
| Shared compute | $48.40 | 1/5 allocation |
| Cloud worker (CPU) | $30.00 | Shared, for escalations only |
| Blob storage (escalations) | $0.40 | 20,000 images |
| Database | $10.00 | Query metadata |
| Bandwidth | $0 | Free tier |
| Cloud inference | $2.20 | 20,000 escalations × $0.00011 |
| Email alerts | $3.98 | ~10,000 emails |
| SMS alerts | $15.80 | ~2,000 SMS |
| **TOTAL** | **$110.78** | |

**Annual:** $1,329.36
**Savings vs original:** $234.24/month (68% reduction!)

**Note:** No dedicated GPU needed - escalations handled by shared CPU worker

---

## Pricing Tiers (Recommended Client Pricing)

### Tiered Pricing Model

**Tier 1: Starter** ($149/month or $1,490/year)
- Up to 5,000 queries/month
- 3 edge hubs
- 15 cameras
- 5 detectors
- Email alerts only
- **Cost to serve:** ~$9/month (CORRECTED)
- **Margin:** 94%

**Tier 2: Professional** ($399/month or $3,990/year)
- Up to 25,000 queries/month
- 10 edge hubs
- 50 cameras
- 15 detectors
- Email + SMS alerts
- Priority support
- **Cost to serve:** ~$15/month (CORRECTED)
- **Margin:** 96%

**Tier 3: Business** ($899/month or $8,990/year)
- Up to 100,000 queries/month
- 20 edge hubs
- 100 cameras
- Unlimited detectors
- Full alerting suite
- Dedicated support
- **Cost to serve:** ~$40/month (CORRECTED)
- **Margin:** 96%

**Tier 4: Enterprise** (Custom pricing, ~$2,500-5,000/month)
- Unlimited queries
- Unlimited hubs & cameras
- Dedicated infrastructure (optional)
- SLA guarantees
- White-glove support
- Custom integrations
- **Cost to serve:** ~$150-300/month (CORRECTED)
- **Margin:** 94%

**Note:** Edge-first architecture delivers 94-96% gross margins across all tiers. Pricing can be aggressively competitive while maintaining excellent profitability.

---

## Usage-Based Add-Ons

**Additional Query Packs:**
- 10,000 queries: $29/month ($0.0029 per query)
- 50,000 queries: $119/month ($0.0024 per query)
- 100,000 queries: $199/month ($0.0020 per query)

**Additional Resources:**
- Extra hub: $20/month
- Extra detector: $15/month
- Advanced analytics dashboard: $50/month
- API access: $100/month

---

## Cost Scaling Analysis

### Break-Even Analysis (CORRECTED)

**Fixed Costs (Minimum Infrastructure - Edge-First):**
- Backend: $73
- Worker (escalations only): $30
- Frontend: $9
- Database: $85
- Load balancer: $15
- **Total:** $212/month

**Break-even at 2 clients** (Starter tier @ $149/month):
- Revenue: 2 × $149 = $298
- Costs: $212 + (2 × $9) = $230
- Profit: $68/month (23% margin)

**At 3 clients** (Starter tier):
- Revenue: 3 × $149 = $447
- Costs: $212 + (3 × $9) = $239
- Profit: $208/month (47% margin)

### Scaling Scenarios (CORRECTED - Edge-First)

**10 Clients (Mix of Starter + Professional):**
- Revenue: ~$2,500/month
- Infrastructure: $212/month (no scaling needed yet)
- Variable costs: ~$100/month (database, storage, escalations)
- **Profit:** $2,188/month (87.5% margin)

**50 Clients (Mixed tiers):**
- Revenue: ~$15,000/month
- Infrastructure: $300/month (scaled DB to handle more connections)
- Variable costs: ~$400/month (database, storage, escalations)
- **Profit:** $14,300/month (95.3% margin)

**100 Clients (Mixed tiers + Enterprise):**
- Revenue: ~$35,000/month
- Infrastructure: $500/month (premium DB, redundancy)
- Variable costs: ~$1,000/month (database, storage, escalations)
- **Profit:** $33,500/month (95.7% margin)

**Key Finding:** Edge-first architecture maintains 95%+ margins at scale, dramatically higher than cloud-only (83-87%).

---

## GPU vs CPU Cost Analysis (UPDATED - Edge-First)

### When to Switch to GPU (Rarely Needed)

**Edge-First Reality:**
- Only escalations (~5-10%) reach cloud worker
- 100,000 total queries = 5,000-10,000 escalations
- CPU worker easily handles 43,000+ escalations/month

**CPU Worker (Sufficient for Most Deployments):**
- Cost: $30/month
- Throughput: 30-50 inferences/min = ~43,000-72,000 inferences/month (24/7)
- **Supports:** 430,000-720,000 total edge queries (at 10% escalation rate)
- Cost per escalation: $0.00011

**GPU Worker (Rarely Justified):**
- Cost: $525/month (reserved)
- Only needed if >400,000 escalations/month
- Equivalent to >4M total queries at 10% escalation rate
- Most deployments will never need GPU

**Recommendation:**
- Start with single CPU worker
- Supports up to 100+ clients with typical usage
- Only consider GPU if platform exceeds 5M queries/month total
- **Edge-first architecture eliminates GPU requirement for 99% of deployments**

---

## Cost Optimization Strategies

### 1. Data Lifecycle Management
- **Archive old images:** Move to Cool/Archive storage after 30/90 days
- **Savings:** 60-80% on storage
- **Implementation cost:** Minimal (Azure lifecycle policies)

### 2. Database Optimization
- **Partition large tables** by client_id and date
- **Archive old queries** to blob storage (JSON/Parquet)
- **Use read replicas** for analytics (prevent prod DB impact)
- **Savings:** 40-60% on database costs at scale

### 3. Compute Optimization
- **Use reserved instances** for predictable workloads (50% savings)
- **Implement autoscaling** for worker pools
- **Batch processing** for non-urgent queries
- **Savings:** 30-50% on compute

### 4. Bandwidth Optimization
- **Compress images** before upload (JPEG quality 85 vs 95)
- **Use Azure CDN** for frontend assets
- **Implement caching** for frequently accessed data
- **Savings:** 20-40% on bandwidth (when out of free tier)

### 5. Alert Optimization
- **Deduplicate alerts** (cooldown periods)
- **Smart batching** (daily digest vs per-event)
- **Email-first strategy** (SMS as premium)
- **Savings:** 60-80% on alerting costs

---

## Hidden Costs & Considerations

### Development & Maintenance
- **DevOps time:** 20-40 hours/month ($2,000-4,000)
- **Bug fixes:** 10-20 hours/month ($1,000-2,000)
- **Feature development:** 40-80 hours/month ($4,000-8,000)

### Support Costs
- **Tier 1 support:** $3,000/month (1 FTE)
- **Tier 2/3 support:** $6,000/month (0.5 FTE)

### Sales & Marketing
- **Demo streaming platform:** $1-4/month (internal sales tool)
- **Sales engineering time:** 20-40 hours/month (POCs, demos)
- **Marketing materials:** Video production, documentation

### Compliance & Security
- **SOC 2 audit:** $20,000-50,000/year
- **Penetration testing:** $10,000-25,000/year
- **Security tools:** $500-2,000/month

### Business Continuity
- **Backups:** $50-200/month (included in most services)
- **DR site:** $500-2,000/month (warm standby)
- **Monitoring/alerting:** $100-500/month (DataDog, etc.)

---

## Demo Streaming Feature Costs

### YouTube Live Stream Demo (Internal Sales Tool)

**Purpose:** Sales demonstrations for prospects (NOT a client-facing feature)

**Components:**
- Server-side capture: yt-dlp + FFmpeg
- Real-time inference: ONNX worker
- Session management: PostgreSQL
- Results storage: Blob + Database

**Cost per Demo Session:**
| Component | Cost | Notes |
|-----------|------|-------|
| Compute (capture) | $0.002/minute | CPU for FFmpeg |
| Inference | $0.00011 × frames | ~1 frame/2 sec = 30 frames/min |
| Storage | $0.0001 | Minimal (results only) |
| Bandwidth | $0.001/minute | YouTube stream ingress |
| **Total** | **~$0.006/minute** | **$0.36/hour** |

**Internal Usage Estimates (Sales/Marketing):**
- Typical demo session: 15-20 minutes
- Cost per demo: $0.09-0.12
- Estimated demos/month: 10-30 (prospect calls)
- **Total monthly cost: $1-4/month**

**Classification:** Sales & Marketing Expense
- Not a revenue-generating feature
- Cost absorbed in customer acquisition
- Minimal impact on overall infrastructure costs (~$50/year)

**ROI for Sales:**
- Enables live demonstrations with any YouTube stream
- No need for physical cameras during sales calls
- Can showcase detection across multiple scenarios (traffic, people, animals, etc.)
- **Value:** Reduces sales cycle time, increases close rate
- **Payback:** First closed deal ($1,490+) pays for 30+ years of demos

---

## Risk Factors & Mitigation

### Cost Overruns

**Risk 1: Unexpected Query Spikes**
- **Impact:** 2-5x normal query volume
- **Mitigation:** Rate limiting, query quotas, overage charges
- **Buffer:** Design for 150% of tier limits

**Risk 2: Storage Growth**
- **Impact:** Clients not deleting old images
- **Mitigation:** Automatic archival policies, storage quotas
- **Buffer:** 6-month storage included, then auto-archive

**Risk 3: Alert Spam**
- **Impact:** Misconfigured alerts → high email/SMS costs
- **Mitigation:** Cooldown periods, daily limits, smart deduplication
- **Buffer:** Cap alerts at 10,000/month per client

### Technical Debt

**Risk:** Infrastructure complexity → higher maintenance costs
- **Mitigation:** Standardize on managed services
- **Use:** Azure PaaS services vs custom solutions
- **Invest:** In automation and monitoring

---

## Recommended Pricing Strategy

### Value-Based Pricing

**Client's ROI Calculation:**
- Avoided labor: 1 security guard = $35,000/year
- Reduced false alarms: ~$5,000/year
- Improved detection speed: Priceless (safety)
- Regulatory compliance: Required (must-have)

**Pricing Anchors:**
- Traditional security cameras: $50-200/camera/month (monitoring)
- Cloud video analytics: $20-100/camera/month
- **IntelliOptics positioning:** Premium tier ($30-80/camera/month)

### Client Acquisition Model

**Target Mix:**
- 60% Starter/Professional (predictable revenue)
- 30% Business (growth segment)
- 10% Enterprise (margin + case studies)

**LTV:CAC Ratio Target:** 3:1 minimum
- **Starter LTV:** $1,490/year × 3 years = $4,470
- **Acceptable CAC:** $1,490
- **Channels:** Direct sales, partners, self-serve

---

## Financial Projections (CORRECTED - Edge-First)

### Year 1 (10 Clients - Mixed Tiers)
**Client Mix:** 6 Starter, 3 Professional, 1 Business

| Metric | Value |
|--------|-------|
| Revenue | $30,000 |
| Infrastructure costs | $2,544 ($212/month × 12) |
| Variable costs | $600 (database, storage, escalations) |
| Gross profit | $26,856 |
| **Margin** | **89.5%** |

### Year 2 (50 Clients - Mixed Tiers)
**Client Mix:** 25 Starter, 18 Professional, 5 Business, 2 Enterprise

| Metric | Value |
|--------|-------|
| Revenue | $180,000 |
| Infrastructure costs | $3,600 ($300/month × 12, scaled DB) |
| Variable costs | $4,800 (database, storage, escalations) |
| Gross profit | $171,600 |
| **Margin** | **95.3%** |

### Year 3 (150 Clients - Mixed Tiers)
**Client Mix:** 70 Starter, 55 Professional, 20 Business, 5 Enterprise

| Metric | Value |
|--------|-------|
| Revenue | $600,000 |
| Infrastructure costs | $8,400 ($700/month × 12, premium DB + redundancy) |
| Variable costs | $18,000 (database, storage, escalations) |
| Gross profit | $573,600 |
| **Margin** | **95.6%** |

**Note:** Margins dramatically higher than cloud-only architecture due to edge inference eliminating the largest variable cost.

---

## Conclusion

### Key Takeaways (CORRECTED)

1. **Unit Economics are Excellent (Edge-First)**
   - Cost per normal query: $0.000002 (edge inference, 95% of queries)
   - Cost per escalated query: $0.00011 (cloud inference, 5% of queries)
   - Blended cost: $0.000007 - $0.000013 per query
   - **95% cheaper than cloud-only architecture**
   - Gross margin: 92-98% at scale
   - Break-even: 3 clients

2. **Scaling is Extremely Cost-Effective**
   - Shared infrastructure model keeps fixed costs low ($212/month)
   - Variable costs minimal (mostly database and storage)
   - Edge devices bear compute cost (client hardware)
   - No GPU needed for most deployments

3. **Pricing Has Massive Headroom**
   - Current pricing 100-200x cost to serve (not 10-20x!)
   - Huge room for discounts, promotions, enterprise deals
   - Can easily offer generous free tier for product-led growth
   - Pricing limited by market value, not costs

4. **Biggest Cost Drivers (CORRECTED)**
   - Shared infrastructure (70% of costs) - Fixed, amortized across clients
   - Database I/O (15% of variable costs) - Query metadata
   - Storage (10% of variable costs) - Escalated images only
   - Cloud inference (3% of variable costs) - Escalations only
   - Bandwidth & alerts (2% of variable costs)

5. **Edge-First Architecture = Massive Savings**
   - Medium client: $12.93/month vs $26.63 (52% reduction)
   - Heavy client: $28.35/month vs $60.56 (53% reduction)
   - Enterprise client: $110.78/month vs $345.02 (68% reduction)
   - **Architecture choice saves 50-70% in cloud costs**

### Next Steps

1. **Implement cost tracking**
   - Tag resources by client
   - Monitor per-client usage
   - Build cost dashboard

2. **Optimize hot paths**
   - GPU for inference
   - Database query optimization
   - Image compression

3. **Automate lifecycle management**
   - Data archival policies
   - Resource scaling
   - Cost anomaly detection

4. **Build pricing calculator**
   - Public pricing page
   - ROI calculator for prospects
   - Usage forecasting for clients

---

**Document Version:** 1.0
**Last Updated:** 2026-01-14
**Next Review:** Q2 2026

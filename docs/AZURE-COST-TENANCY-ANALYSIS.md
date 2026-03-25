# IntelliOptics 2.0 - Azure Cost & Multi-Tenancy Analysis

**Date**: January 13, 2026
**Architecture Strategy**: Edge-First, Cloud-Managed
**Objective**: Analyze the operational costs of hosting the central hub in Azure and the economics of serving multiple clients.

---

## 1. The "Edge First" Economic Advantage
The primary cost driver in computer vision is **Inference Compute** (GPUs) and **Data Egress** (uploading high-res video). By performing 95%+ of these tasks on the local Edge Hub, the Azure Cloud component is reduced to a lightweight orchestration and human-in-the-loop (HITL) validation layer.

*   **Bandwidth Savings**: Only "failed" or "low confidence" images are uploaded to Azure, reducing storage and egress costs by ~90% compared to cloud-streaming models.
*   **Compute Savings**: Azure GPU instances (N-Series) cost $500+/month. By using Edge GPUs (Jetson/NVIDIA), cloud compute is reduced to serverless CPU tasks costing <$50/month.

---

## 2. Shared Infrastructure Costs (Fixed)
These are the "Base Platform" costs. In a multi-tenant model, these expenses are paid once and serve the first 50-100 clients.

| Component | Azure Service | Tier | Est. Monthly |
| :--- | :--- | :--- | :--- |
| **Central Database** | Azure Database for PostgreSQL | Flexible Server (B1ms) | $25.00 |
| **Backend API** | Azure Container Apps (ACA) | Serverless (Scale to 0) | $45.00 |
| **Web Frontend** | Azure Static Web Apps | Standard | $9.00 |
| **Message Broker** | Azure Service Bus | Standard (Base) | $10.00 |
| **Total Base Fixed Cost** | | | **$89.00** |

---

## 3. Usage-Based Costs (Variable/Shared)
These costs are shared across all clients but grow linearly with total platform volume (queries requiring cloud review).

| Component | Azure Service | Unit Cost | scaling Factor |
| :--- | :--- | :--- | :--- |
| **Image Storage** | Azure Blob Storage (Hot) | ~$0.02 per GB | Total escalations |
| **Async worker** | ACA (Cloud Worker) | ~$0.000016 per sec | Total cloud inference time |
| **Email Alerts** | SendGrid | $15.00 (Flat up to 40k) | Total alert volume |
| **SMS Alerts** | Twilio | $0.0079 per msg | Total alert volume |

---

## 4. Multi-Tenancy Strategy: "Shared Database, Shared Schema"
To serve multiple clients from one database instance, we implement **Row-Level Isolation**.

### Architecture
*   **Tenant Table**: A new `Organizations` table stores client metadata (Name, Tier, API Keys).
*   **Discriminator Column**: Every table (Detectors, Hubs, Queries, Users) receives an `org_id` column.
*   **Security**: The Backend API enforces an `org_id` filter on every query based on the authenticated user's token.

### Economic Scaling (The Profitability Math)
Assuming a base operational cost of **$125/month** (including small usage buffers):

| No. of Clients | Base Cost / Client | Per-Client Variable | Total OpEx per Client |
| :--- | :--- | :--- | :--- |
| **1 Client** | $125.00 | $5.00 | **$130.00** |
| **10 Clients** | $12.50 | $5.00 | **$17.50** |
| **50 Clients** | $2.50 | $5.00 | **$7.50** |

---

## 5. Non-Shared Costs (Client-Specific)
These costs are typically passed through to the client or handled outside the Azure tenant:
1.  **Edge Hardware**: The physical NVIDIA Jetson or PC installed at the client site.
2.  **Edge Internet**: The bandwidth provided by the client's facility.
3.  **On-Site Setup**: Professional services for camera mounting and hub configuration.

---

## 6. Implementation Roadmap for Multi-Tenancy
To transition the current build to support its first "Client B," the following code changes are required:

1.  **Database Migration**:
    *   Create `organizations` table.
    *   Add `org_id` (UUID) to `users`, `detectors`, `hubs`, `queries`, and `deployments`.
2.  **Backend Auth Update**:
    *   Modify `get_current_user` to return the `org_id`.
    *   Update all Repository/Service layers to include `.filter(models.Table.org_id == current_user.org_id)`.
3.  **Edge Registration**:
    *   Update the `Install-IntelliOptics-Edge.ps1` script to require an `Organization ID` during setup.

---

## 7. Summary Verdict
The current **Edge-First** build is exceptionally well-suited for a high-margin SaaS model on Azure. 
*   **Infrastructure Overhead**: Extremely low (~$100/mo).
*   **Scalability**: The "Fixed Cost" per client approaches zero as the client base grows.
*   **Risk**: The main variable risk is the volume of human escalations; this is controlled via the `confidence_threshold` setting in the UI.

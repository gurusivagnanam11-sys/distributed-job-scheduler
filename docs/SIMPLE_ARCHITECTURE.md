# Simple System Architecture

This document provides a high-level, simplified architectural overview of the **Distributed Job Scheduler** system.

```mermaid
flowchart LR

    %% =====================================================
    %% STYLES
    %% =====================================================

    classDef client fill:#DBEAFE,stroke:#2563EB,stroke-width:2px,color:#1E3A8A
    classDef api fill:#DCFCE7,stroke:#16A34A,stroke-width:2px,color:#166534
    classDef db fill:#FFEDD5,stroke:#EA580C,stroke-width:2px,color:#9A3412
    classDef worker fill:#EDE9FE,stroke:#7C3AED,stroke-width:2px,color:#5B21B6
    classDef feature fill:#FEF3C7,stroke:#D97706,stroke-width:2px,color:#92400E
    classDef success fill:#DCFCE7,stroke:#16A34A,stroke-width:2px,color:#166534
    classDef failure fill:#FEE2E2,stroke:#DC2626,stroke-width:2px,color:#991B1B

    %% =====================================================
    %% CLIENTS
    %% =====================================================

    subgraph CLIENT["🌐 Clients"]

        WEB["⚛️ React Dashboard<br/>Vite"]

        API_CLIENT["🔌 External Client<br/>REST API"]

    end

    %% =====================================================
    %% API
    %% =====================================================

    subgraph BACKEND["⚡ FastAPI Backend"]

        AUTH["🔐 Authentication<br/>JWT + API Key"]

        JOB_API["📥 Job APIs<br/>Submit • Retry • Manage"]

        QUERY_API["📊 Dashboard APIs<br/>Jobs • Queues • Workers"]

    end

    %% =====================================================
    %% DATABASE
    %% =====================================================

    DB[("🐘 PostgreSQL<br/><b>Source of Truth</b>")]

    %% =====================================================
    %% WORKERS
    %% =====================================================

    subgraph WORKERS["⚙️ Distributed Worker Cluster"]

        W1["👷 Worker 1"]

        W2["👷 Worker 2"]

        WN["👷 Worker N"]

    end

    EXEC["⚡ Job Execution"]

    %% =====================================================
    %% SCHEDULING FEATURES
    %% =====================================================

    subgraph SCHEDULER["🔄 Scheduling & Reliability"]

        QUEUE["📋 Queue<br/>Priority + Concurrency"]

        RETRY["🔁 Retry<br/>Backoff"]

        CRON["⏰ Recurring Jobs<br/>Cron"]

        REAPER["🧹 Reaper<br/>Stale Job Recovery"]

        DLQ["💀 Dead Letter<br/>Failed Jobs"]

    end

    %% =====================================================
    %% OBSERVABILITY
    %% =====================================================

    OBS["📈 Observability<br/>Logs • Metrics • Timeline"]

    %% =====================================================
    %% MAIN FLOW
    %% =====================================================

    WEB -->|"JWT"| AUTH
    API_CLIENT -->|"X-API-Key"| AUTH

    AUTH --> JOB_API
    AUTH --> QUERY_API

    JOB_API --> DB
    QUERY_API --> DB

    %% Queue / scheduling
    DB --> QUEUE
    QUEUE --> W1
    QUEUE --> W2
    QUEUE --> WN

    %% Execution
    W1 --> EXEC
    W2 --> EXEC
    WN --> EXEC

    EXEC --> DB

    %% Reliability
    DB --> RETRY
    RETRY --> DB

    DB --> CRON
    CRON --> DB

    DB --> REAPER
    REAPER --> DB

    RETRY --> DLQ
    DLQ --> DB

    %% Observability
    DB --> OBS
    EXEC --> OBS

    %% =====================================================
    %% CLASSES
    %% =====================================================

    class WEB,API_CLIENT client
    class AUTH,JOB_API,QUERY_API api
    class DB db
    class W1,W2,WN,EXEC worker
    class QUEUE,RETRY,CRON,REAPER feature
    class DLQ failure
    class OBS success
```

For the detailed technical deep-dive and locking mechanics, see [ARCHITECTURE.md](./ARCHITECTURE.md).

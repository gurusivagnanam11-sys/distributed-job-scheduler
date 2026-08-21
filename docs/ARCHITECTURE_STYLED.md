# Architecture Diagram, Styled

This is a visual companion to [ARCHITECTURE.md](./ARCHITECTURE.md). It keeps the same system flow, but adds color, emoji icons, and node grouping for easier scanning in Mermaid viewers.

```mermaid
flowchart TD
    FE[⚛️ Frontend<br/>React + Vite dashboard]
    EXT[🔌 External submission client<br/>X-API-Key]
    API[⚡ FastAPI API layer]
    DB[(🐘 PostgreSQL)]

    subgraph WP[⚙️ Worker process]
        MAIN[⚙️ main.py<br/>worker entrypoint]
        POLL[⚙️ claim loop<br/>poll active queues]
        EXEC[⚙️ executor.py<br/>execute claimed jobs]
        HB[💓 heartbeat loop]
        REAPER[🧹 reaper loop]
        RS[🔁 recurring-scheduler loop]
    end

    SUBMIT[📤 Job submission<br/>immediate / delayed / scheduled / recurring / batch]
    CLAIM[🔐 claim_jobs()<br/>atomic claim + lease]
    RUN[⚙️ Job execution<br/>running -> completed / retrying / dead_letter]
    STALE[⏱️ Stale lease detected]
    RETRY[🔁 Retry with backoff]
    DLQ[☠️ Dead Letter Queue]
    MANUAL[🛠️ Manual retry<br/>API / dashboard]
    RECUR[🔁 Recurring template<br/>next_run_at reached]
    HEART[💓 Worker heartbeat]
    DONE[✅ completed]
    FAIL[❌ failed]

    FE -->|JWT for dashboard actions| API
    EXT --> API

    API --> SUBMIT --> DB
    API -->|read job / queue / worker views| DB

    DB --> MAIN
    MAIN --> POLL
    MAIN --> HB
    MAIN --> REAPER
    MAIN --> RS

    POLL --> CLAIM --> DB
    CLAIM -->|queued / scheduled / retrying| RUN
    RUN --> DB

    RUN -->|success| DONE
    RUN -->|failure with retries left| RETRY --> DB
    RUN -->|retries exhausted| DLQ --> DB
    DLQ --> MANUAL --> DB
    RUN -->|handler failure| FAIL

    REAPER --> STALE --> RETRY
    REAPER --> STALE --> DLQ

    RS --> RECUR --> DB
    HEART --> DB

    DB --> FE

    classDef frontend fill:#dbeafe,stroke:#2563eb,color:#1e3a8a,stroke-width:2px;
    classDef api fill:#dcfce7,stroke:#16a34a,color:#14532d,stroke-width:2px;
    classDef database fill:#ffedd5,stroke:#f59e0b,color:#92400e,stroke-width:2px;
    classDef worker fill:#ede9fe,stroke:#7c3aed,color:#4c1d95,stroke-width:2px;
    classDef completed fill:#dcfce7,stroke:#16a34a,color:#14532d,stroke-width:2px;
    classDef failed fill:#fee2e2,stroke:#dc2626,color:#991b1b,stroke-width:2px;
    classDef retrying fill:#fef3c7,stroke:#f59e0b,color:#92400e,stroke-width:2px;

    class FE,EXT frontend;
    class API,SUBMIT api;
    class DB database;
    class MAIN,POLL,EXEC,HB,REAPER,RS,CLAIM,RUN,STALE,RECUR,HEART,MANUAL worker;
    class DONE completed;
    class FAIL,DLQ failed;
    class RETRY retrying;
```

## Legend

- Blue: frontend and external clients
- Green: API layer and completed jobs
- Amber: PostgreSQL and retrying states
- Purple: worker internals
- Red: failed and dead-letter terminal states

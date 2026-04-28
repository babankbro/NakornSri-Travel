# Travel Route File-Based System - Documentation

An intelligent travel itinerary optimization system that plans multi-day routes visiting tourist attractions in Nakhon Si Thammarat, Thailand. Optimizes for distance, time, and CO2 emissions using metaheuristic algorithms. Entirely file-based — no database required.

## Documentation

| Document | Description |
|----------|-------------|
| [Getting Started](getting-started.md) | Installation, setup, running the server, first optimization |
| [Architecture](architecture.md) | System design, request flow, backend layers, storage layout |
| [API Reference](api-reference.md) | All 18 REST endpoints with request/response examples |
| [Algorithms](algorithms.md) | Deep dive into GA, SA, ALNS, and hybrid optimizers |
| [Algorithm Workflows](algorithm-workflows.md) | Detailed workflows, flowcharts (Mermaid), and pseudocode ([HTML View](algorithm-workflows.html)) |
| [Data Formats](data-formats.md) | CSV input schemas, JSON result structure, matrix formats |
| [Frontend Guide](frontend-guide.md) | UI structure, Leaflet map integration, extending the frontend |

## Existing Thai Documents

| Document | Contents |
|----------|----------|
| [Travel_Route_File_Based_SRS_TOR_API.pdf](Travel_Route_File_Based_SRS_TOR_API.pdf) | Formal SRS, TOR, Use Cases, File Diagram, API Contract (Thai) |
| [Data_Travel_2568.pdf](Data_Travel_2568.pdf) | Travel constraints, experiment framework, expected results (Thai) |

## Quick Start

```bash
pip install -r requirements.txt
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 for the web UI, or http://localhost:8000/docs for the Swagger API docs.

# Architecture Overview

The Return-Risk Intelligence Engine consists of:
- **Event-driven Simulation Layer**: Generates realistic synthetic transactions and fraud vectors.
- **Feature Layer**: Offline point-in-time and online Redis-backed feature computation.
- **Inference & Decisioning**: Sub-50ms scoring with expected cost optimization.
- **Asynchronous SHAP Explanations**: TreeSHAP computed out-of-band for analyst auditability.
- **Analyst Dashboard**: Investigation workbench and network exploration.

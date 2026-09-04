# Phase 1: Data Generation - Summary Report

## Overview
Phase 1 focused on building a robust, flexible, and realistic synthetic data generation pipeline to simulate an e-commerce ecosystem. The goal was to generate synthetic transactions, user sessions, and entity relationships (devices, payment methods, network IPs) that mimic both legitimate customer behaviors and sophisticated fraud patterns (specifically Return Abuse).

Instead of purely statistical noise, we implemented an agent-based **Discrete Event Simulation (DES)** approach. This ensures that the generated data respects strict business logic (e.g., a return can only occur after an item is delivered, and users must have active sessions before they can order). The phase culminated in generating the "World A" dataset containing 10,000 users and approximately 100,000 events, thoroughly validated against strict business constraints.

---

## Files Created and Their Purpose

### Core Simulation Engine (`src/simulation/`)
* **`entities.py`**: Contains the dataclasses/Pydantic models for the core data structures (User, Device, PaymentMethod, Session, Transaction, Event). It enforces schema consistency across the simulation.
* **`event_scheduler.py`**: A priority-queue-based discrete event simulation clock. It manages the timeline of events, ensuring causal relationships are respected (e.g., Session Start -> Order -> Delivery -> Return).
* **`graph_builder.py`**: Responsible for constructing the underlying identity graph. It simulates how entities connect (users sharing devices, networks, or payment methods) and is crucial for injecting both "hard negative" legitimate sharing (like family households) and complex fraud rings.
* **`agents.py`**: Simulates legitimate customer behaviour. It uses statistical distributions to model browsing habits, conversion rates, and normal (non-fraudulent) return probabilities.
* **`fraud_scenarios.py`**: Contains the logic for generating specific, sophisticated fraud patterns. It implements the `FraudScenario` base class and specific handlers for:
  * **Serial Return Abuse**: High volume of orders and returns from a single identity.
  * **Multi-Account Abuse**: Fraudsters spreading orders and returns across multiple synthetic identities to evade velocity checks.
  * **Wardrobing**: The practice of buying an item, using it briefly, and returning it (often leaving distinct temporal footprints).
* **`financial_engine.py`**: Computes the unit economics for every transaction. It calculates item costs, shipping fees, processing fees, revenue, and resulting financial losses when items are returned (including salvage depreciation).
* **`generator.py`**: The main orchestrator. It initializes the simulation environment, samples populations according to the configuration, coordinates the agents and fraud handlers, processes the event queue, and finally dumps the generated logs to Parquet files.

### Configuration & Scripts
* **`config/simulation/world_a.yaml`**: The configuration file that dictates the parameters of the simulation (number of users, fraud penetration rates, scenario difficulty distributions).
* **`scripts/generate_data.py`**: The CLI script used to kick off the simulation process.
* **`scripts/verify_phase1.py`**: The validation script used to verify that the generated data complies with all structural and business logic constraints.

### Output Data
* **`data/raw/`**: Contains the generated Parquet files (`users.parquet`, `transactions.parquet`, `events.parquet`, etc.) which act as the raw input for feature engineering in Phase 2.
* **`data/ground_truth/`**: Contains the highly segregated `hidden_labels.parquet`, ensuring that labels are strictly separated from raw features to prevent target leakage during later modeling phases.

---

## Biggest Challenges Faced (Chronological Order)

1. **Designing a Causally Correct Timeline (The Event Scheduler)**
   * *Challenge*: Initial naive approaches to data generation involved randomly sampling timestamps across a date range. This caused logical impossibilities (e.g., returns requested before an order was placed or delivered).
   * *Solution*: We shifted to a rigorous Discrete Event Simulation (DES) approach (`event_scheduler.py`) where events explicitly trigger future events, enforcing the natural chronological order of an e-commerce lifecycle.

2. **Graph Realism: Hard Negatives vs. Fraud Rings**
   * *Challenge*: Fraud models often overfit on shared entities (e.g., flagging any two accounts sharing a device). We needed the graph to contain "hard negatives"—legitimate users sharing devices/IPs (like a family or roommates) that look suspiciously like multi-account fraud rings but are actually benign.
   * *Solution*: `graph_builder.py` was designed to explicitly sample these overlapping identity clusters for legitimate users, ensuring the downstream GNN model has to learn complex behavioural signals, not just simple shared-entity rules.

3. **Data Extraction & Validation Stringency (Stringified JSON)**
   * *Challenge*: In the validation script (`verify_phase1.py`), Polars struggled to perform relational joins because the `entity_ids` field in `events.parquet` was serialized as a stringified Python dictionary rather than a native struct or JSON object.
   * *Solution*: We engineered robust regex-based extraction logic (`pl.col("entity_ids").str.extract(r"'transaction_id': '([^']+)'")`) within the validation script to correctly parse out UUIDs and enable the massive relational joins needed to verify the data.

4. **Aligning Fraud Scenarios with Delivery Timestamps**
   * *Challenge*: The business constraint validator flagged thousands of "Return before Delivery" violations. The fraud scenario logic was incorrectly anchoring the time of a `RETURN_REQUESTED` event to the `order_time` rather than the `order_delivery_time`.
   * *Solution*: We modified `generator.py` to meticulously track `order_delivery_times` during the legitimate transaction generation pass, and then injected these exact delivery times into the `fraud_scenarios.py` handlers so returns were scheduled realistically *after* delivery.

5. **Cross-Platform Execution Issues (Windows Unicode)**
   * *Challenge*: The validation script crashed upon completion on Windows environments due to `UnicodeEncodeError` when trying to print success checkmarks (✔) to `sys.stdout`.
   * *Solution*: We dynamically reconfigured standard output streams (`sys.stdout` and `sys.stderr`) to use UTF-8 encoding within the Python script to guarantee cross-platform compatibility.

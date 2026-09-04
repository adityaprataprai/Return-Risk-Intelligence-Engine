# Phase 8: Dashboard Frontend

## Objective

Build the Next.js frontend that provides:

- Risk overview with KPIs
- Review queue
- Case investigation workbench (risk, evidence, economics, timeline, graph)
- Abuse network explorer
- Analytics and financial impact
- Policy simulation (read-only)
- Model/system health

The UI must be production-grade, using shadcn/ui, Tailwind CSS, TanStack Table, ECharts/Recharts, Cytoscape.js.

## Scope

- Initialize Next.js app with TypeScript, Tailwind, shadcn/ui.
- Create layout and navigation.
- Implement pages/components for each area using BFF APIs from Phase 7.
- Add mock data fallback if BFF not running.

## Deliverables

```
frontend/
├── package.json
├── next.config.js
├── tailwind.config.ts
├── tsconfig.json
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                 # redirect to overview
│   │   ├── overview/page.tsx
│   │   ├── review-queue/page.tsx
│   │   ├── cases/[request_id]/page.tsx
│   │   ├── networks/page.tsx
│   │   ├── analytics/page.tsx
│   │   ├── policies/page.tsx
│   │   └── health/page.tsx
│   ├── components/
│   │   ├── ui/                      # shadcn components
│   │   ├── dashboard/
│   │   │   ├── KpiCard.tsx
│   │   │   ├── RiskOverview.tsx
│   │   │   ├── ReviewQueueTable.tsx
│   │   │   ├── CaseDetail.tsx
│   │   │   ├── ExplanationPanel.tsx
│   │   │   ├── NetworkGraph.tsx
│   │   │   └── Timeline.tsx
│   ├── lib/
│   │   ├── api.ts                   # BFF client
│   │   ├── types.ts                 # TypeScript interfaces matching API responses
│   │   └── utils.ts
│   └── hooks/
│       ├── useCases.ts
│       ├── useOverview.ts
│       └── useNetwork.ts
```

## Technical Requirements

### 1. Setup

- Use `create-next-app` with TypeScript, Tailwind CSS, App Router.
- Install and configure `shadcn/ui`.
- Set up TanStack Query for data fetching.

### 2. Pages

#### Overview
- KPI cards: Return requests, refund value, fraud prevented, false-positive cost, net margin saved.
- Risk distribution chart (ECharts).
- Action distribution donut.

#### Review Queue
- Table with columns: Risk, Return ID, Customer, Refund, Net Exposure, Primary Reason, Recommended Action, Status, Assignee, Queue Age.
- Filters: risk band, amount range, category, reason, status.
- Pagination and sorting.

#### Case Detail
- Header: Return ID, risk probability, action, status.
- Tabs:
  - Overview: customer/order/risk panels.
  - Explanation: SHAP, reason codes, evidence, data confidence.
  - Timeline: chronological events with risk relevance.
  - Network: mini graph of user-entity relationships.
  - Economics: expected costs table.
  - Audit: decision lineage.
- Action buttons: Approve, Verify, Block (with override reason dialog).

#### Network Explorer
- Cytoscape graph showing user, device, address, payment nodes and relationships.
- Node click opens details.

#### Analytics
- Fraud trends, scenario mix, financial impact charts.

#### Policies
- Display policies, simulate changes (read-only form).

#### Health
- Model & feature health metrics (from BFF).

### 3. API Integration

Use `src/lib/api.ts` to call BFF endpoints. Provide fallback mock data if API unavailable.

### 4. Styling

Use Tailwind + shadcn/ui. Responsive design.

## Acceptance Criteria

- All pages render without errors.
- Overview shows realistic KPIs.
- Review queue loads and filters work.
- Case detail displays explanation and timeline.
- Network explorer renders a graph.
- Action submission posts to BFF and updates case.
- Build succeeds with `npm run build`.

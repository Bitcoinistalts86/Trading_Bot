# Execution & Risk Control

This document provides an overview of the execution engine and the risk control mechanisms in place.

## Execution Flow

The execution flow begins when a trading signal is sent to the execution engine. The following steps are then performed:

1.  **Signal Reception:** The execution engine receives a signal from a model via the `/signal` endpoint.
2.  **Smart Order Routing:** The Smart Order Router (SOR) determines the optimal venue (e.g., Binance, Uniswap) to execute the trade based on liquidity, slippage, and fees.
3.  **Pre-Trade Risk Checks:** The order is checked against a series of pre-trade risk controls, including position limits, fat finger checks, and margin utilization.
4.  **Order Placement:** If the risk checks pass, the order is placed on the selected venue.
5.  **Trade Logging:** The trade is logged to the `trade_logs` table in BigQuery for auditing and analysis.

## Risk Controls

The platform implements a multi-layered approach to risk management.

-   **Pre-Trade Controls:** As described above, all orders are checked against a set of predefined risk limits before being placed.
-   **Real-Time Monitoring:** The platform continuously monitors the overall risk exposure of the portfolio, including drawdown limits and margin utilization.
-   **Kill-Switch:** A manual kill-switch is available to halt all trading activity in the event of a market disruption or system failure.

For more details on the risk control mechanisms, see the [Risk Management Policy](risk_policy.md).

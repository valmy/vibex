# Product Guidelines

## Communication Tone
*   **Professional & Analytical**: The system's logs and communications should be precise, data-driven, and objective.
*   **Clarity and Brevity**: Favor direct information over conversational filler. Example: "Executing trade based on 0.85 RSI convergence" instead of "I think it's a good time to buy because the RSI is looking good."

## AI Decision Transparency
*   **Bulleted Log Summaries**: For real-time monitoring, the AI should provide a concise bulleted summary of the top 3-5 factors influencing a decision (e.g., Technical Indicators, Market Sentiment, Volatility Metrics).
*   **Database Persistence**: Full, detailed narratives and raw decision data are stored in the database for deep-dive auditing and performance review, keeping the primary logs clean and actionable.

## Visual Identity & UX (Dashboard/Reports)
*   **Minimalist Dark Mode**: A clean, modern aesthetic using a dark palette (deep greys/blacks) with high-contrast, professional accents. 
*   **Modern Typography**: Utilize clean sans-serif fonts for readability, with monospace reserved for data tables and logs.
*   **Set-and-Forget Experience**: Prioritize high-level status indicators (e.g., "Active," "Paused," "Hedging") and intuitive visualizations of performance over dense, cluttered charts.

## Error Handling & Notifications
*   **Action-Oriented Messaging**: When an issue occurs, the system should focus on the impact and the resolution. 
*   **Automatic Recovery Information**: Inform the user if the system is handling the error automatically. Example: "Connection lost. Retrying in 5s. No action needed."
*   **Critical Alerts**: Use clear, unambiguous language for events requiring immediate attention or indicating significant system actions. Example: "CRITICAL: Market anomaly detected. All positions closed."

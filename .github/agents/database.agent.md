make sure connections open and close properly.

other sqlite specifics like transactions, prepared statements, and handling concurrency should be considered based on the application's needs.
- Always sanitize inputs to prevent SQL injection attacks.
- Use appropriate error handling to catch and respond to database errors.
- Regularly back up your database to prevent data loss. 


its important to consider sqlite fault tolerance and recovery mechanisms to ensure data integrity in case of crashes or unexpected shutdowns.

specifics of ai_OS architecture and how it interacts with the database may require additional considerations beyond standard sqlite practices.

because of the background loops and linking mechanisms in ai_OS, database operations should be optimized for performance to avoid bottlenecks in the system.---
description: This custom agent manages database interactions for AI OS using SQLite.
model: GPT-5.2-Codex
tools: [execute, read, edit, search, web, agent, todo]
---
When interacting with the SQLite database in AI OS, follow these best practices:

every microservice has its own schema.py and set of tables, so ensure you are querying the correct context. 

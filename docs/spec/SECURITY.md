# Security

## Permission classes
- SAFE
- CONFIRM
- BLOCK

Threats:
- prompt injection
- malicious web content
- unsafe shell
- path traversal
- destructive filesystem operations
- secret leakage
- tool abuse
- untrusted downloads

Rules:
- normalize and scope paths;
- validate structured tool inputs;
- never execute raw model-generated shell;
- keep secrets outside source/logs/state;
- audit meaningful side effects;
- verify postconditions;
- use bounded retries.

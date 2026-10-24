# Cross-User Isolation Test

Two separate users run through the full agent -> job retrieval -> CV generation flow in the same Python process, sharing the same stateless service instances (the shared LLMClient, JobRetrievalTool) but each with their own ProfileAgent/ProfileTool. User A completes first (0 follow-ups); User B runs afterward (2 follow-ups) to also confirm a completed user's state survives a second, unrelated conversation happening after it.

**User A:** Ethan Brooks — Hi, I'm Ethan Brooks, a third-year Bachelor of Computing Science student at UTS. I'm solid in Java, Python, SQL and Git. Last semester I built a library-booking REST API as a team project using Spring Boot and PostgreSQL, and I worked part-time as a junior IT helpdesk assistant fixing account and login issues. I'm targeting Junior Backend Developer and Graduate Software Engineer roles.

**User B:** Devon Okafor — I'm a third-year Bachelor of Computing Science student at UTS. I've been working with Python, Hugging Face Transformers and PyTorch, and I built a sentiment-analysis tool for coursework that classifies product reviews. I haven't figured out exactly what kind of role I want yet.

## Isolation checks

- User A's draft profile unchanged after User B's entire run completed: `True`
- User A and User B have separate ProfileTool instances (`agent_a.tool is not agent_b.tool`): `True`
- No cross-contamination of names between the two confirmed profiles: `True`
- No project-title cross-contamination between the two confirmed profiles: `True`
- User A's generated CV does not mention User B's name/skills: `True`
- User B's generated CV does not mention User A's name/skills: `True`

**All isolation checks passed: `True`**

## User A result

- Retrieved top job: `rag_agent_engineer` (AI Engineer)
- Matched skills: Python
- Missing requirements: Master's degree or above in computer science, artificial intelligence, data systems, or a related field, Three or more years of research or engineering experience, Experience with LLMs, Experience with RAG, Experience with AI agents, Experience with intelligent data systems, Experience with LangChain, Experience with LangGraph, Experience with LlamaIndex, Experience with vector databases, Experience with graph databases, Experience with cloud AI platforms
- CV summary: Ethan Brooks is a third-year Bachelor of Computing Science student at UTS, expected to graduate in December 2025. With hands‑on experience in IT helpdesk support and a team‑based library‑booking REST API project, he has developed strong programming skills in Java, Python, SQL, and related technologies. He is pursuing roles as a Junior Backend Developer or Graduate Software Engineer, bringing a solid foundation in backend development and database management.
- CV skills: Python, Java, SQL, Git, Spring Boot, PostgreSQL

## User B result

- Retrieved top job: `nlp_multimodal_ml_engineer` (Machine Learning Engineer, NLP & Multimodal AI)
- Matched skills: Python, Hugging Face Transformers, PyTorch
- Missing requirements: Spark, Hadoop, Kafka, vector databases, Java, hyperparameter optimisation, production deployment, Git, CI/CD, managing multiple environments
- CV summary: Devon Okafor is a third‑year Bachelor of Computing Science student at UTS, expected to graduate December 2025. He has built a sentiment analysis tool using Python, Hugging Face Transformers, and PyTorch, and is targeting roles as an AI Intern or NLP Research Assistant.
- CV skills: Python, Hugging Face Transformers, PyTorch
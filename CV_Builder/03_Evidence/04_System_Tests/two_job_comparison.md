# Two-Job Comparison

Same confirmed profile (Ethan Brooks, live agent-confirmed via `cv_builder_cli`, not a dataset profile), two different target jobs from his own top-3 retrieval results, generated via `CVGenerator`.

**Initial introduction:** Hi, I'm Ethan Brooks, a third-year Bachelor of Computing Science student at UTS. I'm solid in Java, Python, SQL and Git. Last semester I built a library-booking REST API as a team project using Spring Boot and PostgreSQL, and I worked part-time as a junior IT helpdesk assistant fixing account and login issues. I'm targeting Junior Backend Developer and Graduate Software Engineer roles.

**Profile unchanged after generating both CVs:** `True` (profile dict compared field-for-field before vs. after both generate() calls)

## Side-by-side comparison

| | Job A | Job B |
|---|---|---|
| Target job | AI Engineer (`rag_agent_engineer`) | Machine Learning Engineer (`healthcare_ml_engineer`) |
| Skills order | Python, SQL, Git, Spring Boot, PostgreSQL, Java | Python, SQL, Git, Spring Boot, PostgreSQL, Java |
| Matched skills | Python | Python, SQL, Git, Spring Boot, PostgreSQL |
| # Missing requirements | 9 | 11 |

### Job A: AI Engineer (`rag_agent_engineer`)

**Summary:** Ethan Brooks is a third‑year Computing Science student at UTS, expected to graduate in December 2025. With hands‑on experience in Java, Python, SQL, Git, Spring Boot, and PostgreSQL, he has built a library‑booking REST API and resolved account and login issues in a helpdesk role. He is eager to apply his backend development skills to AI‑powered enterprise applications.

**Skills (order as generated):** Python, SQL, Git, Spring Boot, PostgreSQL, Java

**Section order in this CV:** Summary -> Education -> Skills -> Experience -> Projects

**Matched skills:** Python
**Missing requirements:** Master's degree or above in computer science, artificial intelligence, data systems, or a related field, Three or more years of research or engineering experience, Experience with LLMs, RAG, AI agents, or intelligent data systems, LangChain, LangGraph, LlamaIndex, Vector databases, Graph databases, Cloud AI platforms
**Grounding warnings:** (none)

---

### Job B: Machine Learning Engineer (`healthcare_ml_engineer`)

**Summary:** Ethan Brooks is a third‑year Computing Science student at UTS, expected to graduate in December 2025. With hands‑on experience in backend development using Python, SQL, Spring Boot, and PostgreSQL, he has resolved technical issues in a helpdesk setting and contributed to a team‑built library‑booking REST API. He seeks to transition into machine‑learning engineering, leveraging his programming and database skills.

**Skills (order as generated):** Python, SQL, Git, Spring Boot, PostgreSQL, Java

**Section order in this CV:** Summary -> Education -> Skills -> Experience -> Projects

**Matched skills:** Python, SQL, Git, Spring Boot, PostgreSQL
**Missing requirements:** Linux, Batch or streaming systems, CI/CD, MLOps, Docker, Cloud ML platforms, Streaming data pipelines, Regulated environments, Generative AI, REST or gRPC services, Kubernetes
**Grounding warnings:** (none)

---

Sample PDFs exported to: `03_Evidence/04_System_Tests/sample_cv_pdfs/Ethan_Brooks_rag_agent_engineer_cv.pdf`, `03_Evidence/04_System_Tests/sample_cv_pdfs/Ethan_Brooks_healthcare_ml_engineer_cv.pdf`
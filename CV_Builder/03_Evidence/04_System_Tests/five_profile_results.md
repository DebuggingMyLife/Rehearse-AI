# Five Profile Results



Five distinct synthetic introductions run through the full agent -> job retrieval -> CV generation flow (`cv_builder_cli.run_full_flow`). Two are complete introductions (0 follow-ups expected); three are deliberately incomplete, each missing a different combination of required fields, to exercise the follow-up mechanism in more than one way. CV generated against each profile's own #1 retrieved job.



## Ethan Brooks - backend/software generalist (complete)

**Follow-up questions asked:** 1 (education_dates)
**Target roles:** Junior Backend Developer, Graduate Software Engineer

**Top 3 job matches (document_id — score):**
- `rag_agent_engineer` — AI Engineer (score 0.4732)
- `healthcare_ml_engineer` — Machine Learning Engineer (score 0.4638)
- `agentic_ai_engineer` — AI Engineer (score 0.4506)

**CV generated for:** `rag_agent_engineer` (AI Engineer)
**Matched skills:** Python
**Missing requirements:** LLMs, RAG pipelines, AI-agent workflows, vector databases, graph databases, LangChain, LangGraph, LlamaIndex, cloud AI platforms, Master's degree or above, Three or more years of research or engineering experience
**Grounding warnings:** (none)

**Final CV summary:** Ethan Brooks is a third‑year Computing Science student at UTS, expected to graduate December 2025. He has practical experience as a junior IT helpdesk assistant and has developed a library‑booking REST API using Spring Boot and PostgreSQL. With a solid foundation in Java, Python, SQL, Git, and database technologies, he is eager to transition into backend development roles.
**Final CV skills:** Python, Java, SQL, Git, Spring Boot, PostgreSQL
(Full profile + trace: test_profiles/profile_1_ethan_brooks.md)

## Priya Nair - data/analytics (complete)

**Follow-up questions asked:** 2 (education_dates; project_dates)
**Target roles:** Data Analyst Intern, Business Intelligence Intern

**Top 3 job matches (document_id — score):**
- `graduate_ai_engineer` — Graduate AI Engineer (score 0.4497)
- `rag_agent_engineer` — AI Engineer (score 0.446)
- `recommendation_systems_ml_engineer` — Machine Learning Engineer (score 0.4382)

**CV generated for:** `graduate_ai_engineer` (Graduate AI Engineer)
**Matched skills:** Python, pandas, Power BI
**Missing requirements:** NumPy, scikit-learn, PyTorch, statistics, machine-learning fundamentals, agentic AI, LLMs, RAG, domain-specific fine-tuning, structured data, unstructured data, software-development practice
**Grounding warnings:** (none)

**Final CV summary:** Bachelor of Computing Science student at UTS, expected to graduate December 2026, with hands‑on experience building data visualisation dashboards using Power BI and data manipulation in Python and pandas. Skilled in SQL and data analysis, and eager to apply analytical and programming skills to AI and machine‑learning projects.
**Final CV skills:** Python, pandas, Power BI, SQL
(Full profile + trace: test_profiles/profile_2_priya_nair.md)

## Devon Okafor - AI/NLP (incomplete: name, target_roles)

**Follow-up questions asked:** 4 (name, education_dates, target_roles; education_dates, target_roles; education_dates; project_dates)
**Target roles:** AI Intern, NLP Research Assistant

**Top 3 job matches (document_id — score):**
- `nlp_multimodal_ml_engineer` — Machine Learning Engineer, NLP & Multimodal AI (score 0.4962)
- `graduate_ai_engineer` — Graduate AI Engineer (score 0.4873)
- `rag_agent_engineer` — AI Engineer (score 0.4831)

**CV generated for:** `nlp_multimodal_ml_engineer` (Machine Learning Engineer, NLP & Multimodal AI)
**Matched skills:** Python, Hugging Face Transformers, PyTorch
**Missing requirements:** four years of industry AI or machine-learning experience, master's degree or higher, big-data technologies such as Spark, Hadoop, Kafka, or vector databases, Java, hyperparameter optimisation, production deployment, Git, CI/CD, experience managing multiple environments
**Grounding warnings:** (none)

**Final CV summary:** Devon Okafor is a third‑year Bachelor of Computing Science student at UTS, expected to graduate December 2025. He has developed a sentiment analysis tool using Python, Hugging Face Transformers, and PyTorch, demonstrating proficiency in NLP and deep‑learning frameworks. Seeking an AI internship or NLP research assistant role to apply his skills in large‑scale machine‑learning projects.
**Final CV skills:** Python, Hugging Face Transformers, PyTorch
(Full profile + trace: test_profiles/profile_3_devon_okafor.md)

## Marcus Webb - cybersecurity/systems (incomplete: technical_skills, target_roles)

**Follow-up questions asked:** 3 (education_dates, technical_skills, target_roles; education_dates; project_dates)
**Target roles:** Cybersecurity Intern, Junior SOC Analyst

**Top 3 job matches (document_id — score):**
- `trust_safety_ml_engineer` — Machine Learning Engineer Graduate, Trust and Safety Engineering - 2026 Start (score 0.4774)
- `graduate_ai_engineer` — Graduate AI Engineer (score 0.4221)
- `rag_agent_engineer` — AI Engineer (score 0.4203)

**CV generated for:** `trust_safety_ml_engineer` (Machine Learning Engineer Graduate, Trust and Safety Engineering - 2026 Start)
**Matched skills:** (none)
**Missing requirements:** Machine Learning, Pattern Recognition, NLP, Data Mining, Computer Vision, Data Structures, Algorithms, Communication, Teamwork
**Grounding warnings:** (none)

**Final CV summary:** Computer Science student at UTS with hands‑on experience setting up a home lab to monitor network traffic and document attack patterns. Proficient in Linux and Wireshark, and actively pursuing opportunities in cybersecurity and trust‑and‑safety engineering.
**Final CV skills:** Linux, Wireshark
(Full profile + trace: test_profiles/profile_4_marcus_webb.md)

## Sarah Chen - full-stack/cloud (incomplete: degree, year, institution)

**Follow-up questions asked:** 3 (degree, institution, year; institution, education_dates; institution)
**Target roles:** Full-Stack Developer Intern, Junior Cloud Engineer

**Top 3 job matches (document_id — score):**
- `agentic_ai_engineer` — AI Engineer (score 0.5605)
- `rag_agent_engineer` — AI Engineer (score 0.5531)
- `computer_vision_engineer` — AI Computer Vision Engineer (score 0.5448)

**CV generated for:** `agentic_ai_engineer` (AI Engineer)
**Matched skills:** AWS basics
**Missing requirements:** Python, Langflow, LLM orchestration, RAG, AI-agent solutions, Terraform, Kubernetes, Docker, modern AI tooling, testing, documentation, monitoring practices, translate business needs into maintainable technical solutions
**Grounding warnings:** (none)

**Final CV summary:** Sarah Chen is a second‑year Bachelor of Computing Science student at UTS, expected to graduate December 2026. She has hands‑on experience with JavaScript, React, Node.js, and AWS basics, and is eager to apply her programming and cloud fundamentals to AI‑driven solutions.
**Final CV skills:** AWS basics, Node.js, JavaScript, React
(Full profile + trace: test_profiles/profile_5_sarah_chen.md)
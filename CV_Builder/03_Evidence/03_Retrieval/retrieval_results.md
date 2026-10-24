# Retrieval Results

Top-3 semantic job matches per test profile, from `run_retrieval_tests.py` using `JobRetrievalTool` (sentence-transformers `all-MiniLM-L6-v2` embeddings, cosine similarity). Excerpts are the single sentence within each job's actual description with the highest similarity to the profile's query embedding, not a generic label.

## Maya Chen (student_profile_01)

**Target roles:** Software Engineering Intern, Graduate Software Developer, Junior Backend Developer
**Skills:** Python, Java, SQL, REST APIs, Git, GitHub, pytest, Jupyter Notebook

**Top 3 matched jobs:**

1. **AI Engineer** (`agentic_ai_engineer`) — score 0.66
   > Responsibilities: Deliver end-to-end AI solutions; develop agentic workflows and autonomous components using Python, Langflow, and modern AI tooling; manage the full lifecycle from requirements and stakeholder engagement through to testing and deployment; embed AI components into existing applications; manage and optimise AI infrastructure and model orchestration environments with SRE and platform teams; and apply testing, documentation, and monitoring practices.

2. **AI Engineer** (`rag_agent_engineer`) — score 0.6467
   > Responsibilities: Develop LLM-powered AI applications; design and optimise RAG pipelines and AI-agent workflows; build AI-powered knowledge systems and retrieval solutions; evaluate models and optimise system performance; collaborate with software engineers to deploy production-ready applications; and explore emerging AI technologies.

3. **Graduate AI Engineer** (`graduate_ai_engineer`) — score 0.627
   > Responsibilities: Develop and evaluate machine-learning models and AI agents; build specialised modular AI components; gather requirements; run experiments; validate outputs; iterate from findings; write clean, maintainable Python; and contribute to shared codebases.

## Liam Patel (student_profile_02)

**Target roles:** AI Intern, NLP Intern, Junior Machine Learning Engineer
**Skills:** Python, pandas, NumPy, scikit-learn, PyTorch basics, SQL, Hugging Face Transformers basics, Git, Jupyter Notebook

**Top 3 matched jobs:**

1. **Graduate AI Engineer** (`graduate_ai_engineer`) — score 0.5557
   > Responsibilities: Develop and evaluate machine-learning models and AI agents; build specialised modular AI components; gather requirements; run experiments; validate outputs; iterate from findings; write clean, maintainable Python; and contribute to shared codebases.

2. **AI Engineer** (`rag_agent_engineer`) — score 0.5381
   > Responsibilities: Develop LLM-powered AI applications; design and optimise RAG pipelines and AI-agent workflows; build AI-powered knowledge systems and retrieval solutions; evaluate models and optimise system performance; collaborate with software engineers to deploy production-ready applications; and explore emerging AI technologies.

3. **AI Engineer / Data Scientist (Agentic AI) | Manager/Senior Manager** (`agentic_ai_data_scientist`) — score 0.4819
   > Requirements: Strong Python development; modern LLM frameworks and SDKs; prompt engineering; agentic patterns; tool or function calling; structured outputs; RAG evaluation; vector databases; SQL; scientific evaluation; Git; communication; and experience with cloud, Docker, data pipelines, and related production systems.

## Noah Ibrahim (student_profile_04)

**Target roles:** Cybersecurity Intern, Junior Systems Developer, QA Automation Intern
**Skills:** Python, Linux, SQL, network troubleshooting, Git, REST API testing, Wireshark basics, Docker basics, technical documentation

**Top 3 matched jobs:**

1. **AI Engineer** (`agentic_ai_engineer`) — score 0.6454
   > Responsibilities: Deliver end-to-end AI solutions; develop agentic workflows and autonomous components using Python, Langflow, and modern AI tooling; manage the full lifecycle from requirements and stakeholder engagement through to testing and deployment; embed AI components into existing applications; manage and optimise AI infrastructure and model orchestration environments with SRE and platform teams; and apply testing, documentation, and monitoring practices.

2. **AI Engineer / Data Scientist (Agentic AI) | Manager/Senior Manager** (`agentic_ai_data_scientist`) — score 0.5866
   > About the role: Design, build, and evaluate production agentic AI systems and LLM applications that reason, call tools, retrieve knowledge, and complete multi-step tasks.

3. **AI Computer Vision Engineer** (`computer_vision_engineer`) — score 0.5783
   > Nice to have: YOLO, edge AI or GPU environments, Docker, cloud platforms, production deployment, video streaming, and MLOps.

---

## Tool wiring check: job_retrieval_tool called from ProfileAgent

Demonstrates `job_retrieval_tool` wired into the agent from the previous step: once `ProfileAgent.run()` reaches `FinalAnswer`, it takes one further `RetrieveJobs` Action calling `job_tool.search()` on the confirmed draft profile.

**Introduction used:** Hi, I'm Jordan Ramirez, a third-year Bachelor of Computing Science student at UTS. My strongest skills are Python, SQL and Git. I built a course-timetable API as a university group project using Flask and SQLite. I'm looking for Junior Backend Developer or Software Engineering Intern roles.

**Agent RetrieveJobs Observation:** `{"matches": [{"document_id": "rag_agent_engineer", "title": "AI Engineer", "score": 0.4995, "excerpt": "Requirements: A master's degree or above in computer science, artificial intelligence, data systems, or a related field; three or more years of research or engineering experience; experience with LLMs, RAG, AI agents, or intelligent data systems; and strong Python programming."}, {"document_id": "agentic_ai_engineer", "title": "AI Engineer", "score": 0.4922, "excerpt": "Requirements: A degree in computer science, software engineering, or a related field; two or more years of Python development; experience developing and deploying LLM orchestration, RAG, or AI-agent solutions; modern AI tooling and orchestration frameworks; cloud infrastructure; Terraform or Kubernetes; Docker; and the ability to translate business needs into maintainable technical solutions."}, {"document_id": "graduate_ai_engineer", "title": "Graduate AI Engineer", "score": 0.4745, "excerpt": "Responsibilities: Develop and evaluate machine-learning models and AI agents; build specialised modular AI components; gather requirements; run experiments; validate outputs; iterate from findings; write clean, maintainable Python; and contribute to shared codebases."}]}`
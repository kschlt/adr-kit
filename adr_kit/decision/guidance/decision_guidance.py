"""Decision Quality Guidance - Promptlets for high-quality ADR creation.

This module provides comprehensive guidance for agents writing architectural decisions.
It follows the "ADR Kit provides structure, agents provide intelligence" principle by
offering focused promptlets that guide reasoning without prescribing exact outputs.
"""

from typing import Any


def build_decision_guidance(
    include_examples: bool = True, focus_area: str | None = None
) -> dict[str, Any]:
    """Build comprehensive decision quality guidance promptlet for agents.

    This is Task 1 of the two-step ADR creation flow:
    - Task 1 (this module): Guide agents to write high-quality decision content
    - Task 2 (creation.py): Extract enforceable policies from the decision

    The guidance follows the reasoning-agent promptlet architecture pattern,
    providing structure and letting the agent's intelligence fill in the details.

    Args:
        include_examples: Whether to include good vs bad ADR examples
        focus_area: Optional focus area for tailored examples (e.g., 'database', 'frontend')

    Returns:
        Comprehensive promptlet with ADR structure, quality criteria, examples, and guidance
    """
    guidance = {
        "agent_task": {
            "role": "Architectural Decision Documenter",
            "objective": (
                "Document a significant technical decision with clarity, completeness, "
                "and sufficient detail to enable automated policy extraction and future reasoning."
            ),
            "reasoning_steps": [
                "1. Understand the PROBLEM or OPPORTUNITY that prompted this decision (Context)",
                "2. State the DECISION explicitly - what specific technology/pattern/approach are you choosing?",
                "3. Analyze CONSEQUENCES - document both positive outcomes AND negative trade-offs",
                "4. Document ALTERNATIVES - what did you consider and why did you reject each option?",
                "5. Identify DECIDERS - who made or approved this choice?",
                "6. Extract CONSTRAINTS - what enforceable rules emerge from this decision?",
            ],
            "focus": (
                "Create a decision document that is specific, actionable, complete, and "
                "policy-extraction-ready. Good Task 1 output makes Task 2 (policy extraction) trivial."
            ),
        },
        "adr_structure": {
            "overview": (
                "ADRs follow MADR (Markdown Architectural Decision Records) format with "
                "four main sections. Each serves a distinct purpose in documenting architectural reasoning."
            ),
            "sections": {
                "context": {
                    "purpose": "WHY this decision is needed - the problem or opportunity",
                    "required": True,
                    "what_to_include": [
                        "The problem statement or opportunity being addressed",
                        "Current state and why it's insufficient",
                        "Requirements that must be met",
                        "Constraints or limitations to consider",
                        "Business or technical drivers",
                    ],
                    "what_to_avoid": [
                        "Describing the solution (that's the Decision section)",
                        "Being too vague ('We need a database')",
                        "Skipping the 'why' - context must explain the need",
                    ],
                    "quality_bar": "After reading Context, someone should understand the problem without reading the Decision.",
                },
                "decision": {
                    "purpose": "WHAT you're choosing - the specific technology, pattern, or approach",
                    "required": True,
                    "what_to_include": [
                        "Explicit statement of what is being chosen",
                        "Specific technology names and versions if relevant",
                        "Explicit constraints ('Don't use X', 'Must have Y')",
                        "Scope of applicability ('All new services', 'Frontend only')",
                    ],
                    "what_to_avoid": [
                        "Being generic ('Use a modern framework' → 'Use React 18')",
                        "Ambiguity about scope ('sometimes', 'maybe', 'consider')",
                        "Missing explicit constraints (makes policy extraction harder)",
                    ],
                    "quality_bar": "After reading Decision, it should be crystal clear what technology/approach was chosen and what's forbidden.",
                },
                "consequences": {
                    "purpose": "Trade-offs - both POSITIVE and NEGATIVE outcomes of this decision",
                    "required": True,
                    "what_to_include": [
                        "Positive consequences (benefits, improvements)",
                        "Negative consequences (drawbacks, limitations)",
                        "Risks and how they'll be mitigated",
                        "Impact on team, operations, or future flexibility",
                        "Known pitfalls or gotchas (AI-centric warnings)",
                    ],
                    "what_to_avoid": [
                        "Only listing benefits (every decision has trade-offs)",
                        "Generic statements ('It will work well')",
                        "Hiding or minimizing negative consequences",
                    ],
                    "quality_bar": "Consequences should list both pros AND cons. If you see only positives, something's missing.",
                    "structure_tip": "Use subsections: ### Positive, ### Negative, ### Risks, ### Mitigation",
                },
                "alternatives": {
                    "purpose": "What ELSE did you consider and WHY did you reject each option?",
                    "required": False,
                    "importance": "CRITICAL for policy extraction - rejected alternatives often become 'disallow' policies",
                    "what_to_include": [
                        "Each alternative considered",
                        "Pros and cons of each",
                        "Specific reason for rejection",
                        "Under what conditions you might reconsider",
                    ],
                    "what_to_avoid": [
                        "Saying 'We considered other options' without naming them",
                        "Not explaining WHY each was rejected",
                        "Unfairly dismissing alternatives",
                    ],
                    "quality_bar": "Each alternative should have a clear rejection reason that could become a policy.",
                    "example_structure": "### Flask\n**Rejected**: Lacks native async support.\n- Pros: ...\n- Cons: ...\n- Why not: ...",
                },
            },
        },
        "quality_criteria": {
            "specific": {
                "description": "Use exact technology names, not generic categories",
                "good": "Use PostgreSQL 15 as the primary database",
                "bad": "Use a SQL database",
                "why_it_matters": "Specific decisions enable precise policy extraction and clear implementation guidance",
            },
            "actionable": {
                "description": "Team can implement this decision immediately",
                "good": "Use FastAPI for all new backend services. Migrate existing Flask services opportunistically.",
                "bad": "Consider using FastAPI at some point",
                "why_it_matters": "Vague decisions lead to inconsistent implementation and drift",
            },
            "complete": {
                "description": "All required fields filled with meaningful content",
                "good": "Context explains the problem, Decision states the choice, Consequences list pros AND cons, Alternatives show what was rejected",
                "bad": "Context: 'We need this.' Decision: 'Use X.' Consequences: 'It's good.'",
                "why_it_matters": "Incomplete ADRs don't provide enough information for future reasoning or policy extraction",
            },
            "policy_ready": {
                "description": "Constraints are stated explicitly for automated extraction",
                "good": "Use FastAPI. **Don't use Flask** or Django due to lack of native async support.",
                "bad": "FastAPI is preferred in most cases",
                "why_it_matters": "Explicit constraints ('Don't use X', 'Must have Y') enable Task 2 to extract enforceable policies",
            },
            "balanced": {
                "description": "Documents both benefits AND drawbacks honestly",
                "good": "+ Native async support, + Auto docs, - Smaller ecosystem, - Team learning curve",
                "bad": "FastAPI is perfect for everything",
                "why_it_matters": "Unbalanced ADRs don't help future decision-makers understand when to reconsider",
            },
        },
        "anti_patterns": {
            "too_vague": {
                "bad": "Use a modern web framework",
                "good": "Use React 18 with TypeScript for frontend development",
                "fix": "Replace generic categories with specific technology names and versions",
            },
            "no_trade_offs": {
                "bad": "PostgreSQL is the best database. It has ACID compliance and great performance.",
                "good": "+ ACID compliance, + Great performance, + Rich features, - Higher resource usage than SQLite, - Requires operational expertise",
                "fix": "Always list both positive AND negative consequences. Every decision has trade-offs.",
            },
            "missing_context": {
                "bad": "Decision: Use PostgreSQL",
                "good": "Context: We need ACID transactions for financial data integrity and support for concurrent writes. Decision: Use PostgreSQL.",
                "fix": "Explain WHY before stating WHAT. Context must justify the decision.",
            },
            "no_alternatives": {
                "bad": "(No alternatives section)",
                "good": "### MySQL\nRejected: Weaker JSON support and extensibility vs PostgreSQL.\n### MongoDB\nRejected: Our data is highly relational, ACID compliance is critical.",
                "fix": "Document what else you considered and specific reasons for rejection. This enables 'disallow' policy extraction.",
            },
            "weak_constraints": {
                "bad": "FastAPI is recommended for new services",
                "good": "Use FastAPI for all new services. **Don't use Flask** or Django for new development.",
                "fix": "Use explicit constraint language: 'Don't use', 'Must have', 'All X must Y'. This enables automated policy extraction.",
            },
        },
        "example_workflow": {
            "description": "How Task 1 (decision quality) enables Task 2 (policy extraction)",
            "scenario": "Team needs to choose a web framework for a new API service",
            "bad_adr": {
                "title": "Use a web framework",
                "context": "We need a framework for the API",
                "decision": "Use a modern framework with good performance",
                "consequences": "It will work well for our needs",
                "alternatives": None,
                "why_bad": [
                    "Too vague - 'modern framework' could mean anything",
                    "No specific technology named",
                    "Consequences are generic platitudes",
                    "No alternatives documented",
                    "No explicit constraints for policy extraction",
                ],
                "task_2_result": "❌ Cannot extract any policies - no specific constraints stated",
            },
            "good_adr": {
                "title": "Use FastAPI for API Service",
                "context": (
                    "New API service requires async I/O for handling 1000+ concurrent connections. "
                    "Need automatic OpenAPI documentation for external partners. Team has Python experience."
                ),
                "decision": (
                    "Use **FastAPI** as the web framework for all new backend API services. "
                    "**Don't use Flask or Django** for new services - they lack native async support. "
                    "Existing Flask services can be migrated opportunistically."
                ),
                "consequences": (
                    "### Positive\n"
                    "- Native async/await support enables 10x higher concurrent connections\n"
                    "- Automatic OpenAPI/Swagger documentation reduces API maintenance burden\n"
                    "- Strong typing with Pydantic catches errors at API boundaries\n"
                    "- Modern Python features (3.10+) and excellent IDE support\n\n"
                    "### Negative\n"
                    "- Smaller plugin ecosystem compared to Django/Flask\n"
                    "- Team needs training on async/await patterns\n"
                    "- Async code can be harder to debug than synchronous code\n\n"
                    "### Risks\n"
                    "- Team unfamiliarity with async Python could cause subtle bugs\n\n"
                    "### Mitigation\n"
                    "- Provide async Python training (scheduled Q1 2026)\n"
                    "- Create internal FastAPI template with best practices"
                ),
                "alternatives": (
                    "### Flask\n"
                    "**Rejected**: Lacks native async support.\n"
                    "- Pros: Lightweight, huge ecosystem, team familiarity\n"
                    "- Cons: No native async (requires Quart/ASGI), manual validation\n"
                    "- Why not: Async support is bolt-on, not native\n\n"
                    "### Django\n"
                    "**Rejected**: Too heavyweight for API-only services.\n"
                    "- Pros: Mature, batteries-included, excellent admin\n"
                    "- Cons: Synchronous by default, opinionated structure\n"
                    "- Why not: Don't need ORM or admin for API-only service"
                ),
                "why_good": [
                    "Specific technology named (FastAPI)",
                    "Context explains requirements (async I/O, API docs)",
                    "Decision includes explicit constraints ('Don't use Flask or Django')",
                    "Consequences balanced (pros AND cons, risks AND mitigation)",
                    "Alternatives documented with clear rejection reasons",
                    "Policy-extraction-ready language",
                ],
                "task_2_result": (
                    "✅ Can extract clear policies:\n"
                    "{'imports': {'disallow': ['flask', 'django'], 'prefer': ['fastapi']}, "
                    "'rationales': ['Native async support required', 'Automatic API documentation reduces maintenance']}"
                ),
            },
            "key_insight": (
                "Good Task 1 output (clear constraints + rejected alternatives) "
                "makes Task 2 (policy extraction) trivial. The agent can directly "
                "map 'Don't use Flask' to {'imports': {'disallow': ['flask']}}."
            ),
        },
        "connection_to_task_2": {
            "overview": (
                "Task 1 (Decision Quality) and Task 2 (Policy Construction) work together. "
                "The quality of your decision content directly impacts how easily policies can be extracted."
            ),
            "how_task_1_enables_task_2": [
                {
                    "decision_pattern": "Use FastAPI. Don't use Flask or Django.",
                    "extracted_policy": "{'imports': {'disallow': ['flask', 'django'], 'prefer': ['fastapi']}}",
                    "principle": "Explicit 'Don't use X' statements become 'disallow' policies",
                },
                {
                    "decision_pattern": "All FastAPI handlers must be async functions",
                    "extracted_policy": "{'patterns': {'async_handlers': {'rule': 'async def', 'severity': 'error'}}}",
                    "principle": "'All X must be Y' statements become pattern policies",
                },
                {
                    "decision_pattern": "Frontend must not access database directly",
                    "extracted_policy": "{'architecture': {'layer_boundaries': [{'rule': 'frontend -> database', 'action': 'block'}]}}",
                    "principle": "'X must not access Y' becomes architecture boundary",
                },
                {
                    "decision_pattern": "TypeScript strict mode required for all frontend code",
                    "extracted_policy": "{'config_enforcement': {'typescript': {'tsconfig': {'strict': True}}}}",
                    "principle": "Config requirements become config enforcement policies",
                },
            ],
            "best_practices": [
                "Use explicit constraint language: 'Don't use', 'Must have', 'All X must Y'",
                "Document alternatives with clear rejection reasons (enables 'disallow' extraction)",
                "Be specific about technology names (not 'a modern framework', but 'React 18')",
                "State scope clearly ('All new services', 'Frontend only')",
            ],
        },
        "dos_and_donts": {
            "dos": [
                "✅ Use specific technology names and versions",
                "✅ Document both positive AND negative consequences",
                "✅ Explain WHY in Context before stating WHAT in Decision",
                "✅ List alternatives with clear rejection reasons",
                "✅ Use explicit constraint language ('Don't use', 'Must have')",
                "✅ Include risks and mitigation strategies",
                "✅ State scope of applicability clearly",
                "✅ Identify who made the decision (deciders)",
            ],
            "donts": [
                "❌ Don't be vague or generic ('Use a modern framework')",
                "❌ Don't only list benefits - every decision has trade-offs",
                "❌ Don't skip Context - explain the problem first",
                "❌ Don't forget Alternatives - they become 'disallow' policies",
                "❌ Don't use weak language ('consider', 'maybe', 'sometimes')",
                "❌ Don't hide negative consequences or risks",
                "❌ Don't make decisions sound perfect - honest trade-offs matter",
            ],
        },
        "next_steps": [
            "1. Follow this guidance to draft your ADR content",
            "2. Use adr_create() with your title, context, decision, consequences, and alternatives",
            "3. Review the policy_guidance in the response to construct enforcement policies (Task 2)",
            "4. Call adr_create() again with the policy parameter if you want automated enforcement",
        ],
    }

    # Add examples if requested
    if include_examples:
        guidance["examples"] = _build_examples(focus_area)

    return guidance


def _build_examples(focus_area: str | None = None) -> dict[str, Any]:
    """Build good vs bad ADR examples.

    Args:
        focus_area: Optional focus to tailor examples (e.g., 'database', 'frontend')

    Returns:
        Dictionary with categorized examples
    """
    examples = {
        "database": {
            "good": {
                "title": "Use PostgreSQL for Primary Database",
                "context": (
                    "Application requires ACID transactions for financial data integrity. "
                    "Need support for complex queries with joins, concurrent writes from multiple services, "
                    "and JSON document storage for flexible user metadata. Team has SQL experience."
                ),
                "decision": (
                    "Use **PostgreSQL 15** as the primary database for all application data. "
                    "**Don't use MySQL** (weaker JSON support) or **MongoDB** (eventual consistency conflicts with financial requirements). "
                    "Deploy on AWS RDS with Multi-AZ for high availability."
                ),
                "consequences": (
                    "### Positive\n"
                    "- ACID compliance guarantees data consistency for transactions\n"
                    "- Rich feature set: JSON, full-text search, advanced indexing\n"
                    "- Excellent query planner handles complex joins efficiently\n"
                    "- Mature tooling and ecosystem\n\n"
                    "### Negative\n"
                    "- Higher resource usage (memory/CPU) than simpler databases\n"
                    "- Requires operational expertise for tuning and maintenance\n"
                    "- Vertical scaling limits (single-server architecture)\n\n"
                    "### Risks & Mitigation\n"
                    "- Risk: Poor indexing causes performance issues at scale\n"
                    "- Mitigation: Use connection pooling (PgBouncer), monitor with pg_stat_statements"
                ),
                "alternatives": (
                    "### MySQL\n"
                    "**Rejected**: Weaker JSON support and extensibility compared to PostgreSQL.\n\n"
                    "### MongoDB\n"
                    "**Rejected**: Eventual consistency model conflicts with financial transaction requirements. "
                    "ACID transactions added in 4.0 but less mature than PostgreSQL."
                ),
            },
            "bad": {
                "title": "Use a Database",
                "context": "We need to store data",
                "decision": "Use PostgreSQL",
                "consequences": "PostgreSQL is good for data storage",
                "alternatives": None,
            },
        },
        "frontend": {
            "good": {
                "title": "Use React 18 with TypeScript for Frontend",
                "context": (
                    "Building complex interactive dashboard with real-time data updates. "
                    "Need component reusability, strong typing to catch errors early, and excellent developer tooling. "
                    "Team has JavaScript experience but new to TypeScript."
                ),
                "decision": (
                    "Use **React 18** with **TypeScript** for all frontend development. "
                    "**Don't use Vue or Angular** - smaller ecosystems and steeper learning curves for our use case. "
                    "All new components must be written in TypeScript with strict mode enabled."
                ),
                "consequences": (
                    "### Positive\n"
                    "- Huge ecosystem of components and libraries\n"
                    "- TypeScript catches errors at compile time, reducing runtime bugs\n"
                    "- Concurrent features in React 18 improve perceived performance\n"
                    "- Excellent IDE support and developer experience\n\n"
                    "### Negative\n"
                    "- TypeScript learning curve for team\n"
                    "- More boilerplate than plain JavaScript\n"
                    "- React hooks mental model takes time to master\n\n"
                    "### Risks & Mitigation\n"
                    "- Risk: Team struggles with TypeScript\n"
                    "- Mitigation: 2-week TypeScript training, pair programming on first components"
                ),
                "alternatives": (
                    "### Vue 3\n"
                    "**Rejected**: Smaller ecosystem, less corporate backing than React.\n\n"
                    "### Angular\n"
                    "**Rejected**: Steep learning curve, very opinionated, our team has React experience not Angular."
                ),
            },
            "bad": {
                "title": "Use a Frontend Framework",
                "context": "We need to build a UI",
                "decision": "Use React because it's popular",
                "consequences": "React will work well",
                "alternatives": None,
            },
        },
        "generic": {
            "good": {
                "title": "Use FastAPI for Backend API Services",
                "context": (
                    "Building API service for mobile app with 1000+ concurrent users. "
                    "Need automatic API documentation for mobile team, async I/O for performance, "
                    "and strong typing for reliability. Team knows Python."
                ),
                "decision": (
                    "Use **FastAPI** for all new backend API services. "
                    "**Don't use Flask** (no native async) or **Django** (too heavyweight for API-only). "
                    "Existing Flask services can migrate opportunistically."
                ),
                "consequences": (
                    "### Positive\n"
                    "- Native async/await for 10x better concurrent performance\n"
                    "- Automatic OpenAPI docs reduce coordination overhead with mobile team\n"
                    "- Pydantic validation catches errors at API boundaries\n\n"
                    "### Negative\n"
                    "- Smaller ecosystem than Flask/Django\n"
                    "- Team needs async Python training\n"
                    "- Debugging async code is harder\n\n"
                    "### Mitigation\n"
                    "- Async Python training scheduled Q1 2026\n"
                    "- Internal template with best practices"
                ),
                "alternatives": (
                    "### Flask\n"
                    "**Rejected**: No native async support, would require Quart/ASGI.\n\n"
                    "### Django\n"
                    "**Rejected**: Too heavyweight for API-only service, don't need ORM/admin."
                ),
            },
            "bad": {
                "title": "Use Python Web Framework",
                "context": "Need backend framework",
                "decision": "Use FastAPI",
                "consequences": "FastAPI is fast and modern",
                "alternatives": None,
            },
        },
    }

    # Return focused examples if specified
    if focus_area and focus_area in examples:
        return {
            "focus": focus_area,
            "good_example": examples[focus_area]["good"],
            "bad_example": examples[focus_area]["bad"],
            "comparison": (
                "Notice how the good example is specific, documents trade-offs, "
                "includes alternatives with rejection reasons, and uses explicit constraint language."
            ),
        }

    # Return all examples
    return {
        "by_category": examples,
        "comparison": (
            "Good examples are specific, document both pros and cons, explain context thoroughly, "
            "list alternatives with clear rejection reasons, and use explicit constraint language. "
            "Bad examples are vague, incomplete, and don't provide enough information for policy extraction."
        ),
    }

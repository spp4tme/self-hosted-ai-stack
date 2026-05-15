"""Tâches collaboratives multi-agents prédéfinies."""

from __future__ import annotations

from crewai import Task


def make_tech_analysis_task(agent, topic: str) -> Task:
    return Task(
        description=f"""
        Recherche les dernières avancées en {topic}.
        1. Cherche sur le web les actualités récentes.
        2. Consulte la base de connaissances interne si elle contient des informations.
        3. Synthétise les résultats clés avec sources.
        4. Identifie les CVE ou vulnérabilités récentes si pertinent.
        """,
        expected_output=(
            "Un rapport structuré avec : résumé exécutif, 3-5 points clés, "
            "sources consultées, et recommandations pratiques."
        ),
        agent=agent,
    )


def make_security_audit_task(agent, target: str = "stack Docker") -> Task:
    return Task(
        description=f"""
        Audite la sécurité de : {target}.
        1. Identifie les vecteurs d'attaque potentiels.
        2. Vérifie les secrets hardcodés et les permissions.
        3. Consulte les CVE récentes pour les composants utilisés.
        4. Liste les priorités de correction par gravité (CRITIQUE/HAUTE/MOYENNE).
        """,
        expected_output=(
            "Rapport d'audit avec : liste des vulnérabilités trouvées (CVSS si disponible), "
            "impact potentiel, et plan d'action correctif."
        ),
        agent=agent,
    )


def make_code_review_task(agent, code: str) -> Task:
    return Task(
        description=f"""
        Analyse et améliore ce code Python :
        ```python
        {code}
        ```
        1. Identifie les bugs potentiels.
        2. Vérifie les types hints et docstrings.
        3. Propose des optimisations de performance.
        4. Génère des tests pytest pour les fonctions clés.
        """,
        expected_output=(
            "Code revu avec commentaires inline, bugs identifiés, "
            "code optimisé, et suite de tests pytest."
        ),
        agent=agent,
    )


def make_devops_analysis_task(agent) -> Task:
    return Task(
        description="""
        Analyse l'état de l'infrastructure Docker :
        1. Liste tous les containers et leur état (running/stopped/exited).
        2. Identifie les services avec des erreurs ou ressources élevées.
        3. Propose des actions correctives.
        4. Vérifie les métriques CPU/mémoire via Prometheus.
        """,
        expected_output=(
            "Rapport d'état infrastructure : tableau des services, alertes actives, "
            "métriques clés, et recommandations d'optimisation."
        ),
        agent=agent,
    )


def make_collaborative_task(
    research_agent, code_agent, devops_agent
) -> list[Task]:
    """Pipeline multi-agents : recherche → code → validation infra."""
    research_task = Task(
        description=(
            "Recherche les meilleures pratiques pour optimiser un stack Docker IA. "
            "Focus sur la performance GPU, la gestion mémoire, et la résilience."
        ),
        expected_output="Liste des bonnes pratiques avec sources.",
        agent=research_agent,
    )
    code_task = Task(
        description=(
            "Basé sur les recherches précédentes, génère un script Python "
            "de monitoring automatique pour optimiser les ressources Docker."
        ),
        expected_output="Script Python fonctionnel avec tests.",
        agent=code_agent,
        context=[research_task],
    )
    devops_task = Task(
        description=(
            "Valide que le script généré est compatible avec l'infrastructure actuelle. "
            "Vérifie l'état des containers et propose un plan de déploiement."
        ),
        expected_output="Plan de déploiement validé avec étapes.",
        agent=devops_agent,
        context=[code_task],
    )
    return [research_task, code_task, devops_task]

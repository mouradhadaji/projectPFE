# -*- coding: utf-8 -*-
{
    'name': 'System Gestion Tache',
    'version': '18.0.1.0.0',
    'category': 'Project',
    'summary': 'Système de gestion de projets et tâches avec IA',
    'description': """
        Système de Gestion de Projets et Tâches
        ========================================

        Fonctionnalités:
        ----------------
        * Gestion de projets Agile (Kanban & Scrum)
        * Système de tickets/tâches
        * Gestion des sprints
        * Tableaux de bord interactifs
        * Rapports automatisés
        * Intelligence Artificielle
    """,

    'author': 'Your Name',
    'license': 'LGPL-3',

    # Dépendances
    'depends': [
        'base',
        'web',
        'mail',
        'project',
    ],

    # Fichiers de données
    'data': [
        # Sécurité
        'security/project_security.xml',
        'security/ir.model.access.csv',
        'views/project_views.xml',
        'views/ticket_views.xml',
        'views/sprint_views.xml',


        'views/project_menu.xml',
    ],

    # Installation
    'installable': True,
    'application': True,
    'auto_install': False,

    'sequence': 10,
}
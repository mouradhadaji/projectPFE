# -*- coding: utf-8 -*-
{
    'name': 'Jira Project Management',
    'version': '18.0.1.0.0',
    'category': 'Project',
    'summary': 'Jira-style Project Management with Scrum',
    'description': """
        Jira-Style Project Management System
        =====================================
        Features:
        * Projects with team management
        * Sprint Planning & Management
        * Tickets (Story, Task, Bug, Epic, Subtask)
        * Customizable Workflow States
        * Kanban Boards with drag & drop
        * Burndown Charts
        * Time Tracking
        * Sub-tasks and Linked Issues
        Perfect for Agile/Scrum teams!
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',

    'depends': [
        'base',
        'mail',
        'web',
    ],
    'external_dependencies': {
        'python': ['numpy', 'scikit-learn'],
    },

    'data': [
        # ── Security (ALWAYS FIRST) ──────────────────────────
        'security/jira_groups.xml',
        'security/jira_security.xml',
        'security/ir.model.access.csv',

        # ── Data ─────────────────────────────────────────────
        'data/sequence.xml',
        'data/ir_rule.xml',
        'data/jira_cron.xml',
         'views/jira_ticket_history_views.xml',

        # ── Reports ──────────────────────────────────────────
        'views/jira_report_views.xml',
        'report/jira_sprint_report.xml',

        # ── Wizards ──────────────────────────────────────────
        'wizards/jira_move_to_sprint_wizard_views.xml',

        # ── Views ────────────────────────────────────────────
        'views/jira_workflow_views.xml',
        'views/jira_project_views.xml',
        'views/jira_ticket_views.xml',
        'views/view_jira_ticket_kanban.xml',
        'views/jira_sprint_views.xml',
        'views/jira_sprint_planning_views.xml',
        'views/jira_dashboard_views.xml',

        # ── Menus (ALWAYS LAST) ──────────────────────────────
        'views/jira_menus.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'jira_project/static/src/js/performance_analyzer.js',
            'jira_project/static/src/js/chart.umd.min.js',
            'jira_project/static/src/js/dashboard_chart.js',
            'jira_project/static/src/js/ticket_status_donut.js',
            'jira_project/static/src/js/sprint_burndown_v2.js',
            'jira_project/static/src/css/sprint_kanban.css',
            'jira_project/static/src/css/Tickets_kanban.css',
            'jira_project/static/src/css/navbar.css',
            'jira_project/static/src/css/dashboard.css',
        ],
    },

    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'images': ['static/description/icon.png'],
}